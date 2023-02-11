#!/usr/bin/env python3

from distutils.command.build import build
from setuptools import setup, find_packages
from setuptools.command.install import install
from shutil import copyfile
from glob import glob

import os

class mod_utils_builder(build):
    def run(self):
        build.run(self)
        os.system("make -C utils")

class mod_utils_installer(install):
    def run(self):
        install.run(self)
        source = "utils/libmod_utils.so"
        target = os.path.join(self.install_lib, "modtools", "libmod_utils.so")
        print("Copying %s to %s" % (source, target))
        copyfile(source, target)

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
      data_files=[  (('share/mod/default.pedalboard'), glob('default.pedalboard/*')),
                    (('share/mod/html'), glob('html/*.html')),
                    (('share/mod/html/css'), glob('html/css/*.css')),
                    (('share/mod/html/css/fontello/css/'), glob('html/css/fontello/css/*.css')),
                    (('share/mod/html/css/fontello/font/'), glob('html/css/fontello/font/*.eot')),
                    (('share/mod/html/css/fontello/font/'), glob('html/css/fontello/font/*.svg')),
                    (('share/mod/html/css/fontello/font/'), glob('html/css/fontello/font/*.ttf')),
                    (('share/mod/html/css/fontello/font/'), glob('html/css/fontello/font/*.woff')),
                    (('share/mod/html/css/fontello/font/'), glob('html/css/fontello/font/*.woff2')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-200'), glob('html/fonts/Ek-Mukta/Ek-Mukta-200/*.eot')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-200'), glob('html/fonts/Ek-Mukta/Ek-Mukta-200/*.svg')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-200'), glob('html/fonts/Ek-Mukta/Ek-Mukta-200/*.ttf')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-200'), glob('html/fonts/Ek-Mukta/Ek-Mukta-200/*.woff')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-200'), glob('html/fonts/Ek-Mukta/Ek-Mukta-200/*.woff2')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-600'), glob('html/fonts/Ek-Mukta/Ek-Mukta-600/*.eot')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-600'), glob('html/fonts/Ek-Mukta/Ek-Mukta-600/*.svg')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-600'), glob('html/fonts/Ek-Mukta/Ek-Mukta-600/*.ttf')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-600'), glob('html/fonts/Ek-Mukta/Ek-Mukta-600/*.woff')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-600'), glob('html/fonts/Ek-Mukta/Ek-Mukta-600/*.woff2')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-700'), glob('html/fonts/Ek-Mukta/Ek-Mukta-700/*.eot')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-700'), glob('html/fonts/Ek-Mukta/Ek-Mukta-700/*.svg')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-700'), glob('html/fonts/Ek-Mukta/Ek-Mukta-700/*.ttf')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-700'), glob('html/fonts/Ek-Mukta/Ek-Mukta-700/*.woff')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-700'), glob('html/fonts/Ek-Mukta/Ek-Mukta-700/*.woff2')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-regular'), glob('html/fonts/Ek-Mukta/Ek-Mukta-regular/*.eot')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-regular'), glob('html/fonts/Ek-Mukta/Ek-Mukta-regular/*.svg')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-regular'), glob('html/fonts/Ek-Mukta/Ek-Mukta-regular/*.ttf')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-regular'), glob('html/fonts/Ek-Mukta/Ek-Mukta-regular/*.woff')),
                    (('share/mod/html/fonts/Ek-Mukta/Ek-Mukta-regular'), glob('html/fonts/Ek-Mukta/Ek-Mukta-regular/*.woff2')),
                    (('share/mod/html/fonts/comforta'), glob('html/fonts/comforta/*.ttf')),
                    (('share/mod/html/fonts/cooper'), glob('html/fonts/cooper/*.eot')),
                    (('share/mod/html/fonts/cooper'), glob('html/fonts/cooper/*.ttf')),
                    (('share/mod/html/fonts/cooper'), glob('html/fonts/cooper/*.woff')),
                    (('share/mod/html/fonts/cooper'), glob('html/fonts/cooper/*.woff2')),
                    (('share/mod/html/fonts/css'), glob('html/fonts/css/*.css')),
                    (('share/mod/html/fonts/england-hand'), glob('html/fonts/england-hand/*.css')),
                    (('share/mod/html/fonts/england-hand'), glob('html/fonts/england-hand/*.eot')),
                    (('share/mod/html/fonts/england-hand'), glob('html/fonts/england-hand/*.svg')),
                    (('share/mod/html/fonts/england-hand'), glob('html/fonts/england-hand/*.ttf')),
                    (('share/mod/html/fonts/england-hand'), glob('html/fonts/england-hand/*.woff')),
                    (('share/mod/html/fonts/epf'), glob('html/fonts/epf/*.css')),
                    (('share/mod/html/fonts/epf'), glob('html/fonts/epf/*.eot')),
                    (('share/mod/html/fonts/epf'), glob('html/fonts/epf/*.svg')),
                    (('share/mod/html/fonts/epf'), glob('html/fonts/epf/*.ttf')),
                    (('share/mod/html/fonts/epf'), glob('html/fonts/epf/*.woff')),
                    (('share/mod/html/fonts/nexa'), glob('html/fonts/nexa/*.css')),
                    (('share/mod/html/fonts/nexa'), glob('html/fonts/nexa/*.eot')),
                    (('share/mod/html/fonts/nexa'), glob('html/fonts/nexa/*.svg')),
                    (('share/mod/html/fonts/nexa'), glob('html/fonts/nexa/*.ttf')),
                    (('share/mod/html/fonts/nexa'), glob('html/fonts/nexa/*.woff')),
                    (('share/mod/html/fonts/pirulen'), glob('html/fonts/pirulen/*.css')),
                    (('share/mod/html/fonts/pirulen'), glob('html/fonts/pirulen/*.eot')),
                    (('share/mod/html/fonts/pirulen'), glob('html/fonts/pirulen/*.ttf')),
                    (('share/mod/html/fonts/pirulen'), glob('html/fonts/pirulen/*.woff')),
                    (('share/mod/html/fonts/questrial'), glob('html/fonts/questrial/*.css')),
                    (('share/mod/html/fonts/questrial'), glob('html/fonts/questrial/*.eot')),
                    (('share/mod/html/fonts/questrial'), glob('html/fonts/questrial/*.svg')),
                    (('share/mod/html/fonts/questrial'), glob('html/fonts/questrial/*.ttf')),
                    (('share/mod/html/fonts/questrial'), glob('html/fonts/questrial/*.woff')),
                    (('share/mod/html/img'), glob('html/img/*.gif')),
                    (('share/mod/html/img'), glob('html/img/*.jpg')),
                    (('share/mod/html/img'), glob('html/img/*.png')),
                    (('share/mod/html/img'), glob('html/img/*.svg')),
                    (('share/mod/html/img/cloud'), glob('html/img/cloud/*.png')),
                    (('share/mod/html/img/favicon'), glob('html/img/favicon/*.png')),
                    (('share/mod/html/img/icons'), glob('html/img/icons/*.css')),
                    (('share/mod/html/img/icons'), glob('html/img/icons/*.svg')),
                    (('share/mod/html/img/icons'), glob('html/img/icons/*.png')),
                    (('share/mod/html/img/icons/25'), glob('html/img/icons/25/*.png')),
                    (('share/mod/html/img/icons/36'), glob('html/img/icons/36/*.png')),
                    (('share/mod/html/img/social'), glob('html/img/social/*.png')),
                    (('share/mod/html/include'), glob('html/include/*.html')),
                    (('share/mod/html/js'), glob('html/js/*.js')),
                    (('share/mod/html/js/utils'), glob('html/js/utils/*.js')),
                    (('share/mod/html/js/lib'), glob('html/js/lib/*.js')),
                    (('share/mod/html/js/lib/slick'), glob('html/js/lib/slick/*.js')),
                    (('share/mod/html/js/lib/slick'), glob('html/js/lib/slick/*.css')),
                    (('share/mod/html/js/lib/slick'), glob('html/js/lib/slick/*.gif')),
                    (('share/mod/html/js/lib/slick/fonts'), glob('html/js/lib/slick/fonts/*.eot')),
                    (('share/mod/html/js/lib/slick/fonts'), glob('html/js/lib/slick/fonts/*.svg')),
                    (('share/mod/html/js/lib/slick/fonts'), glob('html/js/lib/slick/fonts/*.ttf')),
                    (('share/mod/html/js/lib/slick/fonts'), glob('html/js/lib/slick/fonts/*.woff')),
                    (('share/mod/html/resources'), glob('html/resources/*.html')),
                    (('share/mod/html/resources/pedals'), glob('html/resources/pedals/*.png')),
                    (('share/mod/html/resources/pedals'), glob('html/resources/pedals/*.css')),
                    (('share/mod/html/resources/templates'), glob('html/resources/templates/*.html')),
      ],
      install_requires = ['tornado'],

      classifiers = [
          'Intended Audience :: Developers',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
      ],
      url = 'http://moddevices.com/',
      cmdclass={'build': mod_utils_builder,
                'install': mod_utils_installer},
)
