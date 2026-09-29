"""Durable epoch and delivery reservations; no delivered-session reexecution."""
import os
import secrets
import sqlite3
from pathlib import Path
from skillloop.protocol import digest_jcs

class ProtectionAuthority:
    def __init__(self, root: Path):
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if root.stat().st_mode & 0o077:
            raise ValueError('private_directory_permissions')
        self.path = root / 'authority.sqlite'
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS epochs (
                campaign TEXT PRIMARY KEY, finalist TEXT NOT NULL, epoch TEXT UNIQUE NOT NULL,
                projection TEXT UNIQUE NOT NULL, opaque_ref TEXT UNIQUE NOT NULL, factory TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS payloads (digest TEXT PRIMARY KEY, epoch TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (key TEXT PRIMARY KEY, epoch TEXT NOT NULL,
                state TEXT NOT NULL, result_digest TEXT);
                CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY, key TEXT NOT NULL,
                old_state TEXT, new_state TEXT NOT NULL);''')
        os.chmod(self.path, 0o600)
    def connect(self):
        db=sqlite3.connect(self.path, timeout=10)
        db.execute('PRAGMA synchronous=FULL')
        return db
    def used(self):
        with self.connect() as db:
            return ([x[0] for x in db.execute('SELECT epoch FROM epochs')],
                [x[0] for x in db.execute('SELECT projection FROM epochs')],
                [x[0] for x in db.execute('SELECT digest FROM payloads')])
    def create_epoch(self, *, campaign, finalist, validation, factory_digest):
        opaque='protected-'+secrets.token_hex(16)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO epochs VALUES(?,?,?,?,?,?)', (campaign,finalist,
                validation['epoch_id'],validation['business_projection_digest'],opaque,factory_digest))
            db.executemany('INSERT INTO payloads VALUES(?,?)',
                [(d,validation['epoch_id']) for d in validation['payload_digests']])
        return opaque
    def reserve(self, deployment, campaign, epoch, subject, case, repetition):
        key=digest_jcs([deployment,campaign,epoch,subject,case,repetition])
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM epochs WHERE campaign=? AND epoch=?',(campaign,epoch)).fetchone() is None:
                raise ValueError('unknown_epoch')
            if db.execute('SELECT 1 FROM sessions WHERE key=?',(key,)).fetchone():
                raise ValueError('no_protected_reexecution')
            db.execute('INSERT INTO sessions VALUES(?,?,?,NULL)',(key,epoch,'reserved'))
            db.execute('INSERT INTO audit(key,old_state,new_state) VALUES(?,NULL,?)',(key,'reserved'))
        return key
    def transition(self, key, expected, state, result_digest=None):
        if (expected,state) not in {('reserved','delivered'),('reserved','not_delivered'),
                ('delivered','unknown'),('delivered','complete')}:
            raise ValueError('invalid_delivery_transition')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            count=db.execute('UPDATE sessions SET state=?,result_digest=? WHERE key=? AND state=?',
                (state,result_digest,key,expected)).rowcount
            if count!=1: raise ValueError('session_cas_conflict')
            db.execute('INSERT INTO audit(key,old_state,new_state) VALUES(?,?,?)',(key,expected,state))
    def state(self, key):
        with self.connect() as db:
            row=db.execute('SELECT state,result_digest FROM sessions WHERE key=?',(key,)).fetchone()
        return row
