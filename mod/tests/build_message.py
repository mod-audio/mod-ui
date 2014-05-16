#!/usr/bin/env python

import sys

"""
This scripts takes in stdin a piece of control_chain documentation and outputs control_chain string messages in format ready for
testing. An example input would be:

| 1| destination     | 00h   |
| 2| origin          | 80h   |
| 3| function        | 03h   |
| 4| data size       | 02h   |
| 5| data size       | 00h   |
| 6| response status | 00h   |
| 7| response status | 00h   |

It also checks the byte number at first column, if it's wrong, the script will break and warn.
"""

string = ''
i = 0
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    char = line.split('|')[3].strip()
    if char.startswith("'"):
        string += char[1]
        i += 1
    if char.endswith('h'):
        string += '\\x%s' % char[:2]
        i += 1
    length = i
    desire = int(line.split('|')[1].strip())
    if not length == desire:
        print line
        print string
        print "Length should be %d, but is %d" % (desire, length)
        sys.exit(1)

print "msg = '%s'" % string
print "self.assertEquals(msg, '%s')" % string
    
        
