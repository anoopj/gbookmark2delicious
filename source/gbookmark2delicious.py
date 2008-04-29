#!/usr/bin/env python

from __future__ import with_statement

import base64
import feedparser
import getopt
import pydelicious
import os
import re
import sys
from urlparse import urlparse
import urllib2
from cPickle import *
from functools import *
from commons.decs import *
from commons.files import *
from commons.seqs import *
from commons.startup import *
from path import *
from time import *
from xml.etree import ElementTree
from itertools import *

def usage(argv):
    print """
Usage:

  %s --googusername <username>      --googpassword <password>
     --delicioususername <username> --deliciouspassword <password>

or:

  %s --credfile <credentials file>

where the credentials file contains the four username/password arguments in the
above order, one per line (e.g. ~/.gbookmark2delicious).  Remember to chmod
600!

Additional options:
    --cachedir <cachedir>   Local cache. If data exists here, then use it.
                            Otherwise, fetch the data remotely (and cache
                            here).
    --camelcase             Use camel case (rather leaving capitalization
                            unchanged) in the tag translation.
    --underscores           Replace spaces with underscores (rather than
                            removing them) in the tag translation.
    --replace               Whether to replace existing entries for same URLs
                            (default: no)
    """ % (os.path.basename(argv[0]), os.path.basename(argv[0]))

def process_args(argv):
    """
    Process the command-line arguments.
    """
    optconfigstr = """
        help
        googusername=
        googpassword=
        delicioususername=
        deliciouspassword=
        credfile=
        cachedir=
        camelcase
        underscores
        replace
    """
    optconfig = optconfigstr.split() + [""]
    try:
        opts, args = getopt.getopt(argv, "", optconfig)
    except getopt.GetoptError:
        usage(argv)
        sys.exit(2)

    global _goog_username, _goog_password, \
            _delicious_username, _delicious_password, \
            _cache_dir, _camelcase, _underscores, _replace
    _goog_username, _goog_password, \
            _delicious_username, _delicious_password, \
            _cache_dir = None, None, None, None, None
    _camelcase, _underscores, _replace = False, False, False
    for opt, arg in opts:
        if opt in ("--help"):
            usage(argv)
            sys.exit()
        elif opt == '--googusername':
            _goog_username = arg
        elif opt == "--googpassword":
            _goog_password = arg
        elif opt == "--delicioususername":
            _delicious_username = arg
        elif opt == "--deliciouspassword":
            _delicious_password = arg
        elif opt == "--credfile":
            with file(arg) as f:
                [_goog_username, _goog_password,
                 _delicious_username, _delicious_password] = \
                         map(lambda x: x.strip(), f.readlines())
        elif opt == "--cachedir":
            _cache_dir = arg
        elif opt == "--camelcase":
            _camelcase = True
        elif opt == "--underscores":
            _underscores = True
        elif opt == "--replace":
            _replace = True

    if None in [_goog_username, _goog_password, _delicious_username, _delicious_password]:
        usage()
        sys.exit(2)

def munge_label(string):
    """
    Strip the spaces in a string and CamelCase it - del.icio.us tags cannot have spaces, but
    Google bookmark labels can have.
    """
    glue = "_" if _underscores else ""
    munger = (lambda x: x.title()) if _camelcase else (lambda x: x)
    return "_".join(map(munger, string.split()))

def grab_goog_bookmarks(username, password, start):
    """
    Grab the Google bookmarks as an RSS feed.
    """
    url = 'https://www.google.com/bookmarks/find?q=&output=rss&num=10000&start=%d' % start
    request = urllib2.Request(url)
    try:
        handle = urllib2.urlopen(request)
    except IOError, cause:
        # here we *want* to fail
        pass
    else:
        # If we don't fail then the page isn't protected.
        print 'Page is not protected by authentication.'
        sys.exit(1)

    if not hasattr(cause, 'code') or cause.code != 401:
        # Got an error - but not a 401
        print 'Page is not protected by authentication.'
        print 'But we failed for another reason. Error Code: ' + e.code
        sys.exit(1)

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
        print 'The authentication header is badly formed.'
        print authline
        sys.exit(1)

    # Extract the scheme and the realm from the header.
    scheme = matchobj.group(1)
    realm = matchobj.group(2)
    if scheme.lower() != 'basic':
        print 'Supports only BASIC authentication.'
        sys.exit(1)

    base64string = base64.encodestring('%s:%s' % (username, password))[:-1]
    authheader =  "Basic %s" % base64string
    request.add_header("Authorization", authheader)
    try:
        handle = urllib2.urlopen(request)
    except IOError, e:
        # Here we shouldn't fail if the username/password is right
        print "Looks like the Google username or password is wrong."
        sys.exit(1)
    thepage = handle.read()
    return thepage

def parse_feed(feed):
    """
    Parses the RSS feed.
    """
    dict = feedparser.parse(feed)
    return dict

def delicious_add(url, description, tags="", extended="", dt="", replace="no"):
    _delicious_api.posts_add(url=url,
                            description=description,
                            tags=tags,
                            extended=extended,
                            dt=dt,
                            replace=replace)

def import_to_delicious(bookmarks, elts):
    """
    Input is a dictionary which contains all the Google bookmarks.
    """
    print "<b>Importing %d bookmarks</b>" %len(bookmarks)
    print "<br/><br/>"
    for bookmark, elt in izip( bookmarks, elts ):
        title = get_value_from_dict(bookmark, "title")
        url = get_value_from_dict(bookmark, "link")
        description = get_value_from_dict(bookmark, "smh_bkmk_annotation")
        labels = elt.findall('{http://www.google.com/history/}bkmk_label')
        tags = ' '.join(munge_label(label.text) for label in labels)
        dt = get_value_from_dict(bookmark, "date")

        print "Title:", title.encode("ascii", "ignore")
        print "URL:", url
        print "Description:", description
        print "Label:", [label.text for label in labels]
        print "Tag:", tags
        print "Updated date:", dt
        print "<br/><br/>"
        replacestr = "yes" if _replace else "no"

        # 10-second inter-request delay with exponential backoff.

        normal_wait = 1
        backoff = 60
        while True:
            try:
                delicious_add(url, title, tags, description,
                              replace = replacestr)
            except pydelicious.PyDeliciousException:
                print 'backing off for', backoff, 'seconds'
                sleep(backoff)
                backoff = 5 * backoff
            else:
                sleep(normal_wait)
                break

def get_value_from_dict(dict, key):
    try: return dict[key]
    except KeyError: return ""

def main(argv):
    global _delicious_api

    process_args(argv[1:])
    if _cache_dir is None:
        usage()
        sys.exit(2)

    _delicious_api = pydelicious.apiNew(_delicious_username, _delicious_password)

    soft_makedirs(_cache_dir)

    dlcs_posts = versioned_cache(
            path(_cache_dir) / 'dlcs-timestamp',
            _delicious_api.posts_update()['update']['time'],
            path(_cache_dir) / "dlcs",
            lambda: _delicious_api.posts_all()
            )

    goog_posts = None
    goog_tree = None
    for start in countstep(1, 1000):
        print 'goog', start
        feed = file_string_memoized(lambda username, password, start: \
                                      path(_cache_dir) / ("goog%d" % start)) \
                                   (grab_goog_bookmarks) \
                                   (_goog_username, _goog_password, start)
        posts = feedparser.parse(feed)
        tree = ElementTree.parse(path(_cache_dir) / ("goog%d" % start))

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

    print 'dlcs', len(dlcs_keys),   'goog', len(goog_keys), \
          'add',  len(keys_to_add), 'rm',   len(keys_to_rm)

    to_add = [ post for post in goog_posts.entries
               if post.link in keys_to_add ]
    to_rm  = [ post for post in dlcs_posts['posts']
               if post['href'] in keys_to_rm ]
    tree_add = [ post for post in goog_tree.findall('/channel/item')
                 if post.find('link').text in keys_to_add ]

    # Carry out changes.

    print 'adding'
    import_to_delicious(to_add, tree_add)

    # TODO implement removal
    # print 'removing'

run_main()

# vim:et:sw=4:ts=4
