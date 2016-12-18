import os.path
from cgi import parse_qs, escape
import sys


py2 = sys.version_info[0] == 2

# mod_python_wsgi doesn't really set the path variables so that it's
# possible to see where we are...
WEB_ROOT = '/home/teeemcee/web'

def text(obj):
    if py2:
        return str(obj)
    return str(obj).encode('utf-8')

def application(environ, start_response):
    fname = WEB_ROOT + environ['PATH_INFO']
    file_wrapper = environ['wsgi.file_wrapper']

    def send_file(fname):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return file_wrapper(open(fname, 'rb'))

    if os.path.isfile(fname):
        return send_file(fname)
    if os.path.isfile(fname + '/index.html'):
        return send_file(fname + '/index.html')

    parameters = parse_qs(environ.get('QUERY_STRING', ''))
    param = ''
    if 'param' in parameters:
        param = escape(parameters['param'][0])

    start_response('200 OK', [('Content-Type', 'text/html')])
    return [text(environ)]
