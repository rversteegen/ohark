# -*- encoding: utf-8 -*-
"""
This is the implementation of the frontend. It generates all webpages, and also
serves static files.
"""

import os.path
import cgi
import sys
import time

import localsite
#import tabulate

import util
import gamedb
import inspect_rpg
import pull_slimesalad

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

def handle_game_aliases(path, db):
    """
    Handle /gamelists/<listname>/<gameid>/... URLs which are aliases to the real pages
    by redirecting to the canonical page. Returns None if not an alias.

    path: a list of path segments; path[0]=='gamelists'
    db:   the loaded DB for this gamelist
    """
    # ss/p=###/..., where p=### is taken from a game URL, as an alias,
    listname, gameid = path[1], path[2]
    if listname == 'ss' and gameid.startswith('p='):
        link_db = gamedb.DataBaseLayer.cached_load('ss_links')
        srcid = link_db['p2t'].get(int(gameid[2:]))
        if not srcid:
            return None
        newpath = path[:]
        newpath[2] = str(srcid)
        url = URL_ROOTPATH + '/'.join(newpath)
        return redirect(url)
    return None

def handle_gamelists(path):
    """Delegate all URLs under gamelists/
    path is a list of path segments; path[0]=='gamelists'
    """
    if len(path) == 1:
        return render_gamelists()
    else:
        listname = path[1]
        with util.Timer() as timing:
            db = gamedb.GameList.cached_load(listname)
        reqinfo.footer_info += " DB load in %.3fs. " % timing.time
        if not db:
            return render_page("<p>Game list %s does not exist.</p>" % listname, status = '404 Not Found')

        if len(path) == 2:
            return render_gamelist(db)
        else:
            gameid = path[2]

            # First, handle aliases to games as special cases (returns a redirection)
            ret = handle_game_aliases(path, db)
            if ret:
                return ret

            if gameid not in db.games:
                return render_page("<p>Game %s/%s does not exist.</p>" % (listname, gameid), status = '404 Not Found')
            return render_game(listname, gameid, db.games[gameid])

################################################################################

def render_gamelists():
    """
    Generate the gamelists/ page
    """
    ret = "<h1>Archived Gamelists</h1>\n"
    ret += "<p>The following gamelists have been imported:</p>\n<ul>"
    for src, info in sorted(gamedb.SOURCES.items()):
        if info.get('hidden', False):
            continue
        ret += '<li> <a href="gamelists/%s">%s</a> </li>\n' % (src, info['name'])
    ret += '</ul>'
    return render_page(ret, title = 'OHR Archive - Gamelists')

def render_gamelist(db):
    """
    Generate one of the gamelists/X/ pages.
    """
    dbinfo = gamedb.SOURCES[db.name]
    is_gamelist = dbinfo['is_gamelist']
    topnote = util.link("gamelists/", "Back to gamelists ...") + "\n"
    ret = "<h1>Gamelist: %s</h1>" % dbinfo['name']
    ret += "<p>Click the Name to go to the game entry.</p>\n"
    ret += "<p>%s games.</p><br/>\n" % len(db.games)

    # Generate a table as a list-of-lists, so it can be sorted
    if is_gamelist:
        headers = 'key', 'Name', 'Author', 'Link', 'Description'
    else:
        headers = 'File', 'Name', 'Description'
    table = []
    for gameid, game in db.games.items():
        #print(type(game.author), [hex(ord(x)) for x in game.author])
        row = []
        row.append( game.name.lower().strip() )  # sort key
        #if is_gamelist:
        row.append( gameid )           
        row.append( util.link('gamelists/%s/%s/' % (db.name, gameid), game.get_name()) )
        if is_gamelist:
            #util.link(game.author_link, game.get_author())
            row.append( game.get_author() )
            row.append( game.url and util.link(game.url, u"➔") )
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
    return render_page(ret, topnote = topnote, title = 'OHR Archive - ' + dbinfo['name'])

def render_game(listname, gameid, game):
    """
    Generates a gamelists/<listname>/<gameid>/ page for a single game entry
    """
    topnote = util.link("gamelists/" + listname + "/", "Back to gamelist ...") + "\n"
    ret = "<h1>%s</h1>" % game.get_name()
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
    if game.website:
        ret += add_row("Website", util.link(game.website, game.website))
    ret += add_row("Description", game.description)
    ret += add_row("Tags", game.tags and ", ".join(game.tags))
    ret += add_row("Screenshots", game.screenshots) #"%d downloaded" % (len(game.screenshots),))
    ret += add_row("Downloads", game.downloads)
    ret += add_row("Reviews", game.reviews)
    info = game.extra_info
    if game.gen:
        info += "\n" + inspect_rpg.get_gen_info(game)
    ret += add_row("Info", util.text2html(info))
    ret += add_row("Last modified", game.mtime and time.ctime(game.mtime))

    ret += "</tbody></table>\n"
    return render_page(ret, topnote = topnote, title = 'OHR Archive - ' + game.name)

################################################################################

def render_page(content, title = 'OHR Archive', topnote = '', status = '200 OK'):
    """
    Put the content of a dynamic page in the generic template, and return it to the WGSI server.
    """
    reqinfo.set_header(status, [('Content-Type', 'text/html')])
    reqinfo.footer_info += " Page rendered in %.3fs." % (util.timer() - reqinfo.start)
    return [encode(PAGE_TEMPLATE.format(
        content = content, title = title, root = URL_ROOTPATH,
        topnote = topnote, footer_info = reqinfo.footer_info
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
            or render_page("<p>Not found.</p>", status = '404 Not Found'))   # fallback

def redirect(link):
    """
    Creates a redirection.
    """
    reqinfo.set_header('301 Moved Permanently', [('Content-Type', 'text/html'), ('Location', link)])
    return [encode("Please follow " + util.link(link, "this redirection"))]

def static_serve(path, environ, start_response):
    """Handles static file requests, and also templated static pages.
    Only needed when using wsgiref.simple_server"""
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
    """
    WGSI main entry point for the web app.
    """
    global reqinfo
    reqinfo = RequestInfo(start_response)

    path = environ.get('PATH_INFO', '/')
    if path.startswith(URL_ROOTPATH):
        path = path[len(URL_ROOTPATH):]
    path = path.split('/')
    while '' in path:
        path.remove('')
    print(path)

    #return render_page(text2html(environ))

    # Handle static files and templated static pages
    ret = static_serve(path, environ, start_response)
    if ret:
        return ret

    # Query string... not used
    parameters = cgi.parse_qs(environ.get('QUERY_STRING', ''))
    #print(parameters)
    param = ''
    if 'param' in parameters:
        param = cgi.escape(parameters['param'][0])

    # Handle dynamic pages
    if path[0] == "gamelists":
        return handle_gamelists(path)
    else:
        return notfound(path)
