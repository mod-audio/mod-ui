
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


import os, subprocess

try:
    import Image
except ImportError:
    from PIL import Image

from tornado import ioloop
from mod.utils import get_pedalboard_size
from mod.settings import (DEVICE_KEY, DEVICE_WEBSERVER_PORT,
                          PHANTOM_BINARY, SCREENSHOT_JS,
                          MAX_THUMB_HEIGHT, MAX_THUMB_WIDTH)

def generate_screenshot(bundlepath, callback):
    if not os.path.exists(PHANTOM_BINARY):
        return callback()
    if not os.path.exists(SCREENSHOT_JS):
        return callback()

    try:
        width, height = get_pedalboard_size(bundlepath)
    except:
        return callback()

    screenshot = os.path.join(bundlepath, "screenshot.png")
    thumbnail  = os.path.join(bundlepath, "thumbnail.png")

    cmd = [PHANTOM_BINARY, SCREENSHOT_JS,
           "http://localhost:%d/pedalboard.html?bundlepath=%s" % (DEVICE_WEBSERVER_PORT, bundlepath),
            screenshot, str(width), str(height)]

    if DEVICE_KEY: # if using a real MOD, setup niceness
        cmd = ["/usr/bin/nice", "-n", "+17"] + cmd

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)

    loop = ioloop.IOLoop.instance()

    def proc_callback(fileno, event):
        if proc.poll() is None:
            return
        loop.remove_handler(fileno)

        if not os.path.exists(screenshot):
            return callback()

        img = Image.open(screenshot)
        resize_image(img)
        img.save(thumbnail)
        img.close()
        callback(thumbnail)

    loop.add_handler(proc.stdout.fileno(), proc_callback, 16)

def resize_image(img):
    width, height = img.size
    if width > MAX_THUMB_WIDTH:
        height = height * MAX_THUMB_WIDTH / width
        width = MAX_THUMB_WIDTH
    if height > MAX_THUMB_HEIGHT:
        width = width * MAX_THUMB_HEIGHT / height
        height = MAX_THUMB_HEIGHT
    img.convert('RGB')
    img.thumbnail((width, height), Image.ANTIALIAS)

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

        generate_screenshot(self.processing, img_callback)

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
