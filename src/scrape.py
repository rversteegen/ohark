#!/usr/bin/env python

"""
Provides get_page for downloading a page from the web or grabbing it from
a local cache, and some utility routines useful for crawling or scraping webpages.
"""

from __future__ import print_function
import sys
import time
import re
import os.path
import posixpath

from urlimp import urlparse, urlencode, urlopen, urlretrieve, HTTPError
import util
from util import py2, tostr
import gamedb

#print(sys.stdout.encoding, "encoding")

# if py2:
#     # For printing unicode to console (otherwise encoding is 'ascii' so unicode can't be encoded)
#     import codecs
#     sys.stdout = codecs.getwriter('utf-8')(sys.stdout)

try:
    from mod_python import apache
    import mod_python
except:
    mod_python = False

if mod_python:
    # # For BS under mod_python only
    thisdir = os.path.split(__file__)[0]
    sys.path.append(os.path.abspath(thisdir))

    from bs4.__init__ import BeautifulSoup, NavigableString
else:
    from bs4 import BeautifulSoup, NavigableString

import bs4

try:
    import lxml
    parse_lib = "lxml"
except ImportError:
    # html.parser is less lenient
    #parse_lib = "html5lib"
    # To support python 2.6, can't use html.parser which isn't lenient enough in python 2.6
    parse_lib = "html.parser"


thisdir = os.path.split(__file__)[0]
page_cache = os.path.abspath(thisdir) + '/download_cache'

extra_log_file = None

class BadInput(ValueError): pass

class TooManyRequests(Exception):
    remaining_allowed = 999

################################################################################
### URLs and page fetching


def joinurl(base_url, path):
    parsed = urlparse(base_url)
    ret = parsed.scheme + '://' + parsed.netloc
    if path[0] != '/':
        ret += parsed.path
    return ret + path

def url_path(url):
    """Return the path of a URL"""
    parsed = urlparse(url)
    return parsed.path

def is_subpage_of(base_url):
    """Returns a predicate function to be used as a BS4 find_all filter, like:
    soup.find_all('a', href=is_subpage_of(current_url))"""
    parsed = urlparse(base_url)
    def predicate(href):
        if not href:
            return False  # Fail if no href attr
        if href[0] == '/':
            return len(href) > len(parsed.path) and href.startswith(parsed.path)
        print("checking", href, "and", base_url)
        return href.startswith(base_url)
    return predicate

class BadUrl(BadInput): pass

def get_url(url, post_data = None, verbose = False, cache = True):
    """Download a URL or fetch it from the cache, and return bytes.
    Raises BadUrl if it can't be downloaded."""
    # Get 'path': local location of cached file
    parsed = urlparse(url)
    path = page_cache + '/' + parsed.netloc + '/' + parsed.path
    if parsed.query:
        path += '?' + parsed.query
    if path[-1] == '/':
        path += 'index.html'
    if post_data:
        encoded_data = urlencode(post_data)
        path += "!POST=" + encoded_data
    else:
        encoded_data = None

    noexist_file = path + '.missing'
    util.mkdir(os.path.dirname(path))

    if os.path.isfile(noexist_file):
        if cache:
            raise BadUrl("%s does not exist (cached)" % (url))
        os.remove(noexist_file)

    if cache and os.path.isfile(path):
        if verbose: print("   found in cache:", url)
    else:
        print("    downloading", url)
        if TooManyRequests.remaining_allowed <= 0:
            raise TooManyRequests('Fetching ' + url)
        TooManyRequests.remaining_allowed -= 1
        time.sleep(0.1)
        fullurl = url
        if not parsed.scheme:
            fullurl = 'http:' + url

        if verbose: print("Retrieving " + url)

        if True:
            try:
                response = urlopen(fullurl)
            except (HTTPError, ValueError) as e:
                util.create_file(noexist_file)
                raise BadUrl('Invalid URL "<b>%s</b>": %s' % (url, str(e)))

            if False:
                # Check for redirections, considering them errors
                if fullurl != response.geturl():
                    util.create_file(noexist_file)
                    raise BadUrl("%s does not exist (it redirects to %s)" % (url, response.geturl()))
            data = response.read()
            try:
                with open(path, "w") as f:
                    f.write(data)
            except e:
                print(e)
                os.unlink(path)
            return data

        else:
            # Doesn't catch 404 errors; returns the error page!
            filename, headers = urlretrieve(fullurl, path, data = encoded_data)

    with open(path, 'rb') as fil:
        return fil.read()

def auto_decode(data, default_encoding = 'utf-8'):
    try:
        data = data.decode(default_encoding)
    except UnicodeDecodeError:
        data = data.decode('latin-1')
    return data

def get_page(url, encoding = 'utf-8', cache = True, post_data = None):
    """Download a URL of an HTML page or fetch it from the cache, and return a BS object"""
    data = get_url(url, post_data, cache = cache)
    data = auto_decode(data, encoding)
    # Convert non-breaking spaces to spaces
    #data = data.replace(u'\xa0', ' ')
    data = data.replace("&#160;", ' ')
    return BeautifulSoup(data, parse_lib)

# def clean_page(page):
#     """Given a BS page, remove junk"""
#     page.head.clear()
#     for tag in page("script"):
#         tag.decompose()  # delete
#     return str(page)

################################################################################

def tag_contents(tag):
    "Get the html contents of a BS4 tag. Same as just str(tag), but excludes the tag itself"
    # Need to convert tags to str/unicode. Must not call 'str' on
    # a py2 unicode obj, because that attempts to encode it to ascii.
    return ''.join(tostr(piece) for piece in tag.contents)


if py2:
    strtypes = (str, unicode)
else:
    strtypes = (str, bytes)

def clean_strings(obj):
    """Replace all bs4.element.NavigableStrings in an object
    with regular str/unicode strings.
    NOTE: modifies object inplace only if mutable; so return value should be used."""
    if hasattr(obj, 'items'):
        for k,v in obj.items():
            #print("dict item %s,%s" % (k,v))
            obj[k] = clean_strings(v)
    elif type(obj) == bs4.element.NavigableString:
        print("NavigableString %s" % obj)
        obj = tostr(obj)
    elif isinstance(obj, strtypes):
        if py2 and isinstance(obj, str):
            # Check it's valid ascii
            try:
                obj.decode()
            except UnicodeDecodeError:
                print('Non-ASCII string "%s"' % obj[:60])
                return obj.decode('latin-1')
        return obj  # Avoid infinite loop iterating a string
    elif hasattr(obj, '__setitem__'):
        for k,v in enumerate(obj):
            #print("list item %s,%s" % (k,v))
            obj[k] = clean_strings(v)
    elif hasattr(obj, '__getitem__'):
        ret = []
        for k,v in enumerate(obj):
            #print("list item %s,%s" % (k,v))
            ret.append(clean_strings(v))
        obj = tuple(ret)
    elif isinstance(obj, gamedb.BinData):
        # Do not recurse to the binary str
        return obj
    elif hasattr(obj, '__dict__'):
        #print("recurse into %s.__dict__" % obj)
        obj.__dict__ = clean_strings(obj.__dict__)
    return obj


#clean_strings({'a':'3'})
