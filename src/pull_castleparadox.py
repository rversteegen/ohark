#!/usr/bin/env python
"""
Pull game listings from the Castle Paradox game list
"""
from __future__ import print_function
import time
import re
from bs4 import BeautifulSoup, NavigableString

import scrape
import gamedb
import util
from util import py2, tostr

db = gamedb.GameList('cp')

# Unfortunately some text is utf-8 and some is latin-1.
# But if each game entry is processed and auto-detected separately, that should be ok.
encoding = 'utf-8'
#encoding = 'latin-1'

def process_game_page(url):
    """Returns description"""
    dom = scrape.get_page(url, encoding)

    assert '?game=' in url and len(url.split('=')) == 2, "Expected only one query in page url, 'game'"
    srcid = url.split('=')[1]

    game = gamedb.Game()
    game.name = dom.find('th', class_='thHead').string.strip() #.encode('utf-8')
    game.url = url
    print ("Processing game:", game.name, "  \tsrcid:", srcid)

    author_link = dom.find('span', class_='gen').a
    game.author = tostr(author_link.string)
    #print(type(game.author), len(game.author), game.author[-1])
    # Some games imported from Op:OHR with no authors link to invalid author ID 0
    if not author_link['href'].endswith('&u=0'):
        # Remove leading './' on link
        game.author_link = 'http://castleparadox.com/' + author_link['href'][2:]

    # Grab description
    descrip_tag = dom.find(id='description').find('span', class_='gen')
    # Replace <br/> tags with newlines
    #game.description = '\n'.join(line.encode('utf-8').strip() for line in descrip_tag.find_all(string=True))
    # Preserve <br/> tags
    game.description = scrape.tag_contents(descrip_tag)

    # Download optional
    download_link = dom.find('a', string=re.compile('Download: '))
    if download_link:
        game.downloads = [ 'http://castleparadox.com/' + download_link['href'] ]

    # Grab download count and rating
    download_count = dom.find_all(string=re.compile('Download count: '))[0]
    game.download_count = int(download_count.split(': ')[1])
    rating = dom.find_all(string=re.compile('Average Grade: '))[0]
    rating = rating.split(': ')[1]
    if rating != 'N/A':
        game.rating = rating

    # Grab screenshot
    img_tag = dom.find('img', class_='zoomable')
    if img_tag:
        datadir = 'data/cp/' + srcid + '/'
        util.mkdir(datadir)

        data = scrape.get_url('http://castleparadox.com/' + img_tag['src'])
        filename = datadir + img_tag['src'].split('/')[-1]
        with open(filename, 'wb') as fil:
            fil.write(data)
        game.screenshots.append(filename)

    # Reviews
    game.reviews = []
    for tag in dom.find_all('a', string=re.compile('Review #')):
        game.reviews.append('http://castleparadox.com/' + tag['href'])

    # Double-check that there are no NavigableStrings
    game = scrape.clean_strings(game)

    print(game.__dict__)
    db.games[srcid] = game

def process_index_page(url, limit = 9999):
    print("Fetching/parsing page...")
    dom = scrape.get_page(url, encoding)

    container = dom.find('td', width='410')
    for tag in container.find_all('th'):
        # The first <a> is the link to the game, the second is the author
        url = 'http://castleparadox.com/' + util.remove_sid(tag.a['href'])
        process_game_page(url)
        #time.sleep(0.1)
        limit -= 1
        if limit <= 0:
            break


process_index_page('http://castleparadox.com/search-gamelist.php?mirror=true')

#process_game_page('http://castleparadox.com/gamelist-display.php?game=640')   # unicode author name
# process_game_page('http://castleparadox.com/gamelist-display.php?game=1040')

db.save()
