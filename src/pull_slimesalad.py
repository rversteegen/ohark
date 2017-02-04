#!/usr/bin/env python
from __future__ import print_function
import re

import scrape
from scrape import urljoin
import gamedb
import util
from util import py2, tostr
from slimesalad_gamedump import ChunkReader, GameInfo

if py2:
    from StringIO import StringIO
else:
    from io import StringIO

def process_game_page(url):
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
    for tag in dom.find_all('a', href=re.compile('download\.php')):
        #print(list(tag.next_siblings))
        info, descrip_tag, _ = tag.next_siblings
        # info is e.g. "(37.5 KB; downloaded 351 times)"
        download_count = int(info.split()[-2])
        download = (urljoin(url, util.remove_sid(tag['href'])),
                    tostr(tag.b.string),  # title of the download
                    download_count,
                    tostr(descrip_tag.string))
        game.downloads.append(download)

    # Grab screenshots
    for img_tag in dom.find_all('img', class_='attach_img'):
        datadir = 'data/%s/%s/' % (db.name, srcid)
        util.mkdir(datadir)

        data = scrape.get_url(urljoin(url, img_tag['src']))
        filename = datadir + img_tag['src'].split('/')[-1]
        with open(filename, 'wb') as fil:
            fil.write(data)
        game.screenshots.append(filename)

    # Reviews
    game.reviews = []
    for tag in dom.find_all('a', string='Review'):
        game.reviews.append(urljoin(url, tag['href']))

    # Tags
    for tag in dom.find_all(attrs = {'data-tag': True}):
        game.tags.append(tostr(tag.a.string))

    # Double-check that there are no NavigableStrings
    game = scrape.clean_strings(game)

    print(game.__dict__)
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
        process_game_page(game.url)
        limit -= 1
        if limit <= 0:
            break

link_db = gamedb.DataBaseLayer.cached_load('ss_links')

def srcid_for_SS_link(url):
    """
    Given a link to a game on SS, returns the srcid for the
    game, or None if it's not a link to a game.
    """
    parsed = scrape.urlparse(url)
    if (parsed.netloc != "www.slimesalad.com"
        or parsed.path not in ("/forum/viewtopic.php", "/forum/viewgame.php")):
        return None

    query = scrape.parse_qs(parsed.query)  # Parse to dict containing lists of values
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
