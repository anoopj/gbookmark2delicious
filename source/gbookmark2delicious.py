#!/usr/bin/env python

from __future__ import with_statement
import base64
import feedparser
import pydelicious
import re
from urlparse import urlparse
import urllib2
from commons.decs import file_string_memoized
from commons.files import soft_makedirs, versioned_cache
from commons.log import config_logging
from commons import log
from commons.networking import retry_exp_backoff
from commons.seqs import countstep
from commons.startup import run_main
import logging
from path import path
from time import sleep
from xml.etree import ElementTree
from itertools import izip
from argparse import ArgumentParser
from functools import partial
from string import maketrans

info  = partial(log.info,  'main')
debug = partial(log.debug, 'main')
error = partial(log.error, 'main')
die   = partial(log.die,   'main')

def process_args(argv):
    """
    Process the command-line arguments.
    """
    parser = ArgumentParser(description = """
        Synchronize del.icio.us bookmarks against Google Bookmarks.
        """)

    parser.add_argument('--googuser', help = "Google username.")
    parser.add_argument('--googpass', help = "Google password.")
    parser.add_argument('--dlcsuser', help = "del.icio.us username.")
    parser.add_argument('--dlcspass', help = "del.icio.us username.")

    parser.add_argument('--credfile',
            default = path( '~/.gbookmark2delicious.auth' ).expanduser(),
            help = """File containing the four username/password arguments in
            the above order, one per line.  Remember to chmod 600! (The
            command-line arguments get precedence.)""")
    parser.add_argument('--cachedir',
            default = path( '~/.gbookmark2delicious.cache' ).expanduser(),
            help = """Local cache. If data exists here, then use it.
            Otherwise, fetch the data remotely (and cache here).""")

    parser.add_argument('--camelcase', action = 'store_true',
            help = """Use camel case (rather than leaving capitalization
            unchanged) in the tag translation.""")
    parser.add_argument('--underscores', action = 'store_true',
            help = """Replace spaces with underscores (rather than removing
            them) in the tag translation.""")
    parser.add_argument('--use-goog-cache', action = 'store_true',
            help = """Whether to read from any available local cache of the
            Google posts instead of actually downloading the posts from
            Google""")
    parser.add_argument('--noreplace', action = 'store_true',
            help = """Whether to replace existing entries for same URLs""")

    parser.add_argument('--debug', action = 'append', default = [],
            help = """Enable logging for messages of the given flags. Flags
            include: compare (failed comparisons), main (main program
            logic)""")

    config = parser.parse_args(argv[1:])
    if config.googuser is None or config.googpass is None or \
            config.dlcsuser is None or config.dlcspass is None:
        with file(config.credfile) as f:
            c = config
            [c.googuser, c.googpass, c.dlcsuser, c.dlcspass] = \
                    map(str.strip, f.readlines())
    return config

def munge_label(string):
    """
    Strip the spaces in a string and CamelCase it - del.icio.us tags cannot have spaces, but
    Google bookmark labels can have.
    """
    glue = "_" if config.underscores else ""
    munger = (lambda x: x.title()) if config.camelcase else (lambda x: x)
    return "_".join(map(munger, string.split()))

def grab_goog_bookmarks(username, password, start):
    """
    Grab the Google bookmarks as an RSS feed.
    """
    info( 'getting goog posts starting from', start )
    url = 'https://www.google.com/bookmarks/find?q=&output=rss&num=10000&start=%d' % start
    request = urllib2.Request(url)
    try:
        handle = urllib2.urlopen(request)
    except IOError, cause:
        # here we *want* to fail
        pass
    else:
        # If we don't fail then the page isn't protected.
        die( 'Page is not protected by authentication.' )

    if not hasattr(cause, 'code') or cause.code != 401:
        # Got an error - but not a 401
        die( 'Page is not protected by authentication. But we failed for another reason. Error Code: ' + e.code )

    # Get the www-authenticate line from the headers
    # which has the authentication scheme and realm in it.
    authline = cause.headers['www-authenticate']

    # Regular expression used to extract scheme and realm.
    authobj = re.compile(r'''(?:\s*www-authenticate\s*:)?\s*(\w*)\s+realm=['"]([^'"]+)['"]''',
                         re.IGNORECASE)
    matchobj = authobj.match(authline)

    if not matchobj:
        # If the authline isn't matched by the regular expression
        # then something is wrong.
        die( 'The authentication header is badly formed: ' + authline )

    # Extract the scheme and the realm from the header.
    scheme = matchobj.group(1)
    realm = matchobj.group(2)
    if scheme.lower() != 'basic':
        die( 'Supports only BASIC authentication.' )

    base64string = base64.encodestring('%s:%s' % (username, password))[:-1]
    authheader =  "Basic %s" % base64string
    request.add_header("Authorization", authheader)
    try:
        handle = urllib2.urlopen(request)
    except IOError, e:
        # Here we shouldn't fail if the username/password is right
        die( "Looks like the Google username or password is wrong." )
    thepage = handle.read()
    return thepage

def parse_feed(feed):
    """
    Parses the RSS feed.
    """
    dict = feedparser.parse(feed)
    return dict

def retry(func):
    def helper():
        try: return func()
        except pydelicious.PyDeliciousException: return None
    return retry_exp_backoff(300, 5, helper)

def delicious_add(url, description, tags="", extended="", dt="", replace="no"):
    _delicious_api.posts_add(url=url,
                            description=description,
                            tags=tags,
                            extended=extended,
                            dt=dt,
                            replace=replace)
    return True

def import_to_delicious(bookmarks, elts):
    """
    Input is a dictionary which contains all the Google bookmarks.
    """
    info( 'importing', len(bookmarks), 'bookmarks' )
    for bookmark, elt in izip( bookmarks, elts ):
        title       = elt.find('title').text # get_value_from_dict(bookmark, "title")
        url         = get_value_from_dict(bookmark, "link")
        annot       = elt.find('{http://www.google.com/history/}bkmk_annotation')
        description = annot.text if annot is not None else ''
        labels      = elt.findall('{http://www.google.com/history/}bkmk_label')
        tags        = ' '.join(munge_label(label.text) for label in labels)
        dt          = get_value_from_dict(bookmark, "date")
        replacestr  = "no" if config.noreplace else "yes"

        info( "Title:", title.encode("ascii", "ignore") )
        info( "URL:", url )
        info( "Description:", description )
        info( "Labels:", [label.text for label in labels] )
        info( "Tags:", tags )
        info( "Updated date:", dt )

        retry(lambda: delicious_add(url, title, tags, description,
                                    replace = replacestr))

        sleep(60)

def get_value_from_dict(dict, key):
    try: return dict[key]
    except KeyError: return ""

def grab_dlcs_posts():
    info( "getting delicious posts" )
    return retry(_delicious_api.posts_all)

def lookup(elt, field):
    child = elt.find(field)
    return '' if child is None else ucode(child.text.strip())
    # XXX return '' if child is None else child.text.encode('utf-8').strip()

translations = [ (u'\x80',u'\u20AC'),
                 (u'\x82',u'\u201A'),
                 (u'\x83',u'\u0192'),
                 (u'\x84',u'\u201E'),
                 (u'\x85',u'\u2026'),
                 (u'\x86',u'\u2020'),
                 (u'\x87',u'\u2021'),
                 (u'\x88',u'\u02C6'),
                 (u'\x89',u'\u2030'),
                 (u'\x8A',u'\u0160'),
                 (u'\x8B',u'\u2039'),
                 (u'\x8C',u'\u0152'),
                 (u'\x8E',u'\u017D'),
                 (u'\x91',u'\u2018'),
                 (u'\x92',u'\u2019'),
                 (u'\x93',u'\u201C'),
                 (u'\x94',u'\u201D'),
                 (u'\x95',u'\u2022'),
                 (u'\x96',u'\u2013'),
                 (u'\x97',u'\u2014'),
                 (u'\x98',u'\u02DC'),
                 (u'\x99',u'\u2122'),
                 (u'\x9A',u'\u0161'),
                 (u'\x9B',u'\u203A'),
                 (u'\x9C',u'\u0153'),
                 (u'\x9E',u'\u017E'),
                 (u'\x9F',u'\u0178') ]

def ucode(x):
    #return x.translate(maketrans('', ''), badchars)
    for a,b in translations:
        x = x.replace(a,b)
    return x

def equal(label, g, d, extracond = False):
    """
    Delicious bookmarks can be truncated versions of Google Bookmarks, which is
    why we use L{str.startswith}.  We also take C{extracond} for when we can
    have an alternative test to satisfy; for instance, in the case of tags,
    Delicious automatically inserts a "system:unfiled" tag.

    @return: True if the Delicious bookmark field is similar to the Google
    Bookmark field, and False otherwise.
    """
    if g.startswith(d) or extracond:
        return True
    else:
        log.info( 'compare', label )
        log.info( 'compare', repr(g) )
        log.info( 'compare', repr(d) )
        return False

def compare((gp,ge),d):
    """
    @return: True if the Delicious bookmark is similar to the Google Bookmark,
    and False otherwise.
    """
    assert gp.link == d['href']

    gtitle = lookup(ge, 'title')
    dtitle = ucode(d['description'])
    gannot = lookup(ge, "{http://www.google.com/history/}bkmk_annotation")
    dannot = ucode(d['extended'])
    gtags  = ' '.join( munge_label(x.text) for x in ge.findall('{http://www.google.com/history/}bkmk_label') )
    dtags  = ucode(d['tag'])

    return ( equal('title', gtitle, dtitle) and
             equal('annot', gannot, dannot) and
             equal('tags', gtags, dtags, gtags == '' and dtags == 'system:unfiled' ) )

def main(argv):
    global _delicious_api, config

    config = process_args(argv)
    config_logging(level = logging.ERROR, do_console = True, flags = config.debug)

    _delicious_api = pydelicious.DeliciousAPI(config.dlcsuser, config.dlcspass, 'utf-8')

    soft_makedirs(config.cachedir)

    # Get and cache all the delicious posts (if necessary, based on timestamp).

    dlcs_posts = versioned_cache(
            path(config.cachedir) / 'dlcs-timestamp',
            _delicious_api.posts_update()['update']['time'],
            path(config.cachedir) / "dlcs",
            grab_dlcs_posts )

    # Get, cache, and parse all the Google posts.

    goog_posts = None
    goog_tree = None
    for start in countstep(1, 1000):
        if config.use_goog_cache:
            feed = file_string_memoized(lambda username, password, start: \
                                          path(config.cachedir) / ("goog%d" % start)) \
                                       (grab_goog_bookmarks) \
                                       (config.googuser, config.googpass, start)
        else:
            feed = grab_goog_bookmarks(config.googuser, config.googpass, start)
            try:
                with file( path(config.cachedir) / ('goog%d' % start), 'w' ) as f:
                    f.write( feed )
            except:
                log.exception('could not cache goog posts')
        posts = feedparser.parse(feed)
        tree = ElementTree.parse(path(config.cachedir) / ("goog%d" % start))

        if goog_posts == None:
            goog_posts = posts
            goog_tree  = tree
        else:
            goog_posts.entries.extend(posts.entries)
            for item in tree.findall('/channel/item'):
                goog_tree.findall('/channel')[0].append(item)

        if len(posts.entries) < 1000: break

    # Calculate the set differences (what to add/remove).

    dlcs_keys = set( post['href'] for post in dlcs_posts['posts'] )
    goog_keys = set( post.link    for post in goog_posts.entries )

    keys_to_add = goog_keys - dlcs_keys
    keys_to_rm  = dlcs_keys - goog_keys
    keys_common = goog_keys & dlcs_keys

    to_add   = [ post for post in goog_posts.entries
                 if post.link in keys_to_add ]
    to_rm    = [ post for post in dlcs_posts['posts']
                 if post['href'] in keys_to_rm ]
    tree_add = [ post for post in goog_tree.findall('/channel/item')
                 if post.find('link').text in keys_to_add ]

    # Determine what posts need updating.

    goog_map = dict( ( post.link, ( post, elt ) ) for post, elt in
            izip( goog_posts.entries, goog_tree.findall('/channel/item') ) )
    dlcs_map = dict( ( post['href'], post ) for post in dlcs_posts['posts'] )

    elts_up = zip( *[ goog_map[url] for url in keys_common if
                      not compare( goog_map[url], dlcs_map[url] ) ] )
    to_up, tree_up = elts_up if elts_up != [] else ([], [])

    info( 'dlcs', len(dlcs_keys), 'goog', len(goog_keys), \
          'add',  len(to_add),    'rm',   len(to_rm),     'up', len(to_up) )

    # Carry out changes.

    info( 'updating' )
    import_to_delicious(to_up, tree_up)

    info( 'adding' )
    import_to_delicious(to_add, tree_add)

    info( 'removing' )
    for url in keys_to_rm: _delicious_api.posts_delete(url)

run_main()

# vim:et:sw=4:ts=4
