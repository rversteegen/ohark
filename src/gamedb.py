#!/usr/bin/env python3
"""
Should probably use a real DB, but for now we just use a pickled python dict.
"""

import pickle
import os

dbfilename = 'game_database.pickle'

class Game:

    def __init__(self):
        self.name = ""
        #altern_names: List[str]
        self.description = ""
        self.external_links = set()   # webpages
        self.screenshots = set()      # local file paths

    # def __str__(self):
    #     return self.name

    def __repr__(self):
        return 'Game<%s>' % (self.name,)

SOURCES = [
    "cp",
    "ss",
    "bahamut",
    "opohr",
    "googleplay",
    "ouya",
    "steam",
]

class DB:

    def __init__(self):
        if os.path.isfile(dbfilename):
            with open(dbfilename, 'rb') as dbfile:
                self.db = pickle.load(dbfile)
        else:
            self.db = {
                'games': [],    # List[Game]
                'indices': {},  # src -> src_id -> Game
            }
            for src in SOURCES:
                self.db['indices'][src.lower()] = {}
       
    def save(self):
        with open(dbfilename, 'wb') as dbfile:
            pickle.dump(self.db, dbfile)

    def find_game(self, srcid, src, create = True):
        """
        Find the DB entry for a game, using any of its identifiers.
        Get the object for a game, or create a new one if it doesn't exist.

        src: string
            The name of an element of SOURCES.
        srcid: string or int
            An id in whatever format is used by this source, e.g. id number or package name.
        create: bool
            Return a new Game if not found.
        """
        src = src.lower()
        gameindex = self.db['indices'][src]
        if srcid in gameindex:
            return gameindex[srcid]
        else:
            if create:
                game = Game()
                self.db['games'].append(game)
                gameindex[srcid] = game
                return game
            else:
                return None

db = DB()
