#!/usr/bin/env python
"""
Pull game listings from the Castle Paradox game list

Usage:  ./pull_castleparadox.py [--backup]
"""
from __future__ import print_function
import sys
import time
import re
from bs4 import BeautifulSoup, NavigableString

import scrape
from urlimp import urljoin
import gamedb
import util
from util import py2, tostr

# Unfortunately some text is utf-8 and some is latin-1.
# But if each game entry is processed and auto-detected separately, that should be ok.
encoding = 'utf-8'
#encoding = 'latin-1'

# Whether to cache the main index and individual game pages
# Games are updated on CP too infrequently to bother...
CACHE_INDEX = True
CACHE_GAMES = True

stats = {'inline_screens': 0, 'downloaded_inline': 0, 'reviews': 0}

def process_game_page(url):
    dom = scrape.get_page(url, encoding, cache = CACHE_GAMES)

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
        game.author_link = urljoin(url, author_link['href'])

    # Grab description
    descrip_tag = dom.find(id='description').find('span', class_='gen')
    # Replace <br/> tags with newlines
    #game.description = '\n'.join(line.encode('utf-8').strip() for line in descrip_tag.find_all(string=True))
    # Preserve <br/> tags
    game.description = scrape.tag_contents(descrip_tag)

    # Download any images embedded in the description
    # (Currently there's only one such game, and all the links are dead!)
    for img_tag in descrip_tag.find_all('img'):
        print("Inline screenshot:", img_tag)
        stats['inline_screens'] += 1
        stats['downloaded_inline'] += game.add_screenshot_link(db.name, srcid, urljoin(url, img_tag['src']), is_inline = True)

    # Download optional
    download_link = dom.find('a', string=re.compile('Download: '))
    if download_link:
        # The text for the download link is e.g. "Download: 3.87 MB"
        download = gamedb.DownloadLink('cp', srcid + '.zip', urljoin(url, download_link['href']))
        download.sizestr = tostr(download_link.string[10:])
        game.downloads.append(download)

    # Complete/demo status
    if dom.find('span', class_='gen', string="Game is in demo stage"):
        game.tags.append('demo')
    elif dom.find('span', class_='gen', string="Game is in production"):
        game.tags.append('in production')
        # If it has a download, might as well put it in demo too
        if game.downloads:
            game.tags.append('demo')
        else:
            game.tags.append('no demo')
    elif dom.find('span', class_='gen', string="This is the final version"):
        game.tags.append('complete')
    else:
        print("!! %s: status not found" % srcid)

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
        game.add_screenshot_link(db.name, srcid, urljoin(url, img_tag['src']))

    # Reviews
    game.reviews = []
    for tag in dom.find_all('a', string=re.compile('Review #')):
        next_rows = tag.find_parent('tr').find_next_siblings('tr')
        author = tostr(next_rows[0].a.string)
        playtime = tostr(next_rows[1].span.string)
        score = tostr(next_rows[2].span.string).split('Overall: ')[-1]
        summary = tostr(next_rows[3].span.string)
        review = gamedb.Review(urljoin(url, tag['href']), author, score = score,
                               summary = summary, location = 'on Castle Paradox')
        game.reviews.append(review)
        stats['reviews'] += 1

    # Double-check that there are no NavigableStrings or undecoded strings
    game = scrape.clean_strings(game)

    #print(game.__dict__)
    db.games[srcid] = game

def process_index_page(url, limit = 9999):
    print("Fetching/parsing page...")
    dom = scrape.get_page(url, encoding, cache = CACHE_INDEX)

    container = dom.find('td', width='410')
    for tag in container.find_all('th'):
        # The first <a> is the link to the game, the second is the author
        gameurl = urljoin(url, util.remove_sid(tag.a['href']))
        process_game_page(gameurl)
        #time.sleep(0.1)
        limit -= 1
        if limit <= 0:
            break


scrape.TooManyRequests.remaining_allowed = 3000  # Override this safety-check

use_backup = len(sys.argv) >= 2 and sys.argv[1] == '--backup'
if not use_backup:
    db = gamedb.GameList('cp')

    process_index_page('http://castleparadox.com/search-gamelist.php?mirror=true')

    #process_game_page('http://castleparadox.com/gamelist-display.php?game=640')   # unicode author name
    #process_game_page('http://castleparadox.com/gamelist-display.php?game=1040')
else:
    # Or browse the backup
    db = gamedb.GameList('cpbkup')

    process_index_page('http://mirror.motherhamster.org/cp/castleparadox.com/search-gamelist.html')

    #process_game_page('http://mirror.motherhamster.org/cp/castleparadox.com/gamelist-display.html?game=963')


print(stats)
db.save()
