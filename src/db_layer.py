"""
This module handles saving, loading, and caching of databases, which are
pickle-able python objects of arbitrary types, not instances of a specific class.

Should probably use a real DB, but for now they are just saved as .pickle files.
"""

from __future__ import print_function
import os
import ctypes

import util
from util import py2

if py2:
    import cPickle as pickle
else:
    import pickle

if py2:
    bytesstr = str
    unistr = unicode
else:
    bytesstr = bytes
    unistr = str

DB_DIR = os.path.join(os.path.dirname(__file__), 'databases')

class BinData(object):
    """
    Contains an 8-bit string (str/bytes) which is interpreted as binary data.
    The main purpose of this class is to allow pickling data with python 2 and loading it
    with python 3 (which by default would try to decode 8-bit str's to unicode str's).
    (Alternative to pickling numpy arrays.)
    """
    def __init__(self, val):
        self.val = val

    def __getstate__(self):
        return self.val  # Not returning self.__dict__ probably also makes the pickling faster/more compact

    def __setstate__(self, val):
        if type(val) == unistr:
            self.val = val.encode('latin-1')
        else:
            self.val = val

    def as_array(self, ctype = ctypes.c_short):
        """Create a ctypes array from a string/bytes object with given type."""
        return util.array_from_string(self.val, ctype)


###############################################################################

class CacheItem:
    "Has two members: .db and .mtime"


_cache = {}
_reqinfo = None  # A RequestInfo object

def _get_timer():
    if _reqinfo:
        return _reqinfo.DB_timer
    else:
        # Use dummy timer if one hasn't been set.
        return util.Timer()

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
            if py2:
                ret.db = pickle.load(dbfile)
            else:
                # When loading a DB pickled by Python 2, str becomes bytes and is decoded to a (unicode) str.
                # Use encoding='latin-1' so that no error is thrown in the case of BinData contents,
                # which BinData.__setstate__ then converts back to bytes.
                # Can't use encoding='bytes' because then all dict keys become bytes!!
                ret.db = pickle.load(dbfile, encoding='latin-1')
            ret.mtime = os.stat(fname).st_mtime
            return ret

def load(source_name):
    """
    Loads (with caching) from saved database with the given name if already exists, otherwise returns None.
    """
    with _get_timer():
        fname = db_filename(source_name)

        if source_name in _cache:
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
        return _cache[source_name].db

def save(source_name, db):
    """
    Save to file, and place in the cache.
    """
    with _get_timer():
        util.mkdir(DB_DIR)
        fname = db_filename(source_name)
        with open(fname, 'wb') as dbfile:
            pickle.dump(db, dbfile, 2)  # protocol 2 for python 2 compat
        item = CacheItem()
        item.db = db
        item.mtime = os.stat(fname).st_mtime
        _cache[source_name] = item

