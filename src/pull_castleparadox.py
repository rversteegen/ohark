#!/usr/bin/env python
"""
Pull game listings from the Castle Paradox game list
"""
import time
import re
from bs4 import BeautifulSoup, NavigableString

import scrape
import gamedb
import util

db = gamedb.GameList('cp')

_sid_regex = re.compile('(.*)(&(amp;)?sid=[0-9a-f]*)(.*)')

def remove_sid(url):
    """Remove &sid=... query, if any, from a url"""
    match = _sid_regex.match(url)
    if match:
        return match.group(1) + match.group(4)
    return url

assert remove_sid('gamelist-display.php?game=206&amp;sid=d12a342f6ae0d&foo=bar') == 'gamelist-display.php?game=206&foo=bar'
assert remove_sid('gamelist-display.php?game=206&sid=d12a342f6ae0d&foo=bar') == 'gamelist-display.php?game=206&foo=bar'
assert remove_sid('gamelist-display.php?game=206&sid=d12a342f6ae0d') == 'gamelist-display.php?game=206'
assert remove_sid('gamelist-display.php?game=206') == 'gamelist-display.php?game=206'


def process_game_page(url):
    """Returns description"""
    dom = scrape.get_page(url, 'latin-1')

    assert '?game=' in url and len(url.split('=')) == 2, "Expected only one query in page url, 'game'"
    srcid = url.split('=')[1]

    game = gamedb.Game()
    game.name = str(dom.find('th', class_='thHead').string)
    game.url = url
    print ("Processing game:", game.name, "  \tsrcid:", srcid)

    author_link = dom.find('span', class_='gen').a
    game.author = str(author_link.string)
    # Some games imported from Op:OHR with no authors link to invalid author ID 0
    if not author_link['href'].endswith('&u=0'):
        # Remove leading './' on link
        game.author_link = 'http://castleparadox.com/' + author_link['href'][2:]

    # Grab description
    descrip_tag = dom.find(id='description').find('span', class_='gen')
    game.description = '\n'.join(str(tag).strip() for tag in descrip_tag.find_all(string=True))

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

    print(game.__dict__)
    #db.games[srcid] = game

def process_index_page(url):
    print("Fetching page..")
    dom = scrape.get_page(url, 'latin-1')

    container = dom.find('td', width='410')
    for tag in container.find_all('th'):
        # The first <a> is the link to the game, the second is the author
        url = 'http://castleparadox.com/' + remove_sid(tag.a['href'])
        process_game_page(url)
        #time.sleep(0.1)


process_index_page('http://castleparadox.com/search-gamelist.php?mirror=true')

# process_game_page('http://castleparadox.com/gamelist-display.php?game=488')
# process_game_page('http://castleparadox.com/gamelist-display.php?game=1040')

print(db.games)
db.save()
