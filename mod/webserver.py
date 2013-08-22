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


import os, re
import json, socket
import tornado.ioloop
import tornado.options
import tornado.escape
import StringIO
import time
try:
    import Image
except ImportError:
    from PIL import Image
from sha import sha
from base64 import b64decode, b64encode
from tornado import gen, web, iostream
from bson import ObjectId
import subprocess
from glob import glob

from mod.settings import (HTML_DIR, CLOUD_PUB, PLUGIN_LIBRARY_DIR,
                          DOWNLOAD_TMP_DIR, EFFECT_DIR, DEVICE_WEBSERVER_PORT,
                          PEDALBOARD_DIR, CLOUD_HTTP_ADDRESS, BANKS_JSON_FILE,
                          DEVICE_SERIAL, DEVICE_KEY, LOCAL_REPOSITORY_DIR,
                          PLUGIN_INSTALLATION_TMP_DIR, DEFAULT_ICON_TEMPLATE,
                          DEFAULT_SETTINGS_TEMPLATE, DEFAULT_ICON_IMAGE,
                          MAX_SCREENSHOT_WIDTH, MAX_SCREENSHOT_HEIGHT,
                          MAX_THUMB_WIDTH, MAX_THUMB_HEIGHT,
                          PACKAGE_SERVER_ADDRESS, DEFAULT_PACKAGE_SERVER_PORT,
                          PACKAGE_REPOSITORY,
                          )


from modcommon.communication import fileserver, crypto
from modcommon import json_handler
from mod import indexing
from mod.session import SESSION
from mod.effect import install_bundle, uninstall_bundle
from mod.pedalboard import save_pedalboard, remove_pedalboard, save_banks
from mod.hardware import get_hardware
from mod.screenshot import ThumbnailGenerator, generate_screenshot, resize_image
from mod.system import (sync_pacman_db, get_pacman_upgrade_list, 
                                pacman_upgrade, set_bluetooth_pin)
from mod import register
from mod import check_environment

THUMB_GENERATOR = ThumbnailGenerator()
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

class EffectInstaller(fileserver.FileReceiver):
    download_tmp_dir = DOWNLOAD_TMP_DIR
    remote_public_key = CLOUD_PUB
    destination_dir = PLUGIN_INSTALLATION_TMP_DIR

    def process_file(self, data, callback):
        def on_finish(result):
            self.result = result
            callback()
        install_bundle(data['_id'], on_finish)

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
        return json.loads(open(os.path.join(self.index.data_source, objid)).read())

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
        term = unicode(self.request.arguments.get('term')[0])
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
            entry.update(self.get_object(entry['id']))
            result.append(entry)
        return result

    def get_by(self):
        query = {}
        for key in self.request.arguments.keys():
            query[key] = self.get_argument(key)
        try:
            return self.index.find(**query).next()
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
            entry = search.next()
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
            entry = search.next()
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
            self.json_args = json.loads(self.request.body)
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

        self.write(open(path).read())

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
        self.write(open(path).read())

class EffectAdd(EffectSearcher):
    @web.asynchronous
    @gen.engine
    def get(self, instance_id):
        objid = self.get_by_url()

        try:
            options = self.get_object(objid)
        except:
            raise web.HTTPError(404)
        res = yield gen.Task(SESSION.add, options['url'], int(instance_id))
        if self.request.connection.stream.closed():
            return
        if res >= 0:
            options['instanceId'] = res
            self.write(json.dumps(options, default=json_handler))
        else:
            self.write(json.dumps(False))
        self.finish()


class EffectGet(EffectSearcher):
    @web.asynchronous
    @gen.engine
    def get(self, instance_id):
        objid = self.get_by_url()

        try:
            options = self.get_object(objid)
        except:
            raise web.HTTPError(404)

        if self.request.connection.stream.closed():
            return

        self.write(json.dumps(options, default=json_handler))
        self.finish()


class EffectRemove(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance_id):
        resp = yield gen.Task(SESSION.remove, int(instance_id))
        if self.request.connection.stream.closed():
            return
        self.write(json.dumps(resp))
        self.finish()

class EffectBypass(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance, value):
        res = yield gen.Task(SESSION.bypass, int(instance), int(value))
        self.write(json.dumps(res))
        self.finish()

class EffectBypassAddress(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance, hwtype, hwid, actype, acid, value, label):
        res = yield gen.Task(SESSION.bypass_address, int(instance), int(hwtype), int(hwid), int(actype), int(acid), int(value), label)
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

class EffectParameterSet(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self, instance, parameter):
        response = yield gen.Task(SESSION.parameter_set,
                                  int(instance),
                                  parameter,
                                  float(self.get_argument('value')),
                                  )
        self.write(json.dumps(response))
        self.finish()

class EffectParameterAddress(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self, instance, parameter):
        data = json.loads(self.request.body)

        actuator = data.get('actuator', [-1] * 4)

        if actuator[0] < 0:
            actuator = [ -1, -1, -1, -1 ]
            result = yield gen.Task(SESSION.parameter_get,
                                    int(instance),
                                    parameter)

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
        unit = data.get('unit', 'none') or 'none'

        options = data.get('options', [])

        result['ok'] = yield gen.Task(SESSION.parameter_address,
                                      int(instance),
                                      parameter,
                                      label,
                                      ctype,
                                      unit,
                                      value,
                                      maximum,
                                      minimum,
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
    def get(self, instance, parameter):
        response = yield gen.Task(SESSION.parameter_get,
                                  int(instance),
                                  parameter)
        self.write(json.dumps(response))
        self.finish()

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
        pedalboard = json.loads(self.request.body)
        if not pedalboard.get('_id'):
            pedalboard['_id'] = ObjectId()

        try:
            metadata = pedalboard.get('metadata', {})
            title = metadata.get('title', '')
            assert bool(title)
        except AssertionError:
            self.write(json.dumps({ 'ok': False, 'error': 'Title cannot be empty' }))
            self.finish()
            raise StopIteration
        
        index = indexing.PedalboardIndex()
        try:
            existing = index.find(title=title).next()
            assert existing['id'] == unicode(pedalboard['_id'])
        except StopIteration:
            pass
        except AssertionError:
            self.write(json.dumps({ 'ok': False, 'error': 'Pedalboard "%s" already exists' % title }))
            self.finish()
            raise StopIteration
        
        # make sure title is unicode
        pedalboard['metadata']['title'] = unicode(title)
        save_pedalboard(pedalboard)
        THUMB_GENERATOR.schedule_thumbnail(pedalboard['_id'])

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({ 'ok': True, 'uid': pedalboard['_id'] }, default=json_handler))
        self.finish()

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
        SESSION.start_session(self.result)
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
                pedalboard.update(full_pedalboard['metadata'])
                pedalboards.append(pedalboard)
            bank['pedalboards'] = pedalboards

        self.write(json.dumps(banks))

class BankSave(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def post(self):
        banks = json.loads(self.request.body)
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
        loader = tornado.template.Loader(HTML_DIR)
        section = path.split('.')[0]
        try:
            context = getattr(self, section)()
        except AttributeError:
            context = {}
        context['cloud_url'] = CLOUD_HTTP_ADDRESS
        self.write(loader.load(path).generate(**context))

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
            'hardware_profile': json.dumps(get_hardware()),
            'max_screenshot_width': MAX_SCREENSHOT_WIDTH,
            'max_screenshot_height': MAX_SCREENSHOT_HEIGHT,
            'package_server_address': PACKAGE_SERVER_ADDRESS or '',
            'default_package_server_port': DEFAULT_PACKAGE_SERVER_PORT,
            'package_repository': PACKAGE_REPOSITORY,
            }
        return context

    def pedalboard(self):
        context = self.index()
        uid = self.get_argument('uid')
        context['pedalboard'] = open(os.path.join(PEDALBOARD_DIR, uid)).read()
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
            self.sock.read_until("\0", set_ps_list)
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
        signature = crypto.Sender(DEVICE_KEY, sid).pack()
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({
                    'signature': signature,
                    'serial': open(DEVICE_SERIAL).read().strip(),
                    }))

class LoginAuthenticate(web.RequestHandler):
    def post(self):
        serialized_user = self.get_argument('user')
        signature = self.get_argument('signature')
        receiver = crypto.Receiver(CLOUD_PUB, signature)
        checksum = receiver.unpack()
        self.set_header('Access-Control-Allow-Origin', CLOUD_HTTP_ADDRESS)
        self.set_header('Content-Type', 'application/json')
        if not sha(serialized_user).hexdigest() == checksum:
            return self.write(json.dumps({ 'ok': False}))
        user = json.loads(b64decode(serialized_user))
        self.write(json.dumps({ 'ok': True, 
                                'user': user }))

class RegistrationStart(web.RequestHandler):
    def get(self, serial_number):
        try:
            package = register.DeviceRegisterer().generate_registration_package(serial_number)
        except register.DeviceAlreadyRegistered:
            raise web.HTTPError(404)

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(package))

class RegistrationFinish(web.RequestHandler):
    def post(self):
        response = json.loads(self.request.body)
        ok = register.DeviceRegisterer().register(response)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(ok))        

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

            (r"/effect/add/(\d+)/?", EffectAdd),
            (r"/effect/get/?", EffectGet),
            (r"/effect/bulk/?", EffectBulkData),
            (r"/effect/remove/([a-z0-9]+)", EffectRemove),
            (r"/effect/connect/([A-Za-z0-9_:]+),([A-Za-z0-9_:]+)", EffectConnect),
            (r"/effect/disconnect/([A-Za-z0-9_:]+),([A-Za-z0-9_:]+)", EffectDisconnect),
            (r"/effect/parameter/set/(\d+),([A-Za-z0-9_]+)", EffectParameterSet),
            (r"/effect/parameter/get/(\d+),([A-Za-z0-9_]+)", EffectParameterGet),
            (r"/effect/parameter/address/(\d+),([A-Za-z0-9_]+)", EffectParameterAddress),
            (r"/effect/bypass/(\d+),(\d+)", EffectBypass),
            (r"/effect/bypass/address/(\d+),([0-9-]+),([0-9-]+),([0-9-]+),([0-9-]+),([01]),(.*)", EffectBypassAddress),
            (r"/effect/image/(screenshot|thumbnail).png", EffectImage),

            (r"/package/([A-Za-z0-9_.-]+)/list/?", PackageEffectList),
            (r"/package/([A-Za-z0-9_.-]+)/uninstall/?", PackageUninstall),
            
            (r"/pedalboard/save", PedalboardSave),
            (r"/pedalboard/load/([0-9a-f]+)/?", PedalboardLoad),
            (r"/pedalboard/remove/([0-9a-f]+)/?", PedalboardRemove),
            (r"/pedalboard/screenshot/([0-9a-f]+)/?", PedalboardScreenshot),

            (r"/banks/?", BankLoad),
            (r"/banks/save/?", BankSave),

            (r"/hardware/?", HardwareLoad),

            (r"/login/sign_session/(.+)", LoginSign),
            (r"/login/authenticate", LoginAuthenticate),

            (r"/reset/?", DashboardClean),
            (r"/disconnect/?", DashboardDisconnect),

            (r"/sdk/sysupdate/?", SDKSysUpdate),
            (r"/sdk/install/?", SDKEffectInstaller),
            (r"/sdk/get_config_script/?", SDKEffectScript),

            (r"/register/start/([A-Z0-9]+)/?", RegistrationStart),
            (r"/register/finish/?", RegistrationFinish),
            
            #(r"/sysmon/ps", SysMonProcessList),
            (r"/sysmon/xrun/(\d+)?", JackXRun),

            (r"/ping/?", Ping),

            (r"/(index.html)?$", EditionLoader),
            (r"/([a-z]+\.html)$", TemplateHandler),
            (r"/load_template/([a-z_]+\.html)$", TemplateLoader),
            (r"/js/templates.js$", BulkTemplateLoader),
            
            (r"/(.*)", web.StaticFileHandler, {"path": HTML_DIR}),
            ],
            debug=True)

def run():
    def run_server():
        application.listen(DEVICE_WEBSERVER_PORT, address="0.0.0.0")
        tornado.options.parse_command_line()

        JackXRun.connect()

    def check():
        check_environment(lambda result: result)

    run_server()
    tornado.ioloop.IOLoop.instance().add_callback(check)
    tornado.ioloop.IOLoop.instance().add_callback(JackXRun.connect)
    
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    run()
