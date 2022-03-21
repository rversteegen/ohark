"""
This module handles saving, loading, and caching of databases, which are
pickle-able python objects of arbitrary types, not instances of a specific class.

Should probably use a real DB, but for now they are just saved as .pickle files.
"""


import os
import ctypes
import numpy
import pickle

import util


DB_DIR = os.path.join(os.path.dirname(__file__), 'databases')

def bindata(data, dtype = numpy.uint8):
    "Turn a bytes into a serialisation format"
    return numpy.frombuffer(data, dtype)


###############################################################################

class CacheItem:
    "Has two members: .db and .mtime"


class RequestContext:
    """A instance should be created when beginning a request, to hold
    request-specific caches, etc.
    It is a global shared for all DB accesses until a new object is created."""

    def __init__(self):
        # If a DB appears in the quickcache, then no check is made whether it needs to be reloaded:
        # it is only reloaded once per request.
        self.quickcache = {}
        # Time DB loads
        self.timer = util.Timer()
        global _context
        _context = self


# _cache holds loaded databases, cached between requests.
_cache = {}
_context = RequestContext()  # Dummy value, until set by a real request


def db_filename(source_name):
    return DB_DIR + '/' + source_name + '.pickle'

def _load(source_name):
    """
    Loads from saved database with the given name if already exists, otherwise returns None.
    Returns a CacheItem. Does not read or write the cache.
    """
    fname = db_filename(source_name)
    if os.path.isfile(fname):
        with open(fname, 'rb') as dbfile:
            print("Loading " + fname)
            ret = CacheItem()
            # When loading a DB pickled by Python 2, str becomes bytes and is decoded to a (unicode) str.
            # Could use encoding='latin-1' so that no error is thrown for
            # strings which aren't UTF-8.
            # Can't use encoding='bytes' because then all dict keys become bytes!!
            ret.db = pickle.load(dbfile)
            ret.mtime = os.stat(fname).st_mtime
            return ret

def load(source_name):
    """
    Loads (with caching) from saved database with the given name if already exists, otherwise returns None.
    """
    try:
        return _context.quickcache[source_name]
    except:
        pass

    with _context.timer:

        if source_name in _cache:
            fname = db_filename(source_name)

            # Check if the DB has changed since
            if not os.path.isfile(fname):
                del _cache[source_name]
                return None

            mtime = os.stat(fname).st_mtime
            if mtime != _cache[source_name].mtime:
                print("Dropped out-of-date cached DB")
                del _cache[source_name]

        if source_name not in _cache:
            db = _load(source_name)
            if not db:
                return None
            _cache[source_name] = db
            _context.quickcache[source_name] = db
        return _cache[source_name].db

def save(source_name, db):
    """
    Save to file, and place in the cache.
    """
    with _context.timer:
        util.mkdir(DB_DIR)
        fname = db_filename(source_name)
        with open(fname, 'wb') as dbfile:
            pickle.dump(db, dbfile, 2)  # protocol 2 for python 2 compat
        item = CacheItem()
        item.db = db
        item.mtime = os.stat(fname).st_mtime
        _cache[source_name] = item

