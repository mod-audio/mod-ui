from setuptools import setup, find_packages
import os

setup(name = 'mod',
      version = '0.1',
      description = 'MOD',
      long_description = 'MOD - Musician Operated Device - python libraries',
      author = "Hacklab and AGR",
      author_email = "lhfagundes@hacklab.com.br",
      license = "Proprietary, hopefully not for long",
      packages = find_packages(),
      entry_points = {
          'console_scripts': [
              'mod-webserver = mod.webserver:run',
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
