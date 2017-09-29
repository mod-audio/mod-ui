#!/usr/bin/env python

import subprocess, time, json, base64, random, os, shutil, sys, Image
from os.path import join

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DATA_DIR = join(ROOT, 'data')

os.environ['MOD_DEV_ENVIRONMENT'] = os.environ.get("MOD_DEV_ENVIRONMENT", '1')
os.environ['MOD_DATA_DIR'] = DATA_DIR
os.environ['MOD_LOG'] = "1"
os.environ['MOD_KEY_PATH'] = join(ROOT, 'keys')
os.environ['MOD_HTML_DIR'] = join(ROOT, 'html')
os.environ['MOD_DEVICE_WEBSERVER_PORT'] = '8888'
os.environ['MOD_PHANTOM_BINARY'] = join(ROOT, 'phantomjs-1.9.0-linux-x86_64/bin/phantomjs')
os.environ['MOD_SCREENSHOT_JS'] = join(ROOT, 'screenshot.js')

sys.path = [ os.path.dirname(os.path.realpath(__file__)) + '/..' ] + sys.path

from mod.settings import PHANTOM_BINARY, SCREENSHOT_JS
from mod.screenshot import resize_image

record = json.loads(open('/tmp/record.json').read())

record['audio'] = base64.b64decode(record['data'])

tmp_dir = '/tmp/' + ''.join([ random.choice('abcdef0123456789') for i in range(8) ])
mydir = os.getcwd()
os.mkdir(tmp_dir)
os.chdir(tmp_dir)

fps=25

def make_screenshot(pedalboard, start_time, end_time, n=0):
    width=pedalboard.get('width', 1920)
    height=pedalboard.get('height', 1080)

    # FIXME
    open(join(PEDALBOARD__DIR, 'tmp'), 'w').write(json.dumps(pedalboard))
    path = 'shot.png'
    proc = subprocess.Popen([ PHANTOM_BINARY,
                              SCREENSHOT_JS,
                              'http://localhost:8888/pedalboard.html?uid=tmp',
                              path,
                              '%d' % width, '%d' % height
                              ])
    proc.wait()

    img = Image.open(path)
    resize_image(img, width, height)

    count = int((end_time - start_time ) * fps)
    template = 'frame_%d.png'
    img.save(template % n)
    for i in range(n+1, n+count):
        os.link(template % n, template % i)

    return n + count

def get_audio_length(path):
    proc = subprocess.Popen([ 'ffmpeg', '-i', path ],
                            stdout=open('/dev/null', 'w'),
                            stderr=subprocess.PIPE)
    proc.wait()
    for line in proc.stderr:
        line = line.strip()
        if not line.startswith('Duration:'):
            continue
        line = line.split()[1].replace(',', '')
        line = line.split(':')
        return float(line[2]) + int(line[1]) * 60 + int(line[0]) * 3600

audio = 'audio.ogg'
open(audio, 'w').write(record['audio'])
length = get_audio_length(audio)

n = 0
tstamp = 0
events = record['events']
for i in range(len(events)):
    event = events[i]
    start = event['tstamp']
    try:
        end = events[i+1]['tstamp']
    except IndexError:
        end = length
    n = make_screenshot(event['data'], start, end, n)

proc = subprocess.Popen(['ffmpeg',
                         '-i', 'audio.ogg',
                         '-i', 'frame_%d.png',
                         '-r', str(fps),
                         '-vcodec', 'mpeg4',
                         '-acodec', 'copy',
                         '-b', '512k',
                         '-s', '1280x720',
                         'video.mp4' ])
proc.wait()

os.chdir(mydir)
i = 0
template = 'video_%d.mp4'
while os.path.exists(template % i):
    i += 1
shutil.move(join(tmp_dir, 'video.mp4'), template % i)
shutil.rmtree(tmp_dir)
