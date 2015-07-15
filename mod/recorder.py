import time, subprocess, os, copy, json
from tornado import ioloop
from mod.settings import CAPTURE_PATH, PLAYBACK_PATH

class Recorder(object):
    def __init__(self):
        self.recording = False
        self.tstamp = None
        self.events = []
        self.last_event = None
        self.proc = None

    def start(self, client_name):
        if self.recording:
            self.stop()
        self.tstamp = time.time()
        self.events = []
        self.last_event = None
        self.proc = subprocess.Popen(['jack_capture',
                                      '-f', 'ogg',
                                      '-V',
                                      '-d', '65',
                                      '--port', '%s:audio_out_*' % client_name,
                                      CAPTURE_PATH],
                                     stdout=open('/tmp/capture.err', 'w'),
                                     stderr=open('/tmp/capture.out', 'w')
                                     )
        self.recording = True

    def stop(self):
        if not self.recording:
            return
        self.proc.send_signal(2)
        self.proc.wait()
        self.recording = False
        result = {
            'handle': open(CAPTURE_PATH, 'rb'),
            'events': copy.deepcopy(self.events),
        }
        os.remove(CAPTURE_PATH)
        self.events = []
        self.last_event = None
        return result

    def event(self, event_type, *data):
        if not self.recording:
            return
        fingerprint = json.dumps([event_type, data])
        if self.last_event == fingerprint:
            return
        self.last_event = fingerprint
        self.events.append({
                'type': event_type,
                'tstamp': time.time() - self.tstamp,
                'data': data,
                })

    def bypass(self, instance_id, value):
        self.event('bypass', instance_id, value)

    def parameter(self, instance_id, port_id, value):
        self.event('parameter', instance_id, port_id, value)

class Player(object):
    def __init__(self):
        self.proc = None
        self.fh = None
        self.stop_callback = None

    @property
    def playing(self):
        return self.proc is not None

    def play(self, fh, stop_callback):
        if self.playing:
            self.stop()
        fh.seek(0)
        with open(PLAYBACK_PATH, 'wb') as fd:
            fd.write(fh.read())
        self.proc = subprocess.Popen(['sndfile-jackplay', PLAYBACK_PATH],
                                     stdout=subprocess.PIPE)
        self.fh = fh
        self.stop_callback = stop_callback
        ioloop.IOLoop().instance().add_handler(self.proc.stdout.fileno(), self.end_callback, 16)

    def end_callback(self, fileno, event):
        self.proc.stdout.read() # just to flush memory
        if self.proc.poll() is None:
            return
        ioloop.IOLoop.instance().remove_handler(fileno)
        self.fh.seek(0)
        self.callback()

    def stop(self):
        ioloop.IOLoop.instance().remove_handler(self.proc.stdout.fileno())
        if self.proc.poll() is None:
            self.proc.kill()
        self.fh.seek(0)
        self.proc = None
        self.callback()

    def callback(self):
        cb = self.stop_callback
        if cb is not None:
            self.stop_callback = None
            cb()
