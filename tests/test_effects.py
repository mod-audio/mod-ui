import json
import os
import shutil
import subprocess
from os.path import join
from tornado.testing import AsyncHTTPTestCase

from mod import settings
from mod.device import effect, pedalboard, webserver, hardware

# let's reload all settings and everything else
settings = reload(settings)
effect = reload(effect)
pedalboard = reload(pedalboard)
webserver = reload(webserver)
hardware = reload(hardware)

from mod.device.webserver import application
from mod.device.effect import install_effects
from modcommon import lv2


DIR = os.path.dirname(__file__)
FIXTURES = join(DIR, 'fixtures')

SOOPERLOOPER = "http://portalmod.com/plugins/sooperlooper"


def clean_data_dir():
    clean(settings.PLUGIN_LIBRARY_DIR)
    clean(settings.EFFECT_DIR)
    clean(settings.PEDALBOARD_DIR)

    if os.path.exists(settings.INDEX_PATH):
        shutil.rmtree(settings.INDEX_PATH)

    if os.path.exists(settings.PEDALBOARD_INDEX_PATH):
        shutil.rmtree(settings.PEDALBOARD_INDEX_PATH)

    if os.path.exists(settings.BANKS_BINARY_FILE):
        os.remove(settings.BANKS_BINARY_FILE)

    if not os.path.exists(settings.PEDALBOARD_BINARY_DIR):
        os.mkdir(settings.PEDALBOARD_BINARY_DIR)

    if not os.path.exists(settings.EFFECT_DIR):
        os.mkdir(settings.EFFECT_DIR)


def clean(path):
    for fname in os.listdir(path):
        fname = os.path.join(path, fname)
        if os.path.isfile(fname):
            os.remove(fname)
        else:
            shutil.rmtree(fname)


def install_plugin(plugin):
    plugin = join(FIXTURES, 'plugins/%s' % plugin)
    package = lv2.PluginPackage(plugin)
    filename = join(settings.PLUGIN_LIBRARY_DIR, '%s.tgz' % package.uid)
    open(filename, 'w').write(package.read())
    proc = subprocess.Popen(['tar','zxf', filename],
                                    cwd=settings.PLUGIN_LIBRARY_DIR,
                                    stdout=subprocess.PIPE)
    proc.wait()
    install_effects()


class TestHandlerBase(AsyncHTTPTestCase):
    def setUp(self):
        clean_data_dir()

        self.instance_id = 0
        super(TestHandlerBase, self).setUp()

    def tearDown(self):
        clean_data_dir()
        super(TestHandlerBase, self).tearDown()

    def get_app(self):
        return application

    def get_http_port(self):
        return settings.default_port

    def effect_add(self, uri=SOOPERLOOPER, instance_id=None, status=200):
        if instance_id is None:
            instance_id = self.instance_id
            self.instance_id += 1
        response = self.fetch(
                '/effect/add/%d?url=%s' % (instance_id, uri),
                method='GET')

        self.assertEqual(response.code, status)
        return response

    def effect_connect(self, porta, portb, status=200):
        response = self.fetch(
                '/effect/connect/%s,%s' % (porta, portb),
                method='GET')

        self.assertEqual(response.code, status)
        return response

    def save_pedalboard(self, content, status=200):
        response = self.fetch('/pedalboard/save',
                method='POST',
                body=content)
        self.assertEqual(response.code, status)


class TestMainPage(TestHandlerBase):
    def test_open_main_page(self):
        response = self.fetch(
                '/',
                method='GET',
                follow_redirects=True)
        
        self.assertEqual(response.code, 200)


class TestEffect(TestHandlerBase):
    def setUp(self):
        super(TestEffect, self).setUp()
        install_plugin('sooperlooper.lv2')

    def test_effect_add(self):
        response = self.effect_add() 

        effect = json.loads(response.body)
        self.assertEquals(effect['url'], SOOPERLOOPER)
    
    def test_effect_add_two_effects(self):
        response = self.effect_add()
        
        effect = json.loads(response.body)
        self.assertEquals(effect['url'], SOOPERLOOPER)
   
        response2 = self.effect_add()
        
        effect2 = json.loads(response.body)
        self.assertEquals(effect2['url'], SOOPERLOOPER)
   
    def test_connect_ports(self):
        self.effect_add()
        self.effect_add()

        response = self.effect_connect("effect_0:output", "effect_1:input")
        self.assertEquals(response.code, 200)
        self.assertEquals(response.body, 'true')


class TestPedalboard(TestHandlerBase):
    def setUp(self):
        super(TestPedalboard, self).setUp()
        install_plugin('amp.lv2')
        install_plugin('saturate.lv2')
        install_plugin('sooperlooper.lv2')

    def test_save_pedalboard(self):
        self.save_pedalboard(open(join(FIXTURES, "pedalboard_1.json")).read())

    def test_save_complex_pedalboards(self):
        pedalboard = open(join(FIXTURES, "complex_pedalboard.json")).read()
        self.save_pedalboard(pedalboard)

    def test_save_two_pedalboards(self):
        self.save_pedalboard(open(join(FIXTURES, "pedalboard_1.json")).read())
        pedalboard = open(join(FIXTURES, "complex_pedalboard.json")).read()
        self.save_pedalboard(pedalboard)

    def test_save_buggy_pedalboard(self):
        self.save_pedalboard(open(join(FIXTURES, "buggy_pedalboard.json")).read())
