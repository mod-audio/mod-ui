# -*- coding: utf-8 -*-

import os, json, gzip
from hashlib import sha1
import tornado.web
from mod.communication.torrent import TorrentReceiver, TorrentGenerator, GridTorrentGenerator
from mod.communication.crypto import Receiver

"""
File transfering between Device and Cloud is done by 3 pieces:
- A FileSender, who will serve the file through HTTP in several json-formatted chunks
- A FileReceiver, who will take these chunks through HTTP and handle the uploaded file
- A Transference instance, in JS, that will pass all json chunks from one server to the other

Both the Device and Cloud implement senders and receivers for each kind of file transference.
"""

class FileSender(tornado.web.RequestHandler):

    @property
    def private_key(self):
        """
        Returns a file path containing the private key used to sign the data
        """
        raise NotImplemented

    @property
    def base_dir(self):
        raise NotImplemented

    @property
    def cache_dir(self):
        return None

    def torrent(self, filename):
        return TorrentGenerator(os.path.join(self.base_dir, filename))

    @classmethod
    def urls(cls, path=''):
        if not path.startswith('/'):
            path = '/%s' % path
        if not path.endswith('/'):
            path = '%s/' % path
        return [
            (r"%s([A-Za-z0-9_.-]+)$" % path, cls),
            (r"%s([A-Za-z0-9_.-]+)/(\d+)" % path, cls),
            ]

    def get(self, filename, chunk_number=None):
        if chunk_number is None:
            return self.get_torrent(filename)
        else:
            return self.get_chunk(filename, int(chunk_number))


    def get_torrent(self, filename):
        self.set_header('Access-Control-Allow-Origin', self.request.headers['Origin'])
        self.set_header('Content-Type', 'application/json')
        self.try_cached('%s.torrent' % filename,
                        self._get_torrent,
                        filename)


    def _get_torrent(self, filename):
        gen = self.torrent(filename)
        return gen.torrent_data(self.private_key)

    def get_chunk(self, filename, chunk_number):
        self.set_header('Access-Control-Allow-Origin', self.request.headers['Origin'])
        self.try_cached('%s.%d' % (filename, chunk_number),
                        self._get_chunk,
                        filename, chunk_number)

    def _get_chunk(self, filename, chunk_number):
        gen = self.torrent(filename)
        return gen.get_chunk(chunk_number)

    def try_cached(self, cache_file, method, filename, *args):
        supports_gzip = 'gzip' in self.request.headers.get('Accept-Encoding', '')

        if self.cache_dir:
            base_cache_file = os.path.join(self.cache_dir, cache_file)
            gzip_cache_file = base_cache_file + '.gz'

            if supports_gzip:
                cache_file = gzip_cache_file
                self.set_header('Content-Encoding', 'gzip')
            else:
                cache_file = base_cache_file

            filepath = os.path.join(self.base_dir, filename)
            if (os.path.exists(cache_file) and
                os.path.getmtime(cache_file) == os.path.getmtime(filepath)
                ):
                print("getting from %s" % cache_file)
                self.write(open(cache_file).read())
                return

        data = method(filename, *args)

        if self.cache_dir:
            fh = open(base_cache_file, 'w')
            fh.write(data)
            fh.close()

            fh = gzip.open(gzip_cache_file, 'wb')
            fh.write(data)
            fh.close()

            mtime = os.path.getmtime(filepath)
            os.utime(base_cache_file, (mtime, mtime))
            os.utime(gzip_cache_file, (mtime, mtime))

            if supports_gzip:
                data = open(gzip_cache_file).read()

        self.write(data)

class GridFileSender(FileSender):

    private_key = None

    @property
    def model(self):
        """
        model property must be a cloud.models.FileCollection subclass
        """
        raise NotImplemented

    def torrent(self, objectid):
        return GridTorrentGenerator(self.model(objectid))


class FileReceiver(tornado.web.RequestHandler):
    @property
    def download_tmp_dir(self):
        raise NotImplemented
    @property
    def remote_public_key(self):
        raise NotImplemented
    @property
    def destination_dir(self):
        raise NotImplemented

    @classmethod
    def urls(cls, path):
        return [
            (r"/%s/$" % path, cls),
            (r"/%s/([a-f0-9]{32})/(\d+)$" % path, cls),
            #(r"/%s/([a-f0-9]{40})/(finish)$" % path, cls),
            ]

    @tornado.web.asynchronous
    def post(self, sessionid=None, chunk_number=None):
        # self.result can be set by subclass in process_file,
        # so that answer will be returned to browser
        self.result = None
        if sessionid is None:
            self.generate_session()
        else:
            self.receive_chunk(sessionid, int(chunk_number))

    def generate_session(self):
        """
        This Handler receives a torrent file and returns a session id to browser, so that
        chunks of this file may be uploaded through ChunkUploader using this session id

        Subclass must implement download_tmp_dir, remote_public_key properties and destination_dir
        """
        torrent_data = self.request.body.decode("utf-8", errors="ignore")
        receiver = TorrentReceiver(download_tmp_dir=self.download_tmp_dir,
                                   remote_public_key=self.remote_public_key,
                                   destination_dir=self.destination_dir)

        try:
            receiver.load(torrent_data)
        except Receiver.UnauthorizedMessage:
            self.write(json.dumps({ 'ok': False,
                                    'reason': "This file's source cannot be recognized. Downloading it is not safe",
                                    }))
            self.finish()
            return

        info = {
            'ok': True,
            # using int instead of boolean saves bandwidth
            'status': [ int(i) for i in receiver.status ],
            'id': receiver.torrent_id,
            }

        def finish():
            self.set_header('Content-type', 'application/json')
            info['result'] = self.result
            self.write(json.dumps(info))
            self.finish()

        if receiver.complete:
            try:
                receiver.torrent.pop('data')
            except KeyError:
                pass
            receiver.finish()
            self.process_file(receiver.torrent, callback=finish)
        else:
            finish()

    def receive_chunk(self, torrent_id, chunk_number):
        """
        This Handler receives chunks of a file being uploaded, previously registered
        through FileUploader.

        Subclass must implement download_tmp_dir and destination_dir property
        """
        receiver = TorrentReceiver(torrent_id,
                                   download_tmp_dir=self.download_tmp_dir,
                                   destination_dir=self.destination_dir)
        receiver.receive(chunk_number, self.request.body)
        response = { 'torrent_id': torrent_id,
                     'chunk_number': chunk_number,
                     'percent': receiver.percent,
                     'complete': False,
                     'ok': True,
                     }
        def finish():
            self.set_header('Content-type', 'application/json')
            response['result'] = self.result
            self.write(json.dumps(response))
            self.finish()

        if receiver.complete:
            response['complete'] = True
            receiver.finish()
            self.process_file(receiver.torrent, callback=finish)
        else:
            finish()


    def process_file(self, file_data, callback):
        """
        To be overriden
        """

