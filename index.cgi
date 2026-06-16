#!/home/dorjecha/public_html/app.cyber-tech.com/venv/bin/python
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from wsgiref.handlers import CGIHandler
from app import app


class StripScriptName:
    """Reset SCRIPT_NAME so Flask url_for() generates clean URLs without /index.cgi prefix."""
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        environ['SCRIPT_NAME'] = ''
        environ.setdefault('PATH_INFO', '/')
        return self.app(environ, start_response)


CGIHandler().run(StripScriptName(app))
