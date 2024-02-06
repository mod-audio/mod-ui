#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import os
import subprocess
import sys
import logging

from tornado.ioloop import IOLoop
from mod.settings import HTML_DIR, DEV_ENVIRONMENT, DEVICE_KEY, CACHE_DIR, DESKTOP


def generate_screenshot(bundle_path, callback):
    screenshot = os.path.join(bundle_path, 'screenshot.png')
    thumbnail = os.path.join(bundle_path, 'thumbnail.png')

    try:
        os.remove(screenshot)
        os.remove(thumbnail)
    except OSError:
        pass

    cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))

    # running packaged through cxfreeze
    if DESKTOP and os.path.isfile(sys.argv[0]):
        cmd = [os.path.join(cwd, 'mod-pedalboard'), 'take_screenshot', bundle_path, HTML_DIR, CACHE_DIR]
        if sys.platform == 'win32':
            cmd[0] += ".exe"
        logging.debug('[screenshot] now running: %s', ' '.join(cmd))

    # regular run
    else:
        cmd = ['python3', '-m', 'modtools.pedalboard', 'take_screenshot', bundle_path, HTML_DIR, CACHE_DIR]
        if not DEV_ENVIRONMENT and DEVICE_KEY:  # if using a real MOD, setup niceness
            cmd = ['/usr/bin/nice', '-n', '+34'] + cmd

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
