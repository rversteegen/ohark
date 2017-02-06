import sys
import os
import re
import time
import ctypes
import cgi

################################################################################
### Util

py2 = sys.version_info[0] == 2
if py2:
    tostr = unicode
else:
    tostr = str


# A high precision wallclock timer
if os.name == 'posix':
    timer = time.time
else:
    timer = time.clock

class Timer(object):
    """
    Utility class for finding total time spent in multiple sections of code.
    Is a context manager. Use either like:
        timing = Timer()
        with timing:
            ...
    or
        with Timer() as timing:
            ...
        print 'Done in', timing
    """
    def __init__(self):
        self.time = 0.
    def start(self):
        self._start = timer()
        return self
    def stop(self):
        self.time += timer() - self._start
        del self._start
        return self
    def __enter__(self):
        self.start()
        return self
    def __exit__(self, *args):
        self.stop()
    def __str__(self):
        if hasattr(self, '_start'):
            #return '<Timer running>'
            return '%.3gs' % (timer() - self._start)
        return '%.3gs' % self.time


def write_log(text):
    global verbose_log
    if mod_python:
        if extra_log_file:
            with open(extra_log_file, "a") as f:
                f.write(text.encode('utf-8') + "\n")
    else:
        sys.stdout.write(text)

# Can be overridden by req.log_error() if running under mod_python
def error_log(text):
    sys.stderr.write(text + "\n")
    write_log(text)

def mkdir(dirname):
    if not os.path.isdir(dirname):
        try:
            os.makedirs(dirname)
        except OSError:
            if os.path.isdir(dirname):
                # Race condition: another process created it. Ignore
                return
            raise

def create_file(path):
    """Create an empty file if it doesn't exist"""
    with open(path, "a"):
        pass

def format_filesize(size):
    """Format a file size, e.g. to '2.5 MB'.
    Do this in exactly the same way as Slime Salad."""
    def form(x):
        ret = "%.2f" % x
        # Trim leading zeroes
        if '.' in ret:
            while ret.endswith('0'):
                ret = ret[:-1]
                if ret.endswith('.'):
                    ret = ret[:-1]
                    break
        return ret
    if size > 1024**3:
        return "%s GB" % form(size / 1024.**3)
    elif size > 1024**2:
        return "%s MB" % form(size / 1024.**2)
    elif size > 1024:
        return "%s KB" % form(size / 1024.)
    return "%d B" % size

def strip_strings(strings):
    """Given a list of strings, strip them""" # and remove whitespace-only strings"""
    return [x.strip() for x in strings]


def program_output(*args, **kwargs):
    """Runs a program and returns stdout as a string"""
    if 'input' in kwargs:
        input = kwargs['input']
        if type(input) == str:
            kwargs['input'] = input.encode()
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    return proc.stdout.strip().decode()

def shell_output(*args, **kwargs):
    """Runs a program on the shell and returns stdout as a string"""
    return program_output(*args, shell=True, **kwargs)

def partial_escape(url):
    """
    Quote characters in urls that browsers can't do automatically, because they have special meaning.
    This can be used for forming srcids.
    """
    chars = "#?\\"
    for char in chars:
        url = url.replace(char, '%%%x' % ord(char))
    return url

_tag_regexp = re.compile('<[^>]*>')

def strip_html(text):
    "Remove HTML tags"
    return ' '.join(_tag_regexp.split(text))

_sid_regex = re.compile('(.*)(&(amp;)?sid=[0-9a-f]*)(.*)')

def remove_sid(url):
    """Remove &sid=... query, if any, from a url"""
    match = _sid_regex.match(url)
    if match:
        return match.group(1) + match.group(4)
    return url

assert remove_sid('gamelist-display.php?game=206&amp;sid=d12a342f6ae0d&foo=bar') == 'gamelist-display.php?game=206&foo=bar'
assert remove_sid('gamelist-display.php?game=206&sid=d12a342f6ae0d&foo=bar') == 'gamelist-display.php?game=206&foo=bar'
assert remove_sid('gamelist-display.php?game=206&sid=d12a342f6ae0d') == 'gamelist-display.php?game=206'
assert remove_sid('gamelist-display.php?game=206') == 'gamelist-display.php?game=206'

def link(href, text):
    if len(href):
        return '<a href="' + href + '">' + text + '</a>'
    return text

def text2html(obj):
    """Format raw text to html"""
    return cgi.escape(obj).replace('\n', '<br>\n')

def shorten(text, maxlen):
    if len(text) > maxlen - 3:
        return text[:maxlen - 3] + "..."
    return text

def array_from_string(string, ctype = ctypes.c_short):
    """Create a ctypes array from a string/bytes object with given type."""
    return ctypes.cast(ctypes.create_string_buffer(string), ctypes.POINTER(ctype))
