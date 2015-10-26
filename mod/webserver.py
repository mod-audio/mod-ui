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

import os, re, shutil, sys
import json, socket
import tornado.ioloop
import tornado.options
import tornado.escape
import lilv
import time, uuid
from datetime import timedelta
from io import StringIO
try:
    import Image
except ImportError:
    from PIL import Image
from hashlib import sha1 as sha
from hashlib import md5
from base64 import b64decode, b64encode
from tornado import gen, web, iostream, websocket
import subprocess
from glob import glob

from mod.settings import (APP, DESKTOP, LOG,
                          HTML_DIR, CLOUD_PUB, DOWNLOAD_TMP_DIR, DEVICE_WEBSERVER_PORT, CLOUD_HTTP_ADDRESS,
                          DEVICE_SERIAL, DEVICE_KEY, LOCAL_REPOSITORY_DIR, LV2_PLUGIN_DIR,
                          DEFAULT_ICON_TEMPLATE, DEFAULT_SETTINGS_TEMPLATE, DEFAULT_ICON_IMAGE,
                          MAX_SCREENSHOT_WIDTH, MAX_SCREENSHOT_HEIGHT,
                          MAX_THUMB_WIDTH, MAX_THUMB_HEIGHT,
                          PACKAGE_SERVER_ADDRESS, DEFAULT_PACKAGE_SERVER_PORT,
                          PACKAGE_REPOSITORY, DEMO_DATA_DIR, DATA_DIR,
                          AVATAR_URL, DEV_ENVIRONMENT,
                          JS_CUSTOM_CHANNEL, AUTO_CLOUD_BACKUP)

from mod import jsoncall, json_handler, symbolify
from mod.communication import fileserver, crypto
from mod.session import SESSION
from mod.bank import list_banks, save_banks
from mod.screenshot import generate_screenshot, resize_image
from mod.system import (sync_pacman_db, get_pacman_upgrade_list,
                                pacman_upgrade, set_bluetooth_pin)
from mod import register
from mod import check_environment

try:
    from mod.utils import (init as lv2_init,
                           add_bundle_to_lilv_world,
                           remove_bundle_from_lilv_world,
                           get_all_plugins,
                           get_plugin_info,
                           get_plugin_info_mini,
                           get_all_pedalboards,
                           get_pedalboard_info,
                           get_pedalboard_name)
    usingFastLilv = True
except:
    print("Failed to import new quick lilv parsing module, doing it the old slower way...")
    from mod.lilvlib import get_pedalboard_info, get_pedalboard_name
    from mod.lv2 import add_bundle_to_lilv_world, remove_bundle_from_lilv_world
    from mod.lv2 import get_all_pedalboards, get_plugin_info, get_all_plugins, init as lv2_init
    usingFastLilv = False

# Global fake timestamp used for pedalboard thumbnails
# FIXME - use real timestamp
global fake_tstamp
fake_tstamp = 0

# Formats the pedalboard in a way that the javascript side understands
def format_pedalboard(pedal):
    global fake_tstamp
    fake_tstamp += 1

    return {
        'instances'  : {},
        'connections': [],
        'metadata'   : {
            'title'    : pedal['name'],
            'thumbnail': pedal['thumbnail'],
            'tstamp'   : fake_tstamp,
        },
        'uri'   : pedal['uri'],
        'bundle': pedal['bundlepath'],
        'width' : pedal['width'],
        'height': pedal['height']
    }

def install_bundles_in_tmp_dir():
    removed   = []
    installed = []

    for bundle in os.listdir(DOWNLOAD_TMP_DIR):
        tmppath    = os.path.join(DOWNLOAD_TMP_DIR, bundle)
        bundlepath = os.path.join(LV2_PLUGIN_DIR, bundle)

        if os.path.exists(bundlepath):
            removed += remove_bundle_from_lilv_world(bundlepath, True)
            shutil.rmtree(bundlepath)

        shutil.move(tmppath, bundlepath)
        installed += add_bundle_to_lilv_world(bundlepath, True)

    # TODO - make ingen refresh lv2 world

    if len(installed) == 0:
        resp = {
            'ok'     : False,
            'error'  : "No plugins found in bundle",
            'removed': removed,
        }
    else:
        resp = {
            'ok'       : True,
            'removed'  : removed,
            'installed': installed,
        }

    if len(removed) > 0:
        lv2_init()

    return resp

def uninstall_bundles(bundles):
    removed = []

    for bundlepath in bundles:
        if os.path.exists(bundlepath):
            removed += remove_bundle_from_lilv_world(bundlepath, True)
            shutil.rmtree(bundlepath)

    # TODO - make ingen refresh lv2 world

    if len(removed) > 0:
        lv2_init()
        resp = {
            'ok'     : True,
            'removed': removed,
        }
    else:
        resp = {
            'ok'   : False,
            'error': "No plugins found",
        }

    return resp

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
        callback(install_bundles_in_tmp_dir())

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

class UpgradeSync(fileserver.FileReceiver):
    download_tmp_dir = DOWNLOAD_TMP_DIR
    remote_public_key = CLOUD_PUB
    destination_dir = LOCAL_REPOSITORY_DIR

    def process_file(self, data, callback):
        def on_finish(result):
            self.result = result
            callback()
        sync_pacman_db(on_finish)

class UpgradePackage(fileserver.FileReceiver):
    download_tmp_dir = DOWNLOAD_TMP_DIR
    remote_public_key = CLOUD_PUB
    destination_dir = LOCAL_REPOSITORY_DIR

    def process_file(self, data, callback):
        self.result = 1
        callback()

class UpgradePackages(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        packages = yield gen.Task(get_pacman_upgrade_list)

        self.write(json.dumps(packages))
        self.finish()

class UpgradeDo(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        result = yield gen.Task(pacman_upgrade)

        self.write(json.dumps(result))
        self.finish()

class BluetoothSetPin(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self):
        pin = self.get_argument("pin", None)

        if pin is None:
            self.write(json.dumps(False))
        else:
            result = yield gen.Task(lambda callback:set_bluetooth_pin(pin, callback))
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

    def process_file(self, data, callback=lambda:None):
        def on_finish(resp):
            self.result = resp
            callback()
        install_package(data['filename'], on_finish)

class SDKSysUpdate(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self):
        upload = self.request.files['update_package'][0]
        update_package = os.path.join(DOWNLOAD_TMP_DIR, upload['filename'])
        open(update_package, 'w').write(upload['body'])
        dirname = os.path.join(DOWNLOAD_TMP_DIR, 'install_update_%s' % os.getpid())
        def install_update(pkg, callback):
            os.mkdir(dirname)
            proc = subprocess.Popen(['tar', 'zxf', pkg, '-C', dirname],
                                        cwd=DOWNLOAD_TMP_DIR,
                                        stdout=subprocess.PIPE)
            def end_untar_pkgs(fileno, event):
                if proc.poll() is None: return
                callback()
            tornado.ioloop.IOLoop.instance().add_handler(proc.stdout.fileno(), end_untar_pkgs, 16)

        res = yield gen.Task(install_update, update_package)
        proc = subprocess.Popen(['pacman', '-U'] + glob(os.path.join(dirname, '*')),
                                        cwd=DOWNLOAD_TMP_DIR,
                                        stdout=subprocess.PIPE)
        def end_pacman(fileno, event):
            if proc.poll() is None: return
        tornado.ioloop.IOLoop.instance().add_handler(proc.stdout.fileno(), end_pacman, 16)

        self.write(json.dumps(True))
        self.finish()

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

class EffectList(web.RequestHandler):
    def get(self):
        data = get_all_plugins()
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(data))

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
            if usingFastLilv and image == "thumbnail":
                data = get_plugin_info_mini(uri)
            else:
                data = get_plugin_info(uri)
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

class EffectPosition(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        x = float(self.get_argument('x'))
        y = float(self.get_argument('y'))
        resp = SESSION.web_set_position(instance, x, y)
        self.write(json.dumps(resp))
        self.finish()

class AtomWebSocket(websocket.WebSocketHandler):
    def open(self):
        print("atom websocket open")
        SESSION.websocket_opened(self)

    def on_close(self):
        print("atom websocket close")
        SESSION.websocket_closed(self)

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

# TODO
class PackageUninstall(web.RequestHandler):
    def post(self):
        bundles = json.loads(self.request.body.decode("utf-8", errors="ignore"))
        # FIXME: check if all bundles are inside LV2_PATH
        # we don't want users sending test messages and deleting randomly system files!
        resp = uninstall_bundles(bundles)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(resp))
        self.finish()

class PedalboardList(web.RequestHandler):
    def get(self):
        result = []

        for pedal in get_all_pedalboards(False):
            result.append(format_pedalboard(pedal))

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(result))

class PedalboardSave(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self):
        title = self.get_argument('title')
        asNew = bool(int(self.get_argument('asNew')))
        saved = yield gen.Task(SESSION.web_save_pedalboard, title, asNew)
        self.write(json.dumps({
            'ok': saved,
            'bundlepath': SESSION.bundlepath
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

        try:
            name = get_pedalboard_name(bundlepath)
        except Exception as e:
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps({ 'ok': False, 'error': str(e).split(") - ",1)[-1] }))
            self.finish()
            return

        SESSION.load_pedalboard(bundlepath, name)

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({
            'ok':   True,
            'name': name
        }))
        self.finish()

class PedalboardLoadWeb(SimpleFileReceiver):
    remote_public_key = CLOUD_PUB # needed?
    destination_dir = os.path.expanduser("~/.lv2/") # FIXME cross-platform, perhaps lookup in LV2_PATH

    def process_file(self, data, callback=lambda:None):
        filename = os.path.join(self.destination_dir, data['filename'])

        if not os.path.exists(filename):
            callback()
            return

        if not os.path.exists(self.destination_dir):
            os.mkdir(self.destination_dir)

        # FIXME - don't use external tools!
        from subprocess import getoutput
        tar_output = getoutput('env LANG=C tar -xvf "%s" -C "%s"' % (filename, self.destination_dir))
        bundlepath = os.path.join(self.destination_dir, tar_output.strip().split("\n", 1)[0])

        if not os.path.exists(bundlepath):
            raise IOError(bundlepath)

        # make sure pedalboard is valid
        name = get_pedalboard_name(bundlepath)

        SESSION.load_pedalboard(bundlepath, name)

        os.remove(filename)
        callback()

class PedalboardRemove(web.RequestHandler):
    def get(self, bundlepath):
        # there's 5 steps to this:
        # 1 - remove the bundle from disk
        # 2 - remove the bundle from our lv2 lilv world
        # 3 - remove references to the bundle in banks
        # 4 - delete all presets of the pedaloard
        # 5 - tell ingen the bundle (plugin) is gone
        pass

class PedalboardScreenshot(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, pedalboard_id):
        img = yield gen.Task(generate_screenshot, pedalboard_id,
                             MAX_SCREENSHOT_WIDTH, MAX_SCREENSHOT_HEIGHT)
        output = StringIO.StringIO()
        img.save(output, format="PNG")
        screenshot_data = output.getvalue()

        resize_image(img, MAX_THUMB_WIDTH, MAX_THUMB_HEIGHT)
        output = StringIO.StringIO()
        img.save(output, format="PNG")
        thumbnail_data = output.getvalue()

        result = {
            'screenshot': b64encode(screenshot_data),
            'thumbnail': b64encode(thumbnail_data),
        }

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(result))
        self.finish()

class PedalboardSize(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        width  = int(self.get_argument('width'))
        height = int(self.get_argument('height'))
        resp   = yield gen.Task(SESSION.pedalboard_size, width, height)
        self.write(json.dumps(resp))
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
        resp = yield gen.Task(SESSION.screenshot_generator.wait_for_pending_jobs, bundlepath)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(resp))
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
        banks = list_banks()

        # Banks have only URI and title of each pedalboard, which are the necessary information for the HMI.
        # But the GUI needs the whole pedalboard metadata
        pedalboards_dict = get_all_pedalboards(True)
        pedalboards_keys = pedalboards_dict.keys()

        for bank in banks:
            pedalboards = []

            for pedalboard in bank['pedalboards']:
                if pedalboard['uri'] in pedalboards_keys:
                    pedalboards.append(format_pedalboard(pedalboards_dict[pedalboard['uri']]))

            bank['pedalboards'] = pedalboards

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(banks))

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
        context['sampleRate'] = SESSION.engine_samplerate
        self.write(loader.load(path).generate(**context))

    def get_version(self):
        if DEV_ENVIRONMENT:
            return str(int(time.time()))
        try:
            proc = subprocess.Popen(['pacman', '-Q'],
                                    stdout=subprocess.PIPE,
                                    stderr=open('/dev/null', 'w')
                                    )
            proc.wait()
            if proc.poll() == 0:
                return md5(proc.stdout.read()).hexdigest()
        except OSError:
            pass

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
            'bundlepath': json.dumps(SESSION.bundlepath),
            'title': json.dumps(SESSION.title),
            'fulltitle': SESSION.title or "Untitled",
            'using_app': json.dumps(APP),
            'using_desktop': json.dumps(DESKTOP),
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

        data = {
            "instances": [],
            "connections": pedalboard['connections'],
            "hardware": pedalboard['hardware'],
        }

        for plugin in pedalboard['plugins']:
            data["instances"].append({
                "uri": plugin['uri'],
                "x": plugin['x'],
                "y": plugin['y'],
                "bypassed": not plugin['enabled'],
            })

        context['pedalboard'] = b64encode(json.dumps(data).encode("utf-8"))
        return context

class EditionLoader(TemplateHandler):
    def get(self, path):
        super(EditionLoader, self).get(path)
        SESSION.start_session()

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
        if not sha(serialized_user).hexdigest() == checksum:
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

class DemoRestore(web.RequestHandler):
    """
    This is used for demo mode. It restores a state of installed plugins
    and saved pedalboards
    """
    def get(self):
        if not DEMO_DATA_DIR or not os.path.exists(DEMO_DATA_DIR):
            self.write("Demo mode disabled")
            return
        btn = 'bluetooth.name'
        if os.path.exists(os.path.join(DATA_DIR, btn)):
            shutil.copy(os.path.join(DATA_DIR, btn),
                        os.path.join(DEMO_DATA_DIR, btn))
        shutil.rmtree(DATA_DIR)
        shutil.copytree(DEMO_DATA_DIR, DATA_DIR, symlinks=True)

        loader = tornado.template.Loader(HTML_DIR)
        ctx = { 'cloud_url': CLOUD_HTTP_ADDRESS }
        self.write(loader.load('demo_restore.html').generate(**ctx))

        #tornado.ioloop.IOLoop.instance().add_callback(lambda: sys.exit(0))

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
        UpgradeSync.urls('system/upgrade/sync') +
        UpgradePackage.urls('system/upgrade/package') +
        EffectInstaller.urls('effect/install') +
        [
            (r"/system/upgrade/packages", UpgradePackages),
            (r"/system/upgrade/do", UpgradeDo),
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
            (r"/pedalboard/remove/?", PedalboardRemove),
            (r"/pedalboard/screenshot/?", PedalboardScreenshot),
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

            (r"/sdk/sysupdate/?", SDKSysUpdate),
            (r"/sdk/install/?", SDKEffectInstaller),
            #(r"/sdk/get_config_script/?", SDKEffectScript),

            (r"/register/start/([A-Z0-9-]+)/?", RegistrationStart),
            (r"/register/finish/?", RegistrationFinish),

            #(r"/sysmon/ps", SysMonProcessList),

            (r"/jack/get_midi_devices", JackGetMidiDevices),
            (r"/jack/set_midi_devices", JackSetMidiDevices),
            (r"/jack/xruns", JackXRuns),

            (r"/ping/?", Ping),

            (r"/(index.html)?$", EditionLoader),
            (r"/([a-z]+\.html)$", TemplateHandler),
            (r"/load_template/([a-z_]+\.html)$", TemplateLoader),
            (r"/js/templates.js$", BulkTemplateLoader),

            (r"/demo/restore/?$", DemoRestore),

            (r"/websocket/?$", AtomWebSocket),

            (r"/(.*)", web.StaticFileHandler, {"path": HTML_DIR}),
            ],
            debug=LOG and False, **settings)

def prepare():
    def run_server():
        application.listen(DEVICE_WEBSERVER_PORT, address="0.0.0.0")
        if LOG:
            tornado.log.enable_pretty_logging()

    def checkhost():
        if SESSION.host.sock is None:
            print("Host failed to initialize, is the backend running?")
            SESSION.host.close_jack()
            sys.exit(1)

        elif not SESSION.host.connected:
            ioinstance.add_callback(checkhost)

    def check():
        check_environment()
        checkhost()

    lv2_init()

    if not (APP or usingFastLilv):
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
