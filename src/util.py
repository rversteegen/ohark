import sys
import os
import re

################################################################################
### Util

py2 = sys.version_info[0] == 2
if py2:
    tostr = unicode
else:
    tostr = str

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

def shorten(text, maxlen):
    if len(text) > maxlen - 3:
        return text[:maxlen - 3] + "..."
    return text
