# -*- encoding: utf-8 -*-
"""
This is the implementation of the frontend. It generates all webpages, and also
serves static files.
"""

from __future__ import print_function
import os.path
import cgi
import sys
import time
import random
from collections import defaultdict

import localsite
#import tabulate

import urlimp
import util
from util import py2
import gamedb
import inspect_rpg
import pull_slimesalad


# mod_python_wsgi doesn't really set the path variables so that it's
# possible to see where we are...
# Where the static files are on the server
#STATIC_ROOT = '/home/teeemcee/ohr/ohr_archive/web/'
STATIC_ROOT = '../web/' #os.path.abspath(os.curdir) + '../web/'
# Part of <base> tag, relative URLs according to this
URL_ROOTPATH = '/ohr-archive/'  #'/ohr/ark/'

#SRC_DIR = '../src/'

print(os.path.abspath('.'))
print(__file__)

################################################################################
# WSGI utility functions, and request handling

def get_website_root():
    "Reconstruct the address for this website"
    environ = reqinfo.environ
    url = environ['wsgi.url_scheme']+'://'
    if environ.get('HTTP_HOST'):
        url += environ['HTTP_HOST']
    else:
        url += environ['SERVER_NAME']
        defport = {'http': '80', 'https': '443'}[environ['wsgi.url_scheme']]
        if environ['SERVER_PORT'] != defport:
            url += ':' + environ['SERVER_PORT']
    return url + URL_ROOTPATH

def encode(obj):
    """Convert to correct format for returning to WSGI server"""
    if py2:
        return unicode(obj).encode('utf-8')
    return str(obj).encode('utf-8')

class RequestInfo:
    def __init__(self, environ, start_response):
        "Initialise self and global variables for a new request"
        self.req_timer = util.Timer().start()  # Time the total time spent handling the request
        self.environ = environ
        self.set_header = start_response
        self.footer_info = ''
        self.DB_timer = util.Timer()  # Time DB loads
        gamedb.DataBaseLayer.reqinfo = self  # Make DB_timer available to DB code

    def get_footer(self):
        ret = self.footer_info
        if self.DB_timer.time:
             ret += " DB load in %.3fs. " % self.DB_timer.time
        self.req_timer.stop()
        ret += " Page rendered in %.3fs." % self.req_timer.time
        return ret


reqinfo = RequestInfo(None, None)  # dummy


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
        link_db = gamedb.DataBaseLayer.load('ss_links')
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
        db = gamedb.GameList.load(listname)
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
    topnote = util.link("/", "Back to root ...") + "\n"
    ret = "<h1>Mirrored Gamelists</h1>\n"
    ret += "<p>The following gamelists have been imported:</p>\n<ul>"
    for src, info in sorted(gamedb.SOURCES.items()):
        if info.get('hidden', False):
            continue
        ret += '<li> <a href="gamelists/%s">%s</a> </li>\n' % (src, info['name'])
    ret += '</ul>'
    return render_page(ret, title = 'OHR Archive - Gamelists', topnote = topnote)

def gamelist_filter_game(game):
    """
    Inspects the query part of the URL, and returns True if this
    game should be displayed on the game page
    """
    if 'tag' in reqinfo.query:
        # There can be multiple tags=... in the query; show a game
        # if any of them match
        for tag in reqinfo.query['tag']:
            if tag in game.tags:
                break
        else:
            return False
    if 'author' in reqinfo.query:
        if game.author not in reqinfo.query['author']:
            return False
    if 'search' in reqinfo.query:
        found = False
        for term in reqinfo.query['search']:
            term = term.lower()
            # FIXME: tags aren't lower-cased, so tags which aren't lower-case can't be found!
            if (term in game.author.lower() or term in game.name.lower()
                or term in game.description.lower() or term in game.tags
                or term in game.extra_info):
                break
            for screenshot in game.screenshots:
                if screenshot.description and term in screenshot.description.lower():
                    found = True
                    break
            if found: break
            for download in game.downloads:
                if term in download.title.lower() or (download.description and term in download.description.lower()):
                    found = True
                    break
            if found: break
        else:
            return False
    return True

def gamelist_describe_filter():
    """
    Provide a piece of text telling which filter is currently active for the gamelist display.
    """
    filters = []
    if 'tag' in reqinfo.query:
        filters.append("tags " + " or ".join('"%s"' % tag for tag in reqinfo.query['tag']))
    if 'author' in reqinfo.query:
        filters.append("author " + " or ".join('"%s"' % author for author in reqinfo.query['author']))
    if 'search' in reqinfo.query:
        filters.append("word " + " or ".join('"%s"' % string for string in reqinfo.query['search']))
    if not filters:
        return ""
    backlink = reqinfo.path  #  Easy way to remove the query
    return ("Filtering for games with %s. Click %s to show all games."
            % (", and ".join(filters), util.link(backlink, "here")))

def render_gamelist(db):
    """
    Generate one of the gamelists/<db.name>/ pages.
    """
    dbinfo = gamedb.SOURCES[db.name]
    # If there is a filter active, say so
    filterinfo = gamelist_describe_filter()
    numtotal = len(db.games)

    keyed_games = []
    for gameid, game in db.games.items():
        # Filter out certain games
        if gamelist_filter_game(game):
            keyed_games.append((db.name, gameid, game))

    return render_games_table(keyed_games, dbinfo['name'], dbinfo['is_gamelist'], filterinfo, numtotal)

def render_games(path):
    """
    Generate the games/ page. Right now this simply combines all game lists.
    """
    keyed_games = []
    numtotal = 0
    for listname, listinfo in gamedb.SOURCES.items():
        if listinfo.get('hidden'):
            continue
        db = gamedb.GameList.load(listname)
        numtotal += len(db.games)
        for gameid, game in db.games.items():
            # Filter out certain games
            if gamelist_filter_game(game):
                keyed_games.append((db.name, gameid, game))

    # If there is a filter active, say so
    filterinfo = gamelist_describe_filter()

    return render_games_table(keyed_games, "All games", True, filterinfo, numtotal, show_source = True)

def render_games_table(keyed_games, list_title, is_gamelist, filterinfo, numtotal, show_source = False):
    """
    Generate a page with a table containing a list of games.

    keyed_games:  This is a list of (dbname: str, srcid: str, game: Game) tuples.
    list_title:   What title to put on the page
    is_gamelist:  True if this is one of the imported game lists, not a list of .rpgs.
    filterinfo:   Extra info shown at the top.
    show_source:  Add the 'Source' column.
    """
    zips_db = gamedb.DataBaseLayer.load('zips')
    # Generate a table as a list-of-lists, so it can be sorted
    if is_gamelist:
        headers = 'Name', 'Author', 'Link', 'Download?', 'Description'
    else:
        headers = 'Name', 'Download?', 'Description'
    if show_source:
        headers = ('Source',) + headers
    table = []
    for dbname, gameid, game in keyed_games:
        row = []
        row.append( game.name.lower().strip() )  # sort key 
        if show_source:
            row.append( dbname )
        row.append( util.link('gamelists/%s/%s/' % (dbname, gameid), game.get_name()) )
        if is_gamelist:
            #util.link(game.author_link, game.get_author())
            row.append( game.get_author() )
            row.append( game.url and util.link(game.url, u"➔") )
        row.append( get_game_download_summary(game, zips_db) )
        row.append( util.shorten(util.strip_html(game.description), 150) )
        table.append(row)
    table.sort()
    # Strip the sort key
    table = [x[1:] for x in table]

    topnote = util.link("gamelists/", "Back to gamelists ...") + "\n"

    table_html = "<tr>" + "".join("<th>%s</th>" % title for title in headers) + "</tr>\n"
    lines = []
    for row in table:
        lines.append("<tr>" + "".join("<td>%s</td>" % item for item in row) + "</tr>\n")
    table_html += "".join(lines)

    format_strs = {'listname': list_title, 'table': table_html, 'filterinfo': filterinfo,
                   'numshown': len(table), 'numtotal': numtotal}
    return templated_page('gamelist.html', topnote = topnote, title = 'OHR Archive - ' + list_title, **format_strs)

def screenshot_box(screenshot):
    """Given a gamedb.Screenshot, return some HTML for it and its description, if any"""
    content = screenshot.img_tag()
    if screenshot.description:
        content += '<div class="caption">%s</div>' % screenshot.description
    return '<div class="screenshot">%s</div>' % content

def get_game_archives_info(game):
    """
    Generates the "Appears in" info for a game entry for an .rpg file, listing the .zips
    or other locations where it appears.
    """
    zips_db = gamedb.DataBaseLayer.load('zips')
    archive_links = []
    for zipkey in game.archives:
        srcname, zipname = zipkey.split(':', 1)
        if zipkey in zips_db:
            link = util.link("zips/" + zipkey, zips_db[zipkey].name())
        else:
            link = zipname
        link += find_game_with_zip(zipkey)
        archive_links.append(link)
    return "<br/>".join(archive_links)

def get_game_downloads_info(game):
    """
    Generates the contents of the Downloads section of a game listing.
    """
    zips_db = gamedb.DataBaseLayer.load('zips')
    rpgs_db = gamedb.DataBaseLayer.load('rpgs')
    download_lines = []
    for downloadlink in game.downloads:
        zipdata = downloadlink.load_zipdata()
        entry = downloadlink.name()
        if zipdata:
            entry += " - " + util.link(downloadlink.internal(), "[info]")
        else:
            entry += " - " + "[not processed]"
        if downloadlink.external:
            entry += " " + util.link(downloadlink.external, "[external download]")
        if zipdata:
            size = util.format_filesize(zipdata.size)
        else:
            size = downloadlink.sizestr  # Might be ""
        if size:
            entry += " (" + size + ")"
        if downloadlink.description:
            entry += " - " + downloadlink.description

        # Preview the .rpgs/.rpgdirs contained in the download
        key = downloadlink.zipkey()
        contents_lines = []
        if key in zips_db:
            zip = zips_db[key]
            if zip.unreadable:
                contents_lines.append('Unreadable file')
            else:
                for fname, gamehash in zips_db[key].rpgs.items():
                    rpg = rpgs_db[gamehash]
                    contents_lines.append("%s -- %s -- %s" % (util.link('gamelists/rpgs/' + gamehash, fname), rpg.name, rpg.description))
        else:
            contents_lines.append('Skipped')
        entry += '<ul>%s</ul>' % '\n'.join('<li>%s</li>' % line for line in contents_lines)

        download_lines.append('<li>%s</li>' % entry)
    return '<ul>%s</ul>' % '\n'.join(download_lines)

def get_game_reviews_info(game):
    """Generate contents of the Reviews section of a game page"""
    lines = []
    for review in game.reviews:
        byline = review.byline
        if not byline:
            byline = review.article_type
            if review.author:
                byline += " by %s" % review.author
        second_line = ''
        if review.summary:
            second_line = '<div class="review_summary">%s</div>' % review.summary
        lines.append('<li>%s %s %s</li>' % (util.link(review.url, byline), review.location, second_line))
    return '<ul>%s</ul>' % '\n'.join(lines)

def get_game_download_summary(game, zips_db):
    """Tell whether a game has a download available"""
    if game.archives:
        # Assume the zip is actually downloadable (FIXME: return Yes for loose .rpgs too)
        return "Yes"
    if not game.downloads and not game.website:
        return "No"
    for download in game.downloads:
        key = download.zipkey()
        if key in zips_db:
            if hasattr(zips_db[key], 'rpgs') and zips_db[key].rpgs:
                # Has at least one rpg/rpgdir, even if it's corrupt or unextractable
                return "Yes"
    # There are download links but we don't recognise them
    return "?"

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

    if listname != 'rpgs':
        ret += add_row("Author", util.link(game.author_link, game.get_author()))
    if game.url:
        ret += add_row("Original entry", util.link(game.url, "On " + gamedb.SOURCES[listname]['name']))
    # else:
    #     ret += add_row("Origin/ID", gameid)
    if game.website:
        ret += add_row("Website", util.link(game.website, game.website))
    ret += add_row("Description", game.description)
    if game.archives:
        ret += add_row("Appears in", get_game_archives_info(game))
    ret += add_row("Tags", ", ".join(util.link("games?tag=" + tag, tag) for tag in game.tags))
    if game.screenshots:
        # Ignore screenshots which are inlined into the description
        shots = '\n'.join(screenshot_box(shot) for shot in game.screenshots if not shot.is_inline)
        ret += add_row("Screenshots", shots)
    if game.error:
        ret += add_row("Error messages", game.error)
    if game.downloads:
        ret += add_row("Downloads", get_game_downloads_info(game))
    if game.reviews:
        ret += add_row("Reviews", get_game_reviews_info(game))
    info = game.extra_info
    if game.gen:
        info += "\n" + inspect_rpg.get_gen_info(game)
    ret += add_row("Info", util.text2html(info))
    ret += add_row("Last modified", game.mtime and time.ctime(game.mtime))

    ret += "</tbody></table>\n"
    return render_page(ret, topnote = topnote, title = 'OHR Archive - ' + game.name)

################################################################################

def render_tags(path):
    """
    Handles tags/ URL. Show list of all tags.
    """
    sorttype = reqinfo.query.get('sort', ['name'])[0]
    display = reqinfo.query.get('display', ['cloud'])[0]
    threshold = int(reqinfo.query.get('threshold', [1])[0])

    tags = defaultdict(int)
    for listname, listinfo in gamedb.SOURCES.items():
        if listinfo.get('hidden', False):
            continue
        db = gamedb.GameList.load(listname)
        for game in db.games.values():
            for tag in game.tags:
                tags[tag] += 1

    tags = [(name, count) for name, count in tags.items() if count >= threshold]
    if sorttype == "count":
        tags.sort(key = lambda x : -x[1])
    else:  # "name"
        tags.sort(key = lambda x : x[0].lower())

    ret = '<div class="%s">' % ("tag" + display)
    for tag, count in tags:
        ret += "<div>%dx %s</div>\n" % (count, util.link("games?tag=" + tag, tag))
    ret += "</div>"
    return templated_page('tags.html', title = 'OHR Archive - Tags',
                          content = ret, sort = sorttype, display = display, threshold = threshold,
                          topnote = util.link("/", "Back to root ..."))

################################################################################

def handle_gallery(path):
    """
    Generate a page of screenshots. Randomly sorted or paged.
    path is ignored.
    """
    screenshots = []

    for listname, listinfo in sorted(gamedb.SOURCES.items()):
        if listinfo.get('hidden', False):
            continue
        db = gamedb.GameList.load(listname)
        for srcid, game in db.games.items():
            if gamelist_filter_game(game):
                gameurl = 'gamelists/%s/%s/' % (db.name, srcid)
                screenshots += [(gameurl, game.name, game.author, screenshot) for screenshot in game.screenshots]

    pagesize = int(reqinfo.query.get('pagesize', [16])[0])
    info = 'Found %s screenshots. ' % len(screenshots)

    def page_url(page = None, random = False):
        """Generate URL for a certain page, or for the random page.
        Preserves the existing query (search terms)."""
        newquery = reqinfo.query.copy()
        newquery.pop('page', None)   # Remove these
        newquery.pop('random', None)
        if page is not None:
            newquery['page'] = page
        if random:
            newquery['random'] = ''
        return reqinfo.path + '?' + urlimp.urlencode(newquery, doseq = True)

    if 'random' in reqinfo.query:
        random.shuffle(screenshots)
        info += "Randomised. " + util.link(page_url(random = True), "Reload") + " to see more! "
        nextpage = 0
        titletext = "Random Gallery"
    else:
        page = int(reqinfo.query.get('page', [0])[0])
        screenshots = screenshots[page * pagesize : (page + 1) * pagesize]
        info += "%s. Page %s. " % (util.link(page_url(random = True), "Randomise"), page)
        nextpage = page + 1
        titletext = "Gallery"
    info += util.link(page_url(page = nextpage), "Go to page %d" % nextpage) + "."

    topnote = util.link("/", "Back to root ...") + "\n"
    ret = "<p>" + info + "</p>"
    ret += "<p>" + gamelist_describe_filter() + "</p>"
    for gameurl, gamename, gameauthor, screenshot in screenshots[:pagesize]:
        byline = (" by %s" % gameauthor) if gameauthor else ""
        ret += util.link(gameurl, screenshot.img_tag('%s%s' % (gamename, byline)))

    return templated_page('gallery.html', images = ret, title = 'OHRRPGCE Gallery',
                          titletext = titletext, topnote = topnote)

################################################################################

def find_game_with_zip(zipkey):
    """Figure out which game has a download for this zip file; return a link to it."""
    srcname, zipname = zipkey.split(':', 1)
    if srcname not in gamedb.SOURCES:
        return " from collection '%s'" % srcname
    location = " on " + gamedb.SOURCES[srcname]['name']
    games_db = gamedb.GameList.load(srcname)
    for srcid, game in games_db.games.items():
        #game = games_db.games
        for download in game.downloads:
            if download.zipkey() == zipkey:
                return " from " + util.link('gamelists/%s/%s' % (srcname, srcid), game.name) + location
    # This can happen for example with old mirrored versions of downloads on SS,
    # which are no longer linked to by their game entries. Or reviews on Op:OHR.
    return " from unknown game" + location + "?"

def render_zip_contents(zips_db, zipkey, fname):
    """
    Handles zips/<zipkey>/<fname> URLs.
    Display the contents of a file in a zip file that was saved when the file was scanned
    (small text files)
    """
    zipdata = zips_db[zipkey]

    topnote = util.link("/zips/" + zipkey, "Back to %s..." % zipdata.name()) + "\n"
    if fname not in zipdata.files:
        return notfound("That file is not available here; download the .zip yourself to view it.")
    ret = '<h1>%s/%s</h1>\n' % (zipdata.name(), fname)
    ret += '<div class="textfile">%s</div>' % util.text2html(zipdata.files[fname])
    return render_page(ret, title = fname, topnote = topnote)

def render_zip(zips_db, zipkey):
    """
    Handles zips/<zipkey> URLs.
    Generate a page showing the contents of a zip file.
    zipkey is of the form "listname:zipname" which identify the source
    gamelist/website (e.g. 'ss') and the specific zip file, e.g. 189.zip.
    """
    zipdata = zips_db[zipkey]

    topnote = util.link("/zips", "Back to index ...") + "\n"
    downloadable = 'Downloadable ' + find_game_with_zip(zipkey)
    note = note2 = table_html = ""

    if zipdata.unreadable:
        note = "This zip file is corrupt or could not be read (e.g. uses unusual compression)."
    else:
        lines = []
        for fname, size, mtime in sorted(zipdata.filelist):
            name = fname
            if fname in zipdata.files:
                # We copied the contents of this file, provide a link to it
                name = util.link("zips/%s/%s" % (zipkey, fname), name)
            if fname in zipdata.rpgs:
                if zipdata.rpgs[fname] is None:
                    # This game couldn't even be hashed, there was an error while extracting files
                    # from the zip (though not necessarily this file)
                    pass
                else:
                    name = util.link("gamelists/rpgs/%s/" % zipdata.rpgs[fname], name)

            lines.append( "<tr><td>%s</td><td>%s</td><td>%s</td></tr>\n" % (name, size, time.ctime(mtime)) )
        table_html = "".join(lines)

    if zipdata.error:
        note2 = "An error occurred while reading this .zip: " + zipdata.error

    format_strs = {'heading': zipdata.name(), 'table': table_html, 'size': zipdata.size,
                   'mtime': time.ctime(zipdata.mtime), 'downloadable': downloadable, 'note': note, 'note2': note2}
    return templated_page('zipinfo.html', topnote = topnote, title = 'OHR Archive - ' + zipdata.name(), **format_strs)

def render_zips(zips_db):
    """
    Handles zips/ URL. Show list of zips. This is for admin purposes, probably won't be public.
    """
    # Just show a simple table
    ret = "<ul>"
    for zipkey in sorted(zips_db.keys()):
        ret += "<li>%s</li>\n" % util.link("zips/" + zipkey, zipkey)
    ret += "</ul>"
    return render_page(ret, topnote = util.link("/", "Back to root ..."))

def handle_zips(path):
    """
    Handle all URLs below zips/
    """
    zips_db = gamedb.DataBaseLayer.load('zips')
    if len(path) == 1:
        # Index
        return render_zips(zips_db)
    else:
        zipkey = path[1]
        if zipkey not in zips_db:
            return notfound("Zip file %s not found." % zipkey)

        if len(path) == 2:
            return render_zip(zips_db, zipkey)
        else:
            return render_zip_contents(zips_db, zipkey, "/".join(path[2:]))

################################################################################
## Top-level application code and WSGI interfacing

with open(STATIC_ROOT + 'page_template.html', 'r') as temp:
    if py2:
        PAGE_TEMPLATE = unicode(temp.read())
    else:
        PAGE_TEMPLATE = temp.read()

def render_page(content, title = 'OHR Archive', topnote = '', status = '200 OK'):
    """
    Put the content of a dynamic page in the generic template, and return it to the WGSI server.
    """
    reqinfo.set_header(status, [('Content-Type', 'text/html')])
    return [encode(PAGE_TEMPLATE.format(
        content = content, title = title, root = get_website_root(),
        topnote = topnote, footer_info = reqinfo.get_footer()
    ))]

def templated_page(fname, title = 'OHR Archive', topnote = '', status = '200 OK', ignore_missing = False, **kwargs):
    """Try to render an .html link by substituting the corresponding .content.html file into
    the global template; otherwise return None if 'ignore_missing' or raise an exception."""
    pagename, extn = os.path.splitext(fname)
    if ignore_missing:
        if not (extn == '.html' and os.path.isfile(pagename + '.content.html')):
            return None
    with open(pagename + '.content.html', 'r') as temp:
        content = temp.read()
        if py2:
            content = content.decode('utf-8')   # read() produced str, not unicode
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
    ret = templated_page(fname, ignore_missing = True)
    if ret:
        return ret
    ret = templated_page(fname + '/index.html', ignore_missing = True)
    if ret:
        return ret

def application(environ, start_response):
    """
    WSGI main entry point for the web app.
    """
    global reqinfo
    reqinfo = RequestInfo(environ, start_response)

    path = environ.get('PATH_INFO', '/')
    # For some reason for me for Python 3 wsgiref.simple_server, PATH_INFO
    # is a str but hasn't been decoded as utf-8
    if not py2:
        path = path.encode('latin-1')
    path = path.decode('utf-8')
    reqinfo.path = path
    if path.startswith(URL_ROOTPATH):
        path = path[len(URL_ROOTPATH):]
    path = path.split('/')
    while '' in path:
        path.remove('')

    # return render_page(util.text2html(str(environ)))

    # Handle static files and templated static pages
    ret = static_serve(path, environ, start_response)
    if ret:
        return ret

    # Convert the query string "?..." into a dictionary
    # mapping to lists of values
    parameters = cgi.parse_qs(environ.get('QUERY_STRING', ''), keep_blank_values = True)
    reqinfo.query = parameters

    # Handle dynamic pages
    if path[0] == "gamelists":
        return handle_gamelists(path)
    elif path[0] == "gallery":
        return handle_gallery(path)
    elif path[0] == "games":
        return render_games(path)
    elif path[0] == "zips":
        return handle_zips(path)
    elif path[0] == "tags":
        return render_tags(path)
    else:
        return notfound(reqinfo.path + " not found")
