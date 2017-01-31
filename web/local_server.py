#!/usr/bin/env python

# NOTE: if the scrapers are run as python 3 and the server as python 2,
# then Game can't be unpickled because __new__ is missing. All other combos work.

import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/../src'))

from wsgiref.simple_server import make_server

import website

httpd = make_server('', 8007, website.application)
print("Serving HTTP on port 8007...")

# Respond to requests until process is killed
httpd.serve_forever()

# Alternative: serve one request, then exit
httpd.handle_request()
