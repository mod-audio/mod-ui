#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, urllib2, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from mod.device.register import DeviceRegisterer

try:
    serial = sys.argv[-1].upper()
except IndexError:
    print "Qual o nº de série deste MOD?"
    serial = sys.stdin.readline().strip().upper()

assert serial

device_address = sys.argv[1] if len(sys.argv) > 2 else 'http://192.168.1.50'
cloud_address = sys.argv[2] if len(sys.argv) > 3 else 'http://cloud.portalmod.com'

def urlify(url):
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'http://' + url
    if url.endswith('/'):
        url = url[:-1]
    return url

device_address = urlify(device_address)
cloud_address = urlify(cloud_address)

registration_package = urllib2.urlopen('%s/register/start/%s' % (device_address, serial)).read()

try:
    json.loads(registration_package)
except:
    print "Can't generate registration package"
    sys.exit(1)

response_package = urllib2.urlopen('%s/api/device/register' % cloud_address, registration_package).read()
try:
    json.loads(response_package)
except:
    print "Can't send registration package"
    sys.exit(1)

if not json.loads(response_package)['ok']:
    print "Cloud rejected this serial number (maybe duplicate?)"
    sys.exit(1)

resp = urllib2.urlopen('%s/register/finish' % device_address, response_package).read()
try:
    ok = json.loads(resp)
except:
    print "Can't finish registration"
    sys.exit(1)

if not ok:
    print "Registration error in final phase!"
    sys.exit(1)

print "DEVICE REGISTERED AS %s" % serial
print "To finish registration, go to the following url:"
print "%s/admin/device/%s" % (cloud_address, serial)
