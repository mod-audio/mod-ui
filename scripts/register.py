#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, json, argparse
from urllib.request import urlopen
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

parser = argparse.ArgumentParser(description='Register device at Cloud')
parser.add_argument('--serial', metavar='Serial Nº', type=str,
                    help='The serial number for this device')
parser.add_argument('--cloud', metavar="Cloud address", default='http://cloud.portalmod.com',
                    type=str, help="The URL where cloud can be found")
parser.add_argument('--device', metavar="Device address", default='http://192.168.1.50',
                    type=str, help="The URL where device can be found")

args = parser.parse_args()

if not args.serial:
    print "Qual o nº de série deste MOD?"
    serial = sys.stdin.readline().strip().upper()
else:
    serial = args.serial

assert serial

def urlify(url):
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'http://' + url
    if url.endswith('/'):
        url = url[:-1]
    return url

device_address = urlify(args.device)
cloud_address = urlify(args.cloud)

registration_package = urlopen('%s/register/start/%s' % (device_address, serial)).read()

try:
    json.loads(registration_package)
except:
    print "Can't generate registration package"
    sys.exit(1)

response_package = urlopen('%s/api/device/register' % cloud_address, registration_package).read()
try:
    json.loads(response_package)
except:
    print "Can't send registration package"
    sys.exit(1)

if not json.loads(response_package)['ok']:
    print "Cloud rejected this serial number (maybe duplicate?)"
    sys.exit(1)

resp = urlopen('%s/register/finish' % device_address, response_package).read()
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
