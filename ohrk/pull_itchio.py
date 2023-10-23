#!/usr/bin/env python3

import re
import time
from xml.etree import ElementTree

if __name__ == '__main__':
    import ohrkpaths  # Setup sys.path

from ohrk import gamedb, scrape, util


OHRRPGCE_TAG_URL = "https://itch.io/games/newest/tag-ohrrpgce.xml"
# The manually mantained collection of OHR games, https://itch.io/c/1079248/ohr-games
OHRRPGCE_COLLECTION_URL = "https://itch.io/games/newest/collection-1079248.xml"


def parse_time(tstr: str):
    "E.g. Sun, 04 Jun 2017 18:52:13 GMT"
    return time.mktime(time.strptime(tstr, "%a, %d %b %Y %H:%M:%S GMT"))

def split_itch_io_url(url):
    match = re.search("://(.*)\.itch\.io/(.*)", url)
    user = match.group(1)
    gamename = match.group(2)
    return user, gamename

def get_srcid(game: gamedb.Game):
    user, gamename = split_itch_io_url(game.url)
    return user + "_" + gamename

def parse_rss_node_game(node: ElementTree.Element) -> gamedb.Game:
    #print(node.findtext('guid'))

    game = gamedb.Game()
    game.name = node.findtext('plainTitle')
    game.url = node.findtext('link')
    game.mtime = parse_time(node.findtext('updateDate'))

    desc = node.findtext('description')
    # Trim the appended newline and <img> tag
    desc = desc.split('&lt;')[0].strip()

    # The following are nonstandard
    game.blurb = desc
    game.ctime = parse_time(node.findtext('createDate'))
    game.pubtime = parse_time(node.findtext('pubDate'))

    #print(node.findtext('updateDate'), node.findtext('pubDate'), game.name)
    #print(f"{game.ctime}, {game.pubtime}, {game.mtime}, {game.name}")

    user, gamename = split_itch_io_url(game.url)
    game.author = user

    srcid = get_srcid(game)
    return srcid, game

def rss_items(contents: str):
    "Return rss <item> Elements"
    tree = ElementTree.fromstring(contents)
    return tree.find('channel').findall('item')

def get_all_rss_items(url, cache = True):
    "Fetch all items on all pages of an rss feed, yielding the Nodes"
    guids = set()
    for page in range(1, 30):
        pageurl = url
        if page > 1:
            pageurl += f"{url}?page={page}"
        contents = scrape.get_url(pageurl, cache = cache)
        tree = ElementTree.fromstring(contents)

        if page > 1:
            assert f"Page {page} " in tree.find('channel').findtext('title'), url + " doesn't support ?page= query"

        items = tree.find('channel').findall('item')
        if len(items) == 0:
            return

        for item in items:
            guid = item.findtext('guid')
            # And item might repeat if a new item is created, causing results to scroll
            if guid not in guids:
                guids.add(guid)
                yield item
            else:
                print("DUPLICATE! ", guid)

def get_new_games(url, cache = False):
    "Returns just games on the first page of 'url' rss feed, which the caller can use to compare"
    games = {}
    contents = scrape.get_url(url, cache = cache)
    #print("get_new_games", url)
    for node in rss_items(contents):
        srcid, game = parse_rss_node_game(node)
        games[srcid] = game
    return games

def get_all_games():
    "TODO: this gets just a list of ohrrpgce games, but doesn't scrape individual pages"

    db = gamedb.GameList('itch.io')

    for node in get_all_rss_items(OHRRPGCE_COLLECTION_URL):
        srcid, game = parse_rss_node_game(node)
        db.games[srcid] = game

    for node in get_all_rss_items(OHRRPGCE_TAG_URL):
        srcid, game = parse_rss_node_game(node)
        if srcid not in db.games:
            print(srcid + " is tagged ohrrpgce but missing from collection!")
            db.games[srcid] = game

    # Sanity checks
    links = [game.url for game in db.games.values()]
    for link in [
            'https://codygaisser.itch.io/noexit',
            'https://the-natural-world.itch.io/bump-land',
            'https://willyelektrix.itch.io/1999megallennium',
    ]:
        if link not in links:
            print("!!! Didn't find " + link)

    return db

def get_devlogs(game_url):
    "Get list of devlogs for a game"
    # devlog.rss doesn't support paging.
    contents = scrape.get_url(game_url + "/devlog.rss")

    devlogs = {}
    for node in rss_items(contents):
        guid = node.findtext('guid')
        log = {}
        log['link'] = node.findtext('link')
        log['title'] = node.findtext('title')
        #TODO: remove <p> tags and unescape &...; codes
        log['description'] = node.findtext('description')
        log['date'] = parse_time(node.findtext('pubDate'))

        print(log['title'])
        #print(log['description'])
        devlogs[guid] = log

    return devlogs


if __name__ == '__main__':
    #get_devlogs("https://feenicks.itch.io/false-skies")

    db = get_all_games()
    db.save()
