"""
Customisable, local configuration.
"""

# Add stuff to sys.path here
# But you can run "./setup.py develop --user" in the rpgbatch
# directory instead of adding a path to rpgbatch here
import sys
#sys.path.append('/home/teeemcee/local/lib/python2.6/site-packages/tabulate-0.7.5-py2.6.egg')
#sys.path.append('/home/ralph/ohr/new-svn/tools/rpgbatch')
#sys.path.append('.')



# mod_python_wsgi doesn't really set the path variables so that it's
# possible to see where we are...
# Where the static files are on the server
#STATIC_ROOT = '/home/teeemcee/ohr/ohr_archive/web/'
STATIC_ROOT = '../web/' #os.path.abspath(os.curdir) + '../web/'
# Part of <base> tag, relative URLs according to this
URL_ROOTPATH = '/ohr-archive/'  #'/ohr/ark/'

#SRC_DIR = '../src/'

def local_path_to_url(local_path):
    """Returns a URL if a file can be accessed externally, or None if it can't"""
    if local_path.startswith('data/'):
        return 'hosted/' + local_path[5:]
