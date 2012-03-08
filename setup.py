#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
  name = 'gbookmark2delicious',
  version = '3.3.1',
  packages = find_packages(),
  install_requires =
    '''
    beautifulsoup>=3.1.0.11
    python-commons==0.7
    distribute
    mechanize>=0.2.5
    pydelicious>=0.5.0
    '''.split(),
  entry_points = {
    'console_scripts': 'gbookmark2delicious = gbookmark2delicious:main'
  },
  # extra metadata for pypi
  author = 'Yang Zhang and Anoop Johnson',
  author_email = 'yaaang NOSPAM at REMOVECAPS gmail',
  url = 'http://gbookmark2delicious.googlecode.com/',
  description = 'Synchronize/share your Google Bookmarks to delicious.com',
  license = 'MIT',
  keywords =
    'google delicious bookmarks synchronization synchronize synchronizer',
  classifiers = [
    'Development Status :: 5 - Production/Stable',
    'Environment :: Console',
    'Intended Audience :: End Users/Desktop',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Topic :: Internet :: WWW/HTTP',
  ],
)
