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
from base64 import b64decode, b64encode
from signal import signal, SIGUSR2
from tornado import gen, iostream, web, websocket
from tornado.util import unicode_type
from uuid import uuid4

from mod.settings import (APP, LOG,
                          HTML_DIR, DOWNLOAD_TMP_DIR, DEVICE_KEY, DEVICE_WEBSERVER_PORT,
                          CLOUD_HTTP_ADDRESS, PEDALBOARDS_HTTP_ADDRESS,
                          LV2_PLUGIN_DIR, LV2_PEDALBOARDS_DIR, IMAGE_VERSION,
                          UPDATE_FILE, USING_256_FRAMES_FILE,
                          DEFAULT_ICON_TEMPLATE, DEFAULT_SETTINGS_TEMPLATE, DEFAULT_ICON_IMAGE,
                          DEFAULT_PEDALBOARD, DATA_DIR, USER_ID_JSON_FILE, FAVORITES_JSON_FILE, BLUETOOTH_PIN)

from mod import check_environment, jsoncall, json_handler
from mod.bank import list_banks, save_banks, remove_pedalboard_from_banks
from mod.session import SESSION
from mod.utils import (init as lv2_init,
                       get_plugin_list,
                       get_all_plugins,
                       get_plugin_info,
                       get_plugin_gui,
                       get_plugin_gui_mini,
                       get_all_pedalboards,
                       get_pedalboard_info,
                       get_jack_buffer_size,
                       set_jack_buffer_size,
                       get_jack_sample_rate,
                       set_truebypass_value,
                       set_process_name,
                       reset_xruns)

try:
    from mod.communication import token
except:
    token = None

# Global webserver state, not part of session
class GlobalWebServerState(object):
    __slots__ = [
        'favorites'
    ]

gState = GlobalWebServerState()
gState.favorites = []

@gen.coroutine
def install_bundles_in_tmp_dir(callback):
    error     = ""
    removed   = []
    installed = []
    needsToSaveFavorites = False

    for bundle in os.listdir(DOWNLOAD_TMP_DIR):
        tmppath    = os.path.join(DOWNLOAD_TMP_DIR, bundle)
        bundlepath = os.path.join(LV2_PLUGIN_DIR, bundle)

        if os.path.exists(bundlepath):
            resp, data = yield gen.Task(SESSION.host.remove_bundle, bundlepath, True)

            # When removing bundles we can ignore the ones that are not loaded
            # It can happen if a previous install failed abruptely
            if not resp and data == "Bundle not loaded":
                resp = True
                data = []

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

    for uri in removed:
        if uri not in installed:
            needsToSaveFavorites = True
            SESSION.favorites.remove(uri)

    if needsToSaveFavorites:
        with open(FAVORITES_JSON_FILE, 'w') as fh:
            json.dump(SESSION.favorites, fh)

    if error or len(installed) == 0:
        # Delete old temp files
        for bundle in os.listdir(DOWNLOAD_TMP_DIR):
            shutil.rmtree(os.path.join(DOWNLOAD_TMP_DIR, bundle))

        resp = {
            'ok'       : False,
            'error'    : error or "No plugins found in bundle",
            'removed'  : removed,
            'installed': [],
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
            'ok'       : False,
            'error'    : "Failed to find archive",
            'installed': [],
            'removed'  : [],
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

def move_file(src, dst, callback):
    proc = subprocess.Popen(['mv', src, dst],
                            stdout=subprocess.PIPE)

    def end_move(fileno, event):
        if proc.poll() is None:
            return
        ioloop.remove_handler(fileno)
        callback()

    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.add_handler(proc.stdout.fileno(), end_move, 16)

class JsonRequestHandler(web.RequestHandler):
    def write(self, data):
        # FIXME: something is sending strings out, need to investigate what later..
        # it's likely something using write(json.dumps(...))
        # we want to prevent that as it causes issues under Mac OS

        if isinstance(data, (bytes, unicode_type, dict)):
            web.RequestHandler.write(self, data)
            self.finish()
            return

        elif data is True:
            data = "true"
            self.set_header("Content-Type", "application/json; charset=UTF-8")

        elif data is False:
            data = "false"
            self.set_header("Content-Type", "application/json; charset=UTF-8")

        # TESTING for data types, remove this later
        #elif not isinstance(data, list):
            #print("=== TESTING: Got new data type for RequestHandler.write():", type(data), "msg:", data)
            #data = json.dumps(data)
            #self.set_header('Content-type', 'application/json')

        else:
            data = json.dumps(data)
            self.set_header("Content-Type", "application/json; charset=UTF-8")

        web.RequestHandler.write(self, data)
        self.finish()

class RemoteRequestHandler(JsonRequestHandler):
    def set_default_headers(self):
        origin = self.request.headers['Origin']
        match  = re.match(r'^(\w+)://([^/]*)/?', origin)
        if match is None:
            return
        protocol, domain = match.groups()
        if protocol not in ("http", "https"):
            return
        if not domain.endswith("moddevices.com"):
            return
        self.set_header("Access-Control-Allow-Origin", origin)

class SimpleFileReceiver(JsonRequestHandler):
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
        name = str(uuid4())
        if not os.path.exists(self.destination_dir):
            os.mkdir(self.destination_dir)
        with open(os.path.join(self.destination_dir, name), 'wb') as fh:
            fh.write(self.request.body)
        data = {
            "filename": name
        }
        yield gen.Task(self.process_file, data)
        self.write({
            'ok'    : True,
            'result': self.result
        })

    def process_file(self, data, callback=lambda:None):
        """to be overriden"""

class BluetoothSetPin(JsonRequestHandler):
    def post(self):
        pin = self.get_argument("pin", None)

        if pin is None:
            self.write(False)
            return

        with open(BLUETOOTH_PIN, 'w') as fh:
            fh.write(pin)

        self.write(True)

class SystemInfo(JsonRequestHandler):
    def get(self):
        uname = os.uname()
        info = {
            "hardware": {},
            "env": dict((k, os.environ[k]) for k in [k for k in os.environ.keys() if k.startswith("MOD")]),
            "python": {
                "argv"    : sys.argv,
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

        self.write(info)

class UpdateDownload(SimpleFileReceiver):
    destination_dir = "/tmp/update"

    @web.asynchronous
    @gen.engine
    def process_file(self, data, callback=lambda:None):
        self.sfr_callback = callback

        # TODO: verify checksum?
        move_file(os.path.join(self.destination_dir, data['filename']), UPDATE_FILE, self.move_file_finished)

    def move_file_finished(self):
        self.result = True
        self.sfr_callback()

class UpdateBegin(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self):
        if not os.path.exists(UPDATE_FILE):
            self.write(False)
            return

        # write & finish before sending message
        self.write(True)

        # send message asap, but not quite right now
        yield gen.Task(self.flush, False)
        yield gen.Task(SESSION.hmi.send, "restore", datatype='boolean')

class EffectInstaller(SimpleFileReceiver):
    destination_dir = DOWNLOAD_TMP_DIR

    @web.asynchronous
    @gen.engine
    def process_file(self, data, callback=lambda:None):
        def on_finish(resp):
            self.result = resp
            callback()
        install_package(data['filename'], on_finish)

class EffectBulk(JsonRequestHandler):
    def prepare(self):
        if "application/json" in self.request.headers.get("Content-Type"):
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

        self.write(result)

class EffectList(JsonRequestHandler):
    def get(self):
        data = get_all_plugins()
        self.write(data)

class SDKEffectInstaller(EffectInstaller):
    @web.asynchronous
    @gen.engine
    def post(self):
        upload = self.request.files['package'][0]

        with open(os.path.join(DOWNLOAD_TMP_DIR, upload['filename']), 'wb') as fh:
            fh.write(b64decode(upload['body']))

        resp = yield gen.Task(install_package, upload['filename'])

        if resp['ok']:
            SESSION.msg_callback("rescan " + b64encode(json.dumps(resp).encode("utf-8")).decode("utf-8"))

        self.write(resp)

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
            modgui = get_plugin_gui_mini(uri)
        except:
            raise web.HTTPError(404)

        try:
            root = modgui['resourcesDirectory']
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

class EffectImage(web.StaticFileHandler):
    def initialize(self):
        uri = self.get_argument('uri')

        try:
            self.modgui = get_plugin_gui_mini(uri)
        except:
            raise web.HTTPError(404)

        try:
            root = self.modgui['resourcesDirectory']
        except:
            raise web.HTTPError(404)

        return web.StaticFileHandler.initialize(self, root)

    def parse_url_path(self, image):
        try:
            path = self.modgui[image]
        except:
            path = None

        if path is None or not os.path.exists(path):
            try:
                path = DEFAULT_ICON_IMAGE[image]
            except:
                raise web.HTTPError(404)
            else:
                web.StaticFileHandler.initialize(self, os.path.dirname(path))

        return path

class EffectFile(web.StaticFileHandler):
    def initialize(self):
        # return custom type directly. The browser will do the parsing
        self.custom_type = None

        uri = self.get_argument('uri')

        try:
            self.modgui = get_plugin_gui(uri)
        except:
            raise web.HTTPError(404)

        try:
            root = self.modgui['resourcesDirectory']
        except:
            raise web.HTTPError(404)

        return web.StaticFileHandler.initialize(self, root)

    def parse_url_path(self, prop):
        try:
            path = self.modgui[prop]
        except:
            raise web.HTTPError(404)

        if prop in ("iconTemplate", "settingsTemplate", "stylesheet", "javascript"):
            self.custom_type = "text/plain"

        return path

    def get_content_type(self):
        if self.custom_type is not None:
            return self.custom_type
        return web.StaticFileHandler.get_content_type(self)

class EffectAdd(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        uri = self.get_argument('uri')
        x   = float(self.request.arguments.get('x', [0])[0])
        y   = float(self.request.arguments.get('y', [0])[0])

        ok = yield gen.Task(SESSION.web_add, instance, uri, x, y)

        if not ok:
            self.write(False)
            return

        try:
            data = get_plugin_info(uri)
        except:
            print("ERROR in webserver.py: get_plugin_info for '%s' failed" % uri)
            raise web.HTTPError(404)

        self.write(data)

class EffectRemove(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        ok = yield gen.Task(SESSION.web_remove, instance)
        self.write(ok)

class EffectGet(JsonRequestHandler):
    def get(self):
        uri = self.get_argument('uri')

        try:
            data = get_plugin_info(uri)
        except:
            print("ERROR in webserver.py: get_plugin_info for '%s' failed" % uri)
            raise web.HTTPError(404)

        self.write(data)

class EffectConnect(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, port_from, port_to):
        ok = yield gen.Task(SESSION.web_connect, port_from, port_to)
        self.write(ok)

class EffectDisconnect(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, port_from, port_to):
        ok = yield gen.Task(SESSION.web_disconnect, port_from, port_to)
        self.write(ok)

class EffectParameterAddress(JsonRequestHandler):
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

        ok = yield gen.Task(SESSION.web_parameter_address, port, uri, label, maximum, minimum, value, steps)
        self.write(ok)

class EffectPresetLoad(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        uri = self.get_argument('uri')
        ok  = yield gen.Task(SESSION.host.preset_load, instance, uri)
        self.write(ok)

class EffectPresetSaveNew(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        name = self.get_argument('name')
        resp = yield gen.Task(SESSION.host.preset_save_new, instance, name)
        self.write(resp)

class EffectPresetSaveReplace(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        uri    = self.get_argument('uri')
        bundle = self.get_argument('bundle')
        name   = self.get_argument('name')
        resp   = yield gen.Task(SESSION.host.preset_save_replace, instance, uri, bundle, name)
        self.write(resp)

class EffectPresetDelete(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        uri    = self.get_argument('uri')
        bundle = self.get_argument('bundle')
        ok     = yield gen.Task(SESSION.host.preset_delete, instance, uri, bundle)
        self.write(ok)

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

    def on_message(self, message):
        if message == "pong":
            return

        data = message.split(" ")
        cmd  = data[0]

        if cmd == "param_set":
            port  = data[1]
            value = float(data[2])
            SESSION.ws_parameter_set(port, value, self)

        elif cmd == "plugin_pos":
            inst = data[1]
            x    = float(data[2])
            y    = float(data[3])
            SESSION.ws_plugin_position(inst, x, y)

        elif cmd == "pb_size":
            width  = int(float(data[1]))
            height = int(float(data[2]))
            SESSION.ws_pedalboard_size(width, height)

class PackageUninstall(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self):
        bundles = json.loads(self.request.body.decode("utf-8", errors="ignore"))
        error   = ""
        removed = []

        print("asked to remove these:", bundles)

        for bundlepath in bundles:
            if os.path.exists(bundlepath) and os.path.isdir(bundlepath):
                resp, data = yield gen.Task(SESSION.host.remove_bundle, bundlepath, True)

                if resp:
                    removed += data
                    shutil.rmtree(bundlepath)
                else:
                    error = data
                    break
            else:
                print("bundlepath is non-existent:", bundlepath)

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
            if len(broken) > 0:
                list_banks(broken)

        self.write(resp)

class PedalboardList(JsonRequestHandler):
    def get(self):
        self.write(get_all_pedalboards())

class PedalboardSave(JsonRequestHandler):
    def post(self):
        title = self.get_argument('title')
        asNew = bool(int(self.get_argument('asNew')))

        bundlepath = SESSION.web_save_pedalboard(title, asNew)

        self.write({
            'ok': bundlepath is not None,
            'bundlepath': bundlepath
        })

class PedalboardPackBundle(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        # ~/.pedalboards/name.pedalboard/
        bundlepath = os.path.abspath(self.get_argument('bundlepath'))
        # ~/.pedalboards/
        parentpath = os.path.abspath(os.path.join(bundlepath, ".."))
        # name.pedalboard
        bundlename = os.path.basename(bundlepath)
        # /tmp/*
        tmpdir   = "/tmp"
        tmpaudio = os.path.join(tmpdir, "audio.ogg")
        tmpstep1 = os.path.join(tmpdir, "pedalboard.tar.gz")
        tmpstep2 = os.path.join(tmpdir, "pedalboard+audio.tar.gz")

        # local usage
        ioloop = tornado.ioloop.IOLoop.instance()

        # save variable locally, used across callbacks
        self.proc = None

        # final callback
        def end_procs(tmpfile):
            with open(tmpfile, 'rb') as fh:
                self.write(fh.read())
            self.finish()
            os.remove(tmpfile)

        # callback for audio + pedalboard.tar.gz packing
        def end_proc2(fileno, event):
            if self.proc.poll() is None:
                return
            ioloop.remove_handler(fileno)

            os.remove(tmpaudio)
            os.remove(tmpstep1)
            end_procs(tmpstep2)

        # callback for pedalboard packing
        def end_proc1(fileno, event):
            if self.proc.poll() is None:
                return
            ioloop.remove_handler(fileno)

            # stop now if no audio available
            if SESSION.recordhandle is None:
                end_procs(tmpstep1)
                return

            # dump audio to disk
            SESSION.recordhandle.seek(0)
            with open(tmpaudio, 'wb') as fh:
                fh.write(SESSION.recordhandle.read())

            # pack audio + pedalboard.tar.gz
            self.proc = subprocess.Popen(['tar', 'czf', tmpstep2, "audio.ogg", "pedalboard.tar.gz"],
                                        cwd=tmpdir,
                                        stdout=subprocess.PIPE)
            ioloop.add_handler(self.proc.stdout.fileno(), end_proc2, 16)

        # start packing pedalboard
        self.proc = subprocess.Popen(['tar', 'czf', tmpstep1, bundlename],
                                     cwd=parentpath,
                                     stdout=subprocess.PIPE)
        ioloop.add_handler(self.proc.stdout.fileno(), end_proc1, 16)

class PedalboardLoadBundle(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self):
        bundlepath = os.path.abspath(self.get_argument("bundlepath"))

        try:
            isDefault = bool(int(self.get_argument("isDefault")))
        except:
            isDefault = False

        if os.path.exists(bundlepath):
            name = SESSION.load_pedalboard(bundlepath, isDefault)
        else:
            name = None

        self.write({
            'ok':   name is not None,
            'name': name or ""
        })

class PedalboardLoadRemote(RemoteRequestHandler):
    def post(self, pedalboard_id):
        if len(SESSION.websockets) == 0:
            self.write(False)
            return

        if pedalboard_id[0] == '/':
            pedalboard_id = pedalboard_id[1:]

        SESSION.websockets[0].write_message("load-pb-remote " + pedalboard_id)
        self.write(True)

class PedalboardLoadWeb(SimpleFileReceiver):
    destination_dir = "/tmp/pedalboards"

    @web.asynchronous
    @gen.engine
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
        bundlepath = os.path.abspath(bundlepath)

        if not os.path.exists(bundlepath):
            raise IOError(bundlepath)

        SESSION.load_pedalboard(bundlepath, False)

        os.remove(filename)
        callback()

class PedalboardInfo(JsonRequestHandler):
    def get(self):
        bundlepath = os.path.abspath(self.get_argument('bundlepath'))
        self.write(get_pedalboard_info(bundlepath))

class PedalboardRemove(JsonRequestHandler):
    def get(self):
        bundlepath = os.path.abspath(self.get_argument('bundlepath'))

        if not os.path.exists(bundlepath):
            self.write(False)
            return

        shutil.rmtree(bundlepath)
        remove_pedalboard_from_banks(bundlepath)
        self.write(True)

class PedalboardImage(web.StaticFileHandler):
    def initialize(self):
        root = self.get_argument('bundlepath')
        return web.StaticFileHandler.initialize(self, root)

    def parse_url_path(self, image):
        return os.path.join(self.root, "%s.png" % image)

class PedalboardImageGenerate(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        bundlepath = os.path.abspath(self.get_argument('bundlepath'))
        ok, ctime  = yield gen.Task(SESSION.screenshot_generator.schedule_screenshot, bundlepath)
        self.write({
            'ok'   : ok,
            'ctime': "%.1f" % ctime,
        })

class PedalboardImageWait(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        bundlepath = os.path.abspath(self.get_argument('bundlepath'))
        ok, ctime  = yield gen.Task(SESSION.screenshot_generator.wait_for_pending_jobs, bundlepath)
        self.write({
            'ok'   : ok,
            'ctime': "%.1f" % ctime,
        })

class DashboardClean(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        ok = yield gen.Task(SESSION.reset)
        self.write(ok)

class BankLoad(JsonRequestHandler):
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
        self.write(banks)

class BankSave(JsonRequestHandler):
    def post(self):
        banks = json.loads(self.request.body.decode("utf-8", errors="ignore"))
        save_banks(banks)
        self.write(True)

class HardwareLoad(JsonRequestHandler):
    def get(self):
        hardware = SESSION.get_hardware()
        self.write(hardware)

class TemplateHandler(web.RequestHandler):
    def get(self, path):
        # Caching strategy.
        # 1. If we don't have a version parameter, redirect
        curVersion = self.get_version()
        try:
            version = tornado.escape.url_escape(self.get_argument('v'))
        except web.MissingArgumentError:
            uri  = self.request.uri
            uri += '&' if self.request.query else '?'
            uri += 'v=%s' % curVersion
            self.redirect(uri)
            return
        # 2. Make sure version is correct
        if IMAGE_VERSION is not None and version != curVersion:
            uri = self.request.uri.replace('v=%s' % version, 'v=%s' % curVersion)
            self.redirect(uri)
            return

        if not path:
            path = 'index.html'

        loader = tornado.template.Loader(HTML_DIR)
        section = path.split('.')[0]
        try:
            context = getattr(self, section)()
        except AttributeError:
            context = {}
        context['cloud_url'] = CLOUD_HTTP_ADDRESS
        context['bufferSize'] = get_jack_buffer_size()
        context['sampleRate'] = get_jack_sample_rate()
        self.write(loader.load(path).generate(**context))

    def get_version(self):
        if IMAGE_VERSION is not None:
            version = IMAGE_VERSION[1:] if IMAGE_VERSION[0] == "v" else IMAGE_VERSION
            if version:
                if "-" in version:
                    # Special build with label, separated by '-'
                    label = version.rsplit("-",1)[1]
                    # Get the first 3 digits (up to 3, might be less)
                    rversion = ".".join(version.split(".")[:3])
                    if label != "stable":
                        rversion += "-"+label
                else:
                    # Normal build (internal or official), show entire version
                    rversion = version
                return tornado.escape.url_escape(rversion)
        return str(int(time.time()))

    def index(self):
        context = {}
        user_id = {}

        try:
            with open(USER_ID_JSON_FILE, 'r') as fd:
                user_id = json.load(fd)
        except:
            pass

        with open(DEFAULT_ICON_TEMPLATE, 'r') as fd:
            default_icon_template = tornado.escape.squeeze(fd.read().replace("'", "\\'"))

        with open(DEFAULT_SETTINGS_TEMPLATE, 'r') as fd:
            default_settings_template = tornado.escape.squeeze(fd.read().replace("'", "\\'"))

        pbname = tornado.escape.xhtml_escape(SESSION.host.pedalboard_name)

        context = {
            'default_icon_template': default_icon_template,
            'default_settings_template': default_settings_template,
            'default_pedalboard': DEFAULT_PEDALBOARD,
            'cloud_url': CLOUD_HTTP_ADDRESS,
            'pedalboards_url': PEDALBOARDS_HTTP_ADDRESS,
            'hardware_profile': b64encode(json.dumps(SESSION.get_hardware()).encode("utf-8")),
            'version': self.get_argument('v'),
            'lv2_plugin_dir': LV2_PLUGIN_DIR,
            'bundlepath': SESSION.host.pedalboard_path,
            'title':  pbname,
            'size': json.dumps(SESSION.host.pedalboard_size),
            'fulltitle':  pbname or "Untitled",
            'titleblend': '' if SESSION.host.pedalboard_name else 'blend',
            'using_app': 'true' if APP else 'false',
            'using_mod': 'true' if DEVICE_KEY else 'false',
            'user_name': tornado.escape.xhtml_escape(user_id.get("name", "")),
            'user_email': tornado.escape.xhtml_escape(user_id.get("email", "")),
            'favorites': json.dumps(SESSION.favorites),
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
            pedalboard = {
                'height': 0,
                'width': 0,
                'title': "",
                'connections': [],
                'plugins': [],
                'hardware': {},
            }

        context['pedalboard'] = b64encode(json.dumps(pedalboard).encode("utf-8"))
        return context

class TemplateLoader(web.RequestHandler):
    def get(self, path):
        with open(os.path.join(HTML_DIR, 'include', path)) as fh:
            self.write(fh.read())
        self.finish()

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
        self.finish()

class Ping(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        start  = end = time.time()
        online = yield gen.Task(SESSION.web_ping)

        if online:
            end  = time.time()
            resp = {
                'ihm_online': online,
                'ihm_time'  : int((end - start) * 1000),
            }
        else:
            resp = {
                'ihm_online': False,
                'ihm_time'  : 0,
            }

        self.write(resp)

class Hello(RemoteRequestHandler):
    def get(self):
        resp = {
          'online' : len(SESSION.websockets) > 0,
          'version': IMAGE_VERSION,
        }
        self.write(resp)

class TrueBypass(JsonRequestHandler):
    def get(self, channelName, bypassed):
        ok = set_truebypass_value(channelName == "Right", bypassed == "true")
        self.write(ok)

class SetBufferSize(JsonRequestHandler):
    def post(self, size):
        size = int(size)

        # If running a real MOD, save this setting for next boot
        if IMAGE_VERSION is not None:
            if size == 256:
                with open(USING_256_FRAMES_FILE, 'w') as fh:
                    fh.write("# if this file exists, jack will use 256 frames instead of the default 128")
            elif os.path.exists(USING_256_FRAMES_FILE):
                os.remove(USING_256_FRAMES_FILE)

        newsize = set_jack_buffer_size(size)
        self.write({
            'ok'  : newsize == size,
            'size': newsize,
        })

class ResetXruns(JsonRequestHandler):
    def post(self):
        reset_xruns()
        self.write(True)

class SaveUserId(JsonRequestHandler):
    def post(self):
        name  = self.get_argument("name")
        email = self.get_argument("email")
        with open(USER_ID_JSON_FILE, 'w') as fh:
            json.dump({
                "name" : name,
                "email": email,
            }, fh)
        self.write(True)

class JackGetMidiDevices(JsonRequestHandler):
    def get(self):
        devsInUse, devList, names = SESSION.web_get_midi_device_list()
        self.write({
            "devsInUse": devsInUse,
            "devList"  : devList,
            "names"    : names,
        })

class JackSetMidiDevices(JsonRequestHandler):
    def post(self):
        devs = json.loads(self.request.body.decode("utf-8", errors="ignore"))
        SESSION.web_set_midi_devices(devs)
        self.write(True)

class FavoritesAdd(JsonRequestHandler):
    def post(self):
        uri = self.get_argument("uri")

        # safety check, no duplicates please
        if uri in SESSION.favorites:
            print("ERROR: URI '%s' already in favorites" % uri)
            self.write(False)
            return

        # add and save
        SESSION.favorites.append(uri)
        with open(FAVORITES_JSON_FILE, 'w') as fh:
            json.dump(SESSION.favorites, fh)

        # done
        self.write(True)

class FavoritesRemove(JsonRequestHandler):
    def post(self):
        uri = self.get_argument("uri")

        # safety check
        if uri not in SESSION.favorites:
            print("ERROR: URI '%s' not in favorites" % uri)
            self.write(False)
            return

        # remove and save
        SESSION.favorites.remove(uri)
        with open(FAVORITES_JSON_FILE, 'w') as fh:
            json.dump(SESSION.favorites, fh)

        # done
        self.write(True)

class AuthNonce(JsonRequestHandler):
    def post(self):
        if token is None:
            message = {}
        else:
            data    = json.loads(self.request.body.decode())
            message = token.create_token_message(data['nonce'])

        self.write(message)

class AuthToken(JsonRequestHandler):
    def post(self):
        access_token = token.decode_and_decrypt(self.request.body.decode())
        # don't ever save this token locally
        self.write({'access_token': access_token})

class RecordingStart(JsonRequestHandler):
    def get(self):
        SESSION.web_recording_start()
        self.write(True)

class RecordingStop(JsonRequestHandler):
    def get(self):
        SESSION.web_recording_stop()
        self.write(True)

class RecordingReset(JsonRequestHandler):
    def get(self):
        SESSION.web_recording_delete()
        self.write(True)

class RecordingPlay(JsonRequestHandler):
    waiting_request = None

    @web.asynchronous
    def get(self, action):
        if action == 'start':
            SESSION.web_playing_start(RecordingPlay.stop_callback)
            self.write(True)
            return

        if action == 'wait':
            if RecordingPlay.waiting_request is not None:
                RecordingPlay.stop_callback()
            RecordingPlay.waiting_request = self
            return

        if action == 'stop':
            SESSION.web_playing_stop()
            self.write(True)
            return

        raise web.HTTPError(404)

    @classmethod
    def stop_callback(kls):
        if kls.waiting_request is None:
            return
        kls.waiting_request.write(True)
        kls.waiting_request = None

class RecordingDownload(JsonRequestHandler):
    def get(self):
        recd = SESSION.web_recording_download()
        data = {
            'ok'   : bool(recd),
            'audio': b64encode(recd).decode("utf-8") if recd else ""
        }
        self.write(data)

class TokensDelete(JsonRequestHandler):
    def get(self):
        tokensConf = os.path.join(DATA_DIR, "tokens.conf")

        if os.path.exists(tokensConf):
            os.remove(tokensConf)

        self.write(True)

class TokensGet(JsonRequestHandler):
    def get(self):
        tokensConf = os.path.join(DATA_DIR, "tokens.conf")

        if os.path.exists(tokensConf):
            with open(tokensConf, 'r') as fd:
                data = json.load(fd)
                keys = data.keys()
                data['ok'] = bool("user_id"       in keys and
                                  "access_token"  in keys and
                                  "refresh_token" in keys)
                self.write(data)
                return

        self.write({ 'ok': False })

class TokensSave(JsonRequestHandler):
    @jsoncall
    def post(self):
        tokensConf = os.path.join(DATA_DIR, "tokens.conf")

        data = dict(self.request.body)
        data.pop("expires_in_days")

        with open(tokensConf, 'w') as fh:
            json.dump(data, fh)

        self.write(True)

settings = {'log_function': lambda handler: None} if not LOG else {}

application = web.Application(
        EffectInstaller.urls('effect/install') +
        [
            (r"/system/bluetooth/set", BluetoothSetPin),
            (r"/system/info", SystemInfo),

            (r"/update/download/", UpdateDownload),
            (r"/update/begin", UpdateBegin),

            (r"/resources/(.*)", EffectResource),

            # plugin management
            (r"/effect/add/*(/[A-Za-z0-9_/]+[^/])/?", EffectAdd),
            (r"/effect/remove/*(/[A-Za-z0-9_/]+[^/])/?", EffectRemove),
            (r"/effect/get", EffectGet),
            (r"/effect/bulk/?", EffectBulk),
            (r"/effect/list", EffectList),

            # plugin parameters
            (r"/effect/parameter/address/*(/[A-Za-z0-9_:/]+[^/])/?", EffectParameterAddress),

            # plugin presets
            (r"/effect/preset/load/*(/[A-Za-z0-9_/]+[^/])/?", EffectPresetLoad),
            (r"/effect/preset/save_new/*(/[A-Za-z0-9_/]+[^/])/?", EffectPresetSaveNew),
            (r"/effect/preset/save_replace/*(/[A-Za-z0-9_/]+[^/])/?", EffectPresetSaveReplace),
            (r"/effect/preset/delete/*(/[A-Za-z0-9_/]+[^/])/?", EffectPresetDelete),

            # plugin resources
            (r"/effect/image/(screenshot|thumbnail).png", EffectImage),
            (r"/effect/file/(.*)", EffectFile),

            # connections
            (r"/effect/connect/*(/[A-Za-z0-9_/]+[^/]),([A-Za-z0-9_/]+[^/])/?", EffectConnect),
            (r"/effect/disconnect/*(/[A-Za-z0-9_/]+[^/]),([A-Za-z0-9_/]+[^/])/?", EffectDisconnect),

            (r"/package/uninstall", PackageUninstall),

            # pedalboard stuff
            (r"/pedalboard/list", PedalboardList),
            (r"/pedalboard/save", PedalboardSave),
            (r"/pedalboard/pack_bundle/?", PedalboardPackBundle),
            (r"/pedalboard/load_bundle/", PedalboardLoadBundle),
            (r"/pedalboard/load_remote/*(/[A-Za-z0-9_/]+[^/])/?", PedalboardLoadRemote),
            (r"/pedalboard/load_web/", PedalboardLoadWeb),
            (r"/pedalboard/info/", PedalboardInfo),
            (r"/pedalboard/remove/", PedalboardRemove),
            (r"/pedalboard/image/(screenshot|thumbnail).png", PedalboardImage),
            (r"/pedalboard/image/generate", PedalboardImageGenerate),
            (r"/pedalboard/image/wait", PedalboardImageWait),

            # bank stuff
            (r"/banks/?", BankLoad),
            (r"/banks/save/?", BankSave),

            (r"/hardware", HardwareLoad),

            (r"/auth/nonce/?$", AuthNonce),
            (r"/auth/token/?$", AuthToken),

            (r"/recording/start", RecordingStart),
            (r"/recording/stop", RecordingStop),
            (r"/recording/play/(start|wait|stop)", RecordingPlay),
            (r"/recording/download", RecordingDownload),
            (r"/recording/reset", RecordingReset),

            (r"/tokens/delete", TokensDelete),
            (r"/tokens/get", TokensGet),
            (r"/tokens/save/?", TokensSave),

            (r"/reset/?", DashboardClean),

            (r"/sdk/install/?", SDKEffectInstaller),

            (r"/jack/get_midi_devices", JackGetMidiDevices),
            (r"/jack/set_midi_devices", JackSetMidiDevices),

            (r"/favorites/add", FavoritesAdd),
            (r"/favorites/remove", FavoritesRemove),

            (r"/ping/?", Ping),
            (r"/hello/?", Hello),

            (r"/truebypass/(Left|Right)/(true|false)", TrueBypass),
            (r"/set_buffersize/(128|256)", SetBufferSize),
            (r"/reset_xruns/", ResetXruns),

            (r"/save_user_id/", SaveUserId),

            (r"/(index.html)?$", TemplateHandler),
            (r"/([a-z]+\.html)$", TemplateHandler),
            (r"/load_template/([a-z_]+\.html)$", TemplateLoader),
            (r"/js/templates.js$", BulkTemplateLoader),

            (r"/websocket/?$", ServerWebSocket),

            (r"/(.*)", web.StaticFileHandler, {"path": HTML_DIR}),
        ],
        debug=LOG and False, **settings)

def signal_upgrade_check():
    with open("/root/check-upgrade-system", 'r') as fh:
        countRead = fh.read().strip()
        countNumb = int(countRead) if countRead else 0

    with open("/root/check-upgrade-system", 'w') as fh:
        fh.write("%i\n" % (countNumb+1))

    SESSION.hmi.send("restore")

def signal_recv(sig, frame=0):
    if sig == SIGUSR2:
        func = signal_upgrade_check if os.path.exists("/root/check-upgrade-system") else SESSION.signal_disconnect
        tornado.ioloop.IOLoop.instance().add_callback_from_signal(func)

def prepare(isModApp = False):
    check_environment()
    lv2_init()

    if os.path.exists(FAVORITES_JSON_FILE):
        with open(FAVORITES_JSON_FILE, 'r') as fd:
            gState.favorites = json.load(fd)

        if isinstance(gState.favorites, list):
            uris = get_plugin_list()
            for uri in gState.favorites:
                if uri not in uris:
                    gState.favorites.remove(uri)
        else:
            gState.favorites = []

    if False:
        print("Scanning plugins, this may take a little...")
        get_all_plugins()
        print("Done!")

    if not isModApp:
        signal(SIGUSR2, signal_recv)
        set_process_name("mod-ui")

    application.listen(DEVICE_WEBSERVER_PORT, address="0.0.0.0")
    if LOG:
        tornado.log.enable_pretty_logging()

    def checkhost():
        if SESSION.host.readsock is None or SESSION.host.writesock is None:
            print("Host failed to initialize, is the backend running?")
            SESSION.host.close_jack()
            sys.exit(1)

        elif not SESSION.host.connected:
            ioinstance.call_later(0.2, checkhost)

    ioinstance = tornado.ioloop.IOLoop.instance()
    ioinstance.add_callback(checkhost)

def start():
    tornado.ioloop.IOLoop.instance().start()

def stop():
    tornado.ioloop.IOLoop.instance().stop()

def run():
    prepare()
    start()

if __name__ == "__main__":
    run()
