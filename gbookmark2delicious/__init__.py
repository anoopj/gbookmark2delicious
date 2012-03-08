"""Synchronize your Delicious bookmarks against your Google Bookmarks.  By
default, this script will read the credentials file for your logins, fetch all
Google bookmarks, determine if anything changed since the last successful sync,
and perform the necessary adds/removes/updates to delicious."""

from __future__ import print_function, unicode_literals
import BeautifulSoup
import cgi
import codecs
import copy
import cPickle as pickle
import datetime
import itertools
import logging
import mechanize
import optparse
import pydelicious
import re
import sys
import time
from functools import partial

import commons.log
from commons import files, networking, strs, structs
from commons.path import path

spaces = re.compile(' {2,}')
ws = re.compile(r'\s')
wss = re.compile(r'\s{2,}')
log = logging.getLogger(__name__)

def squeeze(s): return wss.sub(' ', s)

def process_args(argv):
  """
  Process the command-line arguments.
  """
  parser = optparse.OptionParser(description = __doc__)

  parser.add_option('--goog-user', help = "Google username.")
  parser.add_option('--goog-pass', help = "Google password.")
  parser.add_option('--dlcs-user', help = "delicious username.")
  parser.add_option('--dlcs-pass', help = "delicious username.")

  parser.add_option('--pretend', action = 'store_true',
      help = "Don't actually make changes to delicious.")
  parser.add_option('--no-remove', action = 'store_true',
      help = "Don't remove any bookmarks, only add/update.")
  parser.add_option('--cred-file',
      default = path( '~/.gbookmark2delicious.auth' ).expanduser(),
      help = squeeze("""File containing the four username/password arguments in
      the above order, one per line.  Remember to chmod 600! (The command-line
      arguments get precedence.)"""))
  parser.add_option('--ignore-snapshot', action = 'store_true',
      help = squeeze("""Ignore any snapshot of last successful sync and force
      the program to continue with the comparison/sync as if it didn't
      exist."""))
  parser.add_option('--force-dlcs', action = 'store_true',
      help = squeeze("""Force re-fetch of delicious bookmarks instead of using
      the cache. Only applicable if snapshot is missing/stale/ignored.
      Otherwise, delicious bookmarks are only fetched the first time (cache
      doesn't exist). This option is useful if the cache is corrupted or if
      changes were made to the delicious account out-of-band."""))
  parser.add_option('--cache-dir',
      default = path( '~/.gbookmark2delicious.cache' ).expanduser(),
      help = squeeze("""Local cache for both Google and delicious. Google cache
      is by default ignored (see --use-goog-cache). delicious cache is used if
      it's not obsolete, and refreshed if it's out of date."""))
  parser.add_option('--use-goog-cache', action = 'store_true',
      help = squeeze("""Whether to read from any available local cache of the
      Google posts instead of actually downloading the posts from Google.  This
      is useful as a timesaver for development/debugging purposes."""))
  parser.add_option('--debug', action = 'store_true',
      help = squeeze("""Enable debug logging."""))

  return parser.parse_args(argv[1:])

def setup_config(options):
  config = copy.copy(options)
  if (config.goog_user is None or config.goog_pass is None or
      config.dlcs_user is None or config.dlcs_pass is None):
    with open(config.cred_file) as f:
      c = config
      [c.goog_user, c.goog_pass, c.dlcs_user, c.dlcs_pass] = \
          map(str.strip, f.readlines())

  config.goog_path = config.cache_dir / 'goog.html'
  config.dlcs_path = config.cache_dir / 'dlcs.html'
  config.to_dlcs_path = config.cache_dir / 'to-dlcs.html'
  config.snapshot_path = config.cache_dir / 'snapshot.pickle'

  commons.log.config_logging(
      level = logging.DEBUG if config.debug else logging.INFO,
      do_console = True)

  if log.isEnabledFor(logging.DEBUG):
    to_show = copy.copy(config)
    del to_show.goog_pass
    del to_show.dlcs_pass
    log.debug('config: %s', to_show)

  return config

def create_browser():
  b = mechanize.Browser()
  b.set_handle_robots(False)
  # must specify the proper charset or google will give you a mix of cp-1252
  # and utf-8. the other headers are just for my own psychological comfort.
  b.addheaders = [
          ('User-agent', 'Mozilla/5.0 (X11; U; Linux x86_64; en-US) AppleWebKit/533.2 (KHTML, like Gecko) Chrome/5.0.342.7 Safari/533.2'),
          ('Accept-Language', 'en-US,en;q=0.8'),
          ('Accept-Charset', 'ISO-8859-1,utf-8;q=0.7,*;q=0.3')]
  return b

def dlcs_retry(func):
  # pydelicious 0.6's API calls may return None (this was changed from 0.5).
  # retry_exp_backoff treats None as the sign to retry, so we return True on
  # success.
  def helper():
    try:
      res = func()
    except pydelicious.PyDeliciousException:
      log.exception('got an exception from delicious API')
      return None
    else:
      if res is not None:
        raise Exception('expecting pydelicious to return None, got %r', res)
      return True
  return networking.retry_exp_backoff(300, 5, helper)

def tidy(s):
  """
  This does two things: resolve HTML entity/character references, and
  squeeze consecutive spaces.

  Delicious returns HTML references that start with an extraneous 0, such
  as &#039; instead of &#39;.

  Google Bookmarks returns strings with multiple neighboring spaces.
  Delicious appears to be stripping them out (or expects that they be
  &nbsp; characters).
  """
  return spaces.sub(' ', strs.html2unicode(s or '').strip())

def is_trunc(a, b, dots):
  'Whether a is a truncated copy of b but with a suffix such as "..."'
  return len(a) < len(b) and a.endswith(dots) and b.startswith(a[:-len(dots)])

class bkmk(structs.free_struct): pass

def fetch_goog(config):
  log.info('getting google bookmarks')
  log.info('authenticating with google')
  b = create_browser()
  b.open('https://www.google.com/bookmarks/bookmarks.html')
  b.select_form(nr = 0)
  b.set_value(config.goog_user, 'Email')
  b.set_value(config.goog_pass, 'Passwd')
  resp = b.submit()
  html = resp.read()
  if b'<!DOCTYPE NETSCAPE-Bookmark-file-1>' not in html:
    print(html)
    raise Exception('google authentication failed')
  log.info('google authenticated, got all bookmarks')
  # write the raw bytes
  with open(config.goog_path, 'w') as f: f.write(html)

def try_unicode(s): return '' if unicode(s) == 'None' else unicode(s)

def parse_goog(config):
  log.info('parsing google bookmarks')
  # read in as unicode
  with codecs.open(config.goog_path, encoding = 'utf-8') as f:
    bs = BeautifulSoup.BeautifulSoup(f)

  # Example group structure:
  #
  # <dt><h3 add_date="1257353311424074">.NET tool</h3>
  # <dl><p>
  # </p><dt><a href="http://research.microsoft.com/en-us/projects/stubs/" add_date="1257353268711472">  Stubs - Microsoft Research </a>
  # </dt><dd>Stubs is a lightweight framework for test stubs and detours in .NET that is enterily based on delegates, type safe, refactorable and source code generated. Stubs was designed support the Code Contracts runtime writter and provide a minimal overhead to the Pex white box analysis. Stubs may be used on any .NET method, including non-virtual/static methods in sealed types.
  # </dd><dt><a href="http://research.microsoft.com/en-us/projects/Pex/" add_date="1257353311424074">  Pex, Automated White box Testing for .NET - Microsoft Research </a>
  # </dt><dd>Right from the Visual Studio code editor, Pex finds interesting input-output values of your methods, which you can save as a small test suite with high code coverage. Pex performs a systematic analysis, hunting for boundary conditions, exceptions and assertion failures, which you can debug right away. Pex enables Parameterized Unit Testing, an extension of Unit Testing that reduces test maintenance costs. Pex also comes with a lightweight framework for test stubs and detours, called Stubs and Moles.
  # </dd></dl><p>
  # </p></dt>
  #
  # The page is a set of groups (labels), such that a bookmark can appear
  # multiple times. Convert this into a set of bookmarks, each of which has a
  # set of labels.

  log.info('building google bookmarks into data structure')
  gurl2bkmk = {}
  for group in bs.dl.findAll('dt', recursive = False):
    label = ws.sub('_', strs.html2unicode(group.h3.string))
    for dt in group.findAll('dt'):
      # extract information
      url = try_unicode(dt.a['href'])
      name = try_unicode(dt.a.string)
      sib = dt.nextSibling
      desc = try_unicode(sib.string if sib is not None and sib.name == 'dd' else None)

      # update map, append label
      g = gurl2bkmk.setdefault(url, bkmk(name = name, desc = desc, labels = []))
      assert g.name == name and g.desc == desc and label not in g.labels, \
          '%r vs %r' % (g, (name, desc, label))
      g.labels.append(label)

  return gurl2bkmk

def dlcs_open(b, config, url, expected):
  html = b.open(url).read().decode('utf8')
  if expected not in html:
    log.debug(html)
    log.info('authenticating with delicious')
    b.open('https://delicious.com/login')

    # Temp workaround for <https://github.com/jjlee/mechanize/issues/54>.
    r=b.response()
    c=r._seek_wrapper__cache
    id(b.forms())
    c.seek(0)
    rep = '''
    <form method="post" action="login" id="login-form">
    <input type="text" name="username" class="textInput" id="firstInput"/>
    <input type="password" name="password"class="textInput"/>
    <input type="submit" style="visibility:hidden;"/>
    </form>
    '''
    c.write(c.read().decode('utf8').replace('<hr/>',rep).encode('utf8'))
    c.truncate()
    c.seek(0)
    b._factory._forms_genf=None

    b.select_form(nr = 1)
    b.set_value(config.dlcs_user, 'username')
    b.set_value(config.dlcs_pass, 'password')
    html = b.submit().read().decode('utf8')
    if 'is_logged_in' not in html:
      log.debug(html)
      raise Exception('delicious authentication failed')
    log.info('delicious authenticated')
    html = b.open(url).read().decode('utf8')
  return html

def fetch_dlcs(b, config):
  log.info('getting all delicious bookmarks')
  dlcs_open(b, config,
            'https://export.delicious.com/settings/bookmarks/export',
            'Export / Download Your Delicious Bookmarks')
  b.select_form(nr = 1)
  # leave all fields as default
  resp = b.submit()

  log.info('got all delicious bookmarks')
  # write raw bytes
  with open(config.dlcs_path, 'w') as f: f.write(resp.read())

def parse_dlcs(config):
  log.info('parsing delicious bookmarks')
  with codecs.open(config.dlcs_path, encoding = 'utf-8') as f:
    bs = BeautifulSoup.BeautifulSoup(f)

  log.info('building delicious bookmarks data structure')
  durl2bkmk = {}
  for dt in bs.findAll('dt'):
    # extract information
    url = try_unicode(dt.a['href'])
    name = try_unicode(dt.a.string)
    labels = dt.a['tags'].split(',')
    sib = dt.nextSibling
    desc = try_unicode(sib.string if sib is not None and sib.name == 'dd' else None)

    # save to map
    assert url not in durl2bkmk, url
    durl2bkmk[url] = bkmk(name = name, desc = desc, labels = labels)

  return durl2bkmk

def compare(gurl2bkmk, durl2bkmk):
  def diff(url):
    'Whether goog and dlcs *meaningfully* differ on the given URL.'
    g = copy.copy(gurl2bkmk[url])
    d = copy.copy(durl2bkmk[url])

    # Delicious' importer replaces spaces with underscores.
    g.labels = [ws.sub('_', label) for label in g.labels]

    # Normalize the text fields.
    g.desc = tidy(g.desc)
    d.desc = tidy(d.desc)
    g.name = tidy(g.name)
    d.name = tidy(d.name)

    # Google Bookmarks can have empty names, but Delicious will
    # automatically populate empty names with the URL.
    if g.name == '' and d.name == url: d.name = ''

    # Delicious will truncate fields that are too long. I wasn't able
    # to quickly ascertain the precise truncation policy (256
    # characters for name fields and 1024 for description fields, but
    # it's unclear at what encoding level this truncation occurs), so
    # this is a very sloppy comparison.
    if is_trunc(d.desc, g.desc, '...'): d.desc = g.desc
    if is_trunc(d.name, g.name, '..'):  d.name = g.name

    return g != d

  gurls = set(gurl2bkmk.keys())
  durls = set(durl2bkmk.keys())
  to_add = gurls - durls
  to_rem = durls - gurls
  to_upd = [url for url in durls.intersection(gurls) if diff(url)]
  log.info('add %d rem %d upd %', len(to_add), len(to_rem), len(to_upd))

  # "puts" are adds/updates and are done via import.
  puts = [(url, gurl2bkmk[url]) for url in itertools.chain(to_add, to_upd)]

  if log.isEnabledFor(logging.DEBUG):
    for url in to_add:
      log.debug('to add: %s', dict(url = url) + gurl2bkmk[url])
    for url in to_rem:
      log.debug('to remove: %s', dict(url = url) + durl2bkmk[url])
    for url in to_upd:
      log.debug('to update: %s on goog, %s on dlcs',
          bkmk(url = url) + gurl2bkmk[url],
          bkmk(url = url) + durl2bkmk[url])

  return to_add, to_rem, to_upd, puts

def mk_import(to_dlcs_path, puts):
  # Note that when importing to delicious, don't include the H1 line (as
  # Delicious does when it exports its bookmarks). Delicious interprets
  # headers as additional tags that must be applied on all encapsulated
  # items. This is so that importing from e.g. Google Bookmarks works
  # (partially), since Google Bookmarks doesn't list the tags for each
  # bookmarks, but instead groups bookmarks together by tags (identified
  # using headers). Also, don't try to specify an empty H1, since that will
  # result in the tag "(untitled)". Note additionally that if you try to
  # import Google Bookmarks' format into Delicious, only the first header/tag
  # for each bookmark will be applied, and later ones are discarded.

  log.info('generating file to import into delicious')
  hdr = '''<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<!-- This is an automatically generated file.
It will be read and overwritten.
Do Not Edit! -->
<TITLE>Bookmarks</TITLE>
<DL><p>'''
  ftr = '''</DL><p>'''
  log.info('producing page for delicious to import')
  with codecs.open(to_dlcs_path, 'w', 'utf-8') as f:
    print(hdr, file = f)
    for url, g in puts:
      try:
        labels = ','.join(map(cgi.escape, g.labels))
        print('<DT><A HREF="%s" TAGS="%s">%s</A>' %
                (cgi.escape(url), labels, g.name),
              file = f)
        if g.desc is not None: print('<DD>' + g.desc, file = f)
      except:
        log.exception('problem writing %s', g + bkmk(url = url))
        raise
    print(ftr, file = f)

def do_import(b, config):
  log.info('importing bookmarks to delicious')
  dlcs_open(b, config,
            'https://export.delicious.com/settings/bookmarks/import',
            'Import Your Bookmarks to Delicious')
  with open(config.to_dlcs_path) as f:
    b.select_form(nr = 1)
    b.add_file(f, 'text/html', config.to_dlcs_path.basename())
    b.set_value('', 'tags') # don't automatically add any tags
    b.set_value(['no'], 'private') # make bookmarks public
    resp = b.submit()
  html = resp.read().decode('utf-8')
  if 'Success! Your bookmark import has begun.' not in html:
    raise Exception('could not import bookmarks to delicious, instead got: ' + html)
  log.info('successfully imported to delicious')

def read_snapshot(config):
  # a snapshot is just a serialization of the last successfully synced
  # gurl2bkmk (as a dict, not a defaultdict)
  try:
    with open(config.snapshot_path) as f:
      return pickle.load(f)
  except:
    return None, None

def write_snapshot(gurl2bkmk, config):
  with open(config.snapshot_path, 'w') as f:
    pickle.dump((time.time(), gurl2bkmk), f, protocol = 2)

def main(argv = sys.argv):
  # preliminaries
  options, args = process_args(argv)
  config = setup_config(options)
  files.soft_makedirs(config.cache_dir)

  # get google bookmarks
  if not (config.use_goog_cache and config.goog_path.exists()):
    fetch_goog(config)
  gurl2bkmk = parse_goog(config)

  # get delicious bookmarks
  b = create_browser()
  timestamp, durl2bkmk = read_snapshot(config)
  if config.ignore_snapshot or durl2bkmk is None:
    # get delicious bookmarks; this by default only happens the first time or
    # upon force-request
    if config.force_dlcs or not config.dlcs_path.exists():
      fetch_dlcs(b, config)
    durl2bkmk = parse_dlcs(config)
  else:
    log.info('using sync snapshot from %s',
             datetime.datetime.fromtimestamp(timestamp))

  # compare the two to get diff-sets
  to_add, to_rem, to_upd, puts = compare(gurl2bkmk, durl2bkmk)

  # perform any puts into delicious
  if len(puts) > 0:
    mk_import(config.to_dlcs_path, puts)
    if not config.pretend:
      do_import(b, config)

  # perform any removes
  if not config.pretend and not config.no_remove:
    # Deletes can only be done via the delicious API.
    dlcs_api = pydelicious.DeliciousAPI(config.dlcs_user, config.dlcs_pass, 'utf-8')
    for url in to_rem:
      dlcs_retry(lambda: dlcs_api.posts_delete(url))
      time.sleep(1)

  # update the snapshot; ops are idempotent so it's fine to write this
  # afterward (risking redo's if ops previously failed before this snapshot)
  write_snapshot(gurl2bkmk, config)

# vim:et:sw=2:ts=2
