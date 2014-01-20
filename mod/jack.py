import subprocess
from tornado.ioloop import IOLoop

def change_jack_bufsize(size, callback):
    proc = subprocess.Popen(['jack_bufsize','%d' % size],
                            stdout=subprocess.PIPE)
    

    ioloop = IOLoop.instance()
    
    def check(fileno, event):
        if proc.poll() is None:
            return
        ioloop.remove_handler(fileno)
        callback()

    ioloop.add_handler(proc.stdout.fileno(), check, 16)
