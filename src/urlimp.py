import sys

py2 = sys.version_info[0] == 2

if py2:
    from urlparse import urlparse, urljoin, parse_qs
    from urllib import urlretrieve, quote, unquote, urlencode
    from urllib2 import urlopen, HTTPError
else:
    from urllib.parse import urlparse, urljoin, quote, unquote, urlencode, parse_qs
    from urllib.request import urlopen, urlretrieve
    from urllib.error import HTTPError
