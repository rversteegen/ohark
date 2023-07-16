#!/usr/bin/env python3
"""
Pull game data from Google Play and add to the DB
"""

import time

if __name__ == '__main__':
    import ohrkpaths  # Setup sys.path

from ohrk import gamedb, scrape, util
from ohrk.urlimp import urljoin

# Whether to cache index pages and individual game pages
CACHE_INDEX = False
CACHE_GAMES = True

def process_game_page(url):
    """Returns description"""
    dom = scrape.get_page(url, cache = CACHE_GAMES)

    assert '?id=' in url and len(url.split('=')) == 2, "Expected only one query in page url, the id"
    srcid = url.split('=')[1]

    game = gamedb.Game()
    game.name = str(dom.find('div', class_='id-app-title').string)
    game.url = url
    # The download link is fake; has no info. (So leave srcid to indicate.)
    game.downloads = [gamedb.DownloadLink('googleplay', '', url, "For Android")]
    print ("Processing game:", game.name, "  \tsrcid:", srcid)

    author_div = dom.find('div', itemprop='author')
    game.author = str(author_div.find(itemprop='name').string)
    game.author_link = urljoin(url, author_div.a['href'])

    # Grab description
    descrip_tag = dom.find(itemprop='description')
    game.description = '\n'.join(str(tag) for tag in descrip_tag.div.contents)

    # Categories (only one per game?)
    game.tags = []
    for link in dom.find_all('a', class_='document-subtitle category'):
        game.tags.append(str(link.span.string))

    # Grab screenshots
    for num, img in enumerate(dom.find_all('img', class_='full-screenshot')):
        #filename = datadir + 'screen%d.png' % num
        game.add_screenshot_link(db.name, srcid, img['src'])

    # Double-check that there are no NavigableStrings or undecoded strings
    game = scrape.clean_strings(game)

    db.games[srcid] = game

def process_index_page(url):
    "Returns a list of game URLs"
    ret = []
    dom = scrape.get_page(url, cache = CACHE_INDEX)

    for link in dom.find_all('a', class_='title'):
        #name = link['title']
        gameurl = urljoin(url, link['href'])
        #print(name, gameurl)
        ret.append(gameurl)
    return ret

def process_games(urls):
    for gameurl in urls:
        process_game_page(gameurl)
        #time.sleep(0.5)

###############################################################################

db = gamedb.GameList('googleplay')

# Collect games from various index pages
gameurls = set()
gameurls.update(process_index_page('https://play.google.com/store/search?q=ohrrpgce&c=apps'))
gameurls.update(process_index_page('https://play.google.com/store/apps/developer?id=Hamster+Republic'))
gameurls.update(process_index_page('https://play.google.com/store/apps/developer?id=Red+Triangle+Games'))
gameurls.update(process_index_page('https://play.google.com/store/apps/developer?id=Spoonweaver+Studios'))
gameurls.update(process_index_page('https://play.google.com/store/apps/developer?id=Super+Walrus+Games'))
gameurls.update(process_index_page('https://play.google.com/store/apps/developer?id=A.+Hagen'))

# Extra games not tagged with 'ohrrpgce' (from http://www.slimesalad.com/forum/viewtopic.php?p=127022#127022)
# Missing games: Halalapszichiatrian, Macabre, Universal Wars Saga
# see http://www.slimesalad.com/forum/viewtopic.php?p=127022#127022
gameurls.add('https://play.google.com/store/apps/details?id=com.fyrewulff.swordofjade')
# https://play.google.com/store/apps/details?id=com.superwalrusland.ghoststowns
# https://play.google.com/store/apps/details?id=com.spoonweaver.slimeomancy
# https://play.google.com/store/apps/details?id=com.redtrianglegames.surfasaurus
# https://play.google.com/store/apps/details?id=com.hamsterrepublic.eatsoap
# https://play.google.com/store/apps/details?id=com.hamsterrepublic.eatsoapzh
# https://play.google.com/store/apps/details?id=com.hamsterrepublic.devwaffles.free
# https://play.google.com/store/apps/details?id=com.hamsterrepublic.devwaffles
# https://play.google.com/store/apps/details?id=com.hamsterrepublic.baconthulhu

# https://play.google.com/store/apps/details?id=com.ohrrpgce.necromanceratemycat

###### SEE https://play.google.com/store/search?q=com.ohrrpgce&c=apps&hl=en_US

# Blacklist (non-OHR games):
gameurls.discard('https://play.google.com/store/apps/details?id=com.hamsterrepublic.MantleMoonSea')
gameurls.discard('https://play.google.com/store/apps/details?id=com.hamsterrepublic.vocabmosaic')
gameurls.discard('https://play.google.com/store/apps/details?id=com.hamsterrepublic.stegavorto')

# print(gameurls)
process_games(gameurls)

print(db.games)
db.save()
