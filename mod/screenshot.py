#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import os
import subprocess
import sys
import logging
import time

from tornado.ioloop import IOLoop
from mod.settings import HTML_DIR, DEV_ENVIRONMENT, DEVICE_KEY, CACHE_DIR, DESKTOP
from modtools.utils import get_pedalboard_info, get_plugin_info, get_plugin_gui

INGEN_GRAPH_PROTOTYPE = 'http://drobilla.net/ns/ingen#GraphPrototype'


# Everything the renderer needs, taken from this process's LV2 world (already loaded, plugin info cached):
# the child then renders straight away instead of scanning the whole LV2 world first (several seconds
# of lilv parsing on a device, during which the audio threads lose their caches).
def build_screenshot_job(bundle_path):
    pb = get_pedalboard_info(bundle_path)
    plugins = {}

    for p in pb['plugins']:
        uri = p['uri']
        if uri == INGEN_GRAPH_PROTOTYPE or uri in plugins:
            continue
        plugins[uri] = {
            'info': get_plugin_info(uri),
            'gui': get_plugin_gui(uri),
        }

    return {
        'pedalboard': pb,
        'plugins': plugins,
    }


def generate_screenshot(bundle_path, callback):
    screenshot = os.path.join(bundle_path, 'screenshot.png')
    thumbnail = os.path.join(bundle_path, 'thumbnail.png')

    try:
        os.remove(screenshot)
        os.remove(thumbnail)
    except OSError:
        pass

    cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))

    # one job at a time (ScreenshotGenerator), so a single file is enough
    jobfile = os.path.join(CACHE_DIR, 'screenshot-job.json')
    try:
        job = build_screenshot_job(bundle_path)
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(jobfile, 'w') as fh:
            json.dump(job, fh)
        jobargs = ['--job', jobfile]
    except Exception as ex:
        logging.error('[screenshot] cannot prepare the render job, the renderer will scan the LV2 world itself: %s', ex)
        jobargs = []

    # running packaged through cxfreeze
    if DESKTOP and os.path.isfile(sys.argv[0]):
        cmd = [os.path.join(cwd, 'mod-pedalboard'), 'take_screenshot', bundle_path, HTML_DIR, CACHE_DIR] + jobargs
        if sys.platform == 'win32':
            cmd[0] += ".exe"
        logging.debug('[screenshot] now running: %s', ' '.join(cmd))

    # regular run
    else:
        cmd = ['python3', '-m', 'modtools.pedalboard', 'take_screenshot', bundle_path, HTML_DIR, CACHE_DIR] + jobargs
        if not DEV_ENVIRONMENT and DEVICE_KEY:  # if using a real MOD, setup niceness
            cmd = ['/usr/bin/nice', '-n', '+34'] + cmd

    started = time.time()
    proc = subprocess.Popen(cmd, cwd=cwd)
    loop = IOLoop.instance()

    def proc_callback():
        if proc.poll() is None:
            loop.call_later(0.5, proc_callback)
            return

        if not os.path.exists(screenshot) or not os.path.exists(thumbnail):
            logging.warn('[screenshot] process finished but image files do not exist')
            callback()
            return

        logging.info('[screenshot] %s done in %.1f s', os.path.basename(bundle_path), time.time() - started)
        callback(thumbnail)

    loop.call_later(0.5, proc_callback)


class ScreenshotGenerator(object):
    def __init__(self):
        self.queue = []
        self.callbacks = {}
        self.processing = None

    def schedule_screenshot(self, bundlepath, callback=None):
        bundlepath = os.path.abspath(bundlepath)

        if bundlepath not in self.queue and self.processing != bundlepath:
            self.queue.append(bundlepath)

        if callback is not None:
            self.add_callback(bundlepath, callback)

        if self.processing is None:
            self.process_next()

    def process_next(self):
        if len(self.queue) == 0:
            self.processing = None
            return

        self.processing = self.queue.pop(0)

        def img_callback(thumbnail=None):
            if not thumbnail:
                for callback in self.callbacks.pop(self.processing, []):
                    callback((False, 0.0))
                self.process_next()
                return

            ctime = os.path.getctime(thumbnail)

            for callback in self.callbacks.pop(self.processing, []):
                callback((True, ctime))

            self.process_next()

        try:
            generate_screenshot(self.processing, img_callback)
        except Exception as ex:
            logging.error('[screenshot] %s', ex)
            img_callback()

    def check_screenshot(self, bundlepath):
        bundlepath = os.path.abspath(bundlepath)

        if bundlepath in self.queue or self.processing == bundlepath:
            return 0, 0.0

        thumbnail = os.path.join(bundlepath, "thumbnail.png")
        if not os.path.exists(thumbnail):
            return -1, 0.0

        ctime = os.path.getctime(thumbnail)
        return 1, ctime

    def wait_for_pending_jobs(self, bundlepath, callback):
        bundlepath = os.path.abspath(bundlepath)

        if bundlepath not in self.queue and self.processing != bundlepath:
            # all ok
            thumbnail = os.path.join(bundlepath, "thumbnail.png")
            if os.path.exists(thumbnail):
                ctime = os.path.getctime(thumbnail)
                callback((True, ctime))
            else:
                callback((False, 0.0))
            return

        # report back later
        self.add_callback(bundlepath, callback)

    def add_callback(self, bundlepath, callback):
        if bundlepath not in self.callbacks.keys():
            self.callbacks[bundlepath] = [callback]
        else:
            self.callbacks[bundlepath].append(callback)
