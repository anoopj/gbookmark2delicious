# Overview

Synchronize your Delicious bookmarks against your Google Bookmarks.  By
default, this script will read the credentials file for your logins, fetch all
Google bookmarks, determine if anything changed since the last successful sync,
and perform the necessary adds/removes/updates to Delicious. The program only
touches Delicious if there are pending changes, otherwise relying solely on its
cache of Delicious (stored in `~/.gbookmark2delicious.cache`).

# What about Lists in Google Bookmarks?

Not too long ago, Google Bookmarks introduced [Lists], which got me excited
because I thought they were a way to publish bookmark feeds, which would allow
me to retire gbookmark2delicious. It turned out to be pretty different---Lists
generate a feed for any updates to the pages in the List. (Plus, adding new
bookmarks requires that it be explicitly added to the List, and the bookmarklet
for doing so is IMO less usable than the regular Google Bookmarks bookmarklet.)

[Lists]: http://googleblog.blogspot.com/2010/03/collaborative-bookmarking-with-lists.html

# Usage

First, create a `~/.gbookmark2delicious.auth` with four lines:

```
  your.google.username@gmail.com
  your.google.password
  your_delicious_username
  your_delicious_password
```

Now you're ready to run gbookmark2delicious!

```
  $ gbookmark2delicious
  /usr/local/lib/python2.6/site-packages/pydelicious.py:90: DeprecationWarning: the md5 module is deprecated; use hashlib instead
  import md5, httplib
  2010-04-28 02:28:13,453 INFO     main                : getting google bookmarks
  2010-04-28 02:28:13,499 INFO     main                : authenticating with google
  2010-04-28 02:28:14,706 INFO     main                : google authenticated, got all bookmarks
  2010-04-28 02:28:14,714 INFO     main                : parsing google bookmarks
  2010-04-28 02:28:17,646 INFO     main                : building google bookmarks into data structure
  2010-04-28 02:28:20,099 INFO     main                : getting all delicious bookmarks
  2010-04-28 02:28:20,721 INFO     main                : authenticating with delicious
  2010-04-28 02:28:21,587 INFO     main                : delicious authenticated
  2010-04-28 02:28:24,780 INFO     main                : got all delicious bookmarks
  2010-04-28 02:28:31,158 INFO     main                : parsing delicious bookmarks
  2010-04-28 02:28:33,046 INFO     main                : building delicious bookmarks data structure
  2010-04-28 02:28:35,475 INFO     main                : add 5 rem 1 upd 0
  2010-04-28 02:28:35,476 INFO     main                : generating file to import into delicious
  2010-04-28 02:28:35,477 INFO     main                : producing page for delicious to import
  2010-04-28 02:28:35,478 INFO     main                : importing bookmarks to delicious
  2010-04-28 02:28:36,308 INFO     main                : successfully imported to delicious
```

You may want to have this run regularly from a cron job.  I have the following
entry in my crontab to make gbookmark2delicious run every hour, a quarter past
the hour:

```
  15 *  *   *   *     gbookmark2delicious
```
# Change Log

version 3.3.1, released 2012-03-08

- fixed Unicode bug

version 3.3, released 2012-01-18

- updated to new UI

version 3.2, released 2011-10-25

- updated to new UI

version 3.1.2, released 2010-12-10

- fixed import bug

version 3.1.1, released 2010-12-03

- documentation tweaks
- removed legacy shell-tools setup.bash

version 3.1, released 2010-12-03

- better documentation
- proper `distribute`-style packaging
- cleaned up logging

version 3.0, released 2010-04-17

- complete rewrite
- updated for new Google Bookmarks interface (this broke 2.x)
- thoroughly tested to catch encoding quirks and improve "semantic diff"
- side-stepping API and using mass export/import mechanisms for performance and
  reliability; no longer using feed parsing

version 2.1, released 2008-05-23

- fixed minor typo

version 2.0, released 2008-05-14

- updated to work with current Google Bookmarks and delicious
  interfaces/formats
- more flexibility via beefed-up CLI frontend (more options, etc.)
- misc features like reading from credentials file
- added local cache of the remotely pulled data
- added logging interface
- fixed character set transcoding issues
- added incremental synchronization capability for continuous mirroring of
  Google Bookmarks onto delicious
- added throttling and persistent retries for delicious' fussy REST API

version 1.0

- initial release

# License

The MIT License

Copyright (c) 2008--2010 Yang Zhang and Anoop Johnson.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

# Contact

* [Project Homepage](https://github.com/anoopj/gbookmark2delicious)
* [Yang's Homepage](http://yz.mit.edu/)
* [Anoop's Homepage](http://anoopjohnson.com/)
