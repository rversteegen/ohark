#!/usr/bin/env python
from __future__ import print_function
import re

import scrape
import urlimp
from urlimp import urljoin
import gamedb
import util
from util import py2, tostr
from slimesalad_gamedump import ChunkReader, GameInfo

if py2:
    from StringIO import StringIO
else:
    from io import StringIO


# This is optional (OK to fail loading); used for double checking downloads match
zips_db = gamedb.DataBaseLayer.load('zips')

def process_game_page(url, gameinfo = None):
    dom = scrape.get_page(url, 'windows-1252')

    #Every game on SS has *four* valid links, for example:
    # http://www.slimesalad.com/forum/viewgame.php?t=1021
    # http://www.slimesalad.com/forum/viewtopic.php?t=1021
    # http://www.slimesalad.com/forum/viewtopic.php?p=15109
    # http://www.slimesalad.com/forum/viewgame.php?p=15109
    # (?t= is topic number ?p= is post number)
    # While viewtopic.php can be used instead of viewgame.php, it's missing
    # the tags. Use topic number as srcid.
    assert 'viewgame.php?t=' in url and len(url.split('=')) == 2, "Expected game url to be viewgame.php?t=..."
    srcid = url.split('=')[1]

    # Update the database mapping between the t= and p= links
    link = dom.find(alt='Post').parent['href']
    postnum = int(link.split('#')[-1])
    topicnum = int(url.split('?t=')[-1])
    link_db['p2t'][postnum] = topicnum
    link_db['t2p'][topicnum] = postnum

    game = gamedb.Game()
    game.name = tostr(dom.find(class_='title').string)
    game.url = url
    print ("Processing game:", game.name, "  \tsrcid:", srcid)

    author_box = dom.find(class_='gameauthor')
    game.author = tostr(author_box.find(class_='title').string)
    game.author_link = urljoin(url, util.remove_sid(author_box.a['href']))

    # Grab description
    descrip_tag = dom.find(class_='postbody')
    # Remove <br> tags which are added on every newline
    # (Note: same games like Willy's also include <p> html, which gets lost
    #game.description = '\n'.join(line.encode('utf-8').strip() for line in descrip_tag.strings)
    # Preserve all
    game.description = scrape.tag_contents(descrip_tag)

    # Downloads
    # Have to match up the downloads on gamedump.php (with the mtimes and
    # actual download links) with the entries on the game page (with the descriptions).
    # The order in which the downloads appear in gamedump.php is mostly sorted by ascending
    # download id (which is not shown), but sometimes differs (probably when multiple
    # downloads were uploaded at once).
    # The order the downloads appear on the page is usually but not always
    # (e.g. http://www.slimesalad.com/forum/viewgame.php?t=220) the opposite order
    # (again, multi-uploads seem to cause some permutations).
    # So the kludge is to first match up the download names, and assume multiple downloads
    # with the same name were uploaded separately, and rely on the order of them being
    # opposite in the two lists.
    download_tags = dom.find_all('a', href=re.compile('download\.php'))
    def download_id(a_tag):
        ret = int(util.remove_sid(a_tag['href']).split('id=')[1])
        return ret
    #download_tags.sort(key = download_id)   # This also works instead of inverting
    download_tags = download_tags[::-1]

    for a_tag, gamefile in zip(download_tags, gameinfo.files):
        info, descrip_tag, _ = a_tag.next_siblings
        print("  ", gamefile.name, download_id(a_tag), a_tag.b.string)

    # Sometimes e.g. http://www.slimesalad.com/forum/viewgame.php?t=5996
    # an image is listed as a download, so doesn't appear in gameinfo.files
    #assert len(gameinfo.files) == len(download_tags)
    for a_tag in download_tags:
        info, descrip_tag, _ = a_tag.next_siblings
        # info is e.g. "(37.5 KB; downloaded 351 times)"
        info = info.split()
        download_url = urljoin(url, util.remove_sid(a_tag['href']))
        # The title of the download displayed on the page is the original
        # file name, need to use gamedump.php to find the mangled name.
        title = tostr(a_tag.b.string)  # Display name
        if gameinfo:
            gamefile = gameinfo.file_by_name(title)
            if gamefile in gameinfo.files:   # it might be in gameinfo.pics instead
                gameinfo.files.remove(gamefile)
            assert gamefile.name == title
            zip_fname = gamefile.url.split('/')[-1]
        else:
            zip_fname = title
        download = gamedb.DownloadLink('ss', zip_fname, download_url, title)
        download.count = int(info[-2])
        download.sizestr = info[0][1:] + ' ' + info[1][:-1]
        download.description = descrip_tag.string and tostr(descrip_tag.string)

        if zips_db and download.zipkey() in zips_db:
            # Double check we matched the files correcting by checking the sizes match
            expected = util.format_filesize(zips_db[download.zipkey()].size)
            assert download.sizestr == expected
        game.downloads.append(download)

    # Grab screenshots
    for img_tag in dom.find_all('img', class_='attach_img'):
        caption = img_tag.parent.find_next_sibling('div', class_='attachheader').string
        # caption is either None or a NavigableString
        if caption:
            caption = tostr(caption)
        game.add_screenshot(db.name, urljoin(url, img_tag['src']), caption)

    # Reviews
    game.reviews = []
    for tag in dom.find_all('a', string='Review'):
        game.reviews.append(urljoin(url, tag['href']))

    # Tags
    for tag in dom.find_all(attrs = {'data-tag': True}):
        game.tags.append(tostr(tag.a.string))

    # Double-check that there are no NavigableStrings or undecoded strings
    game = scrape.clean_strings(game)

    #print(game.__dict__)
    db.games[srcid] = game

def process_index_page(url, limit = 9999):
    """
    Generate the db and link_db databases (both global variables)
    """
    print("Fetching/parsing page...")
    page = scrape.get_url(url).decode('windows-1252')

    file = StringIO(page)
    for chunk in ChunkReader(file).each():
        game = GameInfo(chunk)
        process_game_page(game.url, game)
        limit -= 1
        if limit <= 0:
            break

link_db = gamedb.DataBaseLayer.load('ss_links')

def srcid_for_SS_link(url):
    """
    Given a link to a game on SS, returns the srcid for the
    game, or None if it's not a link to a game.
    """
    parsed = urlimp.urlparse(url)
    if (parsed.netloc != "www.slimesalad.com"
        or parsed.path not in ("/forum/viewtopic.php", "/forum/viewgame.php")):
        return None

    query = urlimp.parse_qs(parsed.query)  # Parse to dict containing lists of values
    if 't' in query:
        topicnum = int(query['t'][0])
        if topicnum not in link_db['t2p']:
            return None
        return topicnum
    elif 'p' in query:
        postnum = int(query['p'][0])
        return link_db['p2t'].get(postnum)
    return None

if __name__ == '__main__':
    db = gamedb.GameList('ss')
    link_db = {'p2t':{}, 't2p':{}}  # post -> topic and topic -> post mappings
    process_index_page('http://www.slimesalad.com/forum/gamedump.php')
    #process_game_page('http://www.slimesalad.com/forum/viewgame.php?t=5419')
    db.save()
    gamedb.DataBaseLayer.save('ss_links', link_db)

    # Tests
    assert srcid_for_SS_link('http://www.slimesalad.com/forum/viewtopic.php?p=15109#15109') == 1021
    assert srcid_for_SS_link('http://www.slimesalad.com/forum/viewgame.php?t=345') == 345
    assert srcid_for_SS_link('http://www.slimesalad.com/forum/viewgame.php?t=9999') == None
    assert srcid_for_SS_link('http://www.slimesalad.com/forum/viewtopic.php?t=7123') == None
