#!/usr/bin/env python3

from setuptools import setup, find_packages
from glob import glob

import os
import sys

setup(name = 'mod',
      version = '0.99.8',
      description = 'MOD',
      long_description = 'MOD - Musician Operated Device - User Interface server and libraries',
      author = "Hacklab and AGR",
      author_email = "lhfagundes@hacklab.com.br",
      license = "GPLv3",
      packages = find_packages(),
      entry_points = {
          'console_scripts': [
              'mod-ui = mod.webserver:run',
              ]
          },
      scripts = [
      ],
      data_files=[  (('share/mod/html'), glob('html/*.html')),
                    (('share/mod/html/css'), glob('html/css/*.css')),
                    (('share/mod/html/fonts/comforta'), glob('html/fonts/comforta/*.ttf')),
                    (('share/mod/html/fonts/england-hand'), glob('html/fonts/england-hand/*.css')),
                    (('share/mod/html/fonts/england-hand'), glob('html/fonts/england-hand/*.ttf')),
                    (('share/mod/html/fonts/england-hand'), glob('html/fonts/england-hand/*.woff')),
                    (('share/mod/html/fonts/epf'), glob('html/fonts/epf/*.css')),
                    (('share/mod/html/fonts/epf'), glob('html/fonts/epf/*.ttf')),
                    (('share/mod/html/fonts/epf'), glob('html/fonts/epf/*.woff')),
                    (('share/mod/html/fonts/nexa'), glob('html/fonts/nexa/*.css')),
                    (('share/mod/html/fonts/nexa'), glob('html/fonts/nexa/*.ttf')),
                    (('share/mod/html/fonts/nexa'), glob('html/fonts/nexa/*.woff')),
                    (('share/mod/html/fonts/pirulen'), glob('html/fonts/pirulen/*.css')),
                    (('share/mod/html/fonts/pirulen'), glob('html/fonts/pirulen/*.ttf')),
                    (('share/mod/html/fonts/pirulen'), glob('html/fonts/pirulen/*.woff')),
                    (('share/mod/html/fonts/questrial'), glob('html/fonts/questrial/*.css')),
                    (('share/mod/html/fonts/questrial'), glob('html/fonts/questrial/*.ttf')),
                    (('share/mod/html/fonts/questrial'), glob('html/fonts/questrial/*.woff')),
                    (('share/mod/html/include'), glob('html/include/*.html')),
                    (('share/mod/html/img'), glob('html/img/*.gif')),
                    (('share/mod/html/img'), glob('html/img/*.jpg')),
                    (('share/mod/html/img'), glob('html/img/*.png')),
                    (('share/mod/html/img/cloud'), glob('html/img/cloud/*.png')),
                    (('share/mod/html/img/icons'), glob('html/img/icons/*.png')),
                    (('share/mod/html/js'), glob('html/js/*.js')),
                    (('share/mod/html/js/lib'), glob('html/js/lib/*.js')),
                    (('share/mod/html/resources'), glob('html/resources/*.html')),
                    (('share/mod/html/resources/pedals'), glob('html/resources/pedals/*.png')),
                    (('share/mod/html/resources/pedals'), glob('html/resources/pedals/*.css')),
                    (('share/mod/html/resources/templates'), glob('html/resources/templates/*.html')),
                    (('share/mod'), ['screenshot.js']),
                    (('share/mod/keys'), ['keys/cloud_key.pub']),
          ],
      install_requires = ['tornado', 'whoosh'],
      classifiers = [
          'Intended Audience :: Developers',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
        ],
      url = 'http://moddevices.com/',
)
