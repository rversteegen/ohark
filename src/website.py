import os.path
from cgi import parse_qs, escape
import sys
import tabulate

import gamedb

py2 = sys.version_info[0] == 2

# mod_python_wsgi doesn't really set the path variables so that it's
# possible to see where we are...
# Where the static files are on the server
STATIC_ROOT = './' #'/home/teeemcee/web'
# <base> tag, relative URLs according to this
URL_ROOTPATH = '/'  #'/ohr/ark/'

#SRC_DIR = '../src/'

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

with open(STATIC_ROOT + 'page_template.html', 'r') as temp:
    PAGE_TEMPLATE = temp.read()

def render_page(content, title = 'OHR Archive', status = '200 OK'):
    set_header(status, [('Content-Type', 'text/html')])
    return [encode(PAGE_TEMPLATE.format(content = content, title = title, root = URL_ROOTPATH))]

def gamelists(path):
    ret = "The following gamelists have been imported:<br/>"
    return render_page(ret)

def gamelist(games):
    """
    Render a list of games.
    """
    headers = 'name', 'author', 'url', 'description'
    ret = tabulate.tabulate((game.columns() for game in db.games.values()), headers, 'html')
    return render_page(ret)

def notfound(path):
    return (templated_static_page('404.html', status = '404 Not Found')
            or render_page("Not found.", status = '404 Not Found'))   # fallback

def templated_static_page(fname, status = '200 OK'):
    """Try to render an .html link by substituting the corresponding .content.html file into
    the global template; otherwise return None."""
    pagename, extn = os.path.splitext(fname)
    print pagename, os.path.abspath(os.curdir)
    if extn == '.html' and os.path.isfile(pagename + '.content.html'):
        with open(pagename + '.content.html', 'r') as temp:
            return render_page(temp.read(), status = status)

def static_serve(environ, start_response):
    """Handles static file requests. Only needed when using wsgiref.simple_server"""
    fname = STATIC_ROOT + environ['PATH_INFO']
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
    ret = templated_static_page(fname)
    if ret:
        return ret
    ret = templated_static_page(fname + '/index.html')
    if ret:
        return ret

def application(environ, start_response):
    global set_header
    set_header = start_response

    ret = static_serve(environ, start_response)
    if ret:
        return ret

    parameters = parse_qs(environ.get('QUERY_STRING', ''))
    print(parameters)
    param = ''
    if 'param' in parameters:
        param = escape(parameters['param'][0])

    # Figure out what to delegate to
#    return render_page(text(parameters))

    path = environ.get('PATH_INFO', '/').lower().split('/')[1:]
    if path[0] == "gamelists":
        return gamelists(path)
    else:
        return notfound(path)

    #return [encode(ret)]
##, db.games.keys()))#, headers)) #, 'html'))

    return render_page(text(environ))
