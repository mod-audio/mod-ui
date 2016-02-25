# -*- coding: utf-8 -*-

# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@moddevices.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tornado.ioloop
import tornado.options
import tornado.escape
import time
import uuid
from base64 import b64decode, b64encode
from hashlib import sha1
from hashlib import md5
from signal import signal, SIGUSR2
from tornado import gen, iostream, web, websocket

from mod.settings import (APP, DESKTOP, LOG,
                          HTML_DIR, CLOUD_PUB, DOWNLOAD_TMP_DIR, DEVICE_WEBSERVER_PORT, CLOUD_HTTP_ADDRESS,
                          DEVICE_SERIAL, DEVICE_KEY, LV2_PLUGIN_DIR,
                          DEFAULT_ICON_TEMPLATE, DEFAULT_SETTINGS_TEMPLATE, DEFAULT_ICON_IMAGE,
                          MAX_SCREENSHOT_WIDTH, MAX_SCREENSHOT_HEIGHT,
                          PACKAGE_SERVER_ADDRESS, DEFAULT_PACKAGE_SERVER_PORT,
                          PACKAGE_REPOSITORY, DATA_DIR,
                          AVATAR_URL, DEV_ENVIRONMENT,
                          JS_CUSTOM_CHANNEL, AUTO_CLOUD_BACKUP)

from mod import check_environment, jsoncall, json_handler, register, symbolify
from mod.communication import crypto
from mod.bank import list_banks, save_banks, remove_pedalboard_from_banks
from mod.session import SESSION
from mod.utils import (init as lv2_init,
                       cleanup as lv2_cleanup,
                       get_all_plugins,
                       get_plugin_info,
                       get_plugin_info_mini,
                       get_all_pedalboards,
                       get_pedalboard_info,
                       get_jack_sample_rate,
                       set_truebypass_value)

@gen.coroutine
def install_bundles_in_tmp_dir(callback):
    error     = ""
    removed   = []
    installed = []

    for bundle in os.listdir(DOWNLOAD_TMP_DIR):
        tmppath    = os.path.join(DOWNLOAD_TMP_DIR, bundle)
        bundlepath = os.path.join(LV2_PLUGIN_DIR, bundle)

        if os.path.exists(bundlepath):
            resp, data = yield gen.Task(SESSION.host.remove_bundle, bundlepath, True)

            if resp:
                removed += data
                shutil.rmtree(bundlepath)
            else:
                error = data
                break

        shutil.move(tmppath, bundlepath)
        resp, data = yield gen.Task(SESSION.host.add_bundle, bundlepath)

        if resp:
            installed += data
        else:
            error = data
            # remove bundle that produces errors
            shutil.rmtree(bundlepath)
            break

    # FIXME, where are my ports!?
    lv2_cleanup()
    lv2_init()

    if error or len(installed) == 0:
        # Delete old temp files
        for bundle in os.listdir(DOWNLOAD_TMP_DIR):
            shutil.rmtree(os.path.join(DOWNLOAD_TMP_DIR, bundle))

        resp = {
            'ok'     : False,
            'error'  : error or "No plugins found in bundle",
            'removed': removed,
        }
    else:
        resp = {
            'ok'       : True,
            'removed'  : removed,
            'installed': installed,
        }

    callback(resp)

def install_package(bundlename, callback):
    filename = os.path.join(DOWNLOAD_TMP_DIR, bundlename)

    if not os.path.exists(filename):
        callback({
            'ok'     : False,
            'error'  : "Failed to find archive",
            'removed': [],
        })
        return

    proc = subprocess.Popen(['tar','zxf', filename],
                            cwd=DOWNLOAD_TMP_DIR,
                            stdout=subprocess.PIPE)

    def end_untar_pkgs(fileno, event):
        if proc.poll() is None:
            return
        ioloop.remove_handler(fileno)
        os.remove(filename)
        install_bundles_in_tmp_dir(callback)

    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.add_handler(proc.stdout.fileno(), end_untar_pkgs, 16)

class SimpleFileReceiver(web.RequestHandler):
    @property
    def download_tmp_dir(self):
        raise NotImplemented
    @property
    def remote_public_key(self):
        raise NotImplemented
    @property
    def destination_dir(self):
        raise NotImplemented

    @classmethod
    def urls(cls, path):
        return [
            (r"/%s/$" % path, cls),
            #(r"/%s/([a-f0-9]{32})/(\d+)$" % path, cls),
            #(r"/%s/([a-f0-9]{40})/(finish)$" % path, cls),
            ]

    @web.asynchronous
    @gen.engine
    def post(self, sessionid=None, chunk_number=None):
        # self.result can be set by subclass in process_file,
        # so that answer will be returned to browser
        self.result = None
        name = str(uuid.uuid4())
        if not os.path.exists(self.destination_dir):
            os.mkdir(self.destination_dir)
        fh = open(os.path.join(self.destination_dir, name), 'wb')
        fh.write(self.request.body)
        fh.close()
        data = dict(filename=name)
        yield gen.Task(self.process_file, data)
        info = {'ok': True, 'result': self.result}
        self.write(json.dumps(info))
        self.finish()

    def process_file(self, data, callback=lambda:None):
        """to be overriden"""

class BluetoothSetPin(web.RequestHandler):
    def post(self):
        pin = self.get_argument("pin", None)

        self.set_header('Content-Type', 'application/json')

        if pin is None:
            self.write(json.dumps(False))
            self.finish()
            return

        with open(BLUETOOTH_PIN, 'w') as fh:
            fh.write(pin)

        self.write(json.dumps(True))
        self.finish()

class SystemInfo(web.RequestHandler):
    def get(self):
        uname = os.uname()
        info = {
            "hardware": {},
            "env": dict((k, os.environ[k]) for k in [k for k in os.environ.keys() if k.startswith("MOD")]),
            "python": {
                "argv"    : sys.argv,
                "flags"   : sys.flags,
                "path"    : sys.path,
                "platform": sys.platform,
                "prefix"  : sys.prefix,
                "version" : sys.version
            },
            "uname": {
                "machine": uname.machine,
                "release": uname.release,
                "version": uname.version
            }
        }

        if os.path.exists("/etc/mod-hardware-descriptor.json"):
            with open("/etc/mod-hardware-descriptor.json", 'r') as fd:
                info["hardware"] = json.loads(fd.read())

        self.write(json.dumps(info))
        self.finish()

class EffectInstaller(SimpleFileReceiver):
    remote_public_key = CLOUD_PUB
    destination_dir = DOWNLOAD_TMP_DIR

    @web.asynchronous
    @gen.engine
    def process_file(self, data, callback=lambda:None):
        def on_finish(resp):
            self.result = resp
            callback()
        install_package(data['filename'], on_finish)

class EffectBulk(web.RequestHandler):
    def prepare(self):
        if self.request.headers.get("Content-Type") == "application/json":
            self.uris = json.loads(self.request.body.decode("utf-8", errors="ignore"))
        else:
            raise web.HTTPError(501, 'Content-Type != "application/json"')

    def post(self):
        result = {}
        for uri in self.uris:
            try:
                info = get_plugin_info(uri)
            except:
                continue
            result[uri] = info

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(result))
        self.finish()

class EffectList(web.RequestHandler):
    def get(self):
        data = get_all_plugins()
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(data))
        self.finish()

class SDKEffectInstaller(EffectInstaller):
    @web.asynchronous
    @gen.engine
    def post(self):
        upload = self.request.files['package'][0]

        with open(os.path.join(DOWNLOAD_TMP_DIR, upload['filename']), 'wb') as fh:
            fh.write(b64decode(upload['body']))

        resp = yield gen.Task(install_package, upload['filename'])

        self.write(json.dumps(resp))
        self.finish()

# TODO this is an obsolete implementation that does not work in new lv2 specs.
# it's here for us to remember this should be reimplemented
#class SDKEffectScript(EffectSearcher):
    #def get(self, objid=None):
        #if objid is None:
            #objid = self.get_by_uri()

        #try:
            #options = self.get_object(objid)
        #except:
            #raise web.HTTPError(404)

        #try:
            #path = options['configurationFeedback']
        #except KeyError:
            #raise web.HTTPError(404)

        #path = path.split(options['package']+'/')[-1]
        #path = os.path.join(PLUGIN_LIBRARY__DIR, options['package'], path)

        #self.write(open(path, 'rb').read())

class EffectResource(web.StaticFileHandler):

    def initialize(self):
        # Overrides StaticFileHandler initialize
        pass

    def get(self, path):
        try:
            uri = self.get_argument('uri')
        except:
            return self.shared_resource(path)

        try:
            data = get_plugin_info(uri)
        except:
            raise web.HTTPError(404)

        try:
            root = data['gui']['resourcesDirectory']
        except:
            raise web.HTTPError(404)

        try:
            super(EffectResource, self).initialize(root)
            return super(EffectResource, self).get(path)
        except web.HTTPError as e:
            if e.status_code != 404:
                raise e
            return self.shared_resource(path)
        except IOError:
            raise web.HTTPError(404)

    def shared_resource(self, path):
        super(EffectResource, self).initialize(os.path.join(HTML_DIR, 'resources'))
        return super(EffectResource, self).get(path)

class EffectImage(web.RequestHandler):
    def get(self, image):
        uri = self.get_argument('uri')

        try:
            data = get_plugin_info_mini(uri)
        except:
            raise web.HTTPError(404)

        try:
            path = data['gui'][image]
        except:
            path = None

        if path is None or not os.path.exists(path):
            try:
                path = DEFAULT_ICON_IMAGE[image]
            except:
                raise web.HTTPError(404)

        with open(path, 'rb') as fd:
            self.set_header('Content-type', 'image/png')
            self.write(fd.read())

class EffectHTML(web.RequestHandler):
    def get(self, html):
        uri = self.get_argument('uri')

        try:
            data = get_plugin_info(uri)
        except:
            raise web.HTTPError(404)

        try:
            path = data['gui']['%sTemplate' % html]
        except:
            raise web.HTTPError(404)

        if not os.path.exists(path):
            raise web.HTTPError(404)

        with open(path, 'rb') as fd:
            self.set_header('Content-type', 'text/html')
            self.write(fd.read())

class EffectStylesheet(web.RequestHandler):
    def get(self):
        uri = self.get_argument('uri')

        try:
            data = get_plugin_info(uri)
        except:
            raise web.HTTPError(404)

        try:
            path = data['gui']['stylesheet']
        except:
            raise web.HTTPError(404)

        if not os.path.exists(path):
            raise web.HTTPError(404)

        with open(path, 'rb') as fd:
            self.set_header('Content-type', 'text/css')
            self.write(fd.read())

class EffectJavascript(web.RequestHandler):
    def get(self):
        uri = self.get_argument('uri')

        try:
            data = get_plugin_info(uri)
        except:
            raise web.HTTPError(404)

        try:
            path = data['gui']['javascript']
        except:
            raise web.HTTPError(404)

        if not os.path.exists(path):
            raise web.HTTPError(404)

        with open(path, 'rb') as fd:
            self.set_header('Content-type', 'text/javascript')
            self.write(fd.read())

class EffectAdd(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        uri = self.get_argument('uri')
        x   = float(self.request.arguments.get('x', [0])[0])
        y   = float(self.request.arguments.get('y', [0])[0])

        resp = yield gen.Task(SESSION.web_add, instance, uri, x, y)

        self.set_header('Content-type', 'application/json')

        if resp >= 0:
            try:
                data = get_plugin_info(uri)
            except:
                print("ERROR in webserver.py: get_plugin_info for '%s' failed" % uri)
                raise web.HTTPError(404)
            self.write(json.dumps(data))
        else:
            self.write(json.dumps(False))

        self.finish()

class EffectRemove(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        resp = yield gen.Task(SESSION.web_remove, instance)
        self.write(json.dumps(resp))
        self.finish()

class EffectGet(web.RequestHandler):
    def get(self):
        uri = self.get_argument('uri')

        try:
            data = get_plugin_info(uri)
        except:
            print("ERROR in webserver.py: get_plugin_info for '%s' failed" % uri)
            raise web.HTTPError(404)

        self.set_header('Content-type', 'application/json')
        self.write(json.dumps(data))
        self.finish()

class EffectConnect(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, port_from, port_to):
        resp = yield gen.Task(SESSION.web_connect, port_from, port_to)
        self.write(json.dumps(resp))
        self.finish()

class EffectDisconnect(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, port_from, port_to):
        resp = yield gen.Task(SESSION.web_disconnect, port_from, port_to)
        self.write(json.dumps(resp))
        self.finish()

class EffectParameterSet(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, port):
        resp = yield gen.Task(SESSION.web_parameter_set, port, float(self.get_argument('value')))
        self.write(json.dumps(resp))
        self.finish()

class EffectParameterAddress(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self, port):
        data = json.loads(self.request.body.decode("utf-8", errors="ignore"))
        uri  = data.get('uri', None)

        if uri is None:
            print("ERROR in webserver.py: Attempting to address without an URI")
            raise web.HTTPError(404)

        label   = data.get('label', '---') or '---'
        minimum = float(data['minimum'])
        maximum = float(data['maximum'])
        value   = float(data['value'])
        steps   = int(data.get('steps', 33))

        resp = yield gen.Task(SESSION.web_parameter_address, port, uri, label, maximum, minimum, value, steps)
        self.write(json.dumps(resp))
        self.finish()

class EffectParameterMidiLearn(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, port):
        resp = yield gen.Task(SESSION.web_parameter_midi_learn, port)
        self.write(json.dumps(resp))
        self.finish()

class EffectPresetLoad(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        uri  = self.get_argument('uri')
        resp = yield gen.Task(SESSION.web_preset_load, instance, uri)
        self.write(json.dumps(resp))
        self.finish()

class EffectPresetSave(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        name = self.get_argument('name')
        resp = yield gen.Task(SESSION.web_preset_save, instance, name)
        self.write(json.dumps(resp))
        self.finish()

class EffectPosition(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        x = float(self.get_argument('x'))
        y = float(self.get_argument('y'))
        resp = SESSION.web_set_position(instance, x, y)
        self.write(json.dumps(resp))
        self.finish()

class ServerWebSocket(websocket.WebSocketHandler):
    @gen.coroutine
    def open(self):
        print("websocket open")
        self.set_nodelay(True)
        yield gen.Task(SESSION.websocket_opened, self)

    @gen.coroutine
    def on_close(self):
        print("websocket close")
        yield gen.Task(SESSION.websocket_closed, self)

# I think this is unused...
#class PackageEffectList(web.RequestHandler):
    #def get(self, bundle):
        #if not bundle.endswith(os.sep):
            #bundle += os.sep
        #result = []
        #for plugin in get_all_plugins():
            #if bundle in plugin['bundles']:
                #result.append(plugin)
        #self.set_header('Content-Type', 'application/json')
        #self.write(json.dumps(result))

class PackageUninstall(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self):
        bundles = json.loads(self.request.body.decode("utf-8", errors="ignore"))
        error   = ""
        removed = []

        for bundlepath in bundles:
            if os.path.exists(bundlepath) and os.path.isdir(bundlepath):
                resp, data = yield gen.Task(SESSION.host.remove_bundle, bundlepath, True)

                if resp:
                    removed += data
                    shutil.rmtree(bundlepath)
                else:
                    error = data
                    break

        # FIXME, where are my ports!?
        lv2_cleanup()
        lv2_init()

        if error:
            resp = {
                'ok'     : False,
                'error'  : error,
                'removed': removed,
            }
        elif len(removed) == 0:
            resp = {
                'ok'     : False,
                'error'  : "No plugins found",
                'removed': [],
            }
        else:
            resp = {
                'ok'     : True,
                'removed': removed,
            }

        # FIXME: alternatively we can do this when requested
        #        but we'll need a quick "get_broken_pedalboards" function first
        if len(removed) > 0:
            # Re-save banks, as pedalboards might contain the removed plugin
            broken = []
            for pb in get_all_pedalboards():
                if pb['broken']: broken.append(os.path.abspath(pb['bundle']))
            list_banks(broken)

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(resp))
        self.finish()

class PedalboardList(web.RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(get_all_pedalboards()))
        self.finish()

class PedalboardSave(web.RequestHandler):
    def post(self):
        title = self.get_argument('title')
        asNew = bool(int(self.get_argument('asNew')))

        bundlepath = SESSION.web_save_pedalboard(title, asNew)

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({
            'ok': bundlepath is not None,
            'bundlepath': bundlepath
        }))
        self.finish()

class PedalboardPackBundle(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        bundlepath = os.path.abspath(self.get_argument('bundlepath'))
        parentpath = os.path.abspath(os.path.join(bundlepath, ".."))
        bundledir  = bundlepath.replace(parentpath, "").replace(os.sep, "")
        tmpfile    = "/tmp/upload-pedalboard.tar.gz"

        # make sure the screenshot is ready before proceeding
        yield gen.Task(SESSION.screenshot_generator.wait_for_pending_jobs, bundlepath)

        oldcwd = os.getcwd()
        os.chdir(parentpath) # hmm, is there os.path.parent() ?

        # FIXME - don't use external tools!
        os.system("tar -cvzf %s %s" % (tmpfile, bundledir))

        os.chdir(oldcwd)

        with open(tmpfile, 'rb') as fd:
            self.write(fd.read())

        self.finish()

        os.remove(tmpfile)

class PedalboardLoadBundle(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self):
        bundlepath = self.get_argument("bundlepath")

        name = SESSION.load_pedalboard(bundlepath)

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({
            'ok':   True,
            'name': name
        }))
        self.finish()

class PedalboardLoadWeb(SimpleFileReceiver):
    remote_public_key = CLOUD_PUB # needed?
    destination_dir = os.path.expanduser("~/.pedalboards/") # FIXME cross-platform, perhaps lookup in LV2_PATH

    def process_file(self, data, callback=lambda:None):
        filename = os.path.join(self.destination_dir, data['filename'])

        if not os.path.exists(filename):
            callback()
            return

        if not os.path.exists(self.destination_dir):
            os.mkdir(self.destination_dir)

        # FIXME - don't use external tools!
        tar_output = subprocess.getoutput('env LANG=C tar -xvf "%s" -C "%s"' % (filename, self.destination_dir))
        bundlepath = os.path.join(self.destination_dir, tar_output.strip().split("\n", 1)[0])

        if not os.path.exists(bundlepath):
            raise IOError(bundlepath)

        SESSION.load_pedalboard(bundlepath)

        os.remove(filename)
        callback()

class PedalboardInfo(web.RequestHandler):
    def get(self):
        bundlepath = os.path.abspath(self.get_argument('bundlepath'))
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(get_pedalboard_info(bundlepath)))
        self.finish()

class PedalboardRemove(web.RequestHandler):
    def get(self):
        bundlepath = os.path.abspath(self.get_argument('bundlepath'))

        if not os.path.exists(bundlepath):
            self.write(json.dumps(False))
            self.finish()
            return

        shutil.rmtree(bundlepath)
        remove_pedalboard_from_banks(bundlepath)
        self.write(json.dumps(True))
        self.finish()

class PedalboardSize(web.RequestHandler):
    def get(self):
        width  = int(self.get_argument('width'))
        height = int(self.get_argument('height'))
        SESSION.pedalboard_size(width, height)
        self.write(json.dumps(True))
        self.finish()

class PedalboardImage(web.RequestHandler):
    def get(self, image):
        bundlepath = self.get_argument('bundlepath')
        imagepath  = os.path.join(bundlepath, "%s.png" % image)
        #imagetype  = "png"

        if not os.path.exists(imagepath):
            #imagepath = os.path.join(HTML_DIR, "img", "loading-effect.gif")
            #imagetype = "gif"
            raise web.HTTPError(404)

        with open(imagepath, 'rb') as fd:
            #self.set_header('Content-type', 'image/%s' % imagetype)
            self.set_header('Content-type', 'image/png')
            self.write(fd.read())

class PedalboardImageWait(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        bundlepath = os.path.abspath(self.get_argument('bundlepath'))
        ok, ctime = yield gen.Task(SESSION.screenshot_generator.wait_for_pending_jobs, bundlepath)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({
            'ok'   : ok,
            'ctime': "%.1f" % ctime,
        }))
        self.finish()

class DashboardClean(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        resp = yield gen.Task(SESSION.reset)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(resp))
        self.finish()

class DashboardDisconnect(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        resp = yield gen.Task(SESSION.end_session)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(resp))
        self.finish()

class BankLoad(web.RequestHandler):
    def get(self):
        # Banks have only bundle and title of each pedalboard, which is the necessary information for the HMI.
        # But for the GUI we need to know information about the used pedalboards

        # First we get all pedalboard info
        pedalboards_data = dict((os.path.abspath(pb['bundle']), pb) for pb in get_all_pedalboards())

        # List the broken pedalboards, we do not want to show those
        broken_pedalboards = []

        for bundlepath, pedalboard in pedalboards_data.items():
            if pedalboard['broken']:
                broken_pedalboards.append(bundlepath)

        # Get the banks using our broken pedalboards filter
        banks = list_banks(broken_pedalboards)

        # Put the full pedalboard info into banks
        for bank in banks:
            bank['pedalboards'] = [pedalboards_data[os.path.abspath(pb['bundle'])] for pb in bank['pedalboards']]

        # All set
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(banks))
        self.finish()

class BankSave(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self):
        banks = json.loads(self.request.body.decode("utf-8", errors="ignore"))
        save_banks(banks)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(True))
        self.finish()

class HardwareLoad(web.RequestHandler):
    def get(self):
        hardware = SESSION.get_hardware()
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(hardware))
        self.finish()

class TemplateHandler(web.RequestHandler):
    def get(self, path):
        if not path:
            path = 'index.html'
        # Caching strategy. If we don't have a version parameter,
        # let's redirect to one
        try:
            version = self.get_argument('v')
        except web.MissingArgumentError:
            uri = self.request.uri
            if self.request.query:
                uri += '&'
            else:
                uri += '?'
            uri += 'v=%s' % self.get_version()
            self.redirect(uri)
            return
        loader = tornado.template.Loader(HTML_DIR)
        section = path.split('.')[0]
        try:
            context = getattr(self, section)()
        except AttributeError:
            context = {}
        context['cloud_url'] = CLOUD_HTTP_ADDRESS
        context['sampleRate'] = get_jack_sample_rate()
        self.write(loader.load(path).generate(**context))

    def get_version(self):
        return str(int(time.time()))

    def index(self):
        context = {}

        with open(DEFAULT_ICON_TEMPLATE, 'r') as fd:
            default_icon_template = tornado.escape.squeeze(fd.read().replace("'", "\\'"))

        with open(DEFAULT_SETTINGS_TEMPLATE, 'r') as fd:
            default_settings_template = tornado.escape.squeeze(fd.read().replace("'", "\\'"))

        context = {
            'default_icon_template': default_icon_template,
            'default_settings_template': default_settings_template,
            'cloud_url': CLOUD_HTTP_ADDRESS,
            'hardware_profile': b64encode(json.dumps(SESSION.get_hardware()).encode("utf-8")),
            'max_screenshot_width': MAX_SCREENSHOT_WIDTH,
            'max_screenshot_height': MAX_SCREENSHOT_HEIGHT,
            'package_server_address': PACKAGE_SERVER_ADDRESS or '',
            'default_package_server_port': DEFAULT_PACKAGE_SERVER_PORT,
            'package_repository': PACKAGE_REPOSITORY,
            'js_custom_channel': 'true' if JS_CUSTOM_CHANNEL else 'false',
            'auto_cloud_backup': 'true' if AUTO_CLOUD_BACKUP else 'false',
            'avatar_url': AVATAR_URL,
            'version': self.get_argument('v'),
            'bundlepath': json.dumps(SESSION.host.pedalboard_path),
            'title': json.dumps(SESSION.host.pedalboard_name),
            'size': json.dumps(SESSION.host.pedalboard_size),
            'fulltitle': SESSION.host.pedalboard_name or "Untitled",
            'titleblend': '' if SESSION.host.pedalboard_name else 'blend',
            'using_app': 'true' if APP else 'false',
            'using_desktop': 'true' if DESKTOP else 'false',
        }
        return context

    def icon(self):
        return self.index()

    def pedalboard(self):
        context = self.index()
        bundlepath = self.get_argument('bundlepath')

        try:
            pedalboard = get_pedalboard_info(bundlepath)
        except:
            print("ERROR in webserver.py: get_pedalboard_info failed")
            context['pedalboard'] = ""
            return context

        context['pedalboard'] = b64encode(json.dumps(pedalboard).encode("utf-8"))
        return context

#class EditionLoader(TemplateHandler):
    #def get(self, path):
        #super(EditionLoader, self).get(path)

class TemplateLoader(web.RequestHandler):
    def get(self, path):
        self.write(open(os.path.join(HTML_DIR, 'include', path)).read())

class BulkTemplateLoader(web.RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'text/javascript')
        basedir = os.path.join(HTML_DIR, 'include')
        for template in os.listdir(basedir):
            if not re.match('^[a-z_]+\.html$', template):
                continue
            contents = open(os.path.join(basedir, template)).read()
            template = template[:-5]
            self.write("TEMPLATES['%s'] = '%s';\n\n"
                       % (template,
                          tornado.escape.squeeze(contents.replace("'", "\\'"))
                          )
                       )

class Ping(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        start = time.time()
        ihm = 0
        if SESSION.hmi_initialized:
            ihm = yield gen.Task(SESSION.web_ping_hmi)
        res = {
            'ihm_online': ihm,
            'ihm_time': int((time.time() - start) * 1000),
        }
        self.write(json.dumps(res))
        self.finish()

class TrueBypass(web.RequestHandler):
    def get(self, channelName, bypassed):
        resp = set_truebypass_value(channelName == "Right", bypassed == "true")
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(resp))
        self.finish()

class SysMonProcessList(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        yield gen.Task(self.get_ps_list)
        self.write(self.ps_list[:-1])
        self.finish()

    def get_ps_list(self, callback):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock = iostream.IOStream(s)

        def recv_ps_list():
            def set_ps_list(v):
                self.ps_list = v
                callback()
            self.sock.read_until("\0".encode("utf-8"), set_ps_list)
        self.sock.connect(('127.0.0.1', 57890), recv_ps_list)

class JackGetMidiDevices(web.RequestHandler):
    def get(self):
        devsInUse, devList, names = SESSION.web_get_midi_device_list()
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({
            "devsInUse": devsInUse,
            "devList"  : devList,
            "names"    : names,
        }))
        self.finish()

class JackSetMidiDevices(web.RequestHandler):
    def post(self):
        devs = json.loads(self.request.body.decode("utf-8", errors="ignore"))
        SESSION.web_set_midi_devices(devs)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(True))
        self.finish()

class JackXRuns(web.RequestHandler):
    def get(self):
        self.write(json.dumps(SESSSION.xrun_count))
        self.finish()

class LoginSign(web.RequestHandler):
    def get(self, sid):
        if not os.path.exists(DEVICE_KEY):
            return
        signature = crypto.Sender(DEVICE_KEY, sid).pack()
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({
                    'signature': signature,
                    'serial': open(DEVICE_SERIAL).read().strip(),
                    }))

class LoginAuthenticate(web.RequestHandler):
    def post(self):
        serialized_user = self.get_argument('user').encode("utf-8")
        signature = self.get_argument('signature')
        receiver = crypto.Receiver(CLOUD_PUB, signature)
        checksum = receiver.unpack()
        self.set_header('Access-Control-Allow-Origin', CLOUD_HTTP_ADDRESS)
        self.set_header('Content-Type', 'application/json')
        if not sha1(serialized_user).hexdigest() == checksum:
            return self.write(json.dumps({ 'ok': False}))
        user = json.loads(b64decode(serialized_user).decode("utf-8", errors="ignore"))
        self.write(json.dumps({ 'ok': True,
                                'user': user }))

class RegistrationStart(web.RequestHandler):
    def get(self, serial_number):
        try:
            package = register.DeviceRegisterer().generate_registration_package(serial_number)
        except register.DeviceAlreadyRegistered:
            raise web.HTTPError(403)

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(package))

class RegistrationFinish(web.RequestHandler):
    def post(self):
        response = json.loads(self.request.body.decode("utf-8", errors="ignore"))
        ok = register.DeviceRegisterer().register(response)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(ok))

class RecordingStart(web.RequestHandler):
    def get(self):
        SESSION.start_recording()
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(True))

class RecordingStop(web.RequestHandler):
    def get(self):
        result = SESSION.stop_recording()
        #result['data'] = b64encode(result.pop('handle').read().encode("utf-8"))
        #open('/tmp/record.json', 'w').write(json.dumps(result, default=json_handler))
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(True))

class RecordingPlay(web.RequestHandler):
    waiting_request = None
    @web.asynchronous
    def get(self, action):
        if action == 'start':
            self.playing = True
            SESSION.start_playing(RecordingPlay.stop_callback)
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(True))
            return self.finish()
        if action == 'wait':
            if RecordingPlay.waiting_request is not None:
                RecordingPlay.stop_callback()
            RecordingPlay.waiting_request = self
            return
        if action == 'stop':
            SESSION.stop_playing()
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(True))
            return self.finish()
        raise web.HTTPError(404)
    @classmethod
    def stop_callback(kls):
        if kls.waiting_request is None:
            return
        kls.waiting_request.set_header('Content-Type', 'application/json')
        kls.waiting_request.write(json.dumps(True))
        kls.waiting_request.finish()
        kls.waiting_request = None

class RecordingDownload(web.RequestHandler):
    def get(self):
        recording = SESSION.recording
        recording['handle'].seek(0)
        data = {
            'audio': b64encode(SESSION.recording['handle'].read()),
            'events': recording['events'],
            }
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(data, default=json_handler))

class RecordingReset(web.RequestHandler):
    def get(self):
        SESSION.reset_recording()
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(True))

class TokensDelete(web.RequestHandler):
    def get(self):
        tokensConf = os.path.join(DATA_DIR, "tokens.conf")

        if os.path.exists(tokensConf):
            os.remove(tokensConf)

class TokensGet(web.RequestHandler):
    def get(self):
        #curtime    = int(time.time())
        tokensConf = os.path.join(DATA_DIR, "tokens.conf")

        self.set_header('Content-Type', 'application/json')

        if os.path.exists(tokensConf):
            with open(tokensConf, 'r') as fd:
                data = json.load(fd)
                keys = data.keys()
                data['ok'] = bool("user_id"       in keys and
                                  "access_token"  in keys and
                                  "refresh_token" in keys)
                #data['curtime'] = curtime
                return self.write(json.dumps(data))

        return self.write(json.dumps({ 'ok': False }))

class TokensSave(web.RequestHandler):
    @jsoncall
    def post(self):
        #curtime    = int(time.time())
        tokensConf = os.path.join(DATA_DIR, "tokens.conf")

        data = dict(self.request.body)
        #data['time'] = curtime
        data.pop("expires_in_days")

        with open(tokensConf, 'w') as fd:
            json.dump(data, fd)

settings = {'log_function': lambda handler: None} if not LOG else {}

application = web.Application(
        EffectInstaller.urls('effect/install') +
        [
            #TODO merge these
            #(r"/system/install_pkg/([^/]+)/?", InstallPkg),
            #(r"/system/install_pkg/do/([^/]+)/?", InstallPkgDo),
            (r"/system/bluetooth/set", BluetoothSetPin),
            (r"/system/info", SystemInfo),

            (r"/resources/(.*)", EffectResource),

            # plugin management
            (r"/effect/add/*(/[A-Za-z0-9_/]+[^/])/?", EffectAdd),
            (r"/effect/remove/*(/[A-Za-z0-9_/]+[^/])/?", EffectRemove),
            (r"/effect/get", EffectGet),
            (r"/effect/bulk/?", EffectBulk),
            (r"/effect/list", EffectList),

            # plugin parameters
            (r"/effect/parameter/set/*(/[A-Za-z0-9_:/]+[^/])/?", EffectParameterSet),
            (r"/effect/parameter/address/*(/[A-Za-z0-9_:/]+[^/])/?", EffectParameterAddress),
            (r"/effect/parameter/midi/learn/*(/[A-Za-z0-9_/]+[^/])/?", EffectParameterMidiLearn),

            # plugin presets
            (r"/effect/preset/load/*(/[A-Za-z0-9_/]+[^/])/?", EffectPresetLoad),
            (r"/effect/preset/save/*(/[A-Za-z0-9_/]+[^/])/?", EffectPresetSave),

            # misc plugin stuff
            (r"/effect/position/*(/[A-Za-z0-9_/]+[^/])/?", EffectPosition),

            # plugin resources
            (r"/effect/image/(screenshot|thumbnail).png", EffectImage),
            (r"/effect/(icon|settings).html", EffectHTML),
            (r"/effect/stylesheet.css", EffectStylesheet),
            (r"/effect/gui.js", EffectJavascript),

            # connections
            (r"/effect/connect/*(/[A-Za-z0-9_/]+[^/]),([A-Za-z0-9_/]+[^/])/?", EffectConnect),
            (r"/effect/disconnect/*(/[A-Za-z0-9_/]+[^/]),([A-Za-z0-9_/]+[^/])/?", EffectDisconnect),

            #(r"/package/([A-Za-z0-9_.-]+)/list/?", PackageEffectList),
            (r"/package/uninstall", PackageUninstall),

            # pedalboard stuff
            (r"/pedalboard/list", PedalboardList),
            (r"/pedalboard/save", PedalboardSave),
            (r"/pedalboard/pack_bundle/?", PedalboardPackBundle),
            (r"/pedalboard/load_bundle/", PedalboardLoadBundle),
            (r"/pedalboard/load_web/", PedalboardLoadWeb),
            (r"/pedalboard/info/", PedalboardInfo),
            (r"/pedalboard/remove/", PedalboardRemove),
            (r"/pedalboard/size/?", PedalboardSize),
            (r"/pedalboard/image/(screenshot|thumbnail).png", PedalboardImage),
            (r"/pedalboard/image/wait", PedalboardImageWait),

            # bank stuff
            (r"/banks/?", BankLoad),
            (r"/banks/save/?", BankSave),

            (r"/hardware", HardwareLoad),

            (r"/login/sign_session/(.+)", LoginSign),
            (r"/login/authenticate", LoginAuthenticate),

            (r"/recording/start", RecordingStart),
            (r"/recording/stop", RecordingStop),
            (r"/recording/play/(start|wait|stop)", RecordingPlay),
            (r"/recording/download", RecordingDownload),
            (r"/recording/reset", RecordingReset),

            (r"/tokens/delete", TokensDelete),
            (r"/tokens/get", TokensGet),
            (r"/tokens/save/?", TokensSave),

            (r"/reset/?", DashboardClean),
            (r"/disconnect/?", DashboardDisconnect),

            (r"/sdk/install/?", SDKEffectInstaller),
            #(r"/sdk/get_config_script/?", SDKEffectScript),

            (r"/register/start/([A-Z0-9-]+)/?", RegistrationStart),
            (r"/register/finish/?", RegistrationFinish),

            #(r"/sysmon/ps", SysMonProcessList),

            (r"/jack/get_midi_devices", JackGetMidiDevices),
            (r"/jack/set_midi_devices", JackSetMidiDevices),
            (r"/jack/xruns", JackXRuns),

            (r"/ping/?", Ping),

            (r"/truebypass/(Left|Right)/(true|false)", TrueBypass),

            (r"/(index.html)?$", TemplateHandler),
            (r"/([a-z]+\.html)$", TemplateHandler),
            (r"/load_template/([a-z_]+\.html)$", TemplateLoader),
            (r"/js/templates.js$", BulkTemplateLoader),

            (r"/websocket/?$", ServerWebSocket),

            (r"/(.*)", web.StaticFileHandler, {"path": HTML_DIR}),
            ],
            debug=LOG and False, **settings)

def signal_recv(sig, frame=0):
    if sig == SIGUSR2:
        tornado.ioloop.IOLoop.instance().add_callback_from_signal(SESSION.signal_disconnect)

def prepare():
    def run_server():
        signal(SIGUSR2, signal_recv)
        application.listen(DEVICE_WEBSERVER_PORT, address="0.0.0.0")
        if LOG:
            tornado.log.enable_pretty_logging()

    def checkhost():
        if SESSION.host.readsock is None or SESSION.host.writesock is None:
            print("Host failed to initialize, is the backend running?")
            SESSION.host.close_jack()
            sys.exit(1)

        elif not SESSION.host.connected:
            ioinstance.call_later(0.1, checkhost)

    def check():
        check_environment()
        checkhost()

    lv2_init()

    if False:
        print("Scanning plugins, this may take a little...")
        get_all_plugins()
        print("Done!")

    run_server()

    ioinstance = tornado.ioloop.IOLoop.instance()
    ioinstance.add_callback(check)

def start():
    tornado.ioloop.IOLoop.instance().start()

def stop():
    tornado.ioloop.IOLoop.instance().stop()

def run():
    prepare()
    start()

if __name__ == "__main__":
    run()
