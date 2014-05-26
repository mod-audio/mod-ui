class Browser(object):

    def __init__(self):
        self.control_values = {}
        self.pedalboard = None
        self.on = False
        self.callback = None

    def start(self):
        self.on = True
    def end(self):
        self.on = False
        if self.callback:
            self.callback([])
            self.callback = None

    def send_control_value(self, instance_id, port_id, value):
        if not self.on:
            return
        self.control_values[(instance_id, port_id)] = value
        if self.callback:
            self.callback(self.flush())
            self.callback = None

    def load_pedalboard(self, pedalboard):
        self.control_values = {}
        if not self.on:
            return
        self.pedalboard = pedalboard
        if self.callback:
            self.callback(self.flush())
            self.callback = None

    def flush(self):
        result = []
        if self.pedalboard is not None:
            result.append(['pedalboard', self.pedalboard])
        for key, value in self.control_values.items():
            result.append(['control', [key[0], key[1], value] ])
        self.control_values = {}
        self.pedalboard = None
        return result

    def wait(self, callback):
        if len(self.control_values.keys()) > 0 or self.pedalboard is not None:
            callback(self.flush())
        else:
            self.callback = callback
        
