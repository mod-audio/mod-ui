# -*- coding: utf-8 -*-

# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@portalmod.com>
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


import os, re, shutil, sys, pystache
import json, socket
import tornado.ioloop
import tornado.options
import tornado.escape
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

from mod.settings import (HTML_DIR, CLOUD_PUB, PLUGIN_LIBRARY_DIR,
                          DOWNLOAD_TMP_DIR, DEVICE_WEBSERVER_PORT,
                          PEDALBOARD_DIR, CLOUD_HTTP_ADDRESS, BANKS_JSON_FILE,
                          DEVICE_SERIAL, DEVICE_KEY, LOCAL_REPOSITORY_DIR,
                          PLUGIN_INSTALLATION_TMP_DIR, DEFAULT_ICON_TEMPLATE,
                          DEFAULT_SETTINGS_TEMPLATE, DEFAULT_ICON_IMAGE,
                          MAX_SCREENSHOT_WIDTH, MAX_SCREENSHOT_HEIGHT,
                          MAX_THUMB_WIDTH, MAX_THUMB_HEIGHT,
                          PACKAGE_SERVER_ADDRESS, DEFAULT_PACKAGE_SERVER_PORT,
                          PACKAGE_REPOSITORY, LOG, DEMO_DATA_DIR, DATA_DIR,
                          AVATAR_URL, DEV_ENVIRONMENT,
                          JS_CUSTOM_CHANNEL, AUTO_CLOUD_BACKUP,
                          )


from mod import indexing, jsoncall, json_handler
from mod.communication import fileserver, crypto
from mod.session import SESSION
from mod.effect import install_bundle, uninstall_bundle
from mod.pedalboard import Pedalboard, remove_pedalboard
from mod.bank import save_banks
from mod.hardware import get_hardware
from mod.lv2 import get_pedalboard_info
from mod.screenshot import ScreenshotGenerator, generate_screenshot, resize_image
from mod.system import (sync_pacman_db, get_pacman_upgrade_list,
                                pacman_upgrade, set_bluetooth_pin)
from mod import register
from mod import check_environment

SCREENSHOT_GENERATOR = ScreenshotGenerator()

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
        name = str(uuid.uuid4())
        fh = open(os.path.join(self.destination_dir, name), 'wb')
        fh.write(self.request.body)
        fh.close()
        data = dict(filename=name)
        yield gen.Task(self.process_file, data)
        info = {'ok': True}
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

class EffectInstaller(SimpleFileReceiver):
    remote_public_key = CLOUD_PUB
    destination_dir = PLUGIN_INSTALLATION_TMP_DIR

    def process_file(self, data, callback=lambda:None):
        def on_finish(result):
            self.result = result
            callback()
        install_bundle(data['filename'], on_finish)

class EffectSetLocalVariable(web.RequestHandler):
    def post(self, var):
        url = self.get_argument('url')
        value = self.get_argument(var)
        index = indexing.EffectIndex()
        objid = next(index.find(url=url))['id']
        index.save_local_variable(objid, var, value)

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

# Abstract class
class Searcher(tornado.web.RequestHandler):
    @classmethod
    def urls(cls, path):
        return [
            (r"/%s/(autocomplete)/?" % path, cls),
            (r"/%s/(search)/?" % path, cls),
            (r"/%s/(get)/([a-z0-9]+)?" % path, cls),
            (r"/%s/(get_by)/?" % path, cls),
            (r"/%s/(list)/?" % path, cls),
            ]

    @property
    def index(self):
        raise NotImplemented

    def get_object(self, objid):
        path = os.path.join(self.index.data_source, objid)
        md_path = path + '.metadata'
        obj = json.loads(open(path).read())
        if os.path.exists(md_path):
            obj.update(json.loads(open(md_path).read()))
        return obj

    def get(self, action, objid=None):
        try:
            self.set_header('Access-Control-Allow-Origin', self.request.headers['Origin'])
        except KeyError:
            pass

        self.set_header('Content-Type', 'application/json')

        if action == 'autocomplete':
            response = self.autocomplete()
        if action == 'search':
            response = self.search()
        if action == 'get_by':
            response = self.get_by()
        if action == 'get':
            try:
                response = self.get_object(objid)
            except:
                raise tornado.web.HTTPError(404)

        if action == 'list':
            response = self.list()

        self.write(json.dumps(response, default=json_handler))

    def autocomplete(self):
        term = str(self.request.arguments.get('term')[0])
        result = []
        for entry in self.index.term_search(term):
            result.append(entry)
        return result

    def search(self):
        result = []
        for entry in self.index.term_search(self.request.arguments):
            obj = self.get_object(entry['id'])
            if obj is None:
                # TODO isso acontece qdo sobra lixo no índice, não deve acontecer na produção
                continue
            entry.update(obj)
            result.append(entry)
        return result

    def list(self):
        result = []
        for entry in self.index.every():
            obj = self.get_object(entry['id'])
            if obj is None:
                continue
            entry.update(obj)
            result.append(entry)
        return result

    def get_by(self):
        query = {}
        for key in self.request.arguments.keys():
            query[key] = self.get_argument(key)
        try:
            return next(self.index.find(**query))
        except StopIteration:
            return None

class EffectSearcher(Searcher):
    index = indexing.EffectIndex()

    def get_by_url(self):
        try:
            url = self.request.arguments['url'][0]
        except (KeyError, IndexError):
            raise tornado.web.HTTPError(404)

        search = self.index.find(url=url)
        try:
            entry = next(search)
        except StopIteration:
            raise tornado.web.HTTPError(404)

        return entry['id']

    def get(self, action, objid=None):
        if action == 'get' and objid is None:
            objid = self.get_by_url()

        super(EffectSearcher, self).get(action, objid)

class EffectBulkData(EffectSearcher):
    "Gets data of several plugins"
    def get_effect(self, url):
        "return true if an effect is installed"
        search = self.index.find(url=url)
        try:
            entry = next(search)
        except StopIteration:
            return False
        try:
            return self.get_object(entry['id'])
        except:
            return None

    def post(self):
        urls = self.json_args
        result = {}
        for url in urls:
            effect = self.get_effect(url)
            if effect:
                result[url] = effect
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(result, default=json_handler))

    def prepare(self):
        if self.request.headers.get("Content-Type") == "application/json":
            self.json_args = json.loads(self.request.body.decode("utf-8", errors="ignore"))
        else:
            raise web.HTTPError(501, 'Content-Type != "application/json"')

class SDKEffectInstaller(EffectInstaller):
    @web.asynchronous
    @gen.engine
    def post(self):
        upload = self.request.files['package'][0]
        open(os.path.join(PLUGIN_INSTALLATION_TMP_DIR, upload['filename']), 'w').write(upload['body'])
        uid = upload['filename'].replace('.tgz', '')
        res = yield gen.Task(install_bundle, uid)
        self.write(json.dumps({ 'ok': True }))
        self.finish()

# TODO this is an obsolete implementation that does not work in new lv2 specs.
# it's here for us to remember this should be reimplemented
class SDKEffectScript(EffectSearcher):
    def get(self, objid=None):
        if objid is None:
            objid = self.get_by_url()

        try:
            options = self.get_object(objid)
        except:
            raise web.HTTPError(404)

        try:
            path = options['configurationFeedback']
        except KeyError:
            raise web.HTTPError(404)

        path = path.split(options['package']+'/')[-1]
        path = os.path.join(PLUGIN_LIBRARY_DIR, options['package'], path)

        self.write(open(path, 'rb').read())

class EffectResource(web.StaticFileHandler, EffectSearcher):

    def initialize(self):
        # Overrides StaticFileHandler initialize
        pass

    def get(self, path):
        try:
            objid = self.get_by_url()

            try:
                options = self.get_object(objid)
            except:
                raise web.HTTPError(404)

            try:
                document_root = options['gui']['resourcesDirectory']
            except:
                raise web.HTTPError(404)

            super(EffectResource, self).initialize(document_root)
            super(EffectResource, self).get(path)
        except web.HTTPError as e:
            if (not e.status_code == 404):
                raise e
            super(EffectResource, self).initialize(os.path.join(HTML_DIR, 'resources'))
            super(EffectResource, self).get(path)

class EffectImage(EffectSearcher):
    def get(self, prop):
        objid = self.get_by_url()

        try:
            options = self.get_object(objid)
        except:
            raise web.HTTPError(404)

        try:
            path = options['gui'][prop]
        except:
            try:
                path = DEFAULT_ICON_IMAGE[prop]
            except:
                raise web.HTTPError(404)

        if not os.path.exists(path):
            raise web.HTTPError(404)

        self.set_header('Content-Type', 'image/png')
        self.write(open(path, 'rb').read())

class EffectStylesheet(EffectSearcher):
    def get(self):
        objid = self.get_by_url()

        try:
            effect = self.get_object(objid)
        except:
            raise web.HTTPError(404)

        try:
            path = effect['gui']['stylesheet']
        except:
            raise web.HTTPError(404)

        if not os.path.exists(path):
            raise web.HTTPError(404)


        content = open(path).read()
        context = { 'ns': '?url=%s&bundle=%s' % (effect['url'], effect['package']) }

        self.set_header('Content-type', 'text/css')
        self.write(pystache.render(content, context))

class EffectAdd(EffectSearcher):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        objid = self.get_by_url()

        try:
            options = self.get_object(objid)
        except:
            raise web.HTTPError(404)
        x = self.request.arguments.get('x', [0])[0]
        y = self.request.arguments.get('y', [0])[0]
        res = yield gen.Task(SESSION.add, options['url'], instance, x, y)
        if self.request.connection.stream.closed():
            return
        if res >= 0:
            options['instance'] = res
            presets = []
            for k,preset in options['presets'].items():
                presets.append({'label': preset['label']})
            options['presets'] = presets
            self.write(json.dumps(options, default=json_handler))
        else:
            self.write(json.dumps(False))
        self.finish()


class EffectGet(EffectSearcher):
    @web.asynchronous
    @gen.engine
    def get(self):
        objid = self.get_by_url()

        try:
            options = self.get_object(objid)
            presets = []
            for k,preset in options['presets'].items():
                presets.append({'label': preset['label'],
                                'uri': preset['uri']})
            options['presets'] = presets
        except:
            raise web.HTTPError(404)

        if self.request.connection.stream.closed():
            return

        self.write(json.dumps(options, default=json_handler))
        self.finish()


class EffectRemove(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        resp = yield gen.Task(SESSION.remove, instance)
        if self.request.connection.stream.closed():
            return
        self.write(json.dumps(resp))
        self.finish()

class EffectBypass(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance, value):
        res = yield gen.Task(SESSION.bypass, instance, int(value))
        self.write(json.dumps(res))
        self.finish()

class EffectBypassAddress(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance, hwtype, hwid, actype, acid, value, label):
        res = yield gen.Task(SESSION.parameter_address, instance, ":bypass", 'switch', label, 6, "none",
                            int(value), 1, 0, 0, int(hwtype), int(hwid), int(actype), int(acid), [])

        # TODO: get value when unaddressing
        self.write(json.dumps({ 'ok': res, 'value': False }))
        self.finish()

class EffectConnect(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, port_from, port_to):
        response = yield gen.Task(SESSION.connect, port_from, port_to)
        if self.request.connection.stream.closed():
            return
        self.write(json.dumps(response))
        self.finish()

class EffectDisconnect(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, port_from, port_to):
        response = yield gen.Task(SESSION.disconnect, port_from, port_to)
        if self.request.connection.stream.closed():
            return
        self.write(json.dumps(response))
        self.finish()

class EffectPresetLoad(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance):
        response = yield gen.Task(SESSION.preset_load,
                                  instance,
                                  self.get_argument('uri'))
        self.write(json.dumps(response))
        self.finish()

class EffectParameterSet(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, port):
        response = yield gen.Task(SESSION.parameter_set,
                                  port,
                                  float(self.get_argument('value')),
                                  )
        self.write(json.dumps(response))
        self.finish()

class EffectParameterAddress(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self, port):
        data = json.loads(self.request.body.decode("utf-8", errors="ignore"))

        actuator = data.get('actuator', [-1] * 4)

        if actuator[0] < 0:
            actuator = [ -1, -1, -1, -1 ]
            result = yield gen.Task(SESSION.parameter_get, port)
            if not result['ok']:
                self.write(json.dumps(result))
                self.finish()
                return
        else:
            result = {}

        label = data.get('label', '---')

        try:
            ctype = int(data['type'])
        except:
            ctype = 0

        value = float(data['value'])
        minimum = float(data['minimum'])
        maximum = float(data['maximum'])
        steps = int(data.get('steps', 33))
        unit = data.get('unit', 'none') or 'none'

        options = data.get('options', [])

        result['ok'] = yield gen.Task(SESSION.parameter_address,
                                      port,
                                      data.get('addressing_type', None),
                                      label,
                                      ctype,
                                      unit,
                                      value,
                                      maximum,
                                      minimum,
                                      steps,
                                      actuator[0],
                                      actuator[1],
                                      actuator[2],
                                      actuator[3],
                                      options,
                                      )

        self.write(json.dumps(result))
        self.finish()

class EffectParameterGet(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, port, parameter):
        response = yield gen.Task(SESSION.parameter_get,
                                  port,
                                  parameter)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(response))
        self.finish()

class AtomWebSocket(websocket.WebSocketHandler):
    def open(self):
        SESSION.websocket_opened(self)

    def on_close(self):
        SESSION.websockets.remove(self)


class EffectPosition(web.RequestHandler):
    def get(self, instance):
        instance = instance
        x = int(float(self.get_argument('x')))
        y = int(float(self.get_argument('y')))
        SESSION.effect_position(instance, x, y)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(True))

class PedalboardSize(web.RequestHandler):
    def get(self):
        width = int(self.get_argument('width'))
        height = int(self.get_argument('height'))
        SESSION.pedalboard_size(width, height)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(True))

class PackageEffectList(web.RequestHandler):
    def get(self, package):
        index = indexing.EffectIndex()
        result = list(index.find(package=package))
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(result, default=json_handler))

class PackageUninstall(web.RequestHandler):
    def post(self, package):
        result = uninstall_bundle(package)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(result, default=json_handler))

class PedalboardSearcher(Searcher):
    index = indexing.PedalboardIndex()

class PedalboardSave(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self):
        title = self.get_argument('title')
        as_new = bool(int(self.get_argument('asNew')))

        try:
            bundlepath = SESSION.save_pedalboard(title, as_new)
        except Pedalboard.ValidationError as e:
            self.write(json.dumps({ 'ok': False, 'error': str(e) }))
            self.finish()
            return

        SCREENSHOT_GENERATOR.schedule_screenshot(bundlepath)

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({ 'ok': True, 'bundlepath': bundlepath }, default=json_handler))
        self.finish()

class PedalboardPackBundle(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        bundlepath = os.path.abspath(self.get_argument('bundlepath'))
        parentpath = os.path.abspath(os.path.join(bundlepath, ".."))
        bundledir  = bundlepath.replace(parentpath, "").replace(os.sep, "")
        tmpfile    = "/tmp/upload-pedalboard.tar.gz"

        oldcwd = os.getcwd()
        os.chdir(parentpath) # hmm, is there os.path.parent() ?

        # FIXME - don't use external tools!
        os.system("tar -cvzf %s %s" % (tmpfile, bundledir))

        os.chdir(oldcwd)

        with open(tmpfile, 'rb') as fd:
            self.write(fd.read())

        self.finish()

        #os.remove(tmpfile)

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

        if os.path.exists(bundlepath):
            SESSION.load_pedalboard(bundlepath)

        os.remove(filename)
        callback()

class PedalboardLoad(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, pedalboard_id):
        res = yield gen.Task(SESSION.load_pedalboard, pedalboard_id)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(res, default=json_handler))
        self.finish()

class PedalboardRemove(web.RequestHandler):
    def get(self, uid):
        remove_pedalboard(uid)

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

class DashboardClean(web.RequestHandler):
    @web.asynchronous
    def get(self):
        SESSION.reset(self.result)
    def result(self, resp):
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(resp))
        self.finish()

class DashboardDisconnect(web.RequestHandler):
    @web.asynchronous
    def get(self):
        SESSION.end_session(self.result)
    def result(self, resp):
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(resp))
        self.finish()

class BankLoad(web.RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'application/json')
        try:
            banks = open(BANKS_JSON_FILE).read()
        except IOError:
            self.write(json.dumps([]))
            return
        banks = json.loads(banks)
        # Banks have only ID and title of each pedalboard, which are the necessary information
        # for the IHM. But the GUI needs the whole pedalboard metadata
        for bank in banks:
            pedalboards = []
            for pedalboard in bank['pedalboards']:
                try:
                    full_pedalboard = open(os.path.join(PEDALBOARD_DIR, pedalboard['id'])).read()
                except IOError:
                    # Remove from banks pedalboards that have been removed
                    continue
                except KeyError:
                    # This is a bug. There's a pedalboard without ID. Let's recover from it
                    continue
                full_pedalboard = json.loads(full_pedalboard)
                pedalboards.append(full_pedalboard)
            bank['pedalboards'] = pedalboards

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
        hardware = get_hardware()
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
        ei = indexing.EffectIndex()
        default_icon_template = open(DEFAULT_ICON_TEMPLATE).read()
        default_settings_template = open(DEFAULT_SETTINGS_TEMPLATE).read()
        context = {
            'effects': ei.every(),
            'default_icon_template': tornado.escape.squeeze(default_icon_template.replace("'", "\\'")),
            'default_settings_template': tornado.escape.squeeze(default_settings_template.replace("'", "\\'")),
            'cloud_url': CLOUD_HTTP_ADDRESS,
            'hardware_profile': b64encode(json.dumps(get_hardware()).encode("utf-8")),
            # 'current_pedalboard': b64encode(json.dumps(SESSION.serialize_pedalboard(), default=json_handler).encode("utf-8")),
            'max_screenshot_width': MAX_SCREENSHOT_WIDTH,
            'max_screenshot_height': MAX_SCREENSHOT_HEIGHT,
            'package_server_address': PACKAGE_SERVER_ADDRESS or '',
            'default_package_server_port': DEFAULT_PACKAGE_SERVER_PORT,
            'package_repository': PACKAGE_REPOSITORY,
            'js_custom_channel': 'true' if JS_CUSTOM_CHANNEL else 'false',
            'auto_cloud_backup': 'true' if AUTO_CLOUD_BACKUP else 'false',
            'avatar_url': AVATAR_URL,
            'version': self.get_argument('v'),
            }
        return context

    def icon(self):
        return self.index()

    def pedalboard(self):
        context = self.index()
        bundlepath = self.get_argument('bundlepath')

        #try: # TESTING let us receive exceptions for now
        pedalboard = get_pedalboard_info(bundlepath)
        #except:
            #return None

        data = b'{ "_id": "0", "instances": ['

        first = True
        for plugin in pedalboard['plugins']:
            if first:
                first = False
            else:
                data += b','

            msg = '{ "url": "%s", "bypassed": false, "x": %i, "y": %i, "values": {} }' % (plugin['uri'], plugin['x'], plugin['y'])
            print(msg)
            data += bytes(msg, "utf-8")

        data += b'], "connections": ['

        first = True
        for connection in pedalboard['connections']:
            if first:
                first = False
            else:
                data += b','

            msg = '{ "source": "%s", "target": "%s" }' % (connection['source'], connection['target'])
            print(msg)
            data += bytes(msg, "utf-8")

        data += b'] } '

        context['pedalboard'] = b64encode(data)
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
        if SESSION.pedalboard_initialized:
            ihm = yield gen.Task(SESSION.ping)
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


class JackXRun(web.RequestHandler):
    xruns = 0
    requests = set()

    @classmethod
    def connect(cls):
        pass

    @classmethod
    def xrun(cls, *args):
        cls.xruns += 1
        for request in list(cls.requests):
            request.wake()
        return cls.xruns

    @web.asynchronous
    def get(self, count=None):
        if count is not None and self.xruns > int(count):
            self.write(json.dumps(self.xruns))
            self.finish()
        else:
            self.requests.add(self)

    def wake(self):
        self.write(json.dumps(self.xruns))
        self.finish()
        self.requests.remove(self)

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
        EffectSearcher.urls('effect') +
        PedalboardSearcher.urls('pedalboard') +
        [
            (r"/system/upgrade/packages", UpgradePackages),
            (r"/system/upgrade/do", UpgradeDo),
            #TODO merge these
            #(r"/system/install_pkg/([^/]+)/?", InstallPkg),
            #(r"/system/install_pkg/do/([^/]+)/?", InstallPkgDo),
            (r"/system/bluetooth/set", BluetoothSetPin),
            (r"/resources/(.*)", EffectResource),

            (r"/effect/add/([A-Za-z0-9_]+)/?", EffectAdd),
            (r"/effect/get/?", EffectGet),
            (r"/effect/bulk/?", EffectBulkData),
            (r"/effect/remove/([A-Za-z0-9_]+)", EffectRemove),
            (r"/effect/connect/([A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)?),([A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)?)", EffectConnect),
            (r"/effect/disconnect/([A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)?),([A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)?)", EffectDisconnect),
            (r"/effect/preset/load/([A-Za-z0-9_]+)", EffectPresetLoad),
            (r"/effect/parameter/set/([A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)?)", EffectParameterSet),
            (r"/effect/parameter/get/([A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)?)", EffectParameterGet),
            (r"/effect/parameter/address/([A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)?)", EffectParameterAddress),
            (r"/effect/bypass/([A-Za-z0-9_]+),(\d+)", EffectBypass),
            (r"/effect/bypass/address/([A-Za-z0-9_]),([0-9-]+),([0-9-]+),([0-9-]+),([0-9-]+),([01]),(.*)", EffectBypassAddress),
            (r"/effect/image/(screenshot|thumbnail).png", EffectImage),
            (r"/effect/stylesheet.css", EffectStylesheet),
            (r"/effect/position/([A-Za-z0-9_]+)/?", EffectPosition),
            (r"/effect/set/(release)/?", EffectSetLocalVariable),

            (r"/package/([A-Za-z0-9_.-]+)/list/?", PackageEffectList),
            (r"/package/([A-Za-z0-9_.-]+)/uninstall/?", PackageUninstall),

            (r"/pedalboard/save", PedalboardSave),
            (r"/pedalboard/pack_bundle/?", PedalboardPackBundle),
            (r"/pedalboard/load_web/", PedalboardLoadWeb),
            (r"/pedalboard/load/([0-9a-f]+)/?", PedalboardLoad),
            (r"/pedalboard/remove/([0-9a-f]+)/?", PedalboardRemove),
            (r"/pedalboard/screenshot/([0-9a-f]+)/?", PedalboardScreenshot),
            (r"/pedalboard/size/?", PedalboardSize),

            (r"/banks/?", BankLoad),
            (r"/banks/save/?", BankSave),

            (r"/hardware/?", HardwareLoad),

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
            (r"/sdk/get_config_script/?", SDKEffectScript),

            (r"/register/start/([A-Z0-9-]+)/?", RegistrationStart),
            (r"/register/finish/?", RegistrationFinish),

            #(r"/sysmon/ps", SysMonProcessList),
            (r"/sysmon/xrun/(\d+)?", JackXRun),

            (r"/ping/?", Ping),

            (r"/(index.html)?$", EditionLoader),
            (r"/([a-z]+\.html)$", TemplateHandler),
            (r"/load_template/([a-z_]+\.html)$", TemplateLoader),
            (r"/js/templates.js$", BulkTemplateLoader),

            (r"/demo/restore/?$", DemoRestore),

            (r"/websocket/?$", AtomWebSocket),

            #(r"/pedalboards/(.*)", web.StaticFileHandler, {"path": PEDALBOARD_SCREENSHOT_DIR}), # TODO
            (r"/(.*)", web.StaticFileHandler, {"path": HTML_DIR}),
            ],
            debug=LOG, **settings)

def prepare():
    def run_server():
        application.listen(DEVICE_WEBSERVER_PORT, address="0.0.0.0")
        if LOG:
            tornado.options.parse_command_line()
        JackXRun.connect()

    def check():
        check_environment(lambda result: result)

    run_server()
    tornado.ioloop.IOLoop.instance().add_callback(check)
    tornado.ioloop.IOLoop.instance().add_callback(JackXRun.connect)
    global cpu_load_callback
    cpu_load_callback = tornado.ioloop.PeriodicCallback(SESSION.jack_cpu_load, 1000)

def start():
    global cpu_load_callback
    cpu_load_callback.start()
    tornado.ioloop.IOLoop.instance().start()

def stop():
    global cpu_load_callback
    cpu_load_callback.stop()
    tornado.ioloop.IOLoop.instance().stop()

def run():
    prepare()
    start()

if __name__ == "__main__":
    run()
