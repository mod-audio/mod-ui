import time, subprocess, os, copy, json
from signal import SIGINT
from tornado import ioloop
from mod.settings import CAPTURE_PATH, PLAYBACK_PATH

class Recorder(object):
    def __init__(self):
        self.recording = False
        self.tstamp = None
        self.proc = None

    def start(self):
        if self.recording:
            self.stop(False)
        self.tstamp = time.time()
        self.proc = subprocess.Popen(['jack_capture',
                                      '-f', 'ogg',
                                      '-V', '-dc',
                                      '-d', '65',
                                      '--port', 'mod-host:monitor-out_1',
                                      '--port', 'mod-host:monitor-out_2',
                                      CAPTURE_PATH],
                                     #stdout=open('/tmp/capture.err', 'w'),
                                     #stderr=open('/tmp/capture.out', 'w')
                                     )
        self.recording = True

    def stop(self, returnFileHandle):
        if not self.recording:
            return None
        self.proc.send_signal(SIGINT)
        self.proc.wait()
        self.recording = False
        fhandle = open(CAPTURE_PATH, 'rb') if returnFileHandle else None
        os.remove(CAPTURE_PATH)
        return fhandle

class Player(object):
    def __init__(self):
        self.proc = None
        self.fhandle = None
        self.stop_callback = None

    def play(self, fhandle, stop_callback):
        self.stop()
        fhandle.seek(0)
        with open(PLAYBACK_PATH, 'wb') as fh:
            fh.write(fhandle.read())
        self.proc = subprocess.Popen(['sndfile-jackplay', '-a', 'mod-host:monitor-in_%d', PLAYBACK_PATH],
                                      stdout=subprocess.PIPE)
        self.fhandle = fhandle
        self.stop_callback = stop_callback
        ioloop.IOLoop().instance().add_handler(self.proc.stdout.fileno(), self.end_callback, 16)

    def end_callback(self, fileno, event):
        self.proc.stdout.read() # just to flush memory
        if self.proc.poll() is None:
            return
        ioloop.IOLoop.instance().remove_handler(fileno)
        self.fhandle.seek(0)
        self.callback()

    def stop(self):
        if self.proc is None:
            return
        ioloop.IOLoop.instance().remove_handler(self.proc.stdout.fileno())
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc = None
        self.fhandle.seek(0)
        self.callback()

    def callback(self):
        if self.stop_callback is None:
            return
        cb = self.stop_callback
        self.stop_callback = None
        cb()
