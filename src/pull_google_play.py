#!/usr/bin/env python
"""
Pull game data from Google Play and add to the DB
"""
import time
from bs4 import BeautifulSoup, NavigableString

import scrape
import gamedb
import util

CACHE_INDEX = False

db = gamedb.GameList('googleplay')

def process_game_page(name, url):
    """Returns description"""
    dom = scrape.get_page(url)

    assert '?id=' in url and len(url.split('=')) == 2, "Expected only one query in page url, the id"
    srcid = url.split('=')[1]

    game = gamedb.Game()
    game.name = str(dom.find('div', class_='id-app-title').string)
    game.url = url
    game.downloads = [url]
    print ("Processing game:", game.name, "  \tsrcid:", srcid)

    author_div = dom.find('div', itemprop='author')
    game.author = str(author_div.find(itemprop='name').string)
    game.author_link = 'https://play.google.com' + author_div.a['href']

    # Grab description
    descrip_tag = dom.find(itemprop='description')
    game.description = '\n'.join(str(tag) for tag in descrip_tag.div.contents)

    # Categories (only one per game?)
    game.tags = []
    for link in dom.find_all('a', class_='document-subtitle category'):
        game.tags.append(str(link.span.string))

    # Grab screenshots
    datadir = "data/googleplay/" + srcid + '/'
    util.mkdir(datadir)

    for num, img in enumerate(dom.find_all('img', class_='full-screenshot')):
        data = scrape.get_url(img['src'])
        filename = datadir + 'screen%d.png' % num
        with open(filename, 'wb') as fil:
            fil.write(data)
        game.screenshots.append(filename)

    db.games[srcid] = game

def process_index_page(url):
    dom = scrape.get_page(url, cache = CACHE_INDEX)

    for link in dom.find_all('a', class_='title'):
        name = link['title']
        url = 'https://play.google.com' + link['href']
        #print(name, url)
        process_game_page(name, url)
        #time.sleep(0.5)


process_index_page('https://play.google.com/store/search?q=ohrrpgce&c=apps')

print(db.games)
db.save()
