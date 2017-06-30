"""
Should probably use a real DB, but for now we just use a pickled python object.
"""
from __future__ import print_function
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
    "hs": {'name': "HamsterSpeak reviews", 'is_gamelist': True},
    "rpgs": {'name': "Scanned .rpg files", 'is_gamelist': False},
    "pepsi": {'name': "Games archived by Pepsi Ranger", 'is_gamelist': False, 'hidden': True},
}
    # "bahamut",
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
    reqinfo = None  # A RequestInfo object

    @classmethod
    def _get_timer(cls):
        if cls.reqinfo:
            return cls.reqinfo.DB_timer
        else:
            # Use dummy timer if one hasn't been set.
            return util.Timer()

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
        Loads (with caching) from saved database with the given name if already exists, otherwise returns None.
        """
        with cls._get_timer():
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
        with cls._get_timer():
            util.mkdir(DB_DIR)
            fname = cls.db_filename(source_name)
            with open(fname, 'wb') as dbfile:
                pickle.dump(db, dbfile, 2)  # protocol 2 for python 2 compat
            item = cls.CacheItem()
            item.db = db
            item.mtime = os.stat(fname).st_mtime
            cls.cache[source_name] = item


class Screenshot:
    # Defaults for existing objects
    is_inline = False

    def __init__(self, url, local_path, description = "", is_inline = False):
        self.url = url                 # URL for the original copy
        self.local_path = local_path   # Path of the local copy, if any
        self.description = description
        self.is_inline = is_inline     # True if the screenshot is already inlined in the game description.

    def img_tag(self, title = ""):
        if title and self.description:
            title += "\n"
        title += self.description or ""
        return '<img src="%s" alt="Screen" title="%s" />' % (self.url, title)

    def __repr__(self):
        return 'Screenshot<%s, %s>' % (self.local_path.split('/')[-1], self.description or "")

class Review:
    """
    A link to a review, retrospective, commentary, or preview elsewhere.
    """
    def __init__(self, url, author = "", title = "", byline = '', article_type = "Review", score = "", summary = "", location = ""):
        self.url = url             # External URL
        self.author = author       # Author(s) of the article
        self.byline = byline       # A more detailed description than "<article_type> by <author>"
        self.title = title         # Title of the article, usually the title of the game
        self.location = location   # Where the article is, e.g. 'in HamsterSpeak 13'
        self.article_type = article_type  # Review, Preview, Commentary, Retrospective, Terrible Game Review...
        self.score = score         # String or number, e.g. "A-", "9.5"
        self.summary = summary     # One line summary

    def __repr__(self):
        return 'Review<%s of %s by %s>' % (self.article_type, self.title, self.author)

class DownloadLink:
    """
    Info about a download link on a game entry. May point to an element of the 'zips' DB.
    """
    def __init__(self, listname, zipname, external, title = ""):
        self.listname = listname # The ID of the gamelist, eg 'ss'
        self.zipname = zipname   # The identifier of the zip, equal to util.escape_id(actual_filename)
        self.external = external # Official download link (may increase download counter!)
        self.title = title       # The displayed filename or title of the download. Optional.
        self.description = ""
        self.download_count = None # Number of downloads; usually useless
        self.sizestr = ""        # Size of the download as a string. The ScannedZipData has the real size

    def name(self):
        return self.title or self.zipname

    def zipkey(self):
        "The key used for this file (URL component and key in the 'zips' DB)"
        return self.listname + ":" + self.zipname

    def load_zipdata(self):
        "Returns the corresponding ScannedZipData object from DB, or None"
        if self.zipname:
            zips_db = DataBaseLayer.load('zips')
            return zips_db.get(self.zipkey())

    def internal(self):
        if self.zipname:
            return 'zips/' + self.zipkey()

    # def internal_link(self):
    #     "Generate a link to our page for this download, or None"
    #     if self.zipname:
    #         return util.link(self.internal(), self.name())

    def __repr__(self):
        return 'Download<%s %s>' % (self.zipkey(), self.title)


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
    error = ""              # Any error message that occurred when processing the .rpg (errors extracting not included)
    archinym = None

    def __init__(self):
        self.name = ""
        self.author = ""
        self.author_link = ""        # External URL to the author's profile page, or otherwise mailto:email address
        self.description = ""        # Description from game entry, or aboutline from an .rpg. HTML formatted!
        self.url = ""                # External URL to this game entry on the original site
        self.screenshots = []        # List of Screenshot objects
        self.downloads = []          # Direct download URLs
        self.reviews = []            # List of Reviews
        #self.download_count = None  # Number of times downloaded
        #self.rating = None          # Could be a number or a letter
        self.tags = []               # List of tags (strings)
        self.archives = []

    def get_name(self):
        return self.name or "(blank name)"

    def get_author(self):
        return self.author or "(blank author)"

    def create_datadir(self, dbname, srcid):
        datadir = 'data/%s/%s/' % (dbname, srcid)
        util.mkdir(datadir)
        return datadir

    def add_screenshot(self, dbname, srcid, url, description = "", is_inline = False):
        """
        Add a screenshot to this game, and download a local copy too
        Skips if couldn't download. Returns whether download succeeded.
        """
        # Download the file to datadir
        datadir = self.create_datadir(dbname, srcid)
        if url.startswith('data:'):
            # Displaying the screenshot on a page will just work.
            # However maybe we should host the image as a file? But the data URI
            # doesn't necessarily say what the filetype is (eg "image/*"),
            # so the server might give the wrong mime type? Does it matter?
            filename = datadir + util.md5hash(url)[:7]
        else:
            filename = datadir + url.split('/')[-1]
        try:
            with open(filename, 'wb') as fil:
                fil.write(scrape.get_url(url))
        except scrape.BadUrl:
            print("!! Couldn't download " + url)
            return False
        # Add the screenshot
        screenshot = Screenshot(url, filename, description, is_inline)
        self.screenshots.append(screenshot)
        return True

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
    def load(cls, source_name):
        """Loads from saved database with the given name if already exists, otherwise returns None."""
        # There's no good reason that just .games is saved...
        games = DataBaseLayer.load(source_name)
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

    def __init__(self, zipinfo, filename):
        """zipinfo is an ArchiveInfo object"""
        self.error = zipinfo.error   # Any error message produced while trying to read, else ""
        if self.error:
            print("!! zipinfo error:", self.error)
        self.unreadable = zipinfo.zip is None   # File is completely unreadable
        self.filename = filename
        self.size = zipinfo.size    # Always valid
        self.mtime = zipinfo.mtime  # Always valid
        # Proceed to read the list of files, even if zipinfo.error
        # is set, which indicates at least one file is unreadable.
        if not self.unreadable:
            # Create .rpgs, the fname -> srcid mapping, by truncated the md5 hashs
            self.rpgs = dict(zipinfo.rpgs)
            for fname, hash in self.rpgs.items():
                # hash is None if the game couldn't even be extracted,
                # (or it might be missing entirely
                # but is valid if the game was corrupt.
                if hash:
                    self.rpgs[fname] = hash[:9]
            self.scripts = zipinfo.scripts
            self.filelist = []  # (fname, size, mtime) tuples
            self.files = {}     # Extracted files; fname -> contents mapping
            for fname in zipinfo.zip.namelist():
                size = zipinfo.file_size(fname)
                mtime = zipinfo.file_mtime(fname)
                self.filelist.append((fname, size, mtime))

                if not zipinfo.error:
                    # Also grab small text files
                    extn = os.path.splitext(fname.lower())[1]
                    if 'readme' in fname.lower() or extn in ('.txt', '.hss'):
                        # Filter out large files such as LICENSE-binary.txt
                        if size < 15000 and '_debug' not in fname:
                            self.files[fname] = scrape.auto_decode(zipinfo.zip.read(fname))

    def name(self):
        "For consistency with DownloadLink"
        return self.filename

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
