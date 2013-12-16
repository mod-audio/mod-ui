from setuptools import setup, find_packages
import os

setup(name = 'mod',
      version = '0.28.13',
      description = 'MOD',
      long_description = 'MOD - Musician Operated Device - User Interface server and libraries',
      author = "Hacklab and AGR",
      author_email = "lhfagundes@hacklab.com.br",
      license = "GPLv3",
      packages = find_packages(),
      entry_points = {
          'console_scripts': [
              'mod-ui = mod.webserver:run',
              'mod-rebuild-database = mod:rebuild_database',
              ]
          },
      scripts = [
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
