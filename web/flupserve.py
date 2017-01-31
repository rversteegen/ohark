#!/usr/bin/python
#import sys
#sys.path.append('/home/teeemcee/.local/lib/python2.6/site-packages')
from flup.server.fcgi import WSGIServer
#from flipflop import WSGIServer

#from website import application

def application(environ, start_response):
    with open("/home/teeemcee/ohr/ohr_archive/web/logf.txt", "a") as f:
        f.write("req...\n")
    start_response("200 OK", [('Content-Type', 'text/html')])
    return ["hello2\n"]

if __name__ == '__main__':
    with open("/home/teeemcee/ohr/ohr_archive/web/logf.txt", "a") as f:
        f.write("spawning...\n")
    WSGIServer(application).run()


#See http://flask.pocoo.org/docs/0.12/deploying/fastcgi/
