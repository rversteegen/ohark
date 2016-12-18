#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/../src'))

from wsgiref.simple_server import make_server

import website

httpd = make_server('', 8000, website.application)
print("Serving HTTP on port 8000...")

# Respond to requests until process is killed
httpd.serve_forever()

# Alternative: serve one request, then exit
httpd.handle_request()
