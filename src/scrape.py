#!/usr/bin/env python3

"""

"""

import sys
import time
import re
import os.path
import posixpath

py2 = sys.version_info.major == 2

#print(sys.stdout.encoding, "encoding")

# if py2:
#     # For printing unicode to console (otherwise encoding is 'ascii' so unicode can't be encoded)
#     import codecs
#     sys.stdout = codecs.getwriter('utf-8')(sys.stdout)

if py2:
    from urlparse import urlparse
    from urllib2 import urlopen, HTTPError
else:
    from urllib.parse import urlparse #, urljoin
    from urllib.request import urlopen
    from urllib.error import HTTPError

try:
    from mod_python import apache
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

# html.parser is less lenient
#parse_lib = "html5lib"
parse_lib = "html.parser"


thisdir = os.path.split(__file__)[0]
page_cache = os.path.abspath(thisdir) + '/cache'

extra_log_file = None

class BadInput(ValueError): pass

class TooManyRequests(Exception):
    remaining_allowed = 80

################################################################################
### Util

def write_log(text):
    global verbose_log
    if mod_python:
        if extra_log_file:
            with open(extra_log_file, "a") as f:
                f.write(text.encode('utf-8') + "\n")
    else:
        sys.stdout.write(text)

# Can be overridden by req.log_error() if running under mod_python
def error_log(text):
    sys.stderr.write(text + "\n")
    write_log(text)

def mkdir(dirname):
    if not os.path.isdir(dirname):
        try:
            os.makedirs(dirname)
        except OSError:
            if os.path.isdir(dirname):
                # Race condition: another process created it. Ignore
                return
            raise

def create_file(path):
    """Create an empty file if it doesn't exist"""
    with open(path, "a"):
        pass

def strip_strings(strings):
    """Given a list of strings, strip them""" # and remove whitespace-only strings"""
    return [x.strip() for x in strings]


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

def get_page(url):
    """Download a page or fetch it from the cache, and return a BS object"""
    # Get 'path': local location of cached file
    parsed = urlparse(url)
    path = page_cache + '/' + parsed.netloc + '/' + parsed.path
    if path[-1] == '/':
        path += 'index.html'
    noexist_file = path + '.missing'
    mkdir(os.path.dirname(path))
    print("---FETCHING", path)

    if os.path.isfile(noexist_file):
        raise BadUrl("%s does not exist (cached)" % (url))

    if not os.path.isfile(path):
        if TooManyRequests.remaining_allowed <= 0:
            raise TooManyRequests('Fetching ' + url)
        TooManyRequests.remaining_allowed -= 1
        time.sleep(0.4)

        print("Retrieving " + url)
        #urlretrieve(url, path)
        try:
            response = urlopen(url)
        except ValueError as e:
            create_file(noexist_file)
            raise BadUrl('Invalid URL "<b>%s</b>": %s' % (url, str(e)))
        # Check whether redirected
        if url != response.geturl():
            create_file(noexist_file)
            raise BadUrl("%s does not exist (it redirects to %s)" % (url, response.geturl()))
        data = response.read()
        # python 2: data is hopefully utf-8 encoded bytestream
        # python 3: data has been decoded to unicode, recode it
        if not py2:
            data = data.decode('utf-8')
        try:
            with open(path, "w") as f:
                f.write(data)
        except:
            os.unlink(path)

    with open(path) as fil:
        data = fil.read()
        data = data.decode('utf-8')
        # Convert non-breaking spaces to spaces
        #data = data.replace(u'\xa0', ' ')
        data = data.replace("&#160;", ' ')
        return BeautifulSoup(data, parse_lib)

def clean_page(page):
    """Given a BS page, remove junk"""
    page.head.clear()
    for tag in page("script"):
        tag.decompose()  # delete
    return str(page)
