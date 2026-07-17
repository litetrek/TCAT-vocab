import sys
import os

# Add project root so app.py and all its imports resolve correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: F401  — Vercel invokes this WSGI callable
