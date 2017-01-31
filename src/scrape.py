#!/usr/bin/env python3

"""
Provides get_page for downloading a page from the web or grabbing it from
a local cache.
"""

from __future__ import print_function
import sys
import time
import re
import os.path
import posixpath

import util
from util import py2, tostr

#print(sys.stdout.encoding, "encoding")

# if py2:
#     # For printing unicode to console (otherwise encoding is 'ascii' so unicode can't be encoded)
#     import codecs
#     sys.stdout = codecs.getwriter('utf-8')(sys.stdout)

if py2:
    from urlparse import urlparse
    from urllib import urlretrieve
    from urllib2 import urlopen, HTTPError
else:
    from urllib.parse import urlparse #, urljoin
    from urllib.request import urlopen, urlretrieve
    from urllib.error import HTTPError

try:
    from mod_python import apache
    import mod_python
except:
    mod_python = False

if mod_python:
    # # For BS under mod_python only
    thisdir = os.path.split(__file__)[0]
    sys.path.append(os.path.abspath(thisdir))

    # from mod_python import apache
    #             mod = apache.import_module('~/../src/car-parts-scraper/web_interface.py')

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
    # To support python 2.6, can't use html.parser which isn't lenient enough
    parse_lib = "html.parser"


thisdir = os.path.split(__file__)[0]
page_cache = os.path.abspath(thisdir) + '/download_cache'

extra_log_file = None

class BadInput(ValueError): pass

class TooManyRequests(Exception):
    remaining_allowed = 999

################################################################################
### URLs and page fetching


urljoin = posixpath.join

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

def get_url(url, verbose = False, cache = True):
    """Download a URL or fetch it from the cache, and return bytes"""
    # Get 'path': local location of cached file
    parsed = urlparse(url)
    path = page_cache + '/' + parsed.netloc + '/' + parsed.path
    if parsed.query:
        path += '?' + parsed.query
    if path[-1] == '/':
        path += 'index.html'
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

        if False:
            # This checks for redirections, considering them errors
            try:
                response = urlopen(fullurl)
            except ValueError as e:
                util.create_file(noexist_file)
                raise BadUrl('Invalid URL "<b>%s</b>": %s' % (url, str(e)))

            # Check whether redirected
            if fullurl != response.geturl():
                util.create_file(noexist_file)
                raise BadUrl("%s does not exist (it redirects to %s)" % (url, response.geturl()))
            data = response.read()
            # python 2: data is hopefully utf-8 encoded bytestream
            # python 3: data has been decoded to unicode, recode it
            if not py2:
                data = data.decode('utf-8')
            try:
                with open(path, "w") as f:
                    f.write(data)
            except e:
                print(e)
                os.unlink(path)
            return data

        else:
            filename, headers = urlretrieve(fullurl, path)

    with open(path, 'rb') as fil:
        return fil.read()

def auto_decode(data, default_encoding = 'utf-8'):
    try:
        data = data.decode(default_encoding)
    except UnicodeDecodeError:
        data = data.decode('latin-1')
    return data

def get_page(url, encoding = 'utf-8', cache = True):
    """Download a URL or fetch it from the cache, and return a BS object"""
    data = get_url(url, cache = cache)
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
    return ''.join(tostr(piece).strip() for piece in tag.contents)


def translate(obj):
    "unfinished: remove all bs4.element.NavigableStrings"
    print("A")
    if hasattr(obj, 'items'):
        for k,v in obj.items():
            print("dict item")
            obj[k] = tostr(v)
            # if type(v) == bs4.element.NavigableString:
            #     obj[k] = tostr(v)
    elif hasattr(obj, '__getitem__'):
        for k,v in enumerate(obj):
            print("list item")
            obj[k] = translate(v)
            # if type(v) == bs4.element.NavigableString:
            #     print("list item")
            #     obj[k] = tostr(v)       
    elif hasattr(obj, '__dict__'):
        print("recurse")
        obj.__dict__ = translate(obj.__dict__)
    elif type(obj) == bs4.element.NavigableString:
        print("str")
        obj = tostr(obj)
    return obj
