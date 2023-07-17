#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import sys, tornado, time, socket

#from mod.hmi import HMI
#from mod.protocol import Protocol
#from mod.settings import HMI_BAUD_RATE, HMI_SERIAL_PORT
#from tornado import web, options

s = socket.socket()
s.connect(('localhost', 5555))
#s.settimeout(0.2)

fh = open(sys.argv[1])

queue = []

for line in fh:
    sep = '[host] sending -> '
    if sep in line:
        queue.append(line.strip().split(sep)[1])


if len(queue) == 0:
    print "Nothing to send"
    sys.exit(1)

for msg in queue:
    time.sleep(0.05)
    print 'sending:', msg
    s.send(msg)
    resp = s.recv(1024)
    if resp != '':
        print 'resp:', resp

