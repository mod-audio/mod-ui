# -*- coding: utf-8 -*-

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


import json, os, subprocess, shutil, select
from sha import sha
from os.path import exists, join
from tornado.ioloop import IOLoop
from mod.settings import (INDEX_PATH, EFFECT_DIR, EFFECT_DB_FILE,
                          PLUGIN_LIBRARY_DIR, PLUGIN_INSTALLATION_TMP_DIR)
from mod import indexing

def install_bundle(uid, callback):
    filename = join(PLUGIN_INSTALLATION_TMP_DIR, '%s.tgz' % uid)
    assert exists(filename)

    proc = subprocess.Popen(['tar','zxf', filename],
                            cwd=PLUGIN_INSTALLATION_TMP_DIR,
                            stdout=subprocess.PIPE)


    ioloop = IOLoop.instance()
    
    def install(fileno, event):
        if proc.poll() is None:
            return
        ioloop.remove_handler(fileno)
        os.remove(filename)
        result = install_all_bundles()
        callback(result)

    ioloop.add_handler(proc.stdout.fileno(), install, 16)

def install_all_bundles():
    """
    Install all bundles available in installation temp dir into domain's directory
    Returns list of effects installed
    """
    plugin_dir = PLUGIN_INSTALLATION_TMP_DIR
    effects = []

    # TODO - rewrite for new API without modcommon

    #for package in os.listdir(plugin_dir):
        #bundle_path = join(PLUGIN_LIBRARY_DIR, package)
        #if os.path.exists(bundle_path):
            #uninstall_bundle(package)
        #shutil.move(join(plugin_dir, package), PLUGIN_LIBRARY_DIR)
        #bundle = lv2.Bundle(bundle_path)
        #effects += extract_effects_from_bundle(bundle)
        
    return effects

def extract_effects_from_bundle(bundle):
    index = indexing.EffectIndex()
    effects = []
    for data in bundle.data['plugins'].values():
        remove_old_version(data['url'])
        index.add(data)
        effect_path = join(EFFECT_DIR, data['_id'])
        open(effect_path, 'w').write(json.dumps(data))
        effects.append(data['_id'])
    return effects
        

def remove_old_version(url):
    """
    This will remove old version of a plugin, although it does not remove the
    ttls and binary.
    TODO: we need to keep track of effect binaries and ttls for cleaning
    """
    index = indexing.EffectIndex()
    for effect in index.find(url=url):
        if index.delete(effect['id']):
            path = join(EFFECT_DIR, effect['id'])
            # File is supposed to always be there,
            # but in case it's not, let's have a recoverable state
            if os.path.exists(path):
                os.remove(path)

def uninstall_bundle(package):
    """
    Uninstall a plugin package. Removes the whole bundle directory and
    all effects from filesystem and index
    """
    path = os.path.join(PLUGIN_LIBRARY_DIR, package)
    if not os.path.exists(path):
        return True

    shutil.rmtree(path)

    index = indexing.EffectIndex()
    for effect in index.find(package=package):
        index.delete(effect['id'])
        effect_path = os.path.join(EFFECT_DIR, effect['id'])
        os.remove(effect_path)

        # TODO do something with broken pedalboards, like removing them from banks
        # and marking as broken

    return True
    
