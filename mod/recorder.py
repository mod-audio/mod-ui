import os, subprocess, time
from signal import SIGINT
from tornado.ioloop import IOLoop
from mod.settings import CAPTURE_PATH, PLAYBACK_PATH, DEVICE_KEY

class Recorder(object):
    def __init__(self):
        self.recording = False
        self.tstamp = None
        self.proc = None

    def start(self):
        if self.recording:
            self.stop(False)
        self.tstamp = time.time()
        cmd = ['jack_capture', '-f', 'ogg', '-V', '-dc', '-d', '180', '--port', 'mod-monitor:out_1',
                                                                      '--port', 'mod-monitor:out_2', CAPTURE_PATH]
        if DEVICE_KEY: # if using a real MOD, setup niceness
            cmd = ["/usr/bin/nice", "-n", "+1"] + cmd
        self.proc = subprocess.Popen(cmd)
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
        cmd = ['sndfile-jackplay', PLAYBACK_PATH]
        if DEVICE_KEY: # if using a real MOD, setup niceness
            cmd = ["/usr/bin/nice", "-n", "+1"] + cmd
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        self.fhandle = fhandle
        self.stop_callback = stop_callback
        IOLoop.instance().add_handler(self.proc.stdout.fileno(), self.end_callback, 16)

    def end_callback(self, fileno, _):
        self.proc.stdout.read() # just to flush memory
        if self.proc.poll() is None:
            return
        IOLoop.instance().remove_handler(fileno)
        self.fhandle.seek(0)
        self.callback()

    def stop(self):
        if self.proc is None:
            return
        IOLoop.instance().remove_handler(self.proc.stdout.fileno())
        if self.proc.poll() is None:
            self.proc.send_signal(SIGINT)
            self.proc.wait()
        self.proc = None
        self.fhandle.seek(0)
        self.callback()

    def callback(self):
        if self.stop_callback is None:
            return
        cb = self.stop_callback
        self.stop_callback = None
        cb()
