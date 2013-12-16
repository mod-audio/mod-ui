#!/usr/bin/python

import sys
from mod.hmi import HMI
from mod.protocol import Protocol
from mod.settings import HMI_BAUD_RATE, HMI_SERIAL_PORT
from tornado import web, options
import tornado
import serial

fh = open(sys.argv[1])

SEND = 0
ASK = 1

queue = []

for line in fh:
    sep = '[hmi] sending -> '
    if sep in line:
        queue.append((SEND, line.strip().split(sep)[1]))
    if "received <- 'banks" in line:
        queue.append((ASK, "ENTER BANKS MENU"))
    sep = "received <- 'pedalboards "
    if sep in line:
        pid = int(line.split(sep)[1].split('\\x00')[0])
        queue.append((ASK, "ENTER BANK %d" % pid))
    sep = "received <- 'pedalboard "
    if sep in line:
        pid = int(line.split(sep)[1].split()[-1].split('\\x00')[0])
        queue.append((ASK, "ENTER PEDALBOARD %d" % pid))
    

if len(queue) == 0:
    print "Nothing to send"
    sys.exit(1)

hmi = None
def consume(*args):
    if len(queue) == 0:
        print "Queue empty"
        tornado.ioloop.IOLoop.instance().stop()
    action, msg = queue.pop(0)
    if action == SEND:
        print 'sending %s' % msg
        hmi.send(msg, consume)
    elif action == ASK:
        print msg

def reply(*args):
    if len(queue) == 0:
        print "Queue empty"
        tornado.ioloop.IOLoop.instance().stop()
    hmi.send(queue.pop(0)[1])
    consume()

Protocol.register_cmd_callback("banks", reply)
Protocol.register_cmd_callback("pedalboards", reply)
Protocol.register_cmd_callback("pedalboard", reply)

def start():
    print "pinging"
    hmi.ping(consume)

#hmi = HMI(HMI_SERIAL_PORT, HMI_BAUD_RATE, ping)
hmi = HMI(HMI_SERIAL_PORT, HMI_BAUD_RATE, consume)
application = web.Application()
options.parse_command_line()
tornado.ioloop.IOLoop.instance().start()
