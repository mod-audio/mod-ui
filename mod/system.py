# coding: utf-8

# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@moddevices.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from tornado.ioloop import IOLoop
from os.path import join
from mod.settings import LOCAL_REPOSITORY_DIR, BLUETOOTH_PIN

import subprocess, re, glob

def sync_pacman_db(callback):
    proc = subprocess.Popen(['pacman','-Sy'],
                            stdout=subprocess.PIPE)

    ioloop = IOLoop.instance()
    
    def get_package_list(fileno, event):
        if proc.poll() is None:
            return
        ioloop.remove_handler(fileno)
        
        callback(True)

    ioloop.add_handler(proc.stdout.fileno(), get_package_list, 16)

def get_pacman_upgrade_list(callback):
            
        proc = subprocess.Popen(['pacman', '--noconfirm', '-Sup'], 
                            stdout=subprocess.PIPE)

        ioloop = IOLoop.instance()
        
        def process(fileno, event):
            if proc.poll() is None:
                return
            ioloop.remove_handler(fileno)
 
            result = [ re.sub(r'.*://.*/', '', line) 
                            for line in proc.stdout.read().split() if "://" in line ]
            if len(result) == 0:
                subprocess.Popen(['rm'] + glob.glob(join(LOCAL_REPOSITORY_DIR, "*tar*")))
            callback(result)

        ioloop.add_handler(proc.stdout.fileno(), process, 16)

def pacman_upgrade(callback):
        proc = subprocess.Popen(['pacman', '--noconfirm', '-Su'], 
                            stdout=subprocess.PIPE)

        ioloop = IOLoop.instance()
        
        def process(fileno, event):
            if proc.poll() is None:
                return
            ioloop.remove_handler(fileno)

            subprocess.Popen(['rm'] + glob.glob(join(LOCAL_REPOSITORY_DIR, "*tar*")))
            callback(True)

        ioloop.add_handler(proc.stdout.fileno(), process, 16)

def get_pacman_install_list(pkg, callback):
        proc = subprocess.Popen(['pacman', '--noconfirm', '-Sp', pkg], 
                            stdout=subprocess.PIPE)

        ioloop = IOLoop.instance()
        
        def process(fileno, event):
            if proc.poll() is None:
                return
            ioloop.remove_handler(fileno)
 
            result = [ re.sub(r'.*://.*/', '', line) 
                            for line in proc.stdout.read().split() if "://" in line ]
            if len(result) == 0:
                subprocess.Popen(['rm'] + glob.glob(join(LOCAL_REPOSITORY_DIR, "*tar*")))
            callback(result)

        ioloop.add_handler(proc.stdout.fileno(), process, 16)


def pacman_install(pkg, callback):
        proc = subprocess.Popen(['pacman', '--noconfirm', '-S', pkg], 
                            stdout=subprocess.PIPE)

        ioloop = IOLoop.instance()
        
        def process(fileno, event):
            if proc.poll() is None:
                return
            ioloop.remove_handler(fileno)

            subprocess.Popen(['rm'] + glob.glob(join(LOCAL_REPOSITORY_DIR, "*tar*")))
            callback(True)

        ioloop.add_handler(proc.stdout.fileno(), process, 16)


def set_bluetooth_pin(pin, callback):
    f = open(BLUETOOTH_PIN, 'w')
    f.write(pin)
    f.close()
    callback(True)
