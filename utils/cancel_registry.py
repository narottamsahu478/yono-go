"""Durable cancellation intents. Set CANCEL_DB_PATH to a persistent volume path."""
import os
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(os.getenv('CANCEL_DB_PATH', 'data/cancel_worker.sqlite3'))


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH), timeout=20)
    db.execute('PRAGMA busy_timeout=20000')
    db.execute('''CREATE TABLE IF NOT EXISTS activations (
        provider TEXT NOT NULL, txn_id TEXT NOT NULL, phone TEXT,
        otp_received INTEGER NOT NULL DEFAULT 0,
        state TEXT NOT NULL DEFAULT 'active', attempts INTEGER NOT NULL DEFAULT 0,
        next_check REAL NOT NULL DEFAULT 0, updated REAL NOT NULL,
        PRIMARY KEY(provider, txn_id))''')
    columns = {row[1] for row in db.execute("PRAGMA table_info(activations)")}
    if 'session_id' not in columns:
        db.execute('ALTER TABLE activations ADD COLUMN session_id TEXT')
    db.commit()
    return db


def register(provider, txn_id, phone):
    if not txn_id: return
    import globals
    with connect() as db:
        db.execute('''INSERT INTO activations(provider,txn_id,phone,updated,session_id) VALUES(?,?,?,?,?)
            ON CONFLICT(provider,txn_id) DO UPDATE SET phone=excluded.phone,updated=excluded.updated''',
            (provider, str(txn_id), str(phone), time.time(), globals.cancel_session_id))


def mark_otp(provider, txn_id):
    with connect() as db:
        db.execute("UPDATE activations SET otp_received=1, state='protected',updated=? WHERE provider=? AND txn_id=? AND state NOT IN ('cancelled','finished')",
                   (time.time(), provider, str(txn_id)))


def request_cancel(provider, txn_id, phone):
    register(provider, txn_id, phone)
    with connect() as db:
        db.execute("UPDATE activations SET state='pending_cancel',next_check=0,updated=? WHERE provider=? AND txn_id=? AND otp_received=0 AND state NOT IN ('cancelled','finished','cancelling')",
                   (time.time(), provider, str(txn_id)))


def claim():
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT provider,txn_id,phone,attempts FROM activations WHERE state='pending_cancel' AND otp_received=0 AND next_check<=? ORDER BY updated LIMIT 1", (time.time(),)).fetchone()
        if row:
            db.execute("UPDATE activations SET state='cancelling',updated=? WHERE provider=? AND txn_id=? AND state='pending_cancel'", (time.time(),row[0],row[1]))
        return row


def finish(provider, txn_id, status, attempts=0):
    with connect() as db:
        if status == 'Released':
            db.execute("UPDATE activations SET state='cancelled',updated=? WHERE provider=? AND txn_id=?", (time.time(),provider,str(txn_id)))
        else:
            attempts += 1
            db.execute("UPDATE activations SET state='pending_cancel',attempts=?,next_check=?,updated=? WHERE provider=? AND txn_id=? AND state='cancelling'", (attempts,time.time()+min(300,30*2**min(attempts,4)),time.time(),provider,str(txn_id)))


def recover():
    with connect() as db:
        db.execute("UPDATE activations SET state='pending_cancel' WHERE state='cancelling' AND updated<? AND otp_received=0", (time.time()-180,))


def is_protected(provider, txn_id):
    with connect() as db:
        row = db.execute('SELECT otp_received FROM activations WHERE provider=? AND txn_id=?', (provider,str(txn_id))).fetchone()
        return bool(row and row[0])


def session_cancelled(session_id):
    """Confirmed cancellations for the purchase session, not the worker's current session."""
    if not session_id:
        return []
    with connect() as db:
        rows = db.execute("SELECT provider,txn_id,phone,updated FROM activations WHERE session_id=? AND state='cancelled' ORDER BY updated DESC", (session_id,)).fetchall()
    from datetime import datetime
    return [dict(provider=provider, txn_id=txn, phone=phone, status='Released',
                 time=datetime.fromtimestamp(updated).strftime('%H:%M:%S'), attempts=1,
                 response='Confirmed by cancellation worker') for provider,txn,phone,updated in rows]


def session_transactions(session_id):
    if not session_id:
        return set()
    with connect() as db:
        return {(str(p).lower(), str(t)) for p,t in db.execute('SELECT provider,txn_id FROM activations WHERE session_id=?', (session_id,))}
