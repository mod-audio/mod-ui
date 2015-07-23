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
from whoosh.qparser import MultifieldParser
from whoosh import sorting

from mod import json_handler

class Index(object):
    @property
    def schema(self):
        raise NotImplemented

    @property
    def data(self):
        raise NotImplemented

    def __init__(self):
        self.index = FileIndex.create(RamStorage(), self.schema, WHOOSH_DEF_INDEX_NAME)
        self.reindex()

    def schemed_data(self, obj):
        data = {}

        for key, field in self.schema.items():
            if key == 'id':
                data['id'] = str(obj['_id'])
                continue
            try:
                data[key] = obj[key]
            except KeyError:
                data[key] = ''
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
        print("INDEXING: %f seconds" % t)

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

    def term_search(self, query):
        terms = []
        if query.get('term'):
            parser = MultifieldParser(self.term_fields, schema=self.index.schema)
            terms.append(parser.parse(str(query.pop('term')[0])))
        for key in query.keys():
            terms.append(Or([ Term(key, str(t)) for t in query.pop(key) ]))
        with self.searcher() as searcher:
            for entry in searcher.search(And(terms), limit=None):
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
    schema = Schema(id=ID(unique=True, stored=True), # URI
                    name=NGRAMWORDS(minsize=2, maxsize=5, stored=True),
                    brand=NGRAMWORDS(minsize=2, maxsize=4, stored=True),
                    label=NGRAMWORDS(minsize=2, maxsize=4, stored=True),
                    author_name=TEXT(stored=True),
                    category=ID(stored=True),
                    version=NUMERIC(decimal_places=5, stored=True),
                    stability=ID(stored=True),
                    #input_ports=NUMERIC(stored=True),
                    #output_ports=NUMERIC(stored=True),
                    #pedalModel=STORED(),
                    #pedalColor=STORED(),
                    #pedalLabel=TEXT(stored=True),
                    #smallLabel=STORED(),
                    )

    term_fields = ['label', 'name', 'category', 'author_name', 'brand']

    def schemed_data(self, obj):
        obj['_id'] = obj['uri']
        obj['author_name'] = obj['author']['name']
        return Index.schemed_data(self, obj)

    def add(self, effect):
        if not self.indexable(effect):
            return
        try:
            effect['label'] = effect['gui']['templateData']['label']
        except (KeyError, TypeError):
            pass
        try:
            effect['brand'] = effect['gui']['templateData']['author']
        except (KeyError, TypeError):
            pass

        effect_data = self.schemed_data(effect)

        #effect_data['input_ports'] = len(effect['ports']['audio']['input'])
        #effect_data['output_ports'] = len(effect['ports']['audio']['output'])

        writer = self.index.writer()
        writer.update_document(**effect_data)
        writer.commit()

    def indexable(self, obj):
        return not obj.get('hidden', False)
