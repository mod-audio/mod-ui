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
import argparse
import base64
import json
import os

from enum import Enum
from PIL import Image

from modtools.utils import init as lv2_init, get_pedalboard_info, get_plugin_info, get_plugin_gui

MAX_THUMB_HEIGHT = 640
MAX_THUMB_WIDTH = 640
__version__ = '1.0.0'


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


class Anchor(Enum):
    LEFT_CENTER = 1
    RIGHT_CENTER = 2


def rint(x):
    return int(round(x))


def anchor(size, x, y, align: Anchor):
    if align == Anchor.LEFT_CENTER:
        y = rint(y - size[1] / 2)
    elif align == Anchor.RIGHT_CENTER:
        y = rint(y - size[1] / 2)
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


def take_screenshot(bundle_path, html_dir, cache_dir, size):
    os.makedirs(cache_dir, exist_ok=True)
    lv2_init()
    pb = get_pedalboard_info(bundle_path)

    if size:
        w, h = size.split('x')
        width, height = int(w), int(h)
    else:
        width, height = pb['width'],  pb['height']
    if (width, height) == (0, 0):
        width, height = 3840, 2160

    img_dir = os.path.join(html_dir, 'img')

    # preload images
    audio_input_img = Image.open(os.path.join(img_dir, 'audio-input.png'))
    audio_output_img = Image.open(os.path.join(img_dir, 'audio-output.png'))
    audio_input_connected = Image.open(os.path.join(img_dir, 'audio-input-connected.png'))
    audio_output_connected = Image.open(os.path.join(img_dir, 'audio-output-connected.png'))
    midi_input_img = Image.open(os.path.join(img_dir, 'midi-input.png'))
    midi_output_img = Image.open(os.path.join(img_dir, 'midi-output.png'))
    midi_input_connected = Image.open(os.path.join(img_dir, 'midi-input-connected.png'))
    midi_output_connected = Image.open(os.path.join(img_dir, 'midi-output-connected.png'))
    default_screenshot = Image.open(os.path.join(html_dir, 'resources', 'pedals', 'default.png'))

    right_padding = audio_input_connected.size[0] * 2
    bottom_padding = right_padding

    # create capture/playback connectors
    device_capture = []
    for ix in range(0, pb['hardware']['audio_ins']):
        device_capture.append({
            'symbol': 'capture_{0}'.format(ix + 1),
            'img': audio_output_img,
            'connected_img': audio_output_connected,
            'type': 'audio',
        })
    if pb['hardware'].get('serial_midi_in', False):
        device_capture.append({
            'symbol': 'serial_midi_in',
            'img': midi_output_img,
            'connected_img': midi_output_connected,
            'type': 'midi',
        })
    for midi_in in pb['hardware']['midi_ins']:
        device_capture.append({
            'symbol': midi_in['symbol'],
            'img': midi_output_img,
            'connected_img': midi_output_connected,
            'type': 'midi',
        })

    device_playback = []
    for ix in range(0, pb['hardware']['audio_outs']):
        device_playback.append({
            'symbol': 'playback_{0}'.format(ix + 1),
            'img': audio_input_img,
            'connected_img': audio_input_connected,
            'type': 'audio',
        })
    if pb['hardware'].get('serial_midi_out', False):
        device_playback.append({
            'symbol': 'serial_midi_out',
            'img': midi_input_img,
            'connected_img': midi_input_connected,
            'type': 'midi',
        })
    for midi_out in pb['hardware']['midi_outs']:
        device_playback.append({
            'symbol': midi_out['symbol'],
            'img': midi_input_img,
            'connected_img': midi_input_connected,
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
        screenshot_path = gui.get('screenshot', None)
        pimg = Image.open(screenshot_path).convert('RGBA') if screenshot_path else default_screenshot
        p['img'] = pimg

        if screenshot_path:
            # detect ports and save/read
            version = '{0}.{1}'.format(data['version'], data.get('release', 0)).replace('.', '_')
            encoded_uri = base64.b64encode(p['uri'].encode()).decode()
            filename = os.path.join(cache_dir, '{0}_{1}_{2}'.format(__version__.replace('.', '_'), encoded_uri, version))
            if os.path.isfile(filename):
                with open(filename, 'r') as fh:
                    columns = json.loads(fh.read())
            else:
                columns = {
                    'in_ports': [list(c) for c in detect_first_column(pimg, pimg.size[0])],
                    'out_ports': [list(c) for c in detect_first_column(pimg, pimg.size[0], rtol=True)],
                }
                with open(filename, 'w') as fh:
                    fh.write(json.dumps(columns))
        else:  # tuna can, we have to guess the position of the connectors
            columns = {
                'in_ports': [[-9, 121], [-9, 146], [-9, 190], [-9, 215], [-9, 259], [-9, -284], [-9, 328], [-9, 353]],
                'out_ports': [[259, 121], [259, 146], [259, 190], [259, 215], [259, 259], [259, 284], [259, 328], [259, 353]]
            }

        # detect connectors
        in_ports = data['ports']['audio']['input'] + data['ports']['midi']['input']
        if len(in_ports) > 0:
            for ix, conn in enumerate(chunks(columns['in_ports'], 2)):
                if ix < len(in_ports):
                    in_ports[ix]['connector'] = conn
                    if ix < len(data['ports']['audio']['input']):
                        in_ports[ix]['connected_img'] = audio_input_connected
                        in_ports[ix]['offset'] = (79, 15)
                        in_ports[ix]['type'] = 'audio'
                    else:
                        in_ports[ix]['connected_img'] = midi_input_connected
                        in_ports[ix]['offset'] = (67, 9)
                        in_ports[ix]['type'] = 'midi'
            if not all('connector' in p for p in in_ports):
                raise Exception('Connector detection for input ports of plugin {0} failed'.format(p['uri']))
        out_ports = data['ports']['audio']['output'] + data['ports']['midi']['output']
        if len(out_ports) > 0:
            for ix, conn in enumerate(chunks(columns['out_ports'], 2)):
                if ix < len(out_ports):
                    out_ports[ix]['connector'] = conn
                    if ix < len(data['ports']['audio']['output']):
                        out_ports[ix]['connected_img'] = audio_output_connected
                        out_ports[ix]['offset'] = (8, 15)
                        out_ports[ix]['type'] = 'audio'
                    else:
                        out_ports[ix]['connected_img'] = midi_output_connected
                        out_ports[ix]['offset'] = (8, 9)
                        out_ports[ix]['type'] = 'midi'
            if not all('connector' in p for p in out_ports):
                raise Exception('Connector detection for output ports of plugin {0} failed'.format(p['uri']))

        plugin_map[p['instance']] = p

    # calculate image size
    height = 0
    for p in plugins:
        if p['x'] + p['img'].size[0] + right_padding > width:
            width = p['x'] + p['img'].size[0] + right_padding
        if p['y'] + p['img'].size[1] + bottom_padding > height:
            height = p['y'] + p['img'].size[1] + bottom_padding
    width = rint(width)
    height = rint(height) or rint(1112)

    # calculate device connectors positions
    used_symbols = [c['source'] for c in pb['connections']] + [c['target'] for c in pb['connections']]
    device_capture = [
        d for d in device_capture
        if d['type'] == 'audio' or d['symbol'] == 'serial_midi_in' or d['symbol'] in used_symbols
    ]
    device_playback = [
        d for d in device_playback
        if d['type'] == 'audio' or d['symbol'] == 'serial_midi_out' or d['symbol'] in used_symbols
    ]
    step = rint(height / (len(device_capture) + 1))
    h = step
    for d in device_capture:
        d.update({'x': 0, 'y': h})
        h = h + step
    h = step
    for d in device_playback:
        d.update({'x': width, 'y': h})
        h = h + step

    # draw plugin cables and calculate connectors
    connectors = []
    paths = []
    for ix, c in enumerate(pb['connections']):
        # source
        source = next((s for s in device_capture if s['symbol'] == c['source']), None)
        if source:
            source_connected_img = source['connected_img']
            source_pos = anchor(source_connected_img.size, source['x'], source['y'], Anchor.LEFT_CENTER)
            source_x = source['x'] + source_connected_img.size[0]
            source_y = source['y']
            source_type = source['type']
        else:
            if '/' not in c['source']:
                continue
            source_i, source_s = c['source'].split('/')
            source = plugin_map[source_i]
            all_ports = source['data']['ports']['audio']['output'] + source['data']['ports']['midi']['output']
            port = next(p for p in all_ports if p['symbol'] == source_s)
            conn = port['connector']
            source_connected_img = port['connected_img']
            source_pos = (source['x'] + conn[0][0] - port['offset'][0], source['y'] + conn[0][1] - port['offset'][1])
            source_x = source_pos[0] + source_connected_img.size[0]
            source_y = source_pos[1] + source_connected_img.size[1] / 2
            source_type = port['type']
        # target
        target = next((t for t in device_playback if t['symbol'] == c['target']), None)
        if target:
            target_connected_img = target['connected_img']
            target_pos = anchor(target_connected_img.size, target['x'], target['y'], Anchor.RIGHT_CENTER)
            target_x = target['x'] - target_connected_img.size[0]
            target_y = target['y']
            target_type = target['type']
        else:
            if '/' not in c['target']:
                continue
            target_i, target_s = c['target'].split('/')
            target = plugin_map[target_i]
            all_ports = target['data']['ports']['audio']['input'] + target['data']['ports']['midi']['input']
            port = next(p for p in all_ports if p['symbol'] == target_s)
            conn = port['connector']
            target_connected_img = port['connected_img']
            target_pos = (target['x'] + conn[0][0] - port['offset'][0], target['y'] + conn[0][1] - port['offset'][1])
            target_x = target_pos[0]
            target_y = target_pos[1] + target_connected_img.size[1] / 2
            target_type = port['type']

        delta_x = target_x - source_x - 50
        if delta_x < 0:
            delta_x = 8.5 * (delta_x / 6)
        else:
            delta_x /= 1.5

        path = 'm{0},{1} c{2},{3},{4},{5},{6},{7}'.format(
            rint(source_x),
            rint(source_y),
            rint(target_x - delta_x - source_x),
            0,
            rint(delta_x),
            rint(target_y - source_y),
            rint(target_x - source_x),
            rint(target_y - source_y)
        )
        paths.append((path, source_type, target_type))
        connectors.append((source_connected_img, (rint(source_pos[0]), rint(source_pos[1])), source_connected_img))
        connectors.append((target_connected_img, (rint(target_pos[0]), rint(target_pos[1])), target_connected_img))

    # create image
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    # draw device connectors
    for d in device_capture:
        img.paste(d['img'], anchor(d['img'].size, d['x'], d['y'], Anchor.LEFT_CENTER))
    for d in device_playback:
        img.paste(d['img'], anchor(d['img'].size, d['x'], d['y'], Anchor.RIGHT_CENTER))

    # draw all paths
    try:
        import aggdraw
        draw = aggdraw.Draw(img)
        audio_pen = aggdraw.Pen('#81009A', 7)
        midi_pen = aggdraw.Pen('#00546C', 7)
        for path, source_type, target_type in paths:
            symbol = aggdraw.Symbol(path)
            draw.symbol((0, 0), symbol, midi_pen if source_type == 'midi' or target_type == 'midi' else audio_pen)
        draw.flush()
    except:
        print('Aggdraw failed')

    # draw all connectors
    for c in connectors:
        img.paste(*c)

    # draw plugins
    for p in plugins:
        img.paste(p['img'], (rint(p['x']), rint(p['y'])), p['img'])

    img.save(os.path.join(bundle_path, 'screenshot.png'), compress_level=3)
    resize_image(img)
    img.save(os.path.join(bundle_path, 'thumbnail.png'))
    img.close()


def main():
    parser = argparse.ArgumentParser(description='Pedalboard tools')
    subparsers = parser.add_subparsers()

    # take screenshot bundle_path, html_dir, cache_dir
    def _take_screenshot(args):
        take_screenshot(args.pedalboard_path, args.html_path, args.cache_path, args.size)

    subparser = subparsers.add_parser('take_screenshot', help='Take a screenshot of a given pedalboard')
    subparser.add_argument('pedalboard_path', help='Path to pedalboard bundle folder')
    subparser.add_argument('html_path', help='Path to mod-ui HTML folder')
    subparser.add_argument('cache_path', help='Path to cache folder')
    subparser.add_argument('-s', '--size', help='Screenshot width and height (i.e. 800x600)')
    subparser.set_defaults(func=_take_screenshot)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
        exit(0)
    else:
        parser.print_usage()


if __name__ == '__main__':
    main()
