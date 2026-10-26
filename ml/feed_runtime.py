"""Explicit release selector; no training or network access during runtime."""
import importlib
import os

def create_app():
    release=os.environ.get('FEED_RELEASE','v1')
    ranker=os.environ.get('FEED_RANKER','e5')
    if release not in {'v1','v2'} or ranker not in {'e5','catboost'} or (release=='v1' and ranker!='e5'):
        raise RuntimeError('Supported releases: v1/e5, v2/e5, v2/catboost (experimental)')
    return importlib.import_module('feed.server' if release=='v1' else 'feed_v2.server').create_app()
