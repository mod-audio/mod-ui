
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

from tornado import ioloop
from psutil import Process
import socket, functools, json
import psutil


PS=[]
def update_process_list():
    global PS
    plist = []
    for pid in psutil.get_pid_list():
        try:
            p = Process(pid)
            plist.append((p,p.get_cpu_percent(),p.get_memory_percent())) 
        except psutil.NoSuchProcess:
            continue
    # copy plist to PS
    PS = sorted(plist[:], key=lambda e: e[1] if e[1] > e[2] else e[2], reverse=True)[:25]

def process_stats():
    pslist = []
    for p, cpu, mem in PS:
        try:
            pslist.append({'pid': p.pid, 
                            'name': p.name, 
                            'cpu': float("%.2f" % p.get_cpu_percent(0)), 
                            'mem': float("%.2f" % p.get_memory_percent())})
        except psutil.NoSuchProcess:
            continue
    return sorted(pslist, key=lambda p:p['cpu'], reverse=True)

def connection_ready(sock, fd, events):
    while True:
        try:
            connection, address = sock.accept()
        except socket.error as e:
            if e.args[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise
            return
        connection.setblocking(0)
        connection.send(json.dumps({'ps': process_stats(), 'total_cpu': "%.2f" % psutil.cpu_percent()})+"\0")
        connection.close()
        return

if __name__ == "__main__":
    import thread
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(0)
    sock.bind(("", 57890))
    sock.listen(128)

    io = ioloop.IOLoop.instance()
    cb = functools.partial(connection_ready, sock)
    io.add_handler(sock.fileno(), cb, io.READ)
    ioloop.PeriodicCallback(lambda: thread.start_new_thread(update_process_list,()), 30000, io_loop=io).start()
    update_process_list()
    io.start()
