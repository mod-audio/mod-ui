import time, tornado

PERIOD = 1/20.0 # 50ms

class Clipmeter(object):
    def __init__(self, hmi):
        self.hmi = hmi
        self.timeout = None
        self.states = {}

    def set(self, pos, value):
        self.states[pos] = value
        self.flush()

    def flush(self):
        for pos, value in self.states.items():
            if value > 0:
                self.hmi.clipmeter(pos, lambda r: r)
        ioloop = tornado.ioloop.IOLoop.instance()
        if self.timeout:
            ioloop.remove_timeout(self.timeout)
        self.timeout = ioloop.add_timeout(time.time()+PERIOD, self.flush)
            
            

