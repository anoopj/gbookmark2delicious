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

def usage():
    print "Usage: %s --googusername <username> --googpassword <password> "\
        "--delicioususername <username> --deliciouspassword <password>" %os.path.basename(sys.argv[0])

def process_args(argv):
    """
    Process the command-line arguments.
    """
    if len(argv) != 8:
        usage()
        sys.exit(2)

    try:                                
        opts, args = getopt.getopt(argv, "", ["help", "googusername=", "googpassword=", 
                                              "delicioususername=", "deliciouspassword="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("--help"):
            usage()                     
            sys.exit()                  
        elif opt == '--googusername':
            global _goog_username
            _goog_username = arg
        elif opt == "--googpassword":
            global _goog_password
            _goog_password = arg
        elif opt == "--delicioususername":
            global _delicious_username
            _delicious_username = arg
        elif opt == "--deliciouspassword":
            global _delicious_password
            _delicious_password = arg

def camel_case(string):
    """
    Strip the spaces in a string and CamelCase it - del.icio.us tags cannot have spaces, but
    Google bookmark labels can have.
    """
    return "".join(map(lambda x: x.title(), string.split()))

def underscorify(string):
    """
    Strip the spaces in a string and under_scorify it - del.icio.us tags cannot have spaces, but
    Google bookmark labels can have.
    """
    return "-".join(string.lower().split())

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
    pydelicious.add(user, password, url, description, tags, extended, dt, replace)

def import_to_delicious(bookmarks, username, password):
    """
    Input is a dictionary which contains all the Google bookmarks.
    """
    print "<b>Importing %d bookmarks</b>" %len(bookmarks.entries)
    print "<br/><br/>"
    for bookmark in bookmarks.entries:
        title = get_value_from_dict(bookmark, "title")
        url = get_value_from_dict(bookmark, "link")
        description = get_value_from_dict(bookmark, "bkmk_annotation")
        label = get_value_from_dict(bookmark, "bkmk_label")
        tag = underscorify(label)
        dt = get_value_from_dict(bookmark, "date")

        print "Title: ", title.encode("ascii", "ignore")
        print "URL: ", url
        print "Description: ", description 
        print "Label: ", label
        print "Tag: ", tag 
        print "Updated date: ", dt
        print "<br/><br/>"
        delicious_add(username, password, url, title, tag)


def get_value_from_dict(dict, key):
    try:
        return dict[key] 
    except KeyError:
        return ""

def main():
    process_args(sys.argv[1:])
    feed = grab_goog_bookmarks(_goog_username, _goog_password)
    import_to_delicious(parse_feed(feed), _delicious_username, _delicious_password)

if __name__ == "__main__":
    main()
