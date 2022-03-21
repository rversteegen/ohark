#!/usr/bin/env python3
"""
This module builds a DB by scanning .zip files.
It depends on nohrio (rpgbatch fork) and rpgbatch which need to be in the path.
See http://rpg.hamsterrepublic.com/ohrrpgce/nohrio
and tools/rpgbatch/rpgbatch.py in the OHRRPGCE repository.
(http://rpg.hamsterrepublic.com/source/tools/rpgbatch/rpgbatch.py)
"""

import os
import sys
import time
import random
import numpy as np

import paths
import nohrio.ohrrpgce
from rpgbatch.rpgbatch import RPGIterator, RPGInfo, ArchiveInfo
import util
import scrape
import db_layer
import gamedb
import inspect_rpg


def process_sources(db_name, sources):
    """
    Create and write a GameList.
    sources is a list of .rpg files, .rpgdir directories, .zip files, or directories containing any of these.
    """
    games_db = gamedb.GameList(db_name)
    zips_db = {}

    # Ask the iterator to yield both each game it finds, and each zip file it processes
    iterator = RPGIterator(sources, yield_zips = True, yield_corrupt_games = True)
    for yielded in iterator:
        if isinstance(yielded, ArchiveInfo):
            # A zip file
            zipinfo = yielded
            # The zip files on CP, SS, Op:OHR (by coincidence), Bahamut all have unique names.
            # Others may not. We assume there are no files with duplicate names from the same src.
            fname = os.path.split(zipinfo.path)[-1]
            zipkey = zipinfo.src + ":" + util.id_from_filename(fname)
            print("Processing ZIP", zipkey)
            assert zipkey not in zips_db
            zipdata = gamedb.ScannedZipData(zipinfo, util.unescape_filename(fname))
            zips_db[zipkey] = zipdata
            if zipdata.unreadable:
                continue   # We didn't read any games from this zip

            # Now that we've added this zip to the DB,
            # point every game in it to the DB entry for this zip file.
            for gameid in zipdata.rpgs.values():
                # If the game was corrupt, then it didn't get added to the DB
                if gameid in games_db.games:
                    games_db.games[gameid].archives.append(zipkey)
            continue

        rpg, gameinfo, zipinfo = yielded
        gameid = gameinfo.hash[:9]

        print("Processing RPG ", gameinfo.id, "from", gameinfo.src)

        game = gamedb.Game()
        game.src = gameinfo.src
        game.size = gameinfo.size
        game.mtime = gameinfo.mtime

        if rpg:
            # Game is not corrupt.
            # Read some data out of the .rpg file, including .gen and fixbits lumps

            print(" > ", gameinfo.longname, " --- ", gameinfo.aboutline)
            game.name = (gameinfo.longname or gameinfo.rpgfile).strip()
            game.description = gameinfo.aboutline

            game.gen = rpg.general.view(np.int16).copy()

            if rpg.has_lump('fixbits.bin'):
                with open(rpg.lump_path('fixbits.bin'), 'rb') as f:
                    game.fixbits = db_layer.bindata(f.read())
                fixBits = nohrio.ohrrpgce.fixBits(rpg.lump_path('fixbits.bin'))
            else:
                game.fixbits = None
                fixBits = None

            if not fixBits or not fixBits.wipegen:
                # In old .rpg files, gen contains garbage; this fixbit indicates if it's been cleaned
                game.gen[199:] = 0

        info = [
            "Filename: " + gameinfo.rpgfile,
            "Size: %d KB" % round(game.size / 1024),
            "md5: " + gameinfo.hash,
        ]
        if rpg:
            info += [
                "Created by: " + rpg.archinym.version,
                "archinym: " + rpg.archinym.prefix,
            ]

        # if zipinfo and len(zipinfo.scripts):
        #     info.append("Script files: " + str(zipinfo.scripts))
        game.extra_info = "\n".join(info)

        if gameinfo.error:
            game.error = "Game appears to be corrupt: " + gameinfo.error

        if rpg:
            titlescreen_file = '/tmp/titlescreen.png'
            if inspect_rpg.save_titlescreen(rpg, titlescreen_file):
                game.add_screenshot_file(games_db.name, gameid, titlescreen_file, "Titlescreen")

        # Double-check that there are no undecoded strings
        game = scrape.clean_strings(game)

        games_db.games[gameid] = game

    iterator.print_summary()

    games_db.save()
    db_layer.save('zips', zips_db)

if len(sys.argv) < 2:
    sys.exit("Specify .rpg files, .rpgdir directories, .zip files, or directories containing any of these as arguments.")
sources = sys.argv[1:]
process_sources("rpgs", sources)
