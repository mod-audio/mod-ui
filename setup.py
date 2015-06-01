from setuptools import setup, find_packages
import os, glob

import sys

setup(name = 'mod',
      version = '0.99.8',
      description = 'MOD',
      long_description = 'MOD - Musician Operated Device - User Interface server and libraries',
      author = "Hacklab and AGR",
      author_email = "lhfagundes@hacklab.com.br",
      license = "GPLv3",
      packages = ['mod'],
      entry_points = {
          'console_scripts': [
              'mod-ui = mod.webserver:run',
              'mod-rebuild-database = mod:rebuild_database',
              ]
          },
      scripts = [
      ],
      data_files=[  ('html', glob.glob('html/*.html')),
                    ('html/include', glob.glob('html/include/*.html')),
                    ('html/img', glob.glob('html/img/*.png')),
                    ('html/img', glob.glob('html/img/*.jpg')),
                    ('html/img', glob.glob('html/img/*.jpeg')),
                    ('html/img/cabecote', glob.glob('html/img/cabecote/*.png')),
                    ('html/img/cabecote', glob.glob('html/img/cabecote/*.jpg')),
                    ('html/img/cabecote', glob.glob('html/img/cabecote/*.jpeg')),
                    ('html/img/mxr', glob.glob('html/img/mxr/*.png')),
                    ('html/img/mxr', glob.glob('html/img/mxr/*.jpg')),
                    ('html/img/mxr', glob.glob('html/img/mxr/*.jpeg')),
                    ('html/img/cloud', glob.glob('html/img/cloud/*.png')),
                    ('html/img/cloud', glob.glob('html/img/cloud/*.jpg')),
                    ('html/img/cloud', glob.glob('html/img/cloud/*.jpeg')),
                    ('html/img/japanese', glob.glob('html/img/japanese/*.png')),
                    ('html/img/japanese', glob.glob('html/img/japanese/*.jpg')),
                    ('html/img/japanese', glob.glob('html/img/japanese/*.jpeg')),
                    ('html/img/lata', glob.glob('html/img/lata/*.png')),
                    ('html/img/lata', glob.glob('html/img/lata/*.jpg')),
                    ('html/img/lata', glob.glob('html/img/lata/*.jpeg')),
                    ('html/css', glob.glob('html/css/*.css')),
                    ('html/js', glob.glob('html/js/*.js')),
                    ('html/js/lib', glob.glob('html/js/lib/*.js')),
                    ('tools', 'tools/screenshot.js'),
          ],
      install_requires = ['tornado', 'whoosh'],
      classifiers = [
          'Intended Audience :: Developers',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
        ],
      url = 'http://portalmod.com/',
)
