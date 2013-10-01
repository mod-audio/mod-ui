class BrowserControls(object):

    def __init__(self):
        self.values = {}
        self.on = False
        self.callback = None

    def start(self):
        self.on = True
    def end(self):
        self.on = False
        if self.callback:
            self.callback([])
            self.callback = None

    def send(self, instance_id, port_id, value):
        if not self.on:
            return
        self.values[(instance_id, port_id)] = value
        if self.callback:
            self.callback(self.flush())
            self.callback = None

    def flush(self):
        result = []
        for key, value in self.values.items():
            result.append([key[0], key[1], value])
        self.values = {}
        return result

    def wait(self, callback):
        if len(self.values.keys()) > 0:
            callback(self.flush())
        else:
            self.callback = callback
        
