# coding: utf-8

# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@portalmod.com>
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


import multiprocessing

class ReaderProcess(multiprocessing.Process):
    def __init__(self, sp, queue, lock):
        super(ReaderProcess, self).__init__()
        self.sp = sp
        self.queue = queue
        self.lock = lock
        self.serial_data = ""

    def process_msg(self):
        if (self.serial_data.startswith('resp') or 
            self.serial_data.startswith('not found') or 
            self.serial_data.startswith('few ') or 
            self.serial_data.startswith('many '):
            try:
                self.lock.release()
            except:
                # if the lock was already released, this means something is really wrong
                self.serial_data = ""
                return
        self.queue.put(self.serial_data)
        self.serial_data = ""

    def run(self):
        while True:
            # blocks on read()
            data = self.sp.read()
            if data:
                if data == "\0":
                    self.process_msg()
                else:
                    self.serial_data += data


class WriterProcess(multiprocessing.Process):
    def __init__(self, sp, queue, lock, responses):
        super(WriterProcess, self).__init__()
        self.sp = sp
        self.queue = queue
        self.lock = lock
        self.responses = responses

    def run(self):
        while True:
            msg = self.queue.get()
            if msg.startswith('resp'):
                # don't need to wait for lock to be released
                self.sp.write(msg+ "\0")
            else:
                self.lock.acquire()
                self.sp.write(msg+"\0")
                if not self.lock.acquire(True, timeout=1): # waiting for response, 1 second timeout
                    self.responses.put("resp -1")
                self.lock.release()
