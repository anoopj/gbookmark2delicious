#!/usr/bin/env python

import cgi, pydelicious, sys, urllib2, gbookmark2delicious

form = cgi.FieldStorage()

print "Content-type: text/html\n\n"
print '<style type="text/css">'
print "body {font-family: Helvetica, sans-serif;}"
print "</style>"


if not form.has_key("gusername") or not form.has_key("gpassword") or  not form.has_key("dusername") or not form.has_key("dpassword"):
    print "Need both username and password"
    print form.keys()
    sys.exit(0)

global _goog_username, _goog_password, _delicious_username, _delicious_password

_goog_username = form["gusername"].value
_goog_password = form["gpassword"].value
_delicious_username = form["dusername"].value
_delicious_password = form["dpassword"].value

feed = gbookmark2delicious.grab_goog_bookmarks(_goog_username, _goog_password)
gbookmark2delicious.import_to_delicious(gbookmark2delicious.parse_feed(feed), _delicious_username, _delicious_password)
