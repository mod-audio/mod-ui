import time, subprocess, random, os
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
            'handle': open(CAPTURE_PATH),
            'events': self.events,
            }
        os.remove(CAPTURE_PATH)
        return result

    def log_actuator(self, hwtype, hwid, acttype, actid):
        if not self.recording:
            return
        self.events.append({
                'type': 'actuator',
                'tstamp': time.time() - self.tstamp,
                'data': [ hwtype, hwid, acttype, actid ],
                })

    def log_pedalboard_state(self, pedalboard, tstamp=None):
        if not self.recording:
            return
        if tstamp is None:
            tstamp = time.time() - self.tstamp
        self.events.append({
                'type': 'state',
                'tstamp': tstamp,
                'data': pedalboard.serialize(),
                })
        
