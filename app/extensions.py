"""Shared MongoDB connection for the entire application."""
import os
import logging
from pymongo import MongoClient
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_client = None
_db = None


def init_db(app):
    """Initialize the shared MongoDB client. Call once from create_app()."""
    global _client, _db

    uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/interview_app')

    # Determine database name from URI, fallback to 'interview_app'
    parsed = urlparse(uri)
    db_name = parsed.path.lstrip('/').split('?')[0] or 'interview_app'

    _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    _db = _client[db_name]

    # Ensure indexes
    try:
        _db.users.create_index('email', unique=True)
        _db.interview_runs.create_index([('user_email', 1), ('created_at', -1)])
        _db.resumes.create_index('user_email', unique=True)
        logger.info('MongoDB indexes ensured on %s', db_name)
    except Exception:
        logger.warning('Could not create MongoDB indexes (non-fatal)')

    app.extensions['mongo_client'] = _client
    app.extensions['db'] = _db
    logger.info('MongoDB connected to database: %s', db_name)


def get_db():
    """Return the shared database object. Must be called after init_db()."""
    if _db is None:
        raise RuntimeError('Database not initialized. Call init_db(app) first.')
    return _db
