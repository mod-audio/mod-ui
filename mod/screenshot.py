
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


import os
from enum import Enum

try:
    import Image
except ImportError:
    from PIL import Image

from mod.utils import get_pedalboard_info, get_plugin_info, get_plugin_gui
from mod.settings import MAX_THUMB_HEIGHT, MAX_THUMB_WIDTH, HTML_DIR


def generate_screenshot(bundlepath, callback):
    pb = get_pedalboard_info(bundlepath)

    width = pb['width']
    height = pb['height']
    if (width, height) == (0, 0):
        raise Exception('Invalid pb size (0,0)')

    class Anchor(Enum):
        LEFT_CENTER = 1
        RIGHT_CENTER = 2

    def anchor(size, x, y, align: Anchor):
        if align == Anchor.LEFT_CENTER:
            y = int(round(y - size[1] / 2))
        elif align == Anchor.RIGHT_CENTER:
            y = int(round(y - size[1] / 2))
            x = x - size[0]
        return x, y

    def rgbtoi(r, g, b):
        return (r << 16) + (g << 8) + b

    def detect_first_column(img, scan=20, rtol=False):
        was_zero = True
        found = False
        for _i in range(0, scan):
            i = img.size[0] - _i - 1 if rtol else _i
            for j in range(0, img.size[1]):
                pixel = img.getpixel((i, j))
                is_zero = rgbtoi(*pixel[0:3]) == 0
                if was_zero != is_zero:
                    yield i, j
                    was_zero = is_zero
                    found = True
            if found:
                return

    def chunks(l, n):
        o = list(l) if type(l) is not list else l
        for i in range(0, len(o), n):
            yield o[i:i + n]

    def all_ports(data, type):
        for port in data['ports']['audio'][type]:
            yield port
        for port in data['ports']['midi'][type]:
            yield port

    img_dir = os.path.join(HTML_DIR, 'img')

    # preload images
    audio_output_img = Image.open(os.path.join(img_dir, 'audio-output.png'))
    audio_input_img = Image.open(os.path.join(img_dir, 'audio-input.png'))
    midi_output_img = Image.open(os.path.join(img_dir, 'midi-output.png'))
    midi_input_img = Image.open(os.path.join(img_dir, 'midi-input.png'))
    audio_input_connected = Image.open(os.path.join(img_dir, 'audio-input-connected.png'))
    audio_output_connected = Image.open(os.path.join(img_dir, 'audio-output-connected.png'))

    right_padding = audio_input_connected.size[0] * 2
    bottom_padding = 0

    # create capture/playback connectors
    device_capture = []
    for ix in range(0, pb['hardware']['audio_ins']):
        device_capture.append({
            'symbol': 'capture_{0}'.format(ix + 1),
            'img': audio_output_img,
            'type': 'audio',
        })
    for midi_in in pb['hardware']['midi_ins']:
        device_capture.append({
            'symbol': midi_in['symbol'],
            'img': midi_output_img,
            'type': 'midi',
        })

    device_playback = []
    for ix in range(0, pb['hardware']['audio_outs']):
        device_playback.append({
            'symbol': 'playback_{0}'.format(ix + 1),
            'img': audio_input_img,
            'type': 'audio',
        })
    for midi_out in pb['hardware']['midi_outs']:
        device_playback.append({
            'symbol': midi_out['symbol'],
            'img': midi_input_img,
            'type': 'midi',
        })

    # create plugins
    plugins = pb['plugins']
    plugin_map = {}
    for p in plugins:
        # read plugin data
        data = get_plugin_info(p['uri'])
        p['data'] = data

        # read plugin image
        gui = get_plugin_gui(p['uri'])
        pimg = Image.open(gui['screenshot'])
        p['img'] = pimg

        # detect connectors
        in_ports = list(all_ports(data, 'input'))
        for ix, conn in enumerate(chunks(detect_first_column(pimg), 2)):
            in_ports[ix]['connector'] = conn
        out_ports = list(all_ports(data, 'output'))
        for ix, conn in enumerate(chunks(detect_first_column(pimg, rtol=True), 2)):
            out_ports[ix]['connector'] = conn

        plugin_map[p['instance']] = p

    # calculate image size
    for p in plugins:
        if p['x'] + p['img'].size[0] + right_padding > width:
            width = p['x'] + p['img'].size[0] + right_padding
        if p['y'] + p['img'].size[1] + bottom_padding > height:
            height = p['y'] + p['img'].size[1] + bottom_padding

    # create image
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    # draw device connectors
    step = int(round(height / (len(device_capture) + 1)))
    h = step
    for d in device_capture:
        d.update({'x': 0, 'y': h})
        h = h + step
        if d['type'] == 'audio':
            img.paste(audio_output_img, anchor(audio_output_img.size, d['x'], d['y'], Anchor.LEFT_CENTER))
        elif d['type'] == 'midi':
            img.paste(midi_output_img, anchor(midi_output_img.size, d['x'], d['y'], Anchor.LEFT_CENTER))
    h = step
    for d in device_playback:
        d.update({'x': width, 'y': h})
        h = h + step
        if d['type'] == 'audio':
            img.paste(audio_input_img, anchor(audio_input_img.size, d['x'], d['y'], Anchor.RIGHT_CENTER))
        elif d['type'] == 'midi':
            img.paste(midi_input_img, anchor(midi_input_img.size, d['x'], d['y'], Anchor.RIGHT_CENTER))

    # draw plugin cables and calculate connectors
    connectors = []
    paths = []
    for ix, c in enumerate(pb['connections']):
        if any(s['symbol'] == c['source'] for s in device_capture):
            source = next(s for s in device_capture if s['symbol'] == c['source'])
            source_pos = anchor(audio_output_connected.size, source['x'], source['y'], Anchor.LEFT_CENTER)
            source_x = source['x'] + audio_output_connected.size[0]
            source_y = source['y']
        else:
            if not '/' in c['source']:
                continue
            source_i, source_s = c['source'].split('/')
            source = plugin_map[source_i]
            port = next(p for p in all_ports(source['data'], 'output') if p['symbol'] == source_s)
            conn = port['connector']
            source_pos = (source['x'] + conn[0][0] - 8, source['y'] + conn[0][1] - 15)
            source_x = source_pos[0] + audio_output_connected.size[0]
            source_y = source_pos[1] + audio_input_connected.size[1] / 2
        if any(s['symbol'] == c['target'] for s in device_playback):
            target = next(t for t in device_playback if t['symbol'] == c['target'])
            target_pos = anchor(audio_input_connected.size, target['x'], target['y'], Anchor.RIGHT_CENTER)
            target_x = target['x'] - audio_input_connected.size[0]
            target_y = target['y']
        else:
            if not '/' in c['target']:
                continue
            target_i, target_s = c['target'].split('/')
            target = plugin_map[target_i]
            port = next(p for p in all_ports(target['data'], 'input') if p['symbol'] == target_s)
            conn = port['connector']
            target_pos = (target['x'] + conn[0][0] - 79, target['y'] + conn[0][1] - 15)
            target_x = target_pos[0]
            target_y = target_pos[1] + audio_input_connected.size[1] / 2

        deltaX = target_x - source_x - 50
        if deltaX < 0:
            deltaX = 8.5 * (deltaX / 6)
        else:
            deltaX /= 1.5

        path = 'm{0},{1} c{2},{3},{4},{5},{6},{7}'.format(
            int(round(source_x)),
            int(round(source_y)),
            int(round(target_x - deltaX - source_x)),
            0,
            int(round(deltaX)),
            int(round(target_y - source_y)),
            int(round(target_x - source_x)),
            int(round(target_y - source_y))
        )
        paths.append(path)
        connectors.append((audio_output_connected, (int(round(source_pos[0])), int(round(source_pos[1]))), audio_output_connected))
        connectors.append((audio_input_connected, (int(round(target_pos[0])), int(round(target_pos[1]))), audio_input_connected))

    # draw all paths
    try:
        import aggdraw
        draw = aggdraw.Draw(img)
        outline = aggdraw.Pen('#81009A', 7)
        for path in paths:
            symbol = aggdraw.Symbol(path)
            draw.symbol((0, 0), symbol, outline)
            draw.flush()
    except:
        print('Aggdraw failed')

    # draw all connectors
    for c in connectors:
        img.paste(*c)

    # draw plugins
    for p in plugins:
        img.paste(p['img'], (int(round(p['x'])), int(round(p['y']))), p['img'])

    screenshot = os.path.join(bundlepath, 'screenshot.png')
    thumbnail = os.path.join(bundlepath, 'thumbnail.png')
    img.save(screenshot)
    resize_image(img)
    img.save(thumbnail)
    img.close()

    callback(thumbnail)


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

        try:
            generate_screenshot(self.processing, img_callback)
        except Exception as ex:
            print('ERROR: {0}'.format(ex))
            img_callback()

    def check_screenshot(self, bundlepath):
        bundlepath = os.path.abspath(bundlepath)

        if bundlepath in self.queue or self.processing == bundlepath:
            return (0, 0.0)

        thumbnail = os.path.join(bundlepath, "thumbnail.png")
        if not os.path.exists(thumbnail):
            return (-1, 0.0)

        ctime = os.path.getctime(thumbnail)
        return (1, ctime)

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
