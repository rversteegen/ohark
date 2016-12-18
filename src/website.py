import os.path
from cgi import parse_qs, escape
import sys
import tabulate

import gamedb

py2 = sys.version_info[0] == 2

# mod_python_wsgi doesn't really set the path variables so that it's
# possible to see where we are...
WEB_ROOT = './' #'/home/teeemcee/web'

DATA_DIR = '../src/'

print(os.path.abspath('.'))
print(__file__)

db = gamedb.GameList.load('cp')

def encode(obj):
    """Convert to correct format for returning to WSGI server"""
    if py2:
        return str(obj)
    return str(obj).encode('utf-8')

def text(obj):
    # Apparently escape encodes as bytes?
    return escape(str(obj)).replace('\n', '<br>\n')

with open(DATA_DIR + 'page_template.html', 'r') as temp:
    PAGE_TEMPLATE = temp.read()

def render_page(content, title = 'OHR Archive'):
    return [encode(PAGE_TEMPLATE.format(content = content, title = title))]

def gamelist(games):
    """
    Render a list of games.
    """
    ret = tabulate.tabulate((game.columns() for game in db.games.values()), headers, 'html')
    return render_page(ret)

def static_serve(environ, start_response):
    """Handles static file requests. Only needed when using wsgiref.simple_server"""
    fname = WEB_ROOT + environ['PATH_INFO']
    file_wrapper = environ['wsgi.file_wrapper']

    def send_file(fname):
        ext = fname.split('.')[-1]
        mimetype = {'txt': 'text/plain',
                    'html': 'text/html',
                    'css': 'text/css',
                    'js': 'application/javascript',
        }.get(ext, 'application/octet-stream')
        start_response('200 OK', [('Content-Type', mimetype)])
        return file_wrapper(open(fname, 'rb'))

    if os.path.isfile(fname):
        return send_file(fname)
    if os.path.isfile(fname + '/index.html'):
        return send_file(fname + '/index.html')

def application(environ, start_response):
    ret = static_serve(environ, start_response)
    if ret:
        return ret

    parameters = parse_qs(environ.get('QUERY_STRING', ''))
    param = ''
    if 'param' in parameters:
        param = escape(parameters['param'][0])

    start_response('200 OK', [('Content-Type', 'text/html')])
    headers = 'name', 'author', 'url', 'description'
    ret = headers

    #return [encode(ret)]
##, db.games.keys()))#, headers)) #, 'html'))

    return render_page(text(db.games) + text(environ))
