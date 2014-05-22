#!/usr/bin/env python

import serial, sys, os, fcntl, time

if len(sys.argv) < 2:
    print "socat -d pty,raw,echo=0 pty,raw,echo=0"
    sys.exit(0)

class IHM():
    def __init__(self):
        self.buffer = ''
        self.sp = serial.Serial(sys.argv[1], 500000, timeout=0, writeTimeout=0)
        self.sp.flushInput()
        self.sp.flushOutput()
    
    def receive(self):
        ch = self.sp.read(1)
        while len(ch) == 1:
            if ch == '\0':
                msg = self.buffer
                self.buffer = ''
                return msg
            self.buffer += ch
            ch = self.sp.read(1)
            
    def send(self, message):
        message = self.filter(message)
        print "IHM: -> %s" % message
        self.sp.write(message + '\0')

    def filter(self, message):
        plugins = {
            'filter': 'http://portalmod.com/plugins/caps/AutoFilter',
            'amp': 'http://portalmod.com/plugins/caps/AmpVTS',
            'wider': 'http://portalmod.com/plugins/caps/Wider',
            'eq': 'http://portalmod.com/plugins/caps/Eq10X2',
            }
        if message == 'add':
            return 'stompbox_add http://portalmod.com/plugins/caps/AutoFilter 1'
        elif message.startswith('add'):
            cmd, plugin, slot = message.split()
            plugin = plugins[plugin]
            slot = int(slot)
            return 'stompbox_add %s %d' % (plugin, slot)
        if message == 'clear':
            return 'stompbox_clear'
        elif message.startswith('remove'):
            return 'stompbox_%s' % message
        return message
        
class User():
    def __init__(self):
        self.buffer = ''
        file_num = sys.stdin.fileno()
        old_flags = fcntl.fcntl(file_num, fcntl.F_GETFL)
        fcntl.fcntl(file_num, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)

    def receive(self):
        fd = sys.stdin.fileno()
        try:
            msg = sys.stdin.read()
        except IOError:
            return
        return msg.strip()


user = User()
ihm = IHM()

auto_answers = ('ping',
                'bank_config',
                'ui_con',
                'control_rm',
                )

print "You are IHM"

while True:
    time.sleep(0.001)
    msg = user.receive()
    if msg:
        ihm.send(msg)
    msg = ihm.receive()
    if not msg:
        continue
    print "GOT: <- %s" % msg
    if msg.split()[0] in auto_answers:
        ihm.send('resp 0')
