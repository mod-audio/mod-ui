mod-ui
======

This is the UI for the MOD software. It's a webserver that delivers an HTML5 interface and communicates with mod-host.
It also communicates with the MOD hardware, but does not depend on it to run.

Install
-------

There are instructions for installing in a 64-bit Debian based Linux environment.
It will work in x86, other Linux distributions and Mac, but you might need to adjust the instructions.

The following packages will be required::

    $ sudo apt-get install python-virtualenv python3-pip python3-dev git build-essential liblilv-dev

Start by cloning the repository::

    $ git clone git://github.com/moddevices/mod-ui
    $ cd mod-ui

Create a python virtualenv::

    $ virtualenv modui-env
    $ source modui-env/bin/activate

Install python requirements::

    $ pip3 install -r requirements.txt

Compile libmod_utils::

    $ cd utils
    $ make
    $ cd ..

Run
---

Before running the server, you need to activate your virtualenv
(if you have just done that during installation, you can skip this step, but you'll need to do this again when you open a new shell)::

    $ source modui-env/bin/activate

Mod-ui depends on mod-host and the JACK server running. So run::
  
    $ jack_control start  # or your prefered way to get JACK running
 
Then in another terminal::
 
    $ ./mod-host -n -p 5555 -f 5556

And now you are ready to start the webserver:
  
    $ MOD_APP=1 MOD_LIVE_ISO=1 MOD_DEV_ENVIRONMENT=0 ./server.py

Setting the environment variables is needed when developing on a PC.
Open your webkit based browser (I use Chromium) and point to
http://localhost:8888.
