mod-ui
======

This is the UI for the MOD software. It's a webserver that delivers an HTML5 interface and communicates with mod-host.
It also communicates with the MOD hardware, but does not depend on it to run.

Install
-------

There are instructions for installing in a 64-bit Debian based Linux environment.
It will work in x86, other Linux distributions and Mac, but you might need to adjust the instructions.

The following packages will be required::

    $ sudo apt-get install virtualenv python3-pip python3-dev git build-essential libasound2-dev libjack-jackd2-dev liblilv-dev libjpeg-dev zlib1g-dev

NOTE: libjack-jackd2-dev can be replaced by libjack-dev if you are using JACK1; libjpeg-dev is needed for python-pillow, at least on my system.

Start by cloning the repository::

    $ git clone https://github.com/moddevices/mod-ui.git
    $ cd mod-ui

Create a python virtualenv::

    $ virtualenv modui-env
    $ source modui-env/bin/activate

Install python requirements::

    $ pip3 install -r requirements.txt

Compile libmod_utils::

    $ make -C utils

User files
----------

Create directories to store your files::

    $ mkdir ¨/mod-workdir/user-data
    $ mkdir ¨/mod-workdir/user-data/Audio\ Loops
    $ mkdir ¨/mod-workdir/user-data/Audio\ Recordings
    $ mkdir ¨/mod-workdir/user-data/Audio\ Samples
    $ mkdir ¨/mod-workdir/user-data/Audio\ Tracks
    $ mkdir ¨/mod-workdir/user-data/Speaker\ Cabinets\ IRs
    $ mkdir ¨/mod-workdir/user-data/Hydrogen\ Drumkits
    $ mkdir ¨/mod-workdir/user-data/Reverb\ IRs
    $ mkdir ¨/mod-workdir/user-data/MIDI\ Clips
    $ mkdir ¨/mod-workdir/user-data/MIDI\ Songs
    $ mkdir ¨/mod-workdir/user-data/SF2\ Instruments
    $ mkdir ¨/mod-workdir/user-data/SFZ\ Instruments
    $ mkdir ¨/mod-workdir/user-data/Aida\ DSP\ Models
    $ mkdir ¨/mod-workdir/user-data/NAM\ Models

Run
---

Before running the server, you need to activate your virtualenv
(if you have just done that during installation, you can skip this step, but you'll need to do this again when you open a new shell)::

    $ source modui-env/bin/activate

mod-ui depends on mod-host and the JACK server running in order to make sound. So after you have JACK setup and running, in another terminal do::

    $ mod-host -n -p 5555 -f 5556

If you do not have mod-host, you can tell mod-ui to fake the connection to the audio backend.
You will not get any audio, but you will be able to load plugins, make connections, save pedalboards and all that. For this, run::

    $ export MOD_DEV_HOST=1

And now you are ready to start the webserver::

    $ export MOD_DEV_ENVIRONMENT=0
    $ export MOD_USER_FILES_DIR=¨/mod-workdir/user-data
    $ python3 ./server.py

Setting the environment variables is needed when developing on a PC.
Open your browser and point to http://localhost:8888/.
