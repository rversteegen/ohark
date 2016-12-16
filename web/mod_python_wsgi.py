# This file is not part of ohr-archive. License not known.
"""
===========================
WSGI wrapper for mod_python
===========================
:Author: Eli Collins <elic@astllc.org>
:Version: 2008-05-29

Warning
=======
As of 2011-05-31, this module is no longer maintained; though it has no known bugs.
mod_python it self is no longer actively developed either; and it is *strongly* 
recommended that wsgi projects move away from mod_python 
(in combination with this script or any other),
and use the new mod_wsgi project instead.

About
=====
This is based on the modpython_wsgi.py file found at
http://projects.amor.org/misc/wiki/ModPythonGateway,
but has been signicantly rewritten to add the following features:

    - speed up request handling w/ by storing static values
    - integrated paste support, for easier paste/pylons deployment
    - file_wrapper support using mod_python's sendfile()
    - support for multiple applications at the same time,
      using the ``wsgi.handler_id`` option.

Requirements
============
* requires Python 2.2 or greater
* requires mod_python

Installation
============
This file should be installed in mod_python's directory as "wsgi.py".
It can then be referred to as "mod_python.wsgi" using
the ``PythonHandler`` directive.

This is only the recommended location,
you can install it anywhere reachable by ``sys.path``, just make
sure to give the full import name to ``PythonHandler``.

Configuration
=============

Example Config For Pylons
-------------------------
Most pylons deployments can use this example configuration::

    <Location /myurl>
        SetHandler mod_python
        PythonHandler mod_python.wsgi
        PythonOption wsgi.paste_application /home/user/myapp/deploy.ini
        PythonOption SCRIPT_NAME /myurl
    </Location>

Alternate Config For Pylons
---------------------------
If you need your project's directory added to sys.path,
the following shortcut is available::

    <Location /myurl>
        SetHandler mod_python
        PythonHandler mod_python.wsgi
        PythonOption wsgi.application_path /home/user/myapp
        PythonOption wsgi.paste_application deploy.ini
        PythonOption SCRIPT_NAME /myurl
    </Location>

Note that the ``wsgi.paste_application`` can be specified
relative to the ``wsgi.application_path``, such as in this example,
where this script will look for ``/home/user/myapp/deploy.ini``

Required Keywords
-----------------
.. note::
    Exactly ONE of these two keywords is required

.. note::
    The resulting wsgi ``app`` object may be a
    function, bound method, or callable object.

PythonOption wsgi.application <module>::<func>
    Imports the specified function for use as the
    wsgi application to call with requests.

PythonOption wsgi.paste_application <inipath>
    Calls paste.deploy.loadapp() using the specified 'ini' file.
    This path can be relative ONLY if ``wsgi.application_path`` is specified,
    at which point it is taken to be relative to that path;
    else it is required to be an absolute path.

Optional Keywords
-----------------
PythonOption SCRIPT_NAME <urlpath>
    Specifies the SCRIPT_NAME of the application.
    Defaults to an empty string.

PythonOption wsgi.startup <module>::<func>
    If specified, this function is invoked once per process,
    before the the first request is handled, and is passed in
    the request object associated w/ the first request.

PythonOption wsgi.cleanup <module>::<func>
    If specified, this function is invoked with no arguments
    called when apache unloads each process / thread

PythonOption wsgi.application_path <filepath>
    If present, this specifies the path where the application's libraries
    are stored... it will then be added to sys.path if it isn't already.
    This must be an absolute path.
    If 'wsgi.paste_application' is a specified using a relative path,
    it will be joined to the end of this path.

PythonOption wsgi.handler_id <id>
    If this module is to be handling multiple applications
    within the same virtual host, they must each be given a unique
    handler_id to distiguish them, for internal caching.
    If handler_id isn't specified, one is generated based on
    the file & lineno of the virtual host declaration
    which invoked this handler.

WSGI Compatibility
==================
this code attempts to be compatible with PEP-0333 if at all possible.
However, it deviates from the standard in the following ways:

the `file_wrapper()` function accepts two additional optional keywords
(``offset`` and ``size``) which allow the wrapper to serve HTTP_RANGE requests.
in order to prevent compatibility issues, code which uses these features
should first check for that::

    getattr(environ['wsgi.file_wrapper'], 'supports_http_range', False)

...returns a value of ``True``, else the code should assume the provided
filewrapper does not provide this feature.
for the full specification of this non-standard extension,
see the documentation of the `file_wrapper()` function below.

TODO
====
* write patch for Paste to enable it's FileApp class
  to make use 'wsgi.file_wrapper', as well as support
  this module's HTTP_RANGE extension.

History
=======
    2006-11-03
        * alpha release

    2006-11-30
        * first release

    2007-09-18
        * bugfix

    2008-05-27
        * bugfix

    2008-05-29
        * bugfixes
        * redid how "app" is stored, so that it can be bound method etc.
        * reformatted documentation to use rest markup
"""
#=====================================================
#imports / constants
#=====================================================
#core
import os
import sys
import traceback
try:
    from threading import Lock
except ImportError:
    from dummy_threading import Lock
from warnings import warn
#site
from mod_python import apache
#module

#default block size for FileWrapper transfers
DEFAULT_BLOCK_SIZE = 8 * 1024

#=====================================================
#handlers
#=====================================================
cache = {}
cache_lock = Lock() #lock held when setting cache dict

def handler(req):
    """
    mod_python request handler,
    hands off request to wsgi stack using subclass of Handler
    created new subclass for each virtual host, and uses that class
    to store information that's static for that virtual host
    """
    global cache, cache_lock
    try:
        #since this module may be used by multiple virtual hosts,
        #try to ID each virtual host based off req.server
        #if a handler_id wasn't specified directly...
        handler_id = req.get_options().get('wsgi.handler_id','')
        if handler_id == '':
            handler_id = "%s::%s" % (req.server.defn_name,
                req.server.defn_line_number)

        #'cache' contains a subclass of Handler for each handler_id,
        #which contains static information unique to handler_id,
        #and handles all of it's requests.
        #go find it...
        cache_lock.acquire()
        try:
            handler = cache.get(handler_id, None)
            if handler is None:
                #handler doesn't exist, so create it
                handler = type("Handler_" + handler_id, (Handler,), {})
                handler.handler_id = handler_id
                handler.load_static_values(req)
                #register class in cache only if load_static_values suceeds
                cache[handler_id] = handler
        finally:
            cache_lock.release()

        #invoke the handler to handle the request
        handler(req)
        return apache.OK

    except:
        #something went wrong somewhere!
        traceback.print_exc(None, ErrorWrapper(req))
        raise apache.SERVER_RETURN, apache.HTTP_INTERNAL_SERVER_ERROR

#=====================================================
#request handler class
#=====================================================
path_lock = Lock() #lock used when messing w/ sys.path

class Handler(object):
    """
    this class is instantiated per-request...
    and all action is taken within the __init__ method.
    on the first request, cls.load_static_values() is called to set up
    class defaults based on PythonOption directives and
    other things that won't change between requests.
    """
    #=====================================================
    #virtualhost-wide static values
    #=====================================================
    handler_id = None #the handler_id the subclass belongs to
    app = None #the wsgi application to invoke
    static_environ = None #the static wsgi environ variables
        #ie, values that will stay the same throughout a single virtual host

    def load_static_values(cls, req):
        """
        called once per (process, handler_id)
        before first request is handled.
        loads static configuration values into class.
        """
        global file_wrapper, path_lock

        #get request options
        options = req.get_options()

        #Add application path, if any.
        base_path = options.get('wsgi.application_path', None)
        if base_path is not None:
            if not os.path.isabs(base_path):
                raise ValueError, "wsgi.application_path must be absolute"
            base_path = os.path.normpath(base_path)
            #don't all do this at once
            path_lock.acquire()
            try:
                if base_path not in sys.path:
                    sys.path.append(base_path)
            finally:
                path_lock.release()

        #Run the startup function, if any.
        desc = options.get('wsgi.startup')
        if desc:
            startup = loadFuncDesc(desc)
            startup(req)

        # Register a cleanup function if requested.
        desc = options.get('wsgi.cleanup')
        if desc:
            cleanup = loadFuncDesc(desc)
            def cleaner(data):
                cleanup()
            if hasattr(apache, "register_cleanup"):
                #NOTE: apache.register_cleanup wasn't available until 3.1.4.
                apache.register_cleanup(cleaner)
            else:
                req.server.register_cleanup(req, cleaner)

        # Load the application function
        if 'wsgi.application' in options:
            app = loadFuncDesc(options['wsgi.application'])
        elif 'wsgi.paste_application' in options:
            from paste.deploy import loadapp
            cfgpath = options['wsgi.paste_application']
            if not os.path.isabs(cfgpath):
                if base_path is not None:
                    cfgpath = os.path.join(base_path, cfgpath)
                else:
                    raise ValueError, "wsgi.paste_application must be an absolute path"
            app = loadapp("config:" + cfgpath)
        else:
            raise KeyError, "no wsgi application specified, must specify one of wsgi.application or wsgi.paste_application"
        #NOTE: 'app' may be bound method, callable object, or func...
        #so we wrap it to ensure it always behaves correctly
        def app_wrapper(*args, **kwds):
            return app(*args, **kwds)
        cls.app = staticmethod(app_wrapper)

        # Figure what kinda of mpm apache's using
        try:
            q = apache.mpm_query
            threaded = q(apache.AP_MPMQ_IS_THREADED)
            forked = q(apache.AP_MPMQ_IS_FORKED)
        except AttributeError:
            #else, we've gotta be told explicitly via PythonOption directives
            threaded = readBoolOption(options, 'multithread')
            forked = readBoolOption(options, 'multiprocess')

        #setup static wsgi environ keys
        cls.static_environ = {
            'wsgi.version': (1,0),
            'wsgi.run_once': False,
            'wsgi.file_wrapper': file_wrapper,
            'SCRIPT_NAME': options.get('SCRIPT_NAME', ''),
            'wsgi.multithread': threaded,
            'wsgi.multiprocess': forked,
            }
    load_static_values = classmethod(load_static_values)

    #=====================================================
    #creation & invocation
    #=====================================================
    request = None #set to the request object
    set_headers = False #whether we've set the headers yet
    #NOTE: code uses self.req.bytes_sent to test if we've started writing data

    def __init__(self, req):
        self.request = req

        #set up base env
        env = dict(apache.build_cgi_env(req))
        assert isinstance(self.static_environ, dict), "expected dict, found %r" % (self.static_environ,)
        env.update(self.static_environ)
        env['PATH_INFO'] = req.uri[len(env['SCRIPT_NAME']):]
        env['wsgi.input'] = InputWrapper(req)
        env['wsgi.errors'] = ErrorWrapper(req)
        if env.get("HTTPS") in ('yes', 'on', '1'):
            env['wsgi.url_scheme'] = 'https'
        else:
            env['wsgi.url_scheme'] = 'http'

        #debugging
        ##env['handler.hid'] = self.handler_id
        ##req.log_error("REQUEST: %(REQUEST_METHOD)r %(PATH_INFO)r %(QUERY_STRING)r HID=%(handler.hid)r" % env)

        #run the wsgi application
        result = self.app(env, self.start_response)

        #handle the application's result
        if hasattr(result, 'close'):
            try:
                self.write_result(result)
            finally:
                result.close()
        else:
            self.write_result(result)

    #=====================================================
    #wsgi helpers
    #=====================================================
    def start_response(self, status, headers, exc_info=None):
        """
        set the http response headers.

        In accordance with PEP-0333:

        this function must be called once before writing data.

        this function can be called a second time ONLY if passing in exc_info.
        in that case, the supplied headers will only be used if no data
        has been written... else the exception will simply be reraised.
        """
        req = self.request

        if exc_info:
            try:
                if req.bytes_sent:
                    raise exc_info[0], exc_info[1], exc_info[2]
            finally:
                exc_info = None
        elif self.set_headers:
            raise RuntimeError, "start_response() cannot be called a second time unless an error has occurred!"

        #NOTE: PEP-0333 says to delay sending headers until
        #immediately before first write, but mod_python promises
        #that's just what it'll do if we just set them in 'req'
        req.status = int(status[:3])

        for key, val in headers:
            if key.lower() == 'content-length':
                req.set_content_length(int(val))
            elif key.lower() == 'content-type':
                req.content_type = val
            else:
                req.headers_out.add(key, val)

        self.set_headers = True

        #NOTE: returning this func for legacy imperative applications
        #SHOULD NOT BE USED BY NEW CODE
        return req.write

    def write_result(self, result):
        """
        this method is called by __init__ to handle the application's result value.
        it's in charge of writing it to the request object, and cleaning up afterwards.

        per PEP-0333,
            this must be an iterable yields 0+ strings
            if it has a close() method, this must be called afterwards.
            if it has a __len__ method, this must be an accurate length
        """
        req = self.request
        #TODO: check if content-length is unset, and use strategies PEP suggests

        #check for FileWrapper instances
        if isinstance(result, FileWrapper):
            if not self.set_headers:
                raise RuntimeError, "write() called before start_response()!"
            result.writefile(req)
        else:
            write = req.write
            #TODO: check for & use result.__len__
            if self.set_headers:
                #use fastest loop possible
                for data in result:
                    write(data)
            else:
                #use slow loop, cause we need to check for set_headers
                for data in result:
                    if data and not self.set_headers:
                        raise RuntimeError, "write() called before start_response()!"
                    write(data)
        if not req.bytes_sent:
            #application sent nothing back
            req.set_content_length(0)

    #=====================================================
    #EOC Handler
    #=====================================================

#=====================================================
#wsgi.file_wrapper implemenation
#=====================================================
def file_wrapper(stream, block_size=None, size=None, offset=None):
    """
    this is the function returned by wsgi.file_wrapper.

    :Parameters:
        stream
            The stream to read from, preferably a python file() object.
            If the stream is not of a type that can be accelerated, a DataWrapper
            instance will be returned which will simply act as an iterator and proxy
            the stream's read() method.

        block_size : int | None
            An optional block size to use when iterating over the file.
            This will be ignored if the serving is handled by apache,
            but it will be honored when iterating over the content.

        size : int | None
            Optional keyword, specifying the maximum number of bytes to serve.
            THIS OPTION IS NOT WSGI STANDARD, SEE HTTP_RANGE NOTE BELOW

            if this value is set to None or is an  < 0, the stream will be
            served until the end as per the WSGI spec (the default)

            if this value is  >=0, only that many bytes will be served.

            .. note::
                if an EOF occurs before 'size' bytes have been served,
                serving will stop there, but no error will be raised.

            .. note::
                size=0 is allowed, but why use it?

        offset : int | None
            Optional keyword specifying an offset to begin serving from.
            THIS OPTION IS NOT WSGI STANDARD, SEE HTTP_RANGE NOTE BELOW

            the offset is measured from the CURRENT POSITION of the stream.
            any value of None or < 0 acts like 0 was passed in.
            otherwise, this value must be an integer >=  0

            unlike the size flag, this keyword is not required to
            implement HTTP_RANGE support, but is mainly here for convience,
            or in case another implementation can do it better.

            NOTE: if offset is past EOF, an empty string will be served.

    HTTP_RANGE
    ==========
    The ``offset`` and ``size`` keywords are not part of the WSGI standard.
    However, they are extremely useful, as they provide the ability for
    a file_wrapper to handle HTTP_RANGE requests.

    So as not to break compatibility with the WSGI standard,
    applications that wish to use these keywords should perform
    the following check:

        getattr(environ['wsgi.file_wrapper'], 'supports_http_range', False)

    Only if this returns True should they assume that the file_wrapper
    supports these extensions to the WSGI spec. If it doesn't return True,
    they should assume the standard WSGI behavior.

    Furthermore, these should be specified as KEYWORDS, so as
    to leave any positional parameters free for future WSGI use.
    """
    if not hasattr(stream, "read"):
        raise ValueError, "file_wrapper: stream is missing read() method"
    if size == 0:
        return [ '' ]
    opts = dict(
        block_size=block_size,
        size=size,
        offset=offset,
        )
    if hasattr(stream, "fileno") and hasattr(stream, "name") and hasattr(stream, "tell"):
        #NOTE: need filepath, since apache's sendfile() takes that instead of fd
        #FIXME: need better way to get path from file object!
        path = stream.name
        if not os.path.isabs(path):
            #FIXME: just guessing at this point, hoping getcwd() didn't change!
            cwd = os.getcwd()
            warn("filewrapper: file %r has relative path, using cwd %r" % (path, cwd))
            path = os.path.join(cwd, path)
        if os.path.exists(path):
            return FileWrapper(stream, path, **opts)
    return DataWrapper(stream, **opts)

#set flags so apps can used extended features...
file_wrapper.supports_http_range = True

class DataWrapper(object):
    """
    provides an unaccelerated iterator over a stream via stream.read()
    used if the object passed to file_wrapper() can't be accelerated.
    also provides base iteration ability for FileWrapper class
    """
    def __init__(self, stream, block_size=None, size=None, offset=None):
        global DEFAULT_BLOCK_SIZE
        #set attributes
        self.stream = stream
        if hasattr(stream, "close"):
            self.close = stream.close
        if block_size is None or block_size < 1:
            self.block_size = DEFAULT_BLOCK_SIZE
        else:
            self.block_size = block_size
        if size is None or self.size < 0:
            self.size = None
        else:
            self.size = size
        #move stream forward by offset
        if offset > 0:
            if hasattr(stream, "seek"):
                stream.seek(offset, 1)
            else:
                stream.read(offset)

    def __iter__(self):
        return self

    def next(self):
        chunk_size = self.block_size
        if self.size is not None:
            if self.size < chunk_size:
                chunk_size = self.size
            self.size -= chunk_size
        chunk = self.stream.read(chunk_size)
        if not chunk:
            raise StopIteration
        return chunk

class FileWrapper(DataWrapper):
    """
    provides an iterator over a filehandle.
    used if the object passed in can be accelerated via sendfile()
    """
    def __init__(self, stream, path, **opts):
        super(FileWrapper, self).__init__(stream, **opts)
        self.path = path

    def writefile(self, req):
        """
        called by Handler class to send file using mod_python
        """
        offset = self.stream.tell()
        if self.size is None:
            size = -1
        else:
            size = self.size
        req.sendfile(self.path, offset, size)

#=====================================================
#wsgi.input & wsgi.errors streams
#=====================================================
class InputWrapper(object):
    """
    provides a file-like object to act as the
    'wsgi.input' stream for a request.

    this is class proxys read requests to the request
    objects's read/readline methods.
    """
    def __init__(self, req):
        self.req = req

    def read(self, size=-1):
        #NOTE: 'size' argument REQUIRED in PEP-0333
        return self.req.read(size)

    def readline(self, size=-1):
        #NOTE: 'size' argument NOT SUPPORTED by PEP-0333
        return self.req.readline(size)

    def readlines(self, hint=-1):
        return self.req.readlines(hint)

    def __iter__(self):
        line = self.readline()
        while line:
            yield line
            #NOTE: this won't prefetch the next line; it only
            # gets called if the generator is resumed.
            line = self.readline()

class ErrorWrapper(object):
    """
    provides a file-like object to act as the
    'wsgi.errors' stream for a request.
    this is class proxys write requests
    to the request objects's log_error method.
    """
    def __init__(self, req):
        self.req = req

    def flush(self):
        pass

    def write(self, msg):
        #NOTE: msg may have '\n' delimited lines,
        #but log_error() should seems split these up
        self.req.log_error(msg)

    def writelines(self, seq):
        self.write('\n'.join(seq))

#=====================================================
#support funcs
#=====================================================
def loadFuncDesc(desc):
    """
    load function object from description string using the form::

        ( module "." ) * module '::' fname

    if called multiple times with same string, should return same function.
    """
    module_name, object_name = desc.split('::', 1)
    module = __import__(module_name, globals(), locals(), [''])
    return apache.resolve_object(module, object_name)
    #return getattr(module, object_name)

def readBoolOption(options, key):
    value = options.get(key, '').lower()
    if value == 'on':
        return True
    elif value == 'off':
        return False
    else:
        raise ValueError(
            ("You must provide a PythonOption '%s', either 'on' or 'off', "
             "when running a version of mod_python < 3.1"
             ) % key)

#=====================================================
#EOF
#=====================================================
