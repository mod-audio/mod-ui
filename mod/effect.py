# -*- coding: utf-8 -*-

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


import json, os, subprocess, shutil, select
from hashlib import sha1 as sha
from os.path import exists, join
from tornado.ioloop import IOLoop
from mod.settings import DOWNLOAD_TMP_DIR

def remove_old_version(uri):
    """
    This will remove old version of a plugin, although it does not remove the
    ttls and binary.
    TODO: we need to keep track of effect binaries and ttls for cleaning
    """
    return

def uninstall_package(package):
    """
    Uninstall a plugin package. Removes the whole bundle directory and
    all effects from filesystem and index
    """
    return True

