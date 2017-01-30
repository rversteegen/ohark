#!/usr/bin/env python
from __future__ import print_function
import os
from datetime import datetime
import time
import re
from bs4 import BeautifulSoup, NavigableString
import StringIO

import scrape
import gamedb
import util
from slimesalad_gamedump import ChunkReader, GameInfo

db = gamedb.GameList('ss')

def safe_string():
    "Accessing .string on a bs4 tag with no strign returns None"

def process_game_page(url):
    """Returns description"""
    dom = scrape.get_page(url, 'windows-1252')

    # Equivalent URLs for each game are
    # viewgame.php?t= (topic number), viewgame.php?p= (post number)
    # while viewtopic.php can be used instead of viewgame.php, but missing
    # the tags. Use topic number as srcid.
    assert 'viewgame.php?t=' in url and len(url.split('=')) == 2, "Expected game url to be viewgame.php?t=..."
    srcid = url.split('=')[1]


    game = gamedb.Game()
    game.name = dom.find(class_='title').string.encode('utf-8')
    game.url = url
    print ("Processing game:", game.name, "  \tsrcid:", srcid)

    author_box = dom.find(class_='gameauthor')
    game.author = author_box.find(class_='title').string.encode('utf-8')
    game.author_link = 'http://www.slimesalad.com/forum/' + util.remove_sid(author_box.a['href'])

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
        # strip leading ./ from link
        download = ('http://www.slimesalad.com/forum/' + util.remove_sid(tag['href'])[2:],
                    tag.b.string.encode('utf-8'),  # title of the download
                    download_count,
                    descrip_tag.string)  #.encode('utf-8'))
        game.downloads.append(download)

    # Grab screenshots
    for img_tag in dom.find_all('img', class_='attach_img'):
        datadir = 'data/%s/%s/' % (db.name, srcid)
        util.mkdir(datadir)

        data = scrape.get_url('http://www.slimesalad.com/forum/' + img_tag['src'])
        filename = datadir + img_tag['src'].split('/')[-1]
        with open(filename, 'wb') as fil:
            fil.write(data)
        game.screenshots.append(filename)

    # Reviews
    game.reviews = []
    for tag in dom.find_all('a', string='Review'):
        game.reviews.append('http://www.slimesalad.com/forum/' + tag['href'])

    # Tags
    for tag in dom.find_all(attrs = {'data-tag': True}):
        game.tags.append(str(tag.a.string))

    print(game.__dict__)
    db.games[srcid] = game


def process_index_page(url, limit = 9999):
    print("Fetching/parsing page...")
    page = scrape.get_url(url).decode('windows-1252')

    file = StringIO.StringIO(page)
    for chunk in ChunkReader(file).each():
        game = GameInfo(chunk)
        process_game_page(game.url)
        limit -= 1
        if limit <= 0:
            break

process_index_page('http://www.slimesalad.com/forum/gamedump.php')

#process_game_page('http://www.slimesalad.com/forum/viewgame.php?t=5419')

db.save()
