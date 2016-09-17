#!/usr/bin/env python3
"""
Pull game data from Google Play and add to the DB
"""
import time
from bs4 import BeautifulSoup, NavigableString

import scrape
from gamedb import db
import util


def process_game_page(name, url):
    """Returns description"""
    dom = scrape.get_page(url)

    assert '?id=' in url and len(url.split('=')) == 2, "Expected only one query in page url, the id"
    id = url.split('=')[1]

    game = db.find_game(id, "googleplay")
    game.name = str(dom.find('div', class_='id-app-title').string)
    print ("Processing game:", game.name, "  \tid:", id)

    # Grab description
    descrip_tag = dom.find(itemprop='description')
    game.description = '\n'.join(str(tag) for tag in descrip_tag.div.contents)

    # Grab screenshots
    datadir = "data/googleplay/" + id + '/'
    util.mkdir(datadir)

    for num, img in enumerate(dom.find_all('img', class_='full-screenshot')):
        data = scrape.get_url(img['src'])
        filename = datadir + 'screen%d.png' % num
        with open(filename, 'wb') as fil:
            fil.write(data)
        game.screenshots.add(filename)

def process_index_page(url):
    dom = scrape.get_page(url)

    for link in dom.find_all('a', class_='title'):
        name = link['title']
        url = 'https://play.google.com' + link['href']
        #print(name, url)
        process_game_page(name, url)
        #time.sleep(0.5)


process_index_page('https://play.google.com/store/search?q=ohrrpgce&c=apps')

print(db.db)
db.save()
