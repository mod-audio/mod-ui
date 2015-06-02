mod-ui
======

This is the UI for the MOD software. It's a webserver that delivers an HTML 5 interface and communicates with Ingen. It also communicates with the MOD hardware, but does not depend on it to run.

Install
-------

There are instructions for installing in a 64-bit Debian based Linux environment. It will work in x86, other Linux distributions and Mac, but you might need to adjust the instructions.

The following packages will be required::

    $ sudo apt-get install python-virtualenv python3-pip python3-dev git zlib1g:amd64 build-essential

You also need to install `python3-lilv` from KXStudio repositories. Please, follow
the [KXStudio instructions](http://kxstudio.sourceforge.net/Repositories).

Start by cloning the repository::

    $ git clone --recursive https://github.com/portalmod/mod-ui.git
    $ cd mod-ui

Create a python virtualenv::

    $ virtualenv modui-env
    $ source modui-env/bin/activate

Create the symlink below, that is required by PIL for PNG support::

    $ sudo ln -s /usr/lib/x86_64-linux-gnu/libz.so /usr/lib/

Install python requirements::

    $ pip3 install -r requirements.txt

Download PhantomJS::

    $ wget https://phantomjs.googlecode.com/files/phantomjs-1.9.0-linux-x86_64.tar.bz2
    $ tar jxf phantomjs-1.9.0-linux-x86_64.tar.bz2
    $ rm phantomjs-1.9.0-linux-x86_64.tar.bz2

Run
---

Before running the server, you need to activate your virtualenv (if you have just done that during installation, you can skip this step, but you'll need to do this again when you open a new shell)::

    $ source modui-env/bin/activate

Run the server::

    $ ./server.py

Open your webkit based browser (I use Chromium) and point to http://localhost:8888
