"""
db.py

Very simple database helper built directly on PyMySQL (no ORM).
Every module imports the functions from this file to talk to MySQL.

How it works:
- get_db() opens one PyMySQL connection per request and stores it on
  Flask's "g" object, so the same request reuses the same connection.
- close_db() closes that connection automatically at the end of the request.
- query_all() / query_one() / execute() are small helper functions so
  the rest of the code never has to write raw cursor code by hand.
"""
import pymysql
import pymysql.cursors
from flask import g, current_app


def get_db():
    """Open (or reuse) a PyMySQL connection for the current request."""
    if "db" not in g:
        connect_args = dict(
            host=current_app.config["DB_HOST"],
            port=current_app.config["DB_PORT"],
            user=current_app.config["DB_USER"],
            password=current_app.config["DB_PASSWORD"],
            database=current_app.config["DB_NAME"],
            cursorclass=pymysql.cursors.DictCursor,  # rows come back as dicts
            autocommit=True,
        )
        # Managed MySQL hosts used in production (PlanetScale, Railway,
        # Aiven, etc.) require an SSL connection. Set DB_SSL=true in your
        # .env / host's environment variables to turn this on — local
        # MySQL during development doesn't need it, so it's off by default.
        if current_app.config.get("DB_SSL"):
            connect_args["ssl"] = {"ssl": {}}
        g.db = pymysql.connect(**connect_args)
    return g.db


def close_db(e=None):
    """Close the database connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_all(sql, params=None):
    """Run a SELECT and return all rows as a list of dicts."""
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(sql, params or ())
        return cursor.fetchall()


def query_one(sql, params=None):
    """Run a SELECT and return a single row as a dict (or None)."""
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(sql, params or ())
        return cursor.fetchone()


def execute(sql, params=None):
    """Run an INSERT / UPDATE / DELETE. Returns the last inserted row id."""
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(sql, params or ())
        return cursor.lastrowid


def init_app(app):
    """Register close_db() to run automatically after every request."""
    app.teardown_appcontext(close_db)
