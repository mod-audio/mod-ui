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
      data_files=[  (os.path.join(sys.prefix, 'share/mod/html'), glob('html/*.html')),
                    (os.path.join(sys.prefix, 'share/mod/html/css'), glob('html/css/*.css')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/comforta'), glob('html/fonts/comforta/*.ttf')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/england-hand'), glob('html/fonts/england-hand/*.css')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/england-hand'), glob('html/fonts/england-hand/*.ttf')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/england-hand'), glob('html/fonts/england-hand/*.woff')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/epf'), glob('html/fonts/epf/*.css')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/epf'), glob('html/fonts/epf/*.ttf')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/epf'), glob('html/fonts/epf/*.woff')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/nexa'), glob('html/fonts/nexa/*.css')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/nexa'), glob('html/fonts/nexa/*.ttf')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/nexa'), glob('html/fonts/nexa/*.woff')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/pirulen'), glob('html/fonts/pirulen/*.css')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/pirulen'), glob('html/fonts/pirulen/*.ttf')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/pirulen'), glob('html/fonts/pirulen/*.woff')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/questrial'), glob('html/fonts/questrial/*.css')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/questrial'), glob('html/fonts/questrial/*.ttf')),
                    (os.path.join(sys.prefix, 'share/mod/html/fonts/questrial'), glob('html/fonts/questrial/*.woff')),
                    (os.path.join(sys.prefix, 'share/mod/html/include'), glob('html/include/*.html')),
                    (os.path.join(sys.prefix, 'share/mod/html/img'), glob('html/img/*.gif')),
                    (os.path.join(sys.prefix, 'share/mod/html/img'), glob('html/img/*.jpg')),
                    (os.path.join(sys.prefix, 'share/mod/html/img'), glob('html/img/*.png')),
                    (os.path.join(sys.prefix, 'share/mod/html/img/cloud'), glob('html/img/cloud/*.png')),
                    (os.path.join(sys.prefix, 'share/mod/html/img/icons'), glob('html/img/icons/*.png')),
                    (os.path.join(sys.prefix, 'share/mod/html/js'), glob('html/js/*.js')),
                    (os.path.join(sys.prefix, 'share/mod/html/js/lib'), glob('html/js/lib/*.js')),
                    (os.path.join(sys.prefix, 'share/mod/html/resources'), glob('html/resources/*.html')),
                    (os.path.join(sys.prefix, 'share/mod/html/resources/pedals'), glob('html/resources/pedals/*.png')),
                    (os.path.join(sys.prefix, 'share/mod/html/resources/pedals'), glob('html/resources/pedals/*.css')),
                    (os.path.join(sys.prefix, 'share/mod/html/resources/templates'), glob('html/resources/templates/*.html')),
                    (os.path.join(sys.prefix, 'share/mod'), ['screenshot.js']),
                    (os.path.join(sys.prefix, 'share/mod/keys'), ['keys/cloud_key.pub']),
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
