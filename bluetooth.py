#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess, sys

subprocess.Popen(['sudo', '/bin/true']).wait()

def connect(mac):
    sys.stdout.write('Connecting to %s ' % mac)
    sys.stdout.flush()
    for i in range(10):
        proc = subprocess.Popen(['sudo', 'pand', '-K']).wait()
        proc = subprocess.Popen(['sudo', 'pand', '--connect', mac, '-n'],
                                stderr=subprocess.PIPE)
        proc.wait()
        output = proc.stderr.read()
        if 'bnep0' in output:
            sys.stdout.write('\nConnected\n')
            return True
        sys.stdout.write('.')
        sys.stdout.flush()
    print "Can't connect"
    return False

def get_mac():
    print "Looking for MOD..."
    proc = subprocess.Popen(['sudo', 'hcitool', 'scan'],
                            stdout=subprocess.PIPE)
    proc.wait()
    output = proc.stdout.read()
    result = []
    for line in output.split('\n'):
        if not line.startswith('\t'):
            continue
        if 'quadra' in line.lower() or 'mod' in line.lower():
            result.append(line.strip().split('\t'))

    if len(result) == 1:
        return result[0][0]

    for i, pair in enumerate(result):
        print "%d.\t%s\t%s" % (i, pair[0], pair[1])
    print "\nChoose: "
    return result[int(sys.stdin.readline().strip())][0]

def configure():
    subprocess.Popen(['sudo', 'ifconfig', 'bnep0', '192.168.50.2']).wait()

try:
    mac = sys.argv[1]
except IndexError:
    mac = get_mac()

if connect(mac):
    configure()
        
    
