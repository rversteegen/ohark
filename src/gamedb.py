"""
Should probably use a real DB, but for now we just use a pickled python object.
"""
import os
import ctypes

import util
from util import py2
import scrape

if py2:
    import cPickle as pickle
else:
    import pickle

DB_DIR = os.path.join(os.path.dirname(__file__), 'databases')

SOURCES = {
    "cp": {'name': "Castle Paradox", 'is_gamelist': True},
    "cpbkup": {'name': "Castle Paradox backup", 'is_gamelist': True, 'hidden': True},
    "opohr": {'name': "Operation: OHR", 'is_gamelist': True},
    "ss": {'name': "Slime Salad", 'is_gamelist': True},
    "googleplay": {'name': "Google Play", 'is_gamelist': True},
    "rpgs": {'name': "Scanned .rpg files", 'is_gamelist': False},
}
    # "bahamut",
    # "opohr",
    # "ouya",
    # "steam",

if py2:
    bytesstr = str
    unistr = unicode
else:
    bytesstr = bytes
    unistr = str

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


class DataBaseLayer:
    """
    This class handles saving, loading, and caching of databases (which are just .pickle files).
    DBs are python objects.
    """

    class CacheItem:
        "Has two members: .db and .mtime"

    cache = {}

    @classmethod
    def db_filename(cls, source_name):
        return DB_DIR + '/' + source_name + '.pickle'

    @classmethod
    def _load(cls, source_name):
        """
        Loads from saved database with the given name if already exists, otherwise returns None.
        Returns a CacheItem. Does not read or write the cache.
        """
        fname = cls.db_filename(source_name)
        if os.path.isfile(fname):
            with open(fname, 'rb') as dbfile:
                print("Loading " + fname)
                ret = cls.CacheItem()
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

    @classmethod
    def load(cls, source_name):
        """
        Loads from saved database with the given name if already exists, otherwise returns None.
        """
        item = cls._load(source_name)
        if not item:
            return None
        return item.db

    @classmethod
    def cached_load(cls, source_name):
        """Drop-in replacement for .load(), which does caching"""
        fname = cls.db_filename(source_name)

        if source_name in cls.cache:
            # Check if the DB has changed since
            if not os.path.isfile(fname):
                del cls.cache[source_name]
                return None

            mtime = os.stat(fname).st_mtime
            if mtime != cls.cache[source_name].mtime:
                print("Dropped out-of-date cached DB")
                del cls.cache[source_name]

        if source_name not in cls.cache:
            db = cls._load(source_name)
            if not db:
                return None
            cls.cache[source_name] = db
        return cls.cache[source_name].db

    @classmethod
    def save(cls, source_name, db):
        """
        Save to file, and place in the cache.
        """
        util.mkdir(DB_DIR)
        fname = cls.db_filename(source_name)
        with open(fname, 'wb') as dbfile:
            pickle.dump(db, dbfile, 2)  # protocol 2 for python 2 compat
        item = cls.CacheItem()
        item.db = db
        item.mtime = os.stat(fname).st_mtime
        cls.cache[source_name] = item

class Screenshot:
    def __init__(self, url, local_path, description = ""):
        self.url = url                 # URL for the original copy
        self.local_path = local_path   # Path of the local copy, if any
        self.description = description

    def img_tag(self, title = ""):
        if title and self.description:
            title += "\n"
        title += self.description or ""
        return '<img src="%s" alt="Screen" title="%s" />' % (self.url, title)

    def __repr__(self):
        return 'Screenshot<%s, %s>' % (self.local_path.split('/')[-1], self.description or "")

class Game:
    """
    A single entry
    """

    # FIXME: Adding members to the class provides defaults for old serialised Game objects
    # but can't initialise lists here; this is a mess...
    extra_info = ""         # Info generated by the scraper or .rpg scanner. Raw text.
    mtime = None            # Last modification time of the game/game entry
    size = None             # Game size in bytes
    gen = None              # Contents of .gen lump (BinData object)
    fixbits = None          # Contents of the fixbits.bin lump (BinData object)
    website = None          # URL for an external website (often just author website)
    archives = None         # List of zipkeys (ids) of every zip file in which this game was found.

    def __init__(self):
        self.name = ""
        self.author = ""
        self.author_link = ""        # External URL to the author's profile page, or otherwise mailto:email address
        self.description = ""        # Description from game entry, or aboutline from an .rpg. HTML formatted!
        self.url = ""                # External URL to this game entry on the original site
        self.screenshots = []        # List of Screenshot objects
        self.downloads = []          # Direct download URLs
        self.reviews = []            # Direct review URLs
        #self.download_count = None  # Number of times downloaded
        #self.rating = None          # Could be a number or a letter
        self.tags = []               # List of tags (strings)
        self.archives = []

    def get_name(self):
        return self.name or "(blank name)"

    def get_author(self):
        return self.author or "(blank author)"

    def create_datadir(self, dbname):
        datadir = 'data/%s/%s/' % (dbname, self.name)
        util.mkdir(datadir)
        return datadir

    def add_screenshot(self, dbname, url, description = ""):
        """
        Add a screenshot to this game, and download a local copy too
        """
        # Download the file to datadir
        datadir = self.create_datadir(dbname)
        filename = datadir + url.split('/')[-1]
        with open(filename, 'wb') as fil:
            fil.write(scrape.get_url(url))
        # Add the screenshot
        screenshot = Screenshot(url, filename, description)
        self.screenshots.append(screenshot)

    def __repr__(self):
        return 'Game<%s>' % (self.name,)

class GameList:
    """
    Contains a list of Games, as self.games, from a single source.
    """

    def __init__(self, source_name):
        """Creates a blank game list."""
        self.name = source_name
        self.games = dict()

    @classmethod
    def cached_load(cls, source_name):
        """Loads from saved database with the given name if already exists, otherwise returns None."""
        # There's no good reason that just .games is saved...
        games = DataBaseLayer.cached_load(source_name)
        if not games:
            return None
        ret = cls(source_name)
        ret.games = games
        return ret

    def save(self):
        """
        Save to file.
        """
        DataBaseLayer.save(self.name, self.games)


class ScannedZipData:
    """
    This class holds information about a zip file.
    It's a picklable repackaging of some of the information in rpgbatch.ArchiveInfo
    """

    def __init__(self, zipinfo):
        """zipinfo is an ArchiveInfo object"""
        self.unreadable = zipinfo.zip is None
        if not self.unreadable:
            # fname -> srcid (truncated md5 hash mapping)
            self.rpgs = dict((fname, hash[:9]) for fname, hash in zipinfo.rpgs.items())
            self.scripts = zipinfo.scripts
            self.size = zipinfo.size
            self.mtime = zipinfo.mtime
            self.filelist = []  # (fname, size, mtime) tuples
            self.files = {}     # Extracted files; fname -> contents mapping
            for fname in zipinfo.zip.namelist():
                size = zipinfo.file_size(fname)
                mtime = zipinfo.file_mtime(fname)
                self.filelist.append((fname, size, mtime))

                # Also grab small text files
                extn = os.path.splitext(fname.lower())[1]
                if 'readme' in fname.lower() or extn in ('.txt', '.hss'):
                    # Filter out large files such as LICENSE-binary.txt
                    if size < 15000 and '_debug' not in fname:
                        self.files[fname] = scrape.auto_decode(zipinfo.zip.read(fname))


class _GameIndex():
    """Dead code"""
    def __init__(self):
        # 'games': [],    # List[Game]
        # 'indices': {},  # src -> src_id -> Game
        for src in SOURCES:
            self.db['indices'][src.key.lower()] = {}


    def find_game(self, srcid, src, create = True):
        """
        Find the DB entry for a game, using any of its identifiers.
        Get the object for a game, or create a new one if it doesn't exist.

        src: string
            The .key of an element of SOURCES.
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
