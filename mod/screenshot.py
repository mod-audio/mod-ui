
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


import os, subprocess, json

try:
    import Image
except ImportError:
    from PIL import Image

from tornado import ioloop
from mod.lilvlib import get_pedalboard_info
from mod.settings import (DEVICE_WEBSERVER_PORT,
                          PHANTOM_BINARY, SCREENSHOT_JS,
                          MAX_THUMB_HEIGHT, MAX_THUMB_WIDTH)

def generate_screenshot(bundlepath, max_width, max_height, callback):
    if not os.path.exists(PHANTOM_BINARY):
        return callback()
    #try: # TESTING let us receive exceptions for now
    pedalboard = get_pedalboard_info(bundlepath)
    #except:
        #return callback()

    path = '%s/screenshot.png' % bundlepath
    port = DEVICE_WEBSERVER_PORT

    proc = subprocess.Popen([ PHANTOM_BINARY,
                              SCREENSHOT_JS,
                              'http://localhost:%d/pedalboard.html?bundlepath=%s' % (port, bundlepath),
                              path,
                              str(pedalboard['size']['width']),
                              str(pedalboard['size']['height']),
                             ],
                            stdout=subprocess.PIPE)

    def handle_image():
        img = Image.open(path)
        resize_image(img, max_width, max_height)
        callback(img)

    loop = ioloop.IOLoop.instance()

    def proc_callback(fileno, event):
        if proc.poll() is None:
            return
        loop.remove_handler(fileno)
        handle_image()

    loop.add_handler(proc.stdout.fileno(), proc_callback, 16)

def resize_image(img, max_width, max_height):
        width, height = img.size
        if width > max_width:
            height = height * max_width / width
            width = max_width
        if height > max_height:
            width = width * max_height / height
            height = max_height
        img.convert('RGB')
        img.thumbnail((width, height), Image.ANTIALIAS)

class ScreenshotGenerator(object):
    def __init__(self):
        self.queue = []
        self.processing = False

    def schedule_screenshot(self, bundlepath):
        if not bundlepath in self.queue:
            self.queue.append(bundlepath)
        if not self.processing:
            self.process_next()

    def process_next(self):
        if len(self.queue) == 0:
            self.processing = False
            return
        self.processing = True

        bundlepath = self.queue.pop(0)

        def callback(img=None):
            if not img:
                self.process_next()
                return

            path = os.path.join(bundlepath, 'thumbnail.png')
            img.save(path)

            self.process_next()

        generate_screenshot(bundlepath, MAX_THUMB_WIDTH, MAX_THUMB_HEIGHT, callback)

    def wait_for_pending_jobs(self):
        from time import sleep
        while self.processing:
            sleep(0.5)
