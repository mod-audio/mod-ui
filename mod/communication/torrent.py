#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, json, base64, shutil
from hashlib import md5
from mod.communication import crypto
from mod import json_handler
from bson.objectid import ObjectId

class TorrentGenerator(object):
    
    def __init__(self, path, piece_length=None):
        self.path = path
        if not piece_length:
            piece_length = self._calculate_length()
        self.piece_length = piece_length

    def open(self, mode='rb'):
        return open(self.path, mode)

    def _calculate_length(self):
        size = os.path.getsize(self.path)
        # The length calculation algorithm is based on the following:
        # - There's a minimum reasonable package, depending on general connection.
        # - The metadata package cannot be bigger than a chunk package
        # - Each chunk adds 36 bytes to metadata (torrent) file

        min_pow = 17 # 128k
        max_pow = 19 # 512k
        for i in range(min_pow, max_pow):
            if size < 2 ** (2 * i) / 36:
                return 2 ** i
        return 2 ** max_pow

    def _build_torrent(self):
        assert os.path.exists(self.path)
        torrent = {}

        torrent['filename'] = os.path.basename(self.path)
        torrent['piece_length'] = self.piece_length
        length = os.path.getsize(self.path)
        torrent['length'] = length

        checksum = md5()
        torrent['pieces'] = []
        fp = open(self.path, 'rb')
        while fp.tell() < length:
            chunk = fp.read(self.piece_length)
            checksum.update(chunk)
            chk = md5(chunk).hexdigest()
            torrent['pieces'].append(chk)

        torrent['md5'] = checksum.hexdigest()

        fp.close()

        return torrent

    def sign(self, torrent, keyfile):
        sender = crypto.Sender(keyfile, torrent['md5'])
        torrent['signature'] = sender.pack()
        
    def torrent_data(self, keyfile=None):
        # TODO cache here
        torrent = self._build_torrent()

        if keyfile:
            self.sign(torrent, keyfile)

        if len(torrent['pieces']) == 1:
            torrent['data'] = self.get_chunk(0)

        return json.dumps(torrent, default=json_handler)

    def get_chunk(self, chunk_number):
        fp = self.open()
        fp.seek(chunk_number * self.piece_length)
        chunk = fp.read(self.piece_length)
        fp.close()
        return base64.b64encode(chunk)

class GridTorrentGenerator(TorrentGenerator):
    
    def __init__(self, obj):
        self.obj = obj
        self.piece_length = obj.data['chunkSize']
    
    def open(self):
        return self.obj.open()

    def _build_torrent(self):
        torrent = self.obj.data

        assert torrent is not None

        torrent['piece_length'] = self.piece_length

        return torrent
    
class TorrentReceiver(object):

    def __init__(self, torrent_id=None, download_tmp_dir='/tmp', 
                 remote_public_key=None, destination_dir='/tmp'):
        self.basedir = download_tmp_dir
        self.pubkey = remote_public_key
        self.destination = destination_dir
        self.torrent_id = torrent_id
        if torrent_id:
            self.load(open(self.torrentfile, 'rb').read())

    def _generate_id(self):
        id_data = '\t'.join([ str(self.torrent[key]) for key in ('filename', 'md5', 'piece_length') ])
        return md5(id_data.encode('utf-8')).hexdigest()

    def load(self, torrent_data):
        self.torrent = json.loads(torrent_data)

        for attr in ('length', 'piece_length', 'md5', 'pieces', 'filename', 'signature', 'data'):
            setattr(self, attr, self.torrent.get(attr))

        if self.torrent_id:
            # this might affect performance, might not be necessary
            assert self.torrent_id == self._generate_id()
        else:
            self.torrent_id = self._generate_id()
            
            # ID is being generated for the first time, so let's verify signature
            if self.pubkey:
                receiver = crypto.Receiver(self.pubkey, self.signature)
                assert receiver.unpack() == self.md5
            else:
                assert self.signature is None


        assert (len(self.pieces)-1)*self.piece_length < self.length <= len(self.pieces)*self.piece_length

        existing_file = os.path.join(self.destination, self.filename)
        if os.path.exists(existing_file):
            self._verify_checksum(existing_file)
        else:
            existing_file = None

        if existing_file:
            self.status = [ True for i in self.pieces ]
        elif os.path.exists(self.statusfile):
            self.status = json.loads(open(self.statusfile).read())
        else:
            self.status = [ False for i in self.pieces ]

        if not os.path.exists(self.torrentfile):
            if existing_file:
                shutil.copy(existing_file, self.datafile)
            else:
                open(self.datafile, 'a').truncate(self.length)
            open(self.torrentfile, 'w').write(torrent_data)
            open(self.statusfile, 'w').write(json.dumps(self.status))

        if self.data is not None and not self.status[0]:
            self.receive(0, self.data)

    @property
    def torrentfile(self):
        return os.path.join(self.basedir, '%s.modtorrent' % self.torrent_id)
    @property
    def datafile(self):
        return os.path.join(self.basedir, '%s.data' % self.torrent_id)
    @property
    def statusfile(self):
        return os.path.join(self.basedir, '%s.status' % self.torrent_id)

    def receive(self, chunk_number, chunk):
        data = base64.b64decode(chunk)
        sha = md5(data).hexdigest()
        assert self.pieces[chunk_number] == sha
        assert len(data) == self.piece_length or chunk_number == len(self.pieces)-1
        fp = open(self.datafile, 'r+b')
        fp.seek(chunk_number*self.piece_length)
        fp.write(data)
        fp.close()

        status = self.status
        status[chunk_number] = True
        open(self.statusfile, 'w').write(json.dumps(status))

    @property
    def complete(self):
        for chunk_status in self.status:
            if not chunk_status:
                return False
        return True

    @property
    def percent(self):
        status = self.status
        return round(100.0 * sum(status) / len(status))

    def finish(self):
        assert self.complete
        assert os.path.getsize(self.datafile) == self.length

        dest = os.path.join(self.destination, self.filename)

        assert not os.path.exists(dest) or self._verify_checksum(dest)

        self._verify_checksum(self.datafile)

        shutil.move(self.datafile, dest)

        os.remove(self.torrentfile)
        os.remove(self.statusfile)

    def _verify_checksum(self, filename):
        fp = open(filename, 'rb')

        chk = md5()
        while fp.tell() < self.length:
            chk.update(fp.read(2**13))

        assert chk.hexdigest() == self.md5

        fp.close()

        return True
