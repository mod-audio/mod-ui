import subprocess, os
from tornado.ioloop import IOLoop
from mod.settings import DEV_HOST

def change_jack_bufsize(size, callback):
    ioloop = IOLoop.instance()

    if size == 0 or DEV_HOST or not command_exists('jack_bufsize'):
        ioloop.add_callback(callback)
        return

    proc = subprocess.Popen(['jack_bufsize','%d' % size],
                            stdout=subprocess.PIPE)

    def check(fileno, event):
        if proc.poll() is None:
            return
        ioloop.remove_handler(fileno)
        callback()

    ioloop.add_handler(proc.stdout.fileno(), check, 16)

def command_exists(cmd):
    paths = os.environ['PATH'].split(':')
    for path in paths:
        if os.path.exists(os.path.join(path, cmd)):
            return True
    return False
