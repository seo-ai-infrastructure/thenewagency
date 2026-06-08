#!/usr/bin/env python3
"""
Entry point for the Agency OS Background Worker.
This runs Celery to process long-running AI tasks from Redis.

Usage:
  celery -A lib.tasks worker --loglevel=info
"""
import os
import sys
import pathlib
from dotenv import load_dotenv

# Ensure ROOT is on pythonpath
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

load_dotenv()

from lib.tasks import app

if __name__ == "__main__":
    app.start()
