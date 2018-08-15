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
import subprocess
import sys
import time
from base64 import b64decode, b64encode
from signal import signal, SIGUSR1, SIGUSR2
from tornado import gen, iostream, web, websocket
from tornado.escape import squeeze, url_escape, xhtml_escape
from tornado.ioloop import IOLoop
from tornado.template import Loader
from tornado.util import unicode_type
from uuid import uuid4

from mod.settings import (APP, LOG,
                          HTML_DIR, DOWNLOAD_TMP_DIR, DEVICE_KEY, DEVICE_WEBSERVER_PORT,
                          CLOUD_HTTP_ADDRESS, PLUGINS_HTTP_ADDRESS, PEDALBOARDS_HTTP_ADDRESS, CONTROLCHAIN_HTTP_ADDRESS,
                          LV2_PLUGIN_DIR, LV2_PEDALBOARDS_DIR, IMAGE_VERSION,
                          UPDATE_CC_FIRMWARE_FILE, UPDATE_MOD_OS_FILE, USING_256_FRAMES_FILE,
                          DEFAULT_ICON_TEMPLATE, DEFAULT_SETTINGS_TEMPLATE, DEFAULT_ICON_IMAGE,
                          DEFAULT_PEDALBOARD, DATA_DIR, FAVORITES_JSON_FILE, PREFERENCES_JSON_FILE, USER_ID_JSON_FILE,
                          DEV_HOST)

from mod import check_environment, jsoncall, safe_json_load, TextFileFlusher
from mod.bank import list_banks, save_banks, remove_pedalboard_from_banks
from mod.session import SESSION
from modtools.utils import (
    init as lv2_init, cleanup as lv2_cleanup, get_plugin_list, get_all_plugins, get_plugin_info, get_plugin_gui,
    get_plugin_gui_mini, get_all_pedalboards, get_broken_pedalboards, get_pedalboard_info, get_jack_buffer_size,
    set_jack_buffer_size, get_jack_sample_rate, set_truebypass_value, set_process_name, reset_xruns
)

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
    pluginsWereRemoved = False

    for bundle in os.listdir(DOWNLOAD_TMP_DIR):
        tmppath    = os.path.join(DOWNLOAD_TMP_DIR, bundle)
        bundlepath = os.path.join(LV2_PLUGIN_DIR, bundle)

        if os.path.exists(bundlepath):
            resp, data = yield gen.Task(SESSION.host.remove_bundle, bundlepath, True)

            # When removing bundles we can ignore the ones that are not loaded
            # It can happen if a previous install failed abruptly
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
            pluginsWereRemoved = True
            try:
                gState.favorites.remove(uri)
            except ValueError:
                pass

    if pluginsWereRemoved:
        # Re-save favorites list
        with open(FAVORITES_JSON_FILE, 'w') as fh:
            json.dump(gState.favorites, fh)

        # Re-save banks
        broken = get_broken_pedalboards()
        if len(broken) > 0:
            list_banks(broken)

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

    os.sync()
    callback(resp)

def run_command(args, cwd, callback):
    ioloop = IOLoop.instance()
    proc   = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def end_fileno(fileno, event):
        ret = proc.poll()
        if ret is None:
            return
        ioloop.remove_handler(fileno)
        callback((ret,) + proc.communicate())

    ioloop.add_handler(proc.stdout.fileno(), end_fileno, 16)

def install_package(filename, callback):
    if not os.path.exists(filename):
        callback({
            'ok'       : False,
            'error'    : "Failed to find archive",
            'installed': [],
            'removed'  : [],
        })
        return

    def end_untar_pkgs(resp):
        os.remove(filename)
        install_bundles_in_tmp_dir(callback)

    run_command(['tar','zxf', filename], DOWNLOAD_TMP_DIR, end_untar_pkgs)

@gen.coroutine
def start_restore():
    os.sync()
    yield gen.Task(SESSION.hmi.send, "restore", datatype='boolean')

class TimelessRequestHandler(web.RequestHandler):
    def compute_etag(self):
        return None

    def set_default_headers(self):
        self._headers.pop("Date")

    def should_return_304(self):
        return False

class TimelessStaticFileHandler(web.StaticFileHandler):
    def get_cache_time(self, path, modified, mime_type):
        return 0

    def get_modified_time(self):
        return None

    def set_default_headers(self):
        self._headers.pop("Date")

    def set_extra_headers(self, path):
        self.set_header("Cache-Control", "public, max-age=31536000")

    def should_return_304(self):
        return self.check_etag_header()

class JsonRequestHandler(TimelessRequestHandler):
    def write(self, data):
        # FIXME: something is sending strings out, need to investigate what later..
        # it's likely something using write(json.dumps(...))
        # we want to prevent that as it causes issues under Mac OS

        if isinstance(data, (bytes, unicode_type, dict)):
            TimelessRequestHandler.write(self, data)
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

        TimelessRequestHandler.write(self, data)
        self.finish()

class RemoteRequestHandler(JsonRequestHandler):
    def set_default_headers(self):
        if 'Origin' not in self.request.headers.keys():
            return
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
        ]

    @web.asynchronous
    @gen.engine
    def post(self, sessionid=None, chunk_number=None):
        # self.result can be set by subclass in process_file,
        # so that answer will be returned to browser
        self.result = None
        basename = str(uuid4())
        if not os.path.exists(self.destination_dir):
            os.mkdir(self.destination_dir)
        with open(os.path.join(self.destination_dir, basename), 'wb') as fh:
            fh.write(self.request.body)
        yield gen.Task(self.process_file, basename)
        self.write({
            'ok'    : True,
            'result': self.result
        })

    def process_file(self, basename, callback=lambda:None):
        """to be overriden"""

@web.stream_request_body
class MultiPartFileReceiver(JsonRequestHandler):
    @property
    def destination_dir(self):
        raise NotImplemented

    @classmethod
    def urls(cls, path):
        return [
            (r"/%s/$" % path, cls),
        ]

    def prepare(self):
        self.basename = "/tmp/" + str(uuid4())
        if not os.path.exists(self.destination_dir):
            os.mkdir(self.destination_dir)
        self.filehandle = open(os.path.join(self.destination_dir, self.basename), 'wb')
        self.filehandle.write(b'')

        if 'expected_size' in self.request.arguments:
            self.request.connection.set_max_body_size(int(self.get_argument('expected_size')))
        else:
            self.request.connection.set_max_body_size(200*1024*1024)

        if 'body_timeout' in self.request.arguments:
            self.request.connection.set_body_timeout(float(self.get_argument('body_timeout')))

    def data_received(self, data):
        self.filehandle.write(data)

    @web.asynchronous
    @gen.engine
    def post(self):
        # self.result can be set by subclass in process_file,
        # so that answer will be returned to browser
        self.result = None
        self.filehandle.flush()
        self.filehandle.close()
        yield gen.Task(self.process_file, self.basename)
        self.write({
            'ok'    : True,
            'result': self.result
        })

    def process_file(self, basename, callback=lambda:None):
        """to be overriden"""

class SystemInfo(JsonRequestHandler):
    def get(self):
        hwdesc = safe_json_load("/etc/mod-hardware-descriptor.json", dict)
        uname  = os.uname()

        if os.path.exists("/etc/mod-release/system"):
            with open("/etc/mod-release/system") as fh:
                sysdate = fh.readline().replace("generated=","").split(" at ",1)[0].strip()
        else:
            sysdate = "Unknown"

        info = {
            "hwname": hwdesc.get('name',"Unknown"),
            "sysdate": sysdate,
            "python": {
                "version" : sys.version
            },
            "uname": {
                "machine": uname.machine,
                "release": uname.release,
                "sysname": uname.sysname,
                "version": uname.version
            }
        }

        self.write(info)

class SystemPreferences(JsonRequestHandler):
    OPTION_NULL          = 0
    OPTION_FILE_EXISTS   = 1
    OPTION_FILE_CONTENTS = 2

    def __init__(self, application, request, **kwargs):
        JsonRequestHandler.__init__(self, application, request, **kwargs)

        self.prefs = []

        self.make_pref("bluetooth_name", self.OPTION_FILE_CONTENTS, "/data/bluetooth/name", str)
        self.make_pref("jack_mono_copy",  self.OPTION_FILE_EXISTS, "/data/jack-mono-copy")
        self.make_pref("jack_sync_mode",  self.OPTION_FILE_EXISTS, "/data/jack-sync-mode")
        self.make_pref("jack_256_frames",  self.OPTION_FILE_EXISTS, "/data/using-256-frames")

        # Optional services
        self.make_pref("service_mixserver",  self.OPTION_FILE_EXISTS, "/data/enable-mixserver")
        self.make_pref("service_mod_sdk",    self.OPTION_FILE_EXISTS, "/data/enable-mod-sdk")
        self.make_pref("service_netmanager", self.OPTION_FILE_EXISTS, "/data/enable-netmanager")

    def make_pref(self, label, otype, data, valtype=None, valdef=None):
        self.prefs.append({
            "label": label,
            "type" : otype,
            "data" : data,
            "valtype": valtype,
            "valdef" : valdef,
        })

    def get(self):
        ret = {}

        for pref in self.prefs:
            if pref['type'] == self.OPTION_FILE_EXISTS:
                val = os.path.exists(pref['data'])

            elif pref['type'] == self.OPTION_FILE_CONTENTS:
                if os.path.exists(pref['data']):
                    with open(pref['data'], 'r') as fh:
                        val = fh.read().strip()
                    try:
                        val = pref['valtype'](val)
                    except:
                        val = pref['valdef']
                else:
                    val = pref['valdef']
            else:
                pass

            ret[pref['label']] = val

        self.write(ret)

class SystemExeChange(JsonRequestHandler):
    @gen.coroutine
    def post(self):
        etype = self.get_argument('type')

        if etype == "command":
            cmd = self.get_argument('cmd').split(" ",1)
            if len(cmd) == 1:
                cmd = cmd[0]
            else:
                cmd, cdata = cmd

            if cmd == "reboot":
                yield gen.Task(run_command, ["hmi-reset"], None)
                IOLoop.instance().add_callback(self.reboot)

            elif cmd == "restore":
                IOLoop.instance().add_callback(start_restore)

            elif cmd == "backup-export":
                args  = ["mod-backup", "backup"]
                cdata = cdata.split(",")
                if cdata[0] == "1":
                    args.append("-d")
                if cdata[1] == "1":
                    args.append("-p")
                resp  = yield gen.Task(run_command, args, None)
                error = resp[2].decode("utf-8", errors="ignore").strip()
                if len(error) > 1:
                    error = error[0].title()+error[1:]+"."
                self.write({
                    'ok'   : resp[0] == 0,
                    'error': error,
                })
                return

            elif cmd == "backup-import":
                args  = ["mod-backup", "restore"]
                cdata = cdata.split(",")
                if cdata[0] == "1":
                    args.append("-d")
                if cdata[1] == "1":
                    args.append("-p")
                resp = yield gen.Task(run_command, args, None)
                error = resp[2].decode("utf-8", errors="ignore").strip()
                if len(error) > 1:
                    error = error[0].title()+error[1:]+"."
                self.write({
                    'ok'   : resp[0] == 0,
                    'error': error,
                })
                if resp[0] == 0:
                    IOLoop.instance().add_callback(self.restart_services)
                return

            else:
                self.write(False)
                return

        elif etype == "filecreate":
            path   = self.get_argument('path')
            create = bool(int(self.get_argument('create')))

            if path not in ("jack-mono-copy", "jack-sync-mode", "using-256-frames"):
                self.write(False)
                return

            filename = "/data/" + path

            if create:
                foldername = os.path.dirname(filename)
                if not os.path.exists(foldername):
                    os.makedirs(foldername)
                with open(filename, 'wb') as fh:
                    fh.write(b"")
            elif os.path.exists(filename):
                os.remove(filename)

        elif etype == "filewrite":
            path    = self.get_argument('path')
            content = self.get_argument('content').strip()

            if path not in ("bluetooth/name",):
                self.write(False)
                return

            filename = "/data/" + path

            if content:
                foldername = os.path.dirname(filename)
                if not os.path.exists(foldername):
                    os.makedirs(foldername)
                with open(filename, 'w') as fh:
                    fh.write(content)
            elif os.path.exists(filename):
                os.remove(filename)

        elif etype == "service":
            name   = self.get_argument('name')
            enable = bool(int(self.get_argument('enable')))

            if name not in ("mixserver", "netmanager", "mod-sdk"):
                self.write(False)
                return

            checkname   = "/data/enable-" + name
            servicename = name

            if servicename == "netmanager":
                servicename = "jack-netmanager"

            if enable:
                with open(checkname, 'wb') as fh:
                    fh.write(b"")
                yield gen.Task(run_command, ["systemctl", "start", servicename], None)

            else:
                if os.path.exists(checkname):
                    os.remove(checkname)
                yield gen.Task(run_command, ["systemctl", "stop", servicename], None)

        os.sync()
        self.write(True)

    @gen.coroutine
    def reboot(self):
        os.sync()
        yield gen.Task(run_command, ["reboot"], None)

    @gen.coroutine
    def restart_services(self):
        yield gen.Task(run_command, ["systemctl", "restart", "jack2"], None)
        lv2_cleanup()
        lv2_init()

class UpdateDownload(MultiPartFileReceiver):
    destination_dir = "/tmp/os-update"

    def process_file(self, basename, callback=lambda:None):
        self.sfr_callback = callback

        # TODO: verify checksum?
        src = os.path.join(self.destination_dir, basename)
        dst = UPDATE_MOD_OS_FILE
        run_command(['mv', src, dst], None, self.move_file_finished)

    def move_file_finished(self, resp):
        os.sync()
        self.result = True
        self.sfr_callback()

class UpdateBegin(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self):
        if not os.path.exists(UPDATE_MOD_OS_FILE):
            self.write(False)
            return

        IOLoop.instance().add_callback(start_restore)
        self.write(True)

class ControlChainDownload(SimpleFileReceiver):
    destination_dir = "/tmp/cc-update"

    def process_file(self, basename, callback=lambda:None):
        self.sfr_callback = callback

        # TODO: verify checksum?
        src = os.path.join(self.destination_dir, basename)
        dst = UPDATE_CC_FIRMWARE_FILE
        run_command(['mv', src, dst], None, self.move_file_finished)

    def move_file_finished(self, resp):
        self.result = True
        self.sfr_callback()

class ControlChainCancel(JsonRequestHandler):
    def post(self):
        if not os.path.exists(UPDATE_CC_FIRMWARE_FILE):
            self.write(False)
            return

        os.remove(UPDATE_CC_FIRMWARE_FILE)
        self.write(True)

class EffectInstaller(SimpleFileReceiver):
    destination_dir = DOWNLOAD_TMP_DIR

    @web.asynchronous
    @gen.engine
    def process_file(self, basename, callback=lambda:None):
        def on_finish(resp):
            self.result = resp
            callback()
        install_package(os.path.join(DOWNLOAD_TMP_DIR, basename), on_finish)

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
        upload   = self.request.files['package'][0]
        filename = os.path.join(DOWNLOAD_TMP_DIR, upload['filename'])

        with open(filename, 'wb') as fh:
            fh.write(b64decode(upload['body']))

        resp = yield gen.Task(install_package, filename)

        if resp['ok']:
            SESSION.msg_callback("rescan " + b64encode(json.dumps(resp).encode("utf-8")).decode("utf-8"))

        self.write(resp)

class SDKEffectUpdater(JsonRequestHandler):
    def set_default_headers(self):
        if 'Origin' not in self.request.headers.keys():
            return
        origin = self.request.headers['Origin']
        match  = re.match(r'^(\w+)://([^/]*)/?', origin)
        if match is None:
            return
        protocol, domain = match.groups()
        if protocol != "http" or not domain.endswith(":9000"):
            return
        self.set_header("Access-Control-Allow-Origin", origin)

    def post(self):
        bundle = self.get_argument("bundle")
        uri    = self.get_argument("uri")

        ok, error = SESSION.host.refresh_bundle(bundle, uri)
        if not ok:
            self.write({
                'ok'   : False,
                'error': error
            })
            return

        data = {
            'ok'       : True,
            'removed'  : [uri],
            'installed': [uri],
        }
        SESSION.msg_callback("rescan " + b64encode(json.dumps(data).encode("utf-8")).decode("utf-8"))

        self.write({ 'ok': True })

class EffectResource(TimelessStaticFileHandler):

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

class EffectImage(TimelessStaticFileHandler):
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

        return TimelessStaticFileHandler.initialize(self, root)

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
                TimelessStaticFileHandler.initialize(self, os.path.dirname(path))

        return path

class EffectFile(TimelessStaticFileHandler):
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

        return TimelessStaticFileHandler.initialize(self, root)

    def parse_url_path(self, prop):
        try:
            path = self.modgui[prop]
        except:
            raise web.HTTPError(404)

        if prop in ("iconTemplate", "settingsTemplate", "stylesheet", "javascript"):
            self.custom_type = "text/plain; charset=UTF-8"

        return path

    def get_content_type(self):
        if self.custom_type is not None:
            return self.custom_type
        return TimelessStaticFileHandler.get_content_type(self)

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

        ok = yield gen.Task(SESSION.web_parameter_address, port, uri, label, minimum, maximum, value, steps)
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

        elif cmd == "link_enable":
            on = bool(int(data[1]))
            SESSION.host.set_link_enabled(on, True)

        elif cmd == "transport-bpb":
            bpb = float(data[1])
            SESSION.host.set_transport_bpb(bpb, True)

        elif cmd == "transport-bpm":
            bpm = float(data[1])
            SESSION.host.set_transport_bpm(bpm, True)

        elif cmd == "transport-rolling":
            rolling = bool(int(data[1]))
            SESSION.host.set_transport_rolling(rolling, True)

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

        if len(removed) > 0:
            # Re-save banks, as pedalboards might contain the removed plugins
            broken = get_broken_pedalboards()
            if len(broken) > 0:
                list_banks(broken)

        self.write(resp)

class PedalboardList(JsonRequestHandler):
    def get(self):
        self.write(get_all_pedalboards())

class PedalboardCurrent(JsonRequestHandler):
    def get(self):
        self.write(SESSION.host.pedalboard_path)
        #self.write(get_all_pedalboards())

class PedalboardSave(JsonRequestHandler):
    def post(self):
        title = self.get_argument('title')
        asNew = bool(int(self.get_argument('asNew')))

        bundlepath = SESSION.web_save_pedalboard(title, asNew)

        self.write({
            'ok': bundlepath is not None,
            'bundlepath': bundlepath
        })

class PedalboardPackBundle(TimelessRequestHandler):
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
        ioloop = IOLoop.instance()

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
    def process_file(self, basename, callback=lambda:None):
        filename = os.path.join(self.destination_dir, basename)

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

class PedalboardImage(TimelessStaticFileHandler):
    def initialize(self):
        root = self.get_argument('bundlepath')
        return TimelessStaticFileHandler.initialize(self, root)

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

class PedalboardImageCheck(JsonRequestHandler):
    def get(self):
        bundlepath = os.path.abspath(self.get_argument('bundlepath'))
        ret, ctime = SESSION.screenshot_generator.check_screenshot(bundlepath)
        self.write({
            'status': ret,
            'ctime' : "%.1f" % ctime,
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

class PedalboardPresetEnable(JsonRequestHandler):
    def post(self):
        SESSION.host.pedalpreset_init()
        self.write(True)

class PedalboardPresetDisable(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self):
        yield gen.Task(SESSION.host.pedalpreset_disable)
        self.write(True)

class PedalboardPresetSave(JsonRequestHandler):
    def post(self):
        ok = SESSION.host.pedalpreset_save()
        self.write(ok)

class PedalboardPresetSaveAs(JsonRequestHandler):
    def get(self):
        title = self.get_argument('title')
        idx   = SESSION.host.pedalpreset_saveas(title)

        self.write({
            'ok': idx is not None,
            'id': idx
        })

class PedalboardPresetRename(JsonRequestHandler):
    def get(self):
        idx   = int(self.get_argument('id'))
        title = self.get_argument('title')
        ok    = SESSION.host.pedalpreset_rename(idx, title)
        self.write(ok)

class PedalboardPresetRemove(JsonRequestHandler):
    def get(self):
        idx = int(self.get_argument('id'))
        ok  = SESSION.host.pedalpreset_remove(idx)
        self.write(ok)

class PedalboardPresetList(JsonRequestHandler):
    def get(self):
        presets = SESSION.host.pedalboard_presets
        presets = dict((i, presets[i]['name']) for i in range(len(presets)) if presets[i] is not None)
        self.write(presets)

class PedalboardPresetName(JsonRequestHandler):
    def get(self):
        idx  = int(self.get_argument('id'))
        name = SESSION.host.pedalpreset_name(idx) or ""
        self.write({
            'ok'  : bool(name),
            'name': name
        })

class PedalboardPresetLoad(JsonRequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        idx = int(self.get_argument('id'))
        # FIXME: callback invalid?
        ok  = yield gen.Task(SESSION.host.pedalpreset_load, idx)
        self.write(ok)

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
            bank_pedalboards = []
            for pb in bank['pedalboards']:
                bundle = os.path.abspath(pb['bundle'])
                try:
                    pbdata = pedalboards_data[bundle]
                except KeyError:
                    continue
                bank_pedalboards.append(pbdata)
            bank['pedalboards'] = bank_pedalboards

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

class TemplateHandler(TimelessRequestHandler):
    @gen.coroutine
    def get(self, path):
        # Caching strategy.
        # 1. If we don't have a version parameter, redirect
        curVersion = self.get_version()
        try:
            version = url_escape(self.get_argument('v'))
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
        elif path == 'sdk':
            self.redirect(self.request.full_url().replace("/sdk", ":9000"), True)
            return
        elif path == 'settings':
            uri = '/settings.html?v=%s' % curVersion
            self.redirect(uri, True)
            return
        elif not os.path.exists(os.path.join(HTML_DIR, path)):
            uri = '/?v=%s' % curVersion
            self.redirect(uri)
            return

        loader = Loader(HTML_DIR)
        section = path.split('.',1)[0]

        if section == 'index':
            yield gen.Task(SESSION.wait_for_hardware_if_needed)

        try:
            context = getattr(self, section)()
        except AttributeError:
            context = {}
        self.write(loader.load(path).generate(**context))

    def get_version(self):
        if IMAGE_VERSION is not None and len(IMAGE_VERSION) > 1:
            # strip initial 'v' from version if present
            version = IMAGE_VERSION[1:] if IMAGE_VERSION[0] == "v" else IMAGE_VERSION
            return url_escape(version)
        return str(int(time.time()))

    def index(self):
        user_id = safe_json_load(USER_ID_JSON_FILE, dict)

        with open(DEFAULT_ICON_TEMPLATE, 'r') as fh:
            default_icon_template = squeeze(fh.read().replace("'", "\\'"))

        with open(DEFAULT_SETTINGS_TEMPLATE, 'r') as fh:
            default_settings_template = squeeze(fh.read().replace("'", "\\'"))

        pbname = SESSION.host.pedalboard_name
        prname = SESSION.host.pedalpreset_name()

        fullpbname = pbname or "Untitled"
        if prname:
            fullpbname += " - " + prname

        context = {
            'default_icon_template': default_icon_template,
            'default_settings_template': default_settings_template,
            'default_pedalboard': DEFAULT_PEDALBOARD,
            'cloud_url': CLOUD_HTTP_ADDRESS,
            'plugins_url': PLUGINS_HTTP_ADDRESS,
            'pedalboards_url': PEDALBOARDS_HTTP_ADDRESS,
            'controlchain_url': CONTROLCHAIN_HTTP_ADDRESS,
            'hardware_profile': b64encode(json.dumps(SESSION.get_hardware_actuators()).encode("utf-8")),
            'version': self.get_argument('v'),
            'lv2_plugin_dir': LV2_PLUGIN_DIR,
            'bundlepath': SESSION.host.pedalboard_path,
            'title':  squeeze(pbname.replace("'", "\\'")),
            'size': json.dumps(SESSION.host.pedalboard_size),
            'fulltitle':  xhtml_escape(fullpbname),
            'titleblend': '' if SESSION.host.pedalboard_name else 'blend',
            'using_app': 'true' if APP else 'false',
            'using_mod': 'true' if DEVICE_KEY or DEV_HOST else 'false',
            'user_name': squeeze(user_id.get("name", "").replace("'", "\\'")),
            'user_email': squeeze(user_id.get("email", "").replace("'", "\\'")),
            'favorites': json.dumps(gState.favorites),
            'preferences': json.dumps(SESSION.prefs.prefs),
            'bufferSize': get_jack_buffer_size(),
            'sampleRate': get_jack_sample_rate(),
        }
        return context

    def pedalboard(self):
        bundlepath = self.get_argument('bundlepath')

        with open(DEFAULT_ICON_TEMPLATE, 'r') as fh:
            default_icon_template = squeeze(fh.read().replace("'", "\\'"))

        with open(DEFAULT_SETTINGS_TEMPLATE, 'r') as fh:
            default_settings_template = squeeze(fh.read().replace("'", "\\'"))

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

        context = {
            'default_icon_template': default_icon_template,
            'default_settings_template': default_settings_template,
            'pedalboard': b64encode(json.dumps(pedalboard).encode("utf-8"))
        }

        return context

    def settings(self):
        prefs = safe_json_load(PREFERENCES_JSON_FILE, dict)

        context = {
            'cloud_url': CLOUD_HTTP_ADDRESS,
            'controlchain_url': CONTROLCHAIN_HTTP_ADDRESS,
            'version': self.get_argument('v'),
            'preferences': json.dumps(prefs),
            'bufferSize': get_jack_buffer_size(),
            'sampleRate': get_jack_sample_rate(),
        }
        return context

class TemplateLoader(TimelessRequestHandler):
    def get(self, path):
        self.set_header("Content-Type", "text/plain; charset=UTF-8")
        with open(os.path.join(HTML_DIR, 'include', path), 'r') as fh:
            self.write(fh.read())
        self.finish()

class BulkTemplateLoader(TimelessRequestHandler):
    def get(self):
        self.set_header("Content-Type", "text/plain; charset=UTF-8")
        basedir = os.path.join(HTML_DIR, 'include')
        for template in os.listdir(basedir):
            if not re.match('^[a-z_]+\.html$', template):
                continue
            with open(os.path.join(basedir, template), 'r') as fh:
                contents = fh.read()
            self.write("TEMPLATES['%s'] = '%s';\n\n"
                       % (template[:-5],
                          squeeze(contents.replace("'", "\\'"))
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
                'ihm_time'  : int((end - start) * 1000) or 1,
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

            os.sync()

        newsize = set_jack_buffer_size(size)
        self.write({
            'ok'  : newsize == size,
            'size': newsize,
        })

class ResetXruns(JsonRequestHandler):
    def post(self):
        reset_xruns()
        self.write(True)

class SaveSingleConfigValue(JsonRequestHandler):
    def post(self):
        key   = self.get_argument("key")
        value = self.get_argument("value")

        SESSION.prefs.setAndSave(key, value)
        self.write(True)

class SaveUserId(JsonRequestHandler):
    def post(self):
        name  = self.get_argument("name")
        email = self.get_argument("email")
        with TextFileFlusher(USER_ID_JSON_FILE) as fh:
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
        if uri in gState.favorites:
            print("ERROR: URI '%s' already in favorites" % uri)
            self.write(False)
            return

        # add and save
        gState.favorites.append(uri)
        with TextFileFlusher(FAVORITES_JSON_FILE) as fh:
            json.dump(gState.favorites, fh)

        # done
        self.write(True)

class FavoritesRemove(JsonRequestHandler):
    def post(self):
        uri = self.get_argument("uri")

        # safety check
        if uri not in gState.favorites:
            print("ERROR: URI '%s' not in favorites" % uri)
            self.write(False)
            return

        # remove and save
        gState.favorites.remove(uri)
        with TextFileFlusher(FAVORITES_JSON_FILE) as fh:
            json.dump(gState.favorites, fh)

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
            os.sync()

        self.write(True)

class TokensGet(JsonRequestHandler):
    def get(self):
        tokensConf = os.path.join(DATA_DIR, "tokens.conf")

        if not os.path.exists(tokensConf):
            self.write({ 'ok': False })
            return

        data = safe_json_load(tokensConf, dict)
        keys = data.keys()

        data['ok'] = bool("user_id"       in keys and
                          "access_token"  in keys and
                          "refresh_token" in keys)
        self.write(data)

class TokensSave(JsonRequestHandler):
    @jsoncall
    def post(self):
        tokensConf = os.path.join(DATA_DIR, "tokens.conf")

        data = dict(self.request.body)
        data.pop("expires_in_days")

        with TextFileFlusher(tokensConf) as fh:
            json.dump(data, fh)

        self.write(True)

settings = {'log_function': lambda handler: None} if not LOG else {}

application = web.Application(
        EffectInstaller.urls('effect/install') +
        [
            (r"/system/info", SystemInfo),
            (r"/system/prefs", SystemPreferences),
            (r"/system/exechange", SystemExeChange),

            (r"/update/download/", UpdateDownload),
            (r"/update/begin", UpdateBegin),

            (r"/controlchain/download/", ControlChainDownload),
            (r"/controlchain/cancel/", ControlChainCancel),

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
            (r"/pedalboard/current", PedalboardCurrent),
            (r"/pedalboard/save", PedalboardSave),
            (r"/pedalboard/pack_bundle/?", PedalboardPackBundle),
            (r"/pedalboard/load_bundle/", PedalboardLoadBundle),
            (r"/pedalboard/load_remote/*(/[A-Za-z0-9_/]+[^/])/?", PedalboardLoadRemote),
            (r"/pedalboard/load_web/", PedalboardLoadWeb),
            (r"/pedalboard/info/", PedalboardInfo),
            (r"/pedalboard/remove/", PedalboardRemove),
            (r"/pedalboard/image/(screenshot|thumbnail).png", PedalboardImage),
            (r"/pedalboard/image/generate", PedalboardImageGenerate),
            (r"/pedalboard/image/check", PedalboardImageCheck),
            (r"/pedalboard/image/wait", PedalboardImageWait),

            # pedalboard stuff
            (r"/pedalpreset/enable", PedalboardPresetEnable),
            (r"/pedalpreset/disable", PedalboardPresetDisable),
            (r"/pedalpreset/save", PedalboardPresetSave),
            (r"/pedalpreset/saveas", PedalboardPresetSaveAs),
            (r"/pedalpreset/rename", PedalboardPresetRename),
            (r"/pedalpreset/remove", PedalboardPresetRemove),
            (r"/pedalpreset/list", PedalboardPresetList),
            (r"/pedalpreset/name", PedalboardPresetName),
            (r"/pedalpreset/load", PedalboardPresetLoad),

            # bank stuff
            (r"/banks/?", BankLoad),
            (r"/banks/save/?", BankSave),

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
            (r"/sdk/update", SDKEffectUpdater),

            (r"/jack/get_midi_devices", JackGetMidiDevices),
            (r"/jack/set_midi_devices", JackSetMidiDevices),

            (r"/favorites/add", FavoritesAdd),
            (r"/favorites/remove", FavoritesRemove),

            (r"/config/set", SaveSingleConfigValue),

            (r"/ping/?", Ping),
            (r"/hello/?", Hello),

            (r"/truebypass/(Left|Right)/(true|false)", TrueBypass),
            (r"/set_buffersize/(128|256)", SetBufferSize),
            (r"/reset_xruns/", ResetXruns),

            (r"/save_user_id/", SaveUserId),

            (r"/(index.html)?$", TemplateHandler),
            (r"/([a-z]+\.html)$", TemplateHandler),
            (r"/(sdk|settings)$", TemplateHandler),
            (r"/load_template/([a-z_]+\.html)$", TemplateLoader),
            (r"/js/templates.js$", BulkTemplateLoader),

            (r"/websocket/?$", ServerWebSocket),

            (r"/(.*)", TimelessStaticFileHandler, {"path": HTML_DIR}),
        ],
        debug=LOG and False, **settings)

def signal_device_firmware_updated():
    os.remove(UPDATE_CC_FIRMWARE_FILE)
    SESSION.signal_device_updated()

def signal_upgrade_check():
    with open("/root/check-upgrade-system", 'r') as fh:
        countRead = fh.read().strip()
        countNumb = int(countRead) if countRead else 0

    with TextFileFlusher("/root/check-upgrade-system") as fh:
        fh.write("%i\n" % (countNumb+1))

    SESSION.hmi.send("restore")

def signal_recv(sig, frame=0):
    if sig == SIGUSR1:
        if os.path.exists(UPDATE_CC_FIRMWARE_FILE):
            func = signal_device_firmware_updated
        else:
            func = SESSION.signal_save
    elif sig == SIGUSR2:
        if os.path.exists("/root/check-upgrade-system") and \
           os.path.exists("/etc/systemd/system/upgrade-system-check.service"):
            func = signal_upgrade_check
        else:
            func = SESSION.signal_disconnect
    else:
        return

    IOLoop.instance().add_callback_from_signal(func)

def prepare(isModApp = False):
    check_environment()
    lv2_init()

    gState.favorites = safe_json_load(FAVORITES_JSON_FILE, list)

    if len(gState.favorites) > 0:
        uris = get_plugin_list()
        for uri in gState.favorites:
            if uri not in uris:
                gState.favorites.remove(uri)

    if False:
        print("Scanning plugins, this may take a little...")
        get_all_plugins()
        print("Done!")

    if not isModApp:
        signal(SIGUSR1, signal_recv)
        signal(SIGUSR2, signal_recv)
        set_process_name("mod-ui")

    application.listen(DEVICE_WEBSERVER_PORT, address="0.0.0.0")
    if LOG:
        from tornado.log import enable_pretty_logging
        enable_pretty_logging()

    def checkhost():
        if SESSION.host.readsock is None or SESSION.host.writesock is None:
            print("Host failed to initialize, is the backend running?")
            SESSION.host.close_jack()
            sys.exit(1)

        elif not SESSION.host.connected:
            ioinstance.call_later(0.2, checkhost)

    ioinstance = IOLoop.instance()
    ioinstance.add_callback(checkhost)

def start():
    IOLoop.instance().start()

def stop():
    IOLoop.instance().stop()

def run():
    prepare()
    start()

if __name__ == "__main__":
    run()
