#!/usr/bin/env python
"""
Pull game listings from the backup files of the Op:OHR website.
This is more reliable and easier than going through the website,
and also reveals extra screenshots!
You can download the op:ohr backup at
http://tmc.castleparadox.com/ohr/archive/operation_ohr_backup.tar.xz (158MB)
"""
from __future__ import print_function
import os
from collections import defaultdict
import shutil

import scrape
from scrape import urljoin
import gamedb
import util
from util import py2, tostr

# Point this to where you've extracted the above archive
OPOHR_PATH = '../operationohr/'

assert os.path.isfile(OPOHR_PATH + 'gamelist-display.php')

OPOHR_URL = 'http://www.castleparadox.com/archive/operationohr/'

encoding = 'latin-1'

statuses = "Finished game", "Demo released", "No demo"

unique_extns = '.eml', '.pas', '.dsc', '.aut', '.sta', '.url', '.zip'
expected_extns = '.eml', '.pas', '.dsc', '.aut', '.sta', '.url', '.zip', '.jpg', '.gif', '.LOG', '.cnf'
image_extns = '.gif', '.jpg'

stats = {'extradownloads': 0, 'extragames': 0, 'extrascreenshots': 0}

def fix_escapes(text):
    """Fix instances of \\\\, \\, \' and \" escapes in a string
    (There are a couple games which have \ double escaped for some reason!!)"""
    return text.replace(r'\\', '\\').replace(r'\\', '\\').replace(r"\'", "'").replace(r'\"', '"')

def process_game(dirname, path):
    # Note: Since we're not reading the files over the web, dirname has one
    # less layer of escaping than the URLs

    # Special cases
    if dirname == 'Skias%20Saga':
        # Skip this game, the files in this directory are all named Last%20Legacy
        # and I don't know which is the right name. (There is a real Last Legacy entry)
        # The info about the game is trivial anyway.
        print("!! Skipping " + dirname)
        return
    if dirname == 'Wally%27s%20Castle':
        # The contents of this directory have a different name, Wally%5C%27s%20Castle,
        # which causes Op:OHR to screw up. The files are identical to the Wally's Castle entry anyway.
        print("!! Skipping " + dirname)
        return

    files = os.listdir(path)
    if len(files) == 0:
        print("!! Skipping empty directory " + dirname)
        return

    game = gamedb.Game()
    gamename = fix_escapes(scrape.unquote(dirname.decode(encoding)))
    srcid = util.partial_escape(gamename)
    game.name = gamename.strip()   # One game has trailing whitespace

    # See what files we've got, whether there are any unexpected ones
    by_extn = defaultdict(list)
    for fname in files:
        if fname in ('_vti_cnf',) or fname.endswith('.LOG'):
            # Ignore this crud
            continue
        extn = os.path.splitext(fname)[1]
        if fname.lower() != dirname.lower() + extn:
            if extn in image_extns:  # We make use of extra screenshots, so don't report
                game.extra_info += "(Note: the page for this game on Op:OHR has a missing screenshot.)"
                print(" Note: found game with extra screenshot, %s/%s" % (gamename, fname))
                stats['extrascreenshots'] += 1
            else:
                print(" %s: Extra File %s" % (gamename, fname))
            if extn in unique_extns:
                continue
        elif fname != dirname + extn:
            # This download or screenshot will not work when viewed on Op:OHR because the
            # case does not match
            print(" Note: found game with broken download link or screenshot, " + fname)
            if extn == '.zip':
                stats['extradownloads'] += 1
                game.extra_info += "(Note: the page for this game on Op:OHR has a broken download.)"
            elif extn in image_extns:
                stats['extrascreenshots'] += 1
                game.extra_info += "(Note: the page for this game on Op:OHR has a missing screenshot.)"

        assert extn in expected_extns
        by_extn[extn].append(fname)


    def getdata(extn):
        assert len(by_extn[extn]) == 1
        fname = by_extn[extn][0]
        with open(os.path.join(path, fname)) as f:
            return f.read()

    # Note that we quote it once, and the browser will quote it a second time, as required.
    # Note: there's a game that doesn't show up on the gamelist, '?', but does have a page
    game.url = OPOHR_URL + 'gamelist-display.php?username=' + scrape.quote(dirname)

    game.author = fix_escapes(getdata('.aut').decode(encoding))
    if not game.author:
        print(" %s: Invalid author '%s'" % (gamename, game.author))
    if getdata('.eml') not in ("none", "None", ""):
        game.author_link = "mailto:" + getdata('.eml')
        if '@' not in game.author_link:
            print(" %s: Invalid email '%s'" % (gamename, game.author_link))
    game.description = util.text2html(fix_escapes(getdata('.dsc').decode(encoding)))
    website = getdata('.url')
    if website:
        if len(website) > 7:
            game.website = website
        elif website != 'None' and website != 'http://':
            print(" Invalid website '%s'" % website)
    status = getdata('.sta')
    if '.zip' in by_extn:
        assert len(by_extn['.zip']) == 1
        game.downloads = [OPOHR_URL + 'gamelist/' + dirname + '/' + by_extn['.zip'][0]]
        if status == "No demo":
            print(" %s: Status '%s' but game has a download" % (gamename, status))
            game.extra_info += "(Note: the page for this game on Op:OHR is missing the download link.)"
            stats['extradownloads'] += 1
            status = None

    if status in statuses:
        game.tags.append(status)
    elif status:
        print(" Invalid status '%s'" % status)

    for screenshot in by_extn['.jpg'] + by_extn['.gif']:
        # Copy each screenshot to this game's data directory, and register it
        datadir = game.create_datadir(db.name)
        filename = os.path.join(datadir, screenshot)
        screenshot_url = OPOHR_URL + 'gamelist/' + scrape.quote(dirname + '/' + screenshot)
        shutil.copy2(os.path.join(path, screenshot), filename)
        game.screenshots.append(gamedb.Screenshot(screenshot_url, filename))

    game = scrape.clean_strings(game)

    db.games[srcid] = game

def process_index(path):
    for dirname in os.listdir(path):
        process_game(dirname, os.path.join(path, dirname))


db = gamedb.GameList('opohr')

process_index(os.path.join(OPOHR_PATH, 'gamelist'))

db.save()

print(stats)
