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
      data_files=[  (('/usr/share/mod/html'), glob('html/*.html')),
                    (('/usr/share/mod/html/css'), glob('html/css/*.css')),
                    (('/usr/share/mod/html/fonts/comforta'), glob('html/fonts/comforta/*.ttf')),
                    (('/usr/share/mod/html/fonts/england-hand'), glob('html/fonts/england-hand/*.css')),
                    (('/usr/share/mod/html/fonts/england-hand'), glob('html/fonts/england-hand/*.ttf')),
                    (('/usr/share/mod/html/fonts/england-hand'), glob('html/fonts/england-hand/*.woff')),
                    (('/usr/share/mod/html/fonts/epf'), glob('html/fonts/epf/*.css')),
                    (('/usr/share/mod/html/fonts/epf'), glob('html/fonts/epf/*.ttf')),
                    (('/usr/share/mod/html/fonts/epf'), glob('html/fonts/epf/*.woff')),
                    (('/usr/share/mod/html/fonts/nexa'), glob('html/fonts/nexa/*.css')),
                    (('/usr/share/mod/html/fonts/nexa'), glob('html/fonts/nexa/*.ttf')),
                    (('/usr/share/mod/html/fonts/nexa'), glob('html/fonts/nexa/*.woff')),
                    (('/usr/share/mod/html/fonts/pirulen'), glob('html/fonts/pirulen/*.css')),
                    (('/usr/share/mod/html/fonts/pirulen'), glob('html/fonts/pirulen/*.ttf')),
                    (('/usr/share/mod/html/fonts/pirulen'), glob('html/fonts/pirulen/*.woff')),
                    (('/usr/share/mod/html/fonts/questrial'), glob('html/fonts/questrial/*.css')),
                    (('/usr/share/mod/html/fonts/questrial'), glob('html/fonts/questrial/*.ttf')),
                    (('/usr/share/mod/html/fonts/questrial'), glob('html/fonts/questrial/*.woff')),
                    (('/usr/share/mod/html/include'), glob('html/include/*.html')),
                    (('/usr/share/mod/html/img'), glob('html/img/*.gif')),
                    (('/usr/share/mod/html/img'), glob('html/img/*.jpg')),
                    (('/usr/share/mod/html/img'), glob('html/img/*.png')),
                    (('/usr/share/mod/html/img/cloud'), glob('html/img/cloud/*.png')),
                    (('/usr/share/mod/html/img/icons'), glob('html/img/icons/*.png')),
                    (('/usr/share/mod/html/js'), glob('html/js/*.js')),
                    (('/usr/share/mod/html/js/lib'), glob('html/js/lib/*.js')),
                    (('/usr/share/mod/html/resources'), glob('html/resources/*.html')),
                    (('/usr/share/mod/html/resources/pedals'), glob('html/resources/pedals/*.png')),
                    (('/usr/share/mod/html/resources/pedals'), glob('html/resources/pedals/*.css')),
                    (('/usr/share/mod/html/resources/templates'), glob('html/resources/templates/*.html')),
                    (('/usr/share/mod'), ['screenshot.js']),
                    (('/usr/share/mod/keys'), ['keys/cloud_key.pub']),
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
