#!/usr/bin/python

from distutils.core import setup

setup(name='uozuScripts',
      version='0.2',
      description='A collection of scripts that I use enough to warrant installing',
      author='Warwick Stone',
      author_email='uozu.aho@gmail.com',
      url='https://github.com/uozuAho/uozuScripts',
      scripts=['pyCodeGen.py',
               'pyReadelf.py'],
     )
