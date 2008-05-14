#!/usr/bin/env python

from commons import setup

pkg_info_text = """
Metadata-Version: 1.1
Name: gbookmark2delicious
Version: 2.0
Author: Anoop Johnson and Yang Zhang
Author-email: anoop.johnson@gmail.com, yaaang NOSPAM at REMOVECAPS gmail
Home-page: http://gbookmark2delicious.googlecode.com/
Download-url: http://code.google.com/p/gbookmark2delicious/downloads/list
Summary: Google Bookmarks to Delicious
License: MIT License
Description: Import your Google Bookmarks into del.icio.us.
Keywords: Python,utility,utilities,library,libraries,async,asynchronous,
          IO,networking,network,socket,sockets,I/O,threading,threads,
          thread
Platform: any
Classifier: Development Status :: 5 - Production/Stable
Classifier: Environment :: Console
Classifier: Intended Audience :: End Users/Desktop
Classifier: License :: OSI Approved :: MIT License
Classifier: Operating System :: OS Independent
Classifier: Programming Language :: Python
Classifier: Topic :: Internet :: WWW/HTTP
"""

setup.run_setup(
  pkg_info_text,
  srcdir = 'source',
  scripts = ['source/gbookmark2delicious.py'] )
