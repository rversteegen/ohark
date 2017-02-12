#!/usr/bin/env python
"""
Pull game reviews, previews, etc, from HamsterSpeak.
"""
from __future__ import print_function
from bs4 import BeautifulSoup, NavigableString
import re

import scrape
from urlimp import urljoin
import gamedb
import util
from util import py2, tostr

encoding = 'latin-1'

# TODO: a number of Features are contest results, and should be included.
process_categories = 'Review', 'Retrospective', 'Preview', 'Terrible Game Review', 'Commentary'
all_categories = process_categories + ('Art', 'Feature', 'Link', 'Comic', 'Plotscript of the Month',
                                       'Plotscript', 'Miscellaneous', 'Misc')

stats = {'reviews': 0, 'screenshots': 0, 'broken_screenshots': 0}

def singular_form(word):
    if word.endswith('ous'):
        return word
    if word.endswith('ies'):
        return word[:-3] + 'y'
    if word.endswith('s'):
        return word[:-1]
    return word

def fix_urls(url):
    # Special case for a bad link
    if url.endswith('ah3/title.png'):
        return url.replace('.png', '.PNG')
    return url

def cleanup_string(string):
    # The occasional newline in a string...
    return tostr(string.strip().replace('\r\n', ' ').replace(u'\xa0', ' '))

def get_title_and_author(dom):
    """
    Find the title and author of an article. The whole byline might also be useful,
    e.g. "Mini Reviews by Paul Harrington".
    This was a bit stupid, since author and title are listed on the
    spreadsheet of articles provided by PCH.
    """

    # Find the first two strings on the page, which are usually the
    # title and the byline;
    # Preview articles typically have no byline, and
    # one article has an image as the title.

    def nonempty_string(string):
        # Have to skip <style> and <title> tags if there's no <head>
        if string.parent.name in ('title', 'style'):
            return False
        return string.strip()
    if dom.body:
        # Only some versions of BS4 (Python 2 only?) automatically add <body> if missing
        dom = dom.body

    strings = [cleanup_string(string) for string in dom.find_all(string = nonempty_string, limit = 6)]
    # First glue together strings that start with 'by '
    titles = []
    for idx, string in enumerate(strings):
        if string == 'Download Here':  # one instance
            continue
        if idx > 0 and (string.startswith('by ') or titles[-1].endswith(' by')):
            titles[-1] += ' ' + string
        else:
            titles.append(string)

    # Then find the byline, and glue all preceding lines together
    # Don't allow the first line to be a byline
    title = ''#strings[0]
    author = byline = ''
    for string in titles:
        #print("line", repr(string))
        match = re.search('(^| )by ', string)
        if match:
            byline = string
            author = byline[match.end():]
            break
        if len(title) + len(string) > 120:
            break
        if title:
            title += ' '
        title += string

    if not byline:
        print("!! No byline found")  # These are all previews

    # print('title: ', title)
    # print('byline: ', byline)
    # print('author: ', author)
    return title, author

def process_article(issue, url, link_title, category):
    """Add a game review to the DB.
    This is unfinished; there are various articles (mainly Previews and
    contest results) that have info on multiple games.
    """
    srcid = "%d:%s" % (issue, url.split('/')[-1].split('.')[0])
    print(srcid, url, category, " -- ", link_title)
    dom = scrape.get_page(url, encoding)

    title, author = get_title_and_author(dom)

    # NOTE: link_title and title may differ; title is sometimes very long.
    # Not sure which to use
    game = gamedb.Game()
    game.name = link_title
    game.reviews = [(url, author, title, category)]
    stats['reviews'] += 1

    for img_tag in dom.find_all('img'):
        if game.add_screenshot(db.name, srcid, fix_urls(urljoin(url, img_tag['src']))):
            stats['screenshots'] += 1
        else:
            stats['broken_screenshots'] += 1

    # Double-check that there are no NavigableStrings or undecoded strings
    game = scrape.clean_strings(game)

    assert srcid not in db.games
    db.games[srcid] = game

def process_frame(issue, url):
    """Process the left or right frame of the issue, which contain links to articles"""
    dom = scrape.get_page(url, encoding)
    current_category = None
    new_category = False
    body = dom.find('body')
    for tag in body.descendants:
        if tag.name == 'img':
            assert tag['src'] == 'bar.gif'
            new_category = True
        elif tag.name == 'a':
            if tag.find('a'):
                print("!! Skipping <a> containing another <a>, linking to " + tag['href'])
                continue
            if not tag.string:
                # Special case, an invisible link that leads to a probably nonexistent article
                print("!! Skipping empty link to " + tag['href'])
                continue
            if current_category in process_categories:
                process_article(issue, urljoin(url, tag['href']), cleanup_string(tag.string), current_category)
        elif new_category:
            if tag.string is not None and tag.string.strip():
                #print("CATEGORY:", tag.string.strip())
                current_category = singular_form(cleanup_string(tag.string))
                if current_category not in all_categories:
                    print("!! Unknown category " + repr(current_category))
                assert current_category in all_categories
                new_category = False

def process_issue(issue):
    print("--Issue %d--" % issue)
    url = "http://superwalrusland.com/ohr/issue%d/index.html" % issue
    dom = scrape.get_page(url, encoding)

    leftFrame = dom.find(id = 'leftFrame')
    rightFrame = dom.find(id = 'rightFrame')
    assert leftFrame and rightFrame
    process_frame(issue, urljoin(url, leftFrame['src']))
    process_frame(issue, urljoin(url, rightFrame['src']))


scrape.TooManyRequests.remaining_allowed = 3000  # Override this safety-check
db = gamedb.GameList('hs')
for issue in range(1, 63+1):
   process_issue(issue)
#process_article(3, "http://superwalrusland.com/ohr/issue47/fys/fys.html", '1', '2')

print("Statistics:", stats)
db.save()
