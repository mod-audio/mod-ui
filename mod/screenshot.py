
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


import os, subprocess, json, random, shutil
try:
    import Image
except ImportError:
    from PIL import Image

from tornado import ioloop
from mod.settings import (ROOT, HTML_DIR, DEVICE_WEBSERVER_PORT,
                          PEDALBOARD_DIR, PHANTOM_BINARY, SCREENSHOT_JS,
                          MAX_THUMB_HEIGHT, MAX_THUMB_WIDTH)

def get_pedalboard(uid):
    try:
        return json.loads(open(os.path.join(PEDALBOARD_DIR, uid)).read())
    except (IOError, ValueError):
        return None

def generate_screenshot(uid, max_width, max_height, callback):
    if not os.path.exists(PHANTOM_BINARY):
        return callback()
    pedalboard = get_pedalboard(uid)
    if not pedalboard:
        return callback()

    path = '/tmp/%s.png' % ''.join([ random.choice('0123456789abcdefghijklmnopqrstuvwxyz') for i in range(8) ])
    port = DEVICE_WEBSERVER_PORT

    proc = subprocess.Popen([ PHANTOM_BINARY, 
                              SCREENSHOT_JS,
                              'http://localhost:%d/pedalboard.html?uid=%s' % (port, uid),
                              path,
                              str(pedalboard.get('width', max_width)),
                              str(pedalboard.get('height', max_height)),
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

class ThumbnailGenerator(object):

    def __init__(self):
        self.queue = []
        self.processing = False

    def schedule_thumbnail(self, uid):
        uid = str(uid)
        if not uid in self.queue:
            self.queue.append(uid)
        if not self.processing:
            self.process_next()

    def save_pedalboard(self, uid, thumbnail):
        pedalboard = get_pedalboard(uid)
        pedalboard['metadata']['thumbnail'] = thumbnail
        open(os.path.join(PEDALBOARD_DIR, uid), 'w').write(json.dumps(pedalboard))

    def process_next(self):
        if len(self.queue) == 0:
            self.processing = False
            return
        self.processing = True

        uid = self.queue.pop(0)

        def callback(img=None):
            if not img:# or not os.path.exists(tmp_path):
                self.process_next()
                return

            pedalboard = get_pedalboard(uid)
            if pedalboard is None:
                self.process_next()
                return

            thumbnail = 'pedalboards/%s.png' % uid
            path = os.path.join(HTML_DIR, thumbnail)
            img.save(path)
            self.save_pedalboard(uid, thumbnail)
            self.process_next()

        generate_screenshot(uid, MAX_THUMB_WIDTH, MAX_THUMB_HEIGHT, callback)

