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


import os, json, shutil
from whoosh.fields import Schema, ID, TEXT, NGRAMWORDS, NUMERIC, STORED
from whoosh.index import create_in, open_dir
from whoosh.query import And, Or, Every, Term
from whoosh.qparser import MultifieldParser
from whoosh import sorting

from mod import json_handler
from mod.settings import INDEX_PATH, EFFECT_DIR

class Index(object):
    @property
    def schema(self):
        raise NotImplemented
    @property
    def index_path(self):
        raise NotImplemented
    @property
    def data_source(self):
        raise NotImplemented

    def __init__(self):
        if self.index_path is None:
            pass
        elif not os.path.exists(self.index_path):
            os.mkdir(self.index_path)
            self.reindex()
        else:
            try:
                self.index = open_dir(self.index_path)
            except:
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
        if self.data_source and os.path.exists(self.data_source):
            shutil.rmtree(self.index_path)
            os.mkdir(self.index_path)
            self.index = create_in(self.index_path, self.schema)
            for filename in os.listdir(self.data_source):
                filename = os.path.join(self.data_source, filename)
                if filename.endswith('.metadata'):
                    continue
                if os.path.isdir(filename):
                    continue
                try:
                    data = json.loads(open(filename).read())
                except ValueError:
                    # Not json valid
                    continue
                metadata_file = filename + '.metadata'
                if os.path.exists(metadata_file):
                    try:
                        metadata = json.loads(open(filename).read())
                        data.update(metadata)
                    except ValueError:
                        # Not json valid, just ignore metadata file
                        pass
                self.add(data)

    def save_local_variable(self, objid, var, value):
        path = os.path.join(self.data_source, '%s.metadata' % objid)
        if os.path.exists(path):
            data = json.loads(open(path).read())
        else:
            data = {}
        data[var] = value
        open(path, 'w').write(json.dumps(data))

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
    index_path = INDEX_PATH
    data_source = EFFECT_DIR

    schema = Schema(id=ID(unique=True, stored=True),
                    uri=ID(stored=True),
                    name=NGRAMWORDS(minsize=2, maxsize=5, stored=True),
                    brand=NGRAMWORDS(minsize=2, maxsize=4, stored=True),
                    label=NGRAMWORDS(minsize=2, maxsize=4, stored=True),
                    author=TEXT(stored=True),
                    package=ID(stored=True),
                    category=ID(stored=True),
                    description=TEXT,
                    version=NUMERIC(decimal_places=5, stored=True),
                    stability=ID(stored=True),
                    input_ports=NUMERIC(stored=True),
                    output_ports=NUMERIC(stored=True),
                    pedalModel=STORED(),
                    pedalColor=STORED(),
                    pedalLabel=TEXT(stored=True),
                    smallLabel=STORED(),
                    bufsize=NUMERIC(stored=True),
                    )

    term_fields = ['label', 'name', 'category', 'author', 'description', 'brand']

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

        effect_data['input_ports'] = len(effect['ports']['audio']['input'])
        effect_data['output_ports'] = len(effect['ports']['audio']['output'])

        writer = self.index.writer()
        writer.update_document(**effect_data)
        writer.commit()

    def indexable(self, obj):
        return not obj.get('hidden')

#class PedalboardIndex(Index):
    #index_path = PEDALBOARD__INDEX_PATH
    #data_source = PEDALBOARD__DIR

    #schema = Schema(id=ID(unique=True, stored=True),
                    #title=ID(unique=True, stored=True),
                    #title_words=NGRAMWORDS(minsize=3, maxsize=5, stored=True),
                    #description=TEXT,
                    #)

    #term_fields = ['title_words', 'description']

    #def add(self, pedalboard):
        #if not self.indexable(pedalboard):
            #return
        #data = pedalboard['metadata']
        #data['_id'] = pedalboard['_id']
        #data = self.schemed_data(data)
        #data['title_words'] = data['title']

        #writer = self.index.writer()
        #writer.update_document(**data)
        #writer.commit()
