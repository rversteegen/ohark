"""
This is the implementation of the frontend. It generates all webpages, and also
serves static files.
"""

import os.path
from cgi import parse_qs, escape
import sys
import time

import localsite
#import tabulate

import util
import gamedb

py2 = sys.version_info[0] == 2

# mod_python_wsgi doesn't really set the path variables so that it's
# possible to see where we are...
# Where the static files are on the server
#STATIC_ROOT = '/home/teeemcee/ohr/ohr_archive/web/'
STATIC_ROOT = '../web/' #os.path.abspath(os.curdir) + '../web/'
# <base> tag, relative URLs according to this
URL_ROOTPATH = '/ohr-archive/'  #'/ohr/ark/'

#SRC_DIR = '../src/'

print(os.path.abspath('.'))
print(__file__)

def encode(obj):
    """Convert to correct format for returning to WSGI server"""
    if py2:
        return unicode(obj).encode('utf-8')
    return str(obj).encode('utf-8')

def text(obj):
    # Apparently escape encodes as bytes?
    return escape(str(obj)).replace('\n', '<br>\n')

with open(STATIC_ROOT + 'page_template.html', 'r') as temp:
    if py2:
        PAGE_TEMPLATE = unicode(temp.read())
    else:
        PAGE_TEMPLATE = temp.read()


class RequestInfo:
    def __init__(self, start_response):
        self.start = util.timer()
        self.set_header = start_response
        self.footer_info = ''

reqinfo = RequestInfo(None)  # dummy

################################################################################

def handle_gamelists(path):
    "Delegate all URLs under gamelists/"
    if len(path) == 1:
        return render_gamelists()
    else:
        listname = path[1]
        with util.Timer() as timing:
            db = gamedb.GameList.cached_load(listname)
        reqinfo.footer_info += " DB load in %.3fs. " % timing.time
        if not db:
            return render_page("Game list %s does not exist." % listname, status = '404 Not Found')

        if len(path) == 2:
            return render_gamelist(db)
        else:
            gameid = path[2]
            if gameid not in db.games:
                return render_page("Game %s/%s does not exist." % (listname, gameid), status = '404 Not Found')
            return render_game(listname, gameid, db.games[gameid])

################################################################################

def render_gamelists():
    ret = "<h1>Archived Gamelists</h1>\n"
    ret += "The following gamelists have been imported:\n<ul>"
    for src, info in sorted(gamedb.SOURCES.items()):
        if info.get('hidden', False):
            continue
        ret += '<li> <a href="gamelists/%s">%s</a> </li>\n' % (src, info['name'])
    ret += '</ul>'
    return render_page(ret, 'OHR Archive - Gamelists')

def render_gamelist(db):
    """
    Render a list of games.
    """
    dbinfo = gamedb.SOURCES[db.name]
    is_gamelist = dbinfo['is_gamelist']
    ret = util.link("gamelists/", "Back to gamelists ...") + "\n"
    ret += "<h1>Gamelist: %s</h1>" % dbinfo['name']
    ret += "<p>Click the Name to go to the game entry.</p>\n"
    ret += "<p>%s games.</p><br/>\n" % len(db.games)
    if is_gamelist:
        headers = 'key', 'Name', 'Author', 'Link', 'Description'
    else:
        headers = 'File', 'Name', 'Description'
    table = []
    for gameid, game in db.games.items():
        #print(type(game.author), [hex(ord(x)) for x in game.author])
        row = []
        row.append( game.name.lower() )  # sort key
        #if is_gamelist:
        row.append( gameid )           
        row.append( util.link('gamelists/%s/%s/' % (db.name, gameid), game.get_name()) )
        if is_gamelist:
            #util.link(game.author_link, game.get_author())
            row.append( game.get_author() )
            row.append( game.url and util.link(game.url, "External") )
        row.append( util.shorten(util.strip_html(game.description), 150) )
        table.append(row)
    table.sort()
    # Strip the sort key
    table = [x[1:] for x in table]

    ret += """<table class="game" border="0">\n<tbody>\n"""
    ret += "<tr>" + "".join("<th>%s</th>" % title for title in headers) + "</tr>\n"
    lines = []
    for row in table:
        lines.append("<tr>" + "".join("<td>%s</td>" % item for item in row) + "</tr>\n")
    ret += "".join(lines)
    ret += "</tbody></table>\n"
    return render_page(ret, 'OHR Archive - ' + dbinfo['name'])

def render_game(listname, gameid, game):
    ret = util.link("gamelists/" + listname + "/", "Back to gamelist ...") + "\n"
    ret += "<h1>%s</h1>" % game.get_name()
    ret += """<table class="game" border="0">\n<tbody>\n"""
    def add_row(key, val, even_if_empty = False):
        if val or even_if_empty:
            return '<tr><td class="heading">%s</td><td>%s</td></tr>\n' % (key, val)
        return ''

    ret += add_row("Author", util.link(game.author_link, game.get_author()))
    if game.url:
        ret += add_row("Original entry", util.link(game.url, gameid) + " on " + gamedb.SOURCES[listname]['name'])
    else:
        ret += add_row("Origin/ID", gameid)
    ret += add_row("Description", game.description)
    ret += add_row("Tags", game.tags and ", ".join(game.tags))
    ret += add_row("Screenshots", game.screenshots) #"%d downloaded" % (len(game.screenshots),))
    ret += add_row("Downloads", game.downloads)
    ret += add_row("Reviews", game.reviews)
    ret += add_row("Info", game.extra_info)
    ret += add_row("Last modified", game.mtime and time.ctime(game.mtime))

    ret += "</tbody></table>\n"
    return render_page(ret, 'OHR Archive - ' + game.name)

################################################################################

def render_page(content, title = 'OHR Archive', status = '200 OK'):
    reqinfo.set_header(status, [('Content-Type', 'text/html')])
    reqinfo.footer_info += " Page rendered in %.3fs." % (util.timer() - reqinfo.start)
    return [encode(PAGE_TEMPLATE.format(
        content = content, title = title, root = URL_ROOTPATH,
        footer_info = reqinfo.footer_info
    ))]

def templated_static_page(fname, status = '200 OK'):
    """Try to render an .html link by substituting the corresponding .content.html file into
    the global template; otherwise return None."""
    pagename, extn = os.path.splitext(fname)
    print(pagename, os.path.abspath(os.curdir))
    if extn == '.html' and os.path.isfile(pagename + '.content.html'):
        with open(pagename + '.content.html', 'r') as temp:
            return render_page(temp.read(), status = status)

def notfound(path):
    return (templated_static_page('404.html', status = '404 Not Found')
            or render_page("Not found.", status = '404 Not Found'))   # fallback

def static_serve(path, environ, start_response):
    """Handles static file requests. Only needed when using wsgiref.simple_server"""
    fname = STATIC_ROOT + '/'.join(path)
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
    global reqinfo
    reqinfo = RequestInfo(start_response)

    path = environ.get('PATH_INFO', '/').lower()
    if path.startswith(URL_ROOTPATH):
        path = path[len(URL_ROOTPATH):]
    path = path.split('/')
    while '' in path:
        path.remove('')
    print(path)

    #return render_page(text(environ))

    ret = static_serve(path, environ, start_response)
    if ret:
        return ret

    parameters = parse_qs(environ.get('QUERY_STRING', ''))
    print(parameters)
    param = ''
    if 'param' in parameters:
        param = escape(parameters['param'][0])

    # Figure out what to delegate to

    if path[0] == "gamelists":
        return handle_gamelists(path)
    else:
        return notfound(path)

    #return render_page(text(environ))
