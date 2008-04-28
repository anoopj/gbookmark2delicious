#!/usr/bin/env python

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

def usage():
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
    --feedfile <feedfile>   Cache of the Google Bookmarks. If file exists, then
                            read it. Otherwise, cache the Google Bookmarks here.
    --camelcase             Use camel case (rather leaving capitalization
                            unchanged) in the tag translation.
    --underscores           Replace spaces with underscores (rather than
                            removing them) in the tag translation.
    --replace               Whether to replace existing entries for same URLs
                            (default: no)
    """ % (os.path.basename(sys.argv[0]), os.path.basename(sys.argv[0]))

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
        feedfile=
        camelcase
        underscores
        replace
    """
    optconfig = optconfigstr.split() + [""]
    try:
        opts, args = getopt.getopt(argv, "", optconfig)
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    global _goog_username, _goog_password, \
            _delicious_username, _delicious_password, \
            _feed_file, _camelcase, _underscores, _replace
    _goog_username, _goog_password, \
            _delicious_username, _delicious_password, \
            _feed_file = None, None, None, None, None
    _camelcase, _underscores, _replace = False, False, False
    for opt, arg in opts:
        if opt in ("--help"):
            usage()
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
            f = file(arg)
            try:
                [_goog_username, _goog_password,
                 _delicious_username, _delicious_password] = \
                         map(lambda x: x.strip(), f.readlines())
            finally:
                f.close()
        elif opt == "--feedfile":
            _feed_file = arg
        elif opt == "--camelcase":
            _camelcase = True
        elif opt == "--underscores":
            _underscores = True
        elif opt == "--replace":
            _replace = True

    if None in [_goog_username, _goog_password, _delicious_username, _delicious_password]:
        usage()
        sys.exit(2)

def munge_tag(string):
    """
    Strip the spaces in a string and CamelCase it - del.icio.us tags cannot have spaces, but
    Google bookmark labels can have.
    """
    glue = _underscores and "_" or ""
    munger = _camelcase and (lambda x: x.title()) or (lambda x: x)
    return "_".join(map(munger, string.split()))

def grab_goog_bookmarks(username, password):
    """
    Grab the Google bookmarks as an RSS feed.
    """
    url = 'https://www.google.com/bookmarks/find?q=&output=rss&num=10000'
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

def delicious_add(user, password, url, description, tags="", extended="", dt="", replace="no"):
    global delicious_api
    if delicious_api is None: delicious_api = pydelicious.DeliciousAPI(user, password)
    delicious_api.posts_add(url=url,
                            description=description,
                            tags=tags,
                            extended=extended,
                            dt=dt,
                            replace=replace)

def import_to_delicious(bookmarks, username, password):
    """
    Input is a dictionary which contains all the Google bookmarks.
    """
    print "<b>Importing %d bookmarks</b>" %len(bookmarks.entries)
    print "<br/><br/>"
    for bookmark in bookmarks.entries:
        title = get_value_from_dict(bookmark, "title")
        url = get_value_from_dict(bookmark, "link")
        description = get_value_from_dict(bookmark, "smh_bkmk_annotation")
        label = get_value_from_dict(bookmark, "smh_bkmk_label")
        tag = munge_tag(label)
        dt = get_value_from_dict(bookmark, "date")

        print "Title: ", title.encode("ascii", "ignore")
        print "URL: ", url
        print "Description: ", description
        print "Label: ", label
        print "Tag: ", tag
        print "Updated date: ", dt
        print "<br/><br/>"
        replacestr = _replace and "yes" or "no"
        delicious_add(username, password, url, title, tag, description,
                      replace = replacestr)

def get_value_from_dict(dict, key):
    try: return dict[key]
    except KeyError: return ""

def main():
    global delicious_api
    delicious_api = None

#    posts = pydelicious.get_all(_delicious_username, _delicious_password)
#    with file(_dlcs_cache / _dlcs_cache, 'w') as f:
#        dump(posts, file)

    process_args(sys.argv[1:])

    feed = None
    if _feed_file is not None:
        try:
            f = file(_feed_file)
            try: feed = f.read()
            finally: f.close()
        except IOError, (errno, errstr):
            if errno != 2: raise
    if feed is None:
        if _feed_file is not None:
            feed = grab_goog_bookmarks(_goog_username, _goog_password)
            f = file(_feed_file, 'w')
            try: f.write(feed)
            finally: f.close()
        else:
            feed = grab_goog_bookmarks(_goog_username, _goog_password)
    import_to_delicious(parse_feed(feed), _delicious_username, _delicious_password)

if __name__ == "__main__":
    main()

# vim:et:sw=4:ts=4
