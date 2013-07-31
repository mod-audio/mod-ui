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
from mod.settings import (INDEX_PATH, EFFECT_DIR, EFFECT_DB_FILE, FAVORITES_DIR, 
                          PLUGIN_LIBRARY_DIR, PLUGIN_INSTALLATION_TMP_DIR,
                          UNITS_TTL_PATH)
from modcommon import json_handler, lv2
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

    for package in os.listdir(plugin_dir):
        bundle_path = join(PLUGIN_LIBRARY_DIR, package)
        if os.path.exists(bundle_path):
            uninstall_bundle(package)
        shutil.move(join(plugin_dir, package), PLUGIN_LIBRARY_DIR)
        bundle = lv2.Bundle(bundle_path, units_file=UNITS_TTL_PATH)
        for data in bundle.data['plugins'].values():
            favorite = join(FAVORITES_DIR, sha(data['url']).hexdigest())
            if os.path.exists(favorite):
                data['score'] = json.loads(open(favorite).read())
            remove_old_version(data['url'])
            indexing.EffectIndex().add(data)
            effect_path = join(EFFECT_DIR, data['_id'])
            open(effect_path, 'w').write(json.dumps(data))
            effects.append(data['_id'])
        
    #build_effect_database()

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
            os.remove(join(EFFECT_DIR, effect['id']))

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
    
def build_effect_database():
    """
    Builds the effect database for the IHM
    TODO this is obsolete, probably just remove
    """
    effects = []
    index = indexing.EffectIndex(INDEX_PATH)
    for entry in index.every():
        effect_id = entry['id']
        serialized = open(join(EFFECT_DIR, effect_id)).read()
        data = json.loads(serialized)
        effect = { "name": data['name'], 
                   "ports": data['ports'],
                   "uid": data['url'],
                }
        effects.append(effect)
 
    fh = open(EFFECT_DB_FILE, 'w')
    fh.write(json.dumps({ 'effects': effects }, default=json_handler))
    fh.close()
    
def rebuild_index():
    """
    Rebuild all index
    """
    index = indexing.EffectIndex(INDEX_PATH+'.new')

    for objid in os.listdir(EFFECT_DIR):
        obj = json.loads(open(os.path.join(EFFECT_DIR, objid)).read())
        index.add(obj)

    if os.path.exists(INDEX_PATH):
        shutil.move(INDEX_PATH, INDEX_PATH+'.old')
        shutil.move(INDEX_PATH+'.new', INDEX_PATH)
        shutil.rmtree(INDEX_PATH+'.old')
    else:
        shutil.move(INDEX_PATH+'.new', INDEX_PATH)
