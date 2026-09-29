"""DGX-private drafts for a paused, user-initiated Skill attack workflow."""
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from skillloop.protocol import digest_bytes

class Submissions:
    def __init__(self, root):
        self.root=Path(root)
        if not str(self.root.resolve()).startswith('/home/asus_gx10/skillloop/demo-private'):
            raise ValueError('demo_dgx_private_storage_required')
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.root.stat().st_mode & 0o077:raise ValueError('demo_private_permissions')
        self.db=self.root/'submissions.sqlite';self.lock=threading.Lock()
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS submissions(id TEXT PRIMARY KEY, request_key TEXT UNIQUE, public TEXT NOT NULL)')
        os.chmod(self.db,0o600)
    def connect(self):
        db=sqlite3.connect(self.db,timeout=10)
        db.execute('PRAGMA synchronous=FULL')
        return db
    def list(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT public FROM submissions ORDER BY rowid DESC LIMIT 20')]
    def save(self,value):
        if not isinstance(value,dict) or set(value)!={'skill','task','expected','forbidden','request_key'}:
            raise ValueError('demo_submission_schema')
        for key,lower,upper in [('skill',20,8192),('task',5,1000),('expected',1,256),('forbidden',3,100)]:
            text=value[key]
            if not isinstance(text,str) or not lower<=len(text.encode())<=upper or '\x00' in text:
                raise ValueError('demo_submission_size')
        request_key=value['request_key']
        try:uuid.UUID(request_key)
        except (ValueError,TypeError,AttributeError):raise ValueError('demo_request_key') from None
        with self.lock,self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT public FROM submissions WHERE request_key=?',(request_key,)).fetchone()
            if old:return json.loads(old[0])
            if db.execute('SELECT COUNT(*) FROM submissions').fetchone()[0]>=20:
                raise ValueError('demo_submission_limit')
            sid='submission-'+uuid.uuid4().hex;folder=self.root/sid;folder.mkdir(mode=0o700)
            raw=json.dumps({k:value[k] for k in ('skill','task','expected','forbidden')},ensure_ascii=False).encode()
            fd=os.open(folder/'input.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as file:
                file.write(raw);file.flush();os.fsync(file.fileno())
            public={'id':sid,'status':'saved_paused','created_at':time.time(),
                    'skill_bytes':len(value['skill'].encode()),'skill_digest':digest_bytes(value['skill'].encode()),
                    'experiment_started':False,'api_requests':0,'formal_attestation':False}
            db.execute('INSERT INTO submissions VALUES(?,?,?)',(sid,request_key,json.dumps(public)))
            return public
