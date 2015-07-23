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


import os, json, shutil
from whoosh.fields import Schema, ID, TEXT, NGRAMWORDS, NUMERIC, STORED
from whoosh.index import FileIndex, open_dir
from whoosh.index import _DEF_INDEX_NAME as WHOOSH_DEF_INDEX_NAME
from whoosh.filedb.filestore import RamStorage
from whoosh.query import And, Or, Every, Term
from whoosh.qparser import QueryParser
from whoosh import sorting

from mod import json_handler

class Index(object):
    schema = Schema(id=ID(unique=True, stored=True), data=NGRAMWORDS(minsize=3, maxsize=5, at="start"))

    @property
    def fields(self):
        raise NotImplemented

    @property
    def data(self):
        raise NotImplemented

    def __init__(self):
        self.index = FileIndex.create(RamStorage(), self.schema, WHOOSH_DEF_INDEX_NAME)
        self.reindex()

    def schemed_data(self, obj):
        data = {'id': obj['uri']}
        data['data'] = " ".join([ obj[field] for field in self.fields ])
        return data

    def searcher(self):
        try:
            return self.index.searcher()
        except Exception as e:
            self.reindex()
            return self.index.searcher()

    def indexable(self, obj):
        return True

    def reindex(self):
        import time
        t=time.time()
        if self.data is not None:
            self.index.storage.destroy()
            self.index = FileIndex.create(RamStorage(), self.schema, WHOOSH_DEF_INDEX_NAME)
            for data in self.data:
                self.add(data)
        t=time.time()-t
        print("INDEXING %s: %f seconds" % (self.__class__.__name__, t))

    def find(self, **kwargs):
        terms = []
        for key, value in kwargs.items():
            terms.append(Term(key, value))

        with self.searcher() as searcher:
            for entry in searcher.search(And(terms), limit=None):
                yield entry.fields()

    def every(self):
        with self.searcher() as searcher:
            for entry in searcher.search(Every(), limit=None):
                yield entry.fields()

    def search(self, term):
        parser = QueryParser('data', schema=self.index.schema)
        with self.searcher() as searcher:
            for entry in searcher.search(parser.parse(str(term)), limit=None):
                yield entry.fields()

    def add(self, obj):
        if not self.indexable(obj):
            return
        data = self.schemed_data(obj)

        writer = self.index.writer()
        writer.update_document(**data)
        writer.commit()

    def delete(self, objid):
        writer = self.index.writer()
        count = writer.delete_by_term('id', objid)
        writer.commit()
        return count > 0

class EffectIndex(Index):
    data = None
    fields = ['label', 'name', 'categories', 'author_name', 'author_email', 'brand']

    def schemed_data(self, obj):
        try:
            obj['label'] = obj['gui']['templateData']['label']
        except (KeyError, TypeError):
            pass
        try:
            obj['brand'] = obj['gui']['templateData']['author']
        except (KeyError, TypeError):
            pass

        obj['author_name']  = obj['author']['name']
        obj['author_email'] = obj['author']['email']
        obj['categories']   = " ".join(obj['category'])
        return Index.schemed_data(self, obj)

    def indexable(self, obj):
        return not obj.get('hidden', False)

class PedalboardIndex(Index):
    data = None
    fields = ['name']

    def indexable(self, obj):
        return not obj.get('hidden', False)
