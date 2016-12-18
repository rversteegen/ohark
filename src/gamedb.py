#!/usr/bin/env python3
"""
Should probably use a real DB, but for now we just use a pickled python dict.
"""

import pickle
import os
import util

DB_DIR = os.path.join(os.path.dirname(__file__), 'databases')
#print(DB_DIR)


SOURCES = [
    "cp",
    "ss",
    "bahamut",
    "opohr",
    "googleplay",
    "ouya",
    "steam",
]


class Game:
    """
    A single entry
    """

    def __init__(self):
        self.name = ""
        self.author = ""
        self.author_link = ""
        self.description = ""
        #self.external_links = []    # webpages
        self.url = ""                # URL for this game entry
        self.screenshots = []        # Local file paths
        self.downloads = []          # Direct download URLs
        self.reviews = []            # Direct review URLs
        #self.download_count = None  # Number of times downloaded
        #self.rating = None          # Could be a number or a letter
        self.tags = []               # List of tags (strings)
        #self.rpg_location           # Gives the path to the .rpg/rpgdir file inside the .zip, in case there is more than one

    # def __str__(self):
    #     return self.name

    def columns(self):
        """For tabulating. Return an iterable"""
        return self.name, self.author, self.url, self.description

    def __repr__(self):
        return 'Game<%s>' % (self.name,)

def db_filename(source_name):
    return DB_DIR + '/' + source_name + '.pickle'

class GameList:
    """
    Contains a list of Games, as self.games, from a single source.
    """

    def __init__(self, source_name):
        """Creates a blank game list."""
        self.name = source_name
        self.games = dict()

    @classmethod
    def load(cls, source_name):
        """
        Loads from saved database with the given name if already exists, otherwise creates a blank one.
        """
        ret = cls(source_name)
        fname = db_filename(source_name)
        if os.path.isfile(fname):
            with open(fname, 'rb') as dbfile:
                ret.games = pickle.load(dbfile)
        return ret

    def save(self):
        """
        Save to file.
        """
        util.mkdir(DB_DIR)
        with open(db_filename(self.name), 'wb') as dbfile:
            pickle.dump(self.games, dbfile)


class _GameIndex():
    """Dead code"""
    def __init__(self):
        # 'games': [],    # List[Game]
        # 'indices': {},  # src -> src_id -> Game
        for src in SOURCES:
            self.db['indices'][src.lower()] = {}


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
