#!/usr/bin/env python
"""
Process data from a g_debug.txt dump produced by tmc's rpgbrowse_printer branch,
which log info about .rpg files as you browse around,
and specifically the games listing provided by Pepsi Ranger.
"""

from __future__ import print_function
import time
import datetime
import calendar
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

def convert_dateserial(serial):
    "Convert FB date serial (like VisualBasic) to a Unix timestamp"
    days = int(serial)
    seconds = 86400 * (serial - days)
    date = datetime.datetime(1899, 12, 30) + datetime.timedelta(days, seconds)   # Note, not 31st Dec but 30th!
    # FIXME: need to check whether this is UTC or not (use time.mktime instead of calender.timegm)
    #return calendar.timegm(date.timetuple())
    return time.mktime(date.timetuple())

def process_file(log_fname):
    contents = util.read_text_file(log_fname, 'latin-1').strip()
    for line in contents.split('\n'):
        stuff = line.split(' :: ')
        assert stuff[0] == 'Game'
        _, path, archinym, size, modified, created_with, longname, description = stuff

        fname = path.split('\\')[-1]
        #srcid = ':'.join(path.split('\\')[-2:])
        game = gamedb.Game()
        game.name = longname or fname
        game.description = description
        game.size = int(size.split()[1])
        game.mtime = convert_dateserial(float(modified.split()[1]))
        game.archinym = archinym

        srcid = fname + ":" + str(game.size)

        info = [
            "Filename: " + path,
            "Size: %d KB" % (game.size / 1024),
            "Created by: " + created_with,
            "archinym: " + archinym,
        ]
        game.extra_info = '\n'.join(info)

        if srcid in db.games:
            if archinym == 'nil':
                print("!! skipping duplicate (due to bad archinym) " + path)
                continue
            elif db.games[srcid].archinym == 'nil':
                #overwrite it
                pass
            else:
                print("!! skipping duplicate " + path)
                # continue
        db.games[srcid] = game


db = gamedb.GameList('pepsi')
process_file("../pepsi_oldest.txt")

db.save()
