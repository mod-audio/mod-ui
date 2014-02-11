import time, subprocess, random, os
from tornado import ioloop
from mod.settings import CAPTURE_PATH

class Recorder(object):

    def __init__(self):
        self.recording = False
        self.tstamp = None
        self.events = None
        self.proc = None

    def start(self, pedalboard):
        if self.recording:
            self.stop()
        self.tstamp = time.time()
        self.pedalboard = pedalboard
        self.events = []
        self.proc = subprocess.Popen(['jack_capture',
                                      '-f', 'ogg',
                                      CAPTURE_PATH],
                                     stdout=open('/dev/null', 'w'),
                                     stderr=open('/dev/null', 'w'))
        self.recording = True
        self.log_pedalboard_state(pedalboard, 0)

    def stop(self):
        if not self.recording:
            return
        self.proc.kill()
        self.recording = False
        result = {
            'pedalboard': self.pedalboard.serialize(),
            'handle': open(CAPTURE_PATH),
            'events': self.events,
            }
        os.remove(CAPTURE_PATH)
        return result

    def event(self, event_type, *data):
        if not self.recording:
            return
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
        self.proc = subprocess.Popen(['mplayer', '-ao', 'jack', '-'],
                                     stdin=fh,
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
        

