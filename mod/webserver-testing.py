#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ------------------------------------------------------------------------------------------------------------
# Imports (Global)

import json
import os

# ------------------------------------------------------------------------------------------------------------
# Imports (tornado)

from pystache import render as pyrender
from tornado.gen import engine
from tornado.ioloop import IOLoop
from tornado.web import asynchronous, HTTPError
from tornado.web import Application, RequestHandler, StaticFileHandler

# ------------------------------------------------------------------------------------------------------------
# Set up environment for the webserver

PORT     = "8888"
ROOT     = "/home/falktx/FOSS/GIT-mine/MOD/mod-app/source/modules/"
DATA_DIR = os.path.expanduser("~/.local/share/mod-data/")
HTML_DIR = os.path.join(ROOT, "mod-ui", "html")

os.environ['MOD_DEV_HOST'] = "1"
os.environ['MOD_DEV_HMI']  = "1"
os.environ['MOD_DESKTOP']  = "1"
os.environ['MOD_LOG']      = "1" # TESTING

os.environ['MOD_DATA_DIR']           = DATA_DIR
os.environ['MOD_HTML_DIR']           = HTML_DIR
os.environ['MOD_KEY_PATH']           = os.path.join(DATA_DIR, "keys")
os.environ['MOD_CLOUD_PUB']          = os.path.join(ROOT, "mod-ui", "keys", "cloud_key.pub")
os.environ['MOD_PLUGIN_LIBRARY_DIR'] = os.path.join(DATA_DIR, "lib")

os.environ['MOD_DEFAULT_JACK_BUFSIZE']  = "0"
os.environ['MOD_PHANTOM_BINARY']        = "/usr/bin/phantomjs"
os.environ['MOD_SCREENSHOT_JS']         = os.path.join(ROOT, "mod-ui", "screenshot.js")
os.environ['MOD_DEVICE_WEBSERVER_PORT'] = PORT

# ------------------------------------------------------------------------------------------------------------
# Imports (MOD)

from mod.indexing import EffectIndex

# ------------------------------------------------------------------------------------------------------------
# MOD related classes

class EffectSearcher(RequestHandler):
    index = EffectIndex()

    @classmethod
    def urls(cls, path):
        return [
            (r"/%s/(get)/([a-z0-9]+)?" % path, cls),
        ]

    def get(self, action, objid=None):
        if action != 'get':
            raise HTTPError(404)

        try:
            self.set_header('Access-Control-Allow-Origin', self.request.headers['Origin'])
        except KeyError:
            pass

        self.set_header('Content-Type', 'application/json')

        if objid is None:
            objid = self.get_by_url()

        try:
            response = self.get_object(objid)
        except:
            raise HTTPError(404)

        self.write(json.dumps(response))

    def get_by_url(self):
        try:
            url = self.request.arguments['url'][0]
        except (KeyError, IndexError):
            raise HTTPError(404)

        search = self.index.find(url=url)
        try:
            entry = next(search)
        except StopIteration:
            raise HTTPError(404)

        return entry['id']

    def get_object(self, objid):
        path = os.path.join(self.index.data_source, objid)
        md_path = path + '.metadata'
        obj = json.loads(open(path).read())
        if os.path.exists(md_path):
            obj.update(json.loads(open(md_path).read()))
        return obj

class EffectGet(EffectSearcher):
    @asynchronous
    @engine
    def get(self, instance_id):
        objid = self.get_by_url()

        try:
            options = self.get_object(objid)
            presets = []
            for _, preset in options['presets'].items():
                presets.append({'label': preset['label']})
            options['presets'] = presets
        except:
            raise HTTPError(404)

        if self.request.connection.stream.closed():
            return

        self.write(json.dumps(options))
        self.finish()

class EffectStylesheet(EffectSearcher):
    def get(self):
        objid = self.get_by_url()

        try:
            effect = self.get_object(objid)
        except:
            raise HTTPError(404)

        try:
            path = effect['gui']['stylesheet']
        except:
            raise HTTPError(404)

        if not os.path.exists(path):
            raise HTTPError(404)

        content = open(path).read()
        context = { 'ns': '?url=%s&bundle=%s' % (effect['url'], effect['package']) }

        self.set_header('Content-type', 'text/css')
        self.write(pyrender(content, context))

class EffectResource(StaticFileHandler, EffectSearcher):
    def initialize(self):
        # Overrides StaticFileHandler initialize
        pass

    def get(self, path):
        try:
            objid = self.get_by_url()

            try:
                options = self.get_object(objid)
            except:
                raise HTTPError(404)

            try:
                document_root = options['gui']['resourcesDirectory']
            except:
                raise HTTPError(404)

            super(EffectResource, self).initialize(document_root)
            super(EffectResource, self).get(path)

        except HTTPError as e:
            if e.status_code != 404:
                raise e

            super(EffectResource, self).initialize(os.path.join(HTML_DIR, 'resources'))
            super(EffectResource, self).get(path)

application = Application(
    EffectSearcher.urls('effect') +
    [
        (r"/effect/get/?", EffectGet),
        (r"/effect/stylesheet.css", EffectStylesheet),
        (r"/resources/(.*)", EffectResource),
        (r"/(.*)", StaticFileHandler, {"path": HTML_DIR}),
    ],
    debug=True)

def prepare():
    application.listen(PORT, address="0.0.0.0")

def start():
    IOLoop.instance().start()

def stop():
    IOLoop.instance().stop()

def run():
    prepare()
    start()

# ------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    run()

# ------------------------------------------------------------------------------------------------------------
