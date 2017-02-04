#!/usr/bin/env python
"""
Pull game data from Google Play and add to the DB
"""
from __future__ import print_function
import time

import scrape
from scrape import urljoin
import gamedb
import util
from util import py2, tostr

CACHE_INDEX = False

def process_game_page(name, url):
    """Returns description"""
    dom = scrape.get_page(url)

    assert '?id=' in url and len(url.split('=')) == 2, "Expected only one query in page url, the id"
    srcid = url.split('=')[1]

    game = gamedb.Game()
    game.name = tostr(dom.find('div', class_='id-app-title').string)
    game.url = url
    game.downloads = [url]
    print ("Processing game:", game.name, "  \tsrcid:", srcid)

    author_div = dom.find('div', itemprop='author')
    game.author = tostr(author_div.find(itemprop='name').string)
    game.author_link = urljoin(url, author_div.a['href'])

    # Grab description
    descrip_tag = dom.find(itemprop='description')
    game.description = '\n'.join(tostr(tag) for tag in descrip_tag.div.contents)

    # Categories (only one per game?)
    game.tags = []
    for link in dom.find_all('a', class_='document-subtitle category'):
        game.tags.append(tostr(link.span.string))

    # Grab screenshots
    datadir = 'data/%s/%s/' % (db.name, srcid)
    util.mkdir(datadir)

    for num, img in enumerate(dom.find_all('img', class_='full-screenshot')):
        #filename = datadir + 'screen%d.png' % num
        game.add_screenshot(db.name, img['src'])

    # Double-check that there are no NavigableStrings or undecoded strings
    game = scrape.clean_strings(game)

    db.games[srcid] = game

def process_index_page(url):
    dom = scrape.get_page(url, cache = CACHE_INDEX)

    for link in dom.find_all('a', class_='title'):
        name = link['title']
        gameurl = urljoin(url, link['href'])
        #print(name, gameurl)
        process_game_page(name, gameurl)
        #time.sleep(0.5)


db = gamedb.GameList('googleplay')

process_index_page('https://play.google.com/store/search?q=ohrrpgce&c=apps')
#process_game_page("C. Kane", "https://play.google.com/store/apps/details?id=com.superwalrusland.ckane")

print(db.games)
db.save()
