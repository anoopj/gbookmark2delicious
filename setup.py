#!/usr/bin/env python

from commons import setup

pkg_info_text = """
Metadata-Version: 1.1
Name: gbookmark2delicious
Version: 3.0
Author: Yang Zhang and Anoop Johnson
Author-email: yaaang NOSPAM at REMOVECAPS gmail, anoop.johnson@gmail.com
Home-page: http://gbookmark2delicious.googlecode.com/
Download-url: http://code.google.com/p/gbookmark2delicious/downloads/list
Summary: Synchronize your Delicious bookmarks against your Google Bookmarks.
License: MIT License
Description: Import your Google Bookmarks into del.icio.us.
Keywords: Google,Delicious,bookmarks,synchronization,synchronize,synchronizer
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
  srcdir = 'src',
  scripts = ['src/gbookmark2delicious.py'] )
