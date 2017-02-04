# -*- encoding: utf-8 -*-
"""
This is the implementation of the frontend. It generates all webpages, and also
serves static files.
"""

import os.path
import cgi
import sys
import time
import random

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
            return notfound("Game list %s does not exist." % listname)

        if len(path) == 2:
            return render_gamelist(db)
        else:
            gameid = path[2]

            # First, handle aliases to games as special cases (returns a redirection)
            ret = handle_game_aliases(path, db)
            if ret:
                return ret

            if gameid not in db.games:
                return notfound("Game %s/%s does not exist." % (listname, gameid))
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

def gamelist_filter_game(db, gameid):
    """
    Inspects the query part of the URL, and returns True if this
    game should be displayed on the game page
    """
    if 'tag' not in reqinfo.query:
        return True   # Show all games
    game = db.games[gameid]
    # There can be multiple tags=... in the query; show a game
    # if any of them match
    for tag in reqinfo.query['tag']:
        if tag in game.tags:
            return True
    return False

def gamelist_describe_filter(listname):
    """
    Provide a piece of text telling which filter is currently active for the gamelist display.
    """
    if 'tag' not in reqinfo.query:
        return ""
    tags = ' or '.join('"%s"' % tag for tag in reqinfo.query['tag'])
    return ("Filtering for games with tag %s. Click %s to show all games."
            % (tags, util.link("gamelists/" + listname, "here")))

def render_gamelist(db):
    """
    Generate one of the gamelists/X/ pages.
    """
    dbinfo = gamedb.SOURCES[db.name]
    is_gamelist = dbinfo['is_gamelist']
    topnote = util.link("gamelists/", "Back to gamelists ...") + "\n"
    # If there is a filter active, say so
    filterinfo = gamelist_describe_filter(db.name)

    # Generate a table as a list-of-lists, so it can be sorted
    if is_gamelist:
        headers = 'key', 'Name', 'Author', 'Link', 'Description'
    else:
        headers = 'File', 'Name', 'Description'
    table = []
    for gameid, game in db.games.items():
        # Filter out certain games
        if not gamelist_filter_game(db, gameid):
            continue

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

    table_html = "<tr>" + "".join("<th>%s</th>" % title for title in headers) + "</tr>\n"
    lines = []
    for row in table:
        lines.append("<tr>" + "".join("<td>%s</td>" % item for item in row) + "</tr>\n")
    table_html += "".join(lines)

    format_strs = {'listname': dbinfo['name'], 'table': table_html, 'filterinfo': filterinfo,
                   'numshown': len(table), 'numtotal': len(db.games)}
    return templated_page('gamelist.html', topnote = topnote, title = 'OHR Archive - ' + dbinfo['name'], **format_strs)

def screenshot_box(screenshot):
    """Given a gamedb.Screenshot, return some HTML for it and its description, if any"""
    content = screenshot.img_tag()
    if screenshot.description:
        content += '<div class="caption">%s</div>' % screenshot.description
    return '<div class="screenshot">%s</div>' % content

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
    if game.screenshots:
        shots = '\n'.join(screenshot_box(shot) for shot in game.screenshots)
        ret += add_row("Screenshots", shots)
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

def handle_gallery(path):
    """
    Generate a page of random screenshots.
    path is ignored.
    """
    screenshots = []

    for listname, listinfo in gamedb.SOURCES.items():
        if listinfo.get('hidden', False):
            continue
        db = gamedb.GameList.cached_load(listname)
        for srcid, game in db.games.items():
            gameurl = 'gamelists/%s/%s/' % (db.name, srcid)
            screenshots += [(gameurl, game.name, game.author, screenshot) for screenshot in game.screenshots]

    random.shuffle(screenshots)
    ret = ''
    for gameurl, gamename, gameauthor, screenshot in screenshots[:20]:
        ret += util.link(gameurl, screenshot.img_tag('%s by %s' % (gamename, gameauthor)))

    return templated_page('gallery.html', images = ret, title = 'OHRRPGCE Gallery')


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

def templated_page(fname, title = 'OHR Archive', topnote = '', status = '200 OK', **kwargs):
    """Try to render an .html link by substituting the corresponding .content.html file into
    the global template; otherwise return None."""
    pagename, extn = os.path.splitext(fname)
    print(pagename, os.path.abspath(os.curdir))
    if extn == '.html' and os.path.isfile(pagename + '.content.html'):
        with open(pagename + '.content.html', 'r') as temp:
            content = temp.read().decode('utf-8')   # Read, and first convert to unicode
            content = content.format(**kwargs)
            return render_page(content, title = title, topnote = topnote, status = status)

def notfound(message):
    return templated_page('404.html', message = message, title = 'OHR Archive - 404', status = '404 Not Found')

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
    ret = templated_page(fname)
    if ret:
        return ret
    ret = templated_page(fname + '/index.html')
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

    # Convert the query string "?..." into a dictionary
    # mapping to lists of values
    parameters = cgi.parse_qs(environ.get('QUERY_STRING', ''))
    reqinfo.query = parameters

    # Handle dynamic pages
    if path[0] == "gamelists":
        return handle_gamelists(path)
    elif path[0] == "gallery":
        return handle_gallery(path)
    else:
        return notfound(environ.get('PATH_INFO', '/') + " not found")
