#!/usr/bin/env python3
"""
Pull game listings from the Op:OHR game list, parsing the HTML.
UNFINISHED! Only pulls author name. I've abandoned this in favour of
pull_opohr_from_backup.py
"""

import time
import re
from bs4 import BeautifulSoup, NavigableString

import scrape
import urlimp
import gamedb
import util


encoding = 'latin-1'

def process_game_page(url):
    if url.endswith('Foresca') or url.endswith('Skias%2520Saga') or url.endswith('Wally%2527s%2520Castle'):
        # This .html file goes forever, containing "<BR>&nbsp;&nbsp;" repeated over and over
        # Apache only seems to return approx 27MB before aborting.
        # There are more pages...
        print("Skipping game with broken page")
        return

    dom = scrape.get_page(url, encoding)

    assert '?username=' in url and len(url.split('=')) == 2, "Expected only one query in page url, 'username'"
    # Have to DOUBLE unquote
    srcid = urlimp.unquote(urlimp.unquote(url.split('=')[1])).decode(encoding)

    game = gamedb.Game()

    title = dom.find('td', background='line.jpg').b
    game.name = str(dom.find('td', background='line.jpg').b.contents[0])
    assert game.name == srcid
    game.url = url
    print ("Processing game:", game.name, "  \tsrcid:", srcid)

    info = dom.find('td', width=24).find_next_sibling('td')
    head_author, head_homepage, head_description, head_status, head_screenshot = info.find_all('b')

    assert head_author.string == "Author:"
    #print(list(head_author.next_siblings))
    authnext = head_author.next_sibling
    authnextnext = authnext.next_sibling
    print([authnext, authnextnext])
    # Authors with email addresses are put in an <a> tag, some
    if authnext.string != '\n':
        game.author = str(authnext.string)
    elif authnextnext.name == 'a':
        game.author = str(authnextnext.string)
        if authnextnext['href'] != 'mailto:':
            game.author_link = authnextnext['href']
        else:
            print("blank email")
    else:
        raise Exception("Author field not understood")

    # Double-check that there are no NavigableStrings
    game = scrape.clean_strings(game)

    #print(game.__dict__)
    db.games[srcid] = game

def process_index_page(url, limit = 9999):
    print("Fetching/parsing page...")
    dom = scrape.get_page(url, encoding, post_data = {'name':'All', 'demos':'All'})

    for tag in dom.find_all('a'):
        if tag['href'] and tag['href'].startswith('gamelist-display.php'):
            # The first <a> is the link to the game, the second is the author
            gameurl = urlimp.urljoin(url, tag['href'])
            print(gameurl)
            process_game_page(gameurl)
            #time.sleep(0.1)
            limit -= 1
            if limit <= 0:
                break

db = gamedb.GameList('opohr')

process_index_page('http://www.castleparadox.com/archive/operationohr/gamelist-list.php')

db.save()
