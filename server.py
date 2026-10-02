"""Loopback-only local archive. SQLite transactions keep attempts append-only."""
import argparse
import io
import json
import mimetypes
import os
import shutil
import sqlite3
import threading
import uuid
import zipfile
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from PIL import Image
from importer import scan, build_catalog, metadata

ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT/'examples'/'foundations'
STATES = ('未做过','做错了','做对了')
MAX_IMAGE = 12*1024*1024

class Archive:
    def __init__(self, data, source, archive_settings=None):
        self.data, self.source = Path(data).resolve(), Path(source).resolve()
        self.archive_settings=archive_settings
        self.data.mkdir(parents=True,exist_ok=True)
        (self.data/'media').mkdir(exist_ok=True)
        (self.data/'backups').mkdir(exist_ok=True)
        self.db = self.data/'archive.sqlite3'
        self.lock = threading.RLock()
        with self.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS questions(id TEXT PRIMARY KEY,data TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,question_id TEXT NOT NULL REFERENCES questions(id),created_at TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN ('未做过','做错了','做对了')),note TEXT NOT NULL,images TEXT NOT NULL,selected_option TEXT,request_id TEXT NOT NULL UNIQUE);
            CREATE INDEX IF NOT EXISTS records_question ON records(question_id,created_at);''')
        self.refresh()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db,timeout=20)
        connection.execute('PRAGMA foreign_keys=ON')
        connection.row_factory=sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def refresh(self):
        settings=metadata(self.source,self.archive_settings)
        questions, issues = scan(self.source,self.archive_settings)
        if not questions:raise ValueError('没有可导入题目；请检查题库路径')
        with self.lock, self.connect() as c:
            # Keep prior valid data when a source file is temporarily being edited.
            failed = {i['file'].replace('\\','/') for i in issues}
            previous = [json.loads(r['data']) for r in c.execute('SELECT data FROM questions WHERE active=1')]
            questions += [q for q in previous if q['sourceFile'] in failed]
            questions.sort(key=lambda q:(q['chapterNumber'],q['sectionNumber'],q['type']=='综合应用题',q['number'],q['id']))
            c.execute('UPDATE questions SET active=0')
            c.executemany('INSERT INTO questions VALUES(?,?,1) ON CONFLICT(id) DO UPDATE SET data=excluded.data,active=1',[(q['id'],json.dumps(q,ensure_ascii=False)) for q in questions])
            catalog=build_catalog(questions,issues,settings)
            catalog['sourceRoot']=self.source.as_posix()
            catalog['importedAt']=datetime.now(timezone.utc).isoformat()
            tmp=self.data/'catalog.json.tmp'
            tmp.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
            os.replace(tmp,self.data/'catalog.json')
            self.catalog=catalog
        return {'total':catalog['total'],'issues':issues,'importedAt':catalog['importedAt']}

    def question(self, identifier):
        with self.connect() as c:
            row=c.execute('SELECT data FROM questions WHERE id=? AND active=1',(identifier,)).fetchone()
        if not row:raise KeyError('题目不存在')
        return json.loads(row['data'])

    @staticmethod
    def record_dict(row):
        return {'id':row['id'],'questionId':row['question_id'],'createdAt':row['created_at'],'state':row['state'],'note':row['note'],'images':json.loads(row['images']),'selectedOption':row['selected_option'],'requestId':row['request_id']}

    def records(self, identifier):
        with self.connect() as c:
            rows=c.execute('SELECT * FROM records WHERE question_id=? ORDER BY rowid',(identifier,)).fetchall()
        return [self.record_dict(row) for row in rows]

    def progress(self):
        with self.connect() as c:
            rows=c.execute('SELECT question_id,state,created_at,(SELECT count(*) FROM records x WHERE x.question_id=r.question_id) attempts FROM records r WHERE rowid=(SELECT max(rowid) FROM records x WHERE x.question_id=r.question_id)').fetchall()
        return {r['question_id']:{'state':r['state'],'attempts':r['attempts'],'createdAt':r['created_at']} for r in rows}

    def submit(self, payload):
        if not isinstance(payload,dict):raise ValueError('提交内容必须是 JSON 对象')
        identifier=payload.get('questionId')
        question=self.question(identifier)
        state=payload.get('state')
        if state not in STATES:raise ValueError('状态必须是未做过、做错了或做对了')
        note=payload.get('note','')
        if not isinstance(note,str) or len(note)>200000:raise ValueError('笔记必须是 20 万字以内的文字')
        images=payload.get('images',[])
        if not isinstance(images,list) or len(images)>30:raise ValueError('每次记录最多 30 张图片')
        for image in images:
            if not isinstance(image,str) or not image.startswith('/media/') or '/' in image[7:] or not (self.data/image.lstrip('/')).is_file():raise ValueError('笔记图片不存在，请先上传图片')
        option=payload.get('selectedOption')
        if option is not None and option not in [o['label'] for o in question['options']]:raise ValueError('选项不属于这道题')
        request=payload.get('requestId') or str(uuid.uuid4())
        if not isinstance(request,str) or len(request)>100:raise ValueError('requestId 不合法')
        with self.lock,self.connect() as c:
            existing=c.execute('SELECT * FROM records WHERE request_id=?',(request,)).fetchone()
            if existing:
                record=self.record_dict(existing)
                comparable={k:record[k] for k in ('questionId','state','note','images','selectedOption')}
                if comparable!={'questionId':identifier,'state':state,'note':note,'images':images,'selectedOption':option}:raise ValueError('这个 requestId 已用于另一份记录')
                return record
            record={'id':str(uuid.uuid4()),'questionId':identifier,'createdAt':datetime.now(timezone.utc).isoformat(),'state':state,'note':note,'images':images,'selectedOption':option,'requestId':request}
            c.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?)',(record['id'],identifier,record['createdAt'],state,note,json.dumps(images),option,request))
        self.backup_daily()
        return record

    def upload(self, blob):
        if not blob or len(blob)>MAX_IMAGE:raise ValueError('图片需小于 12 MB')
        try:
            with Image.open(io.BytesIO(blob)) as img:
                fmt=img.format
                if img.width*img.height>50000000:raise ValueError('图片尺寸太大')
                img.verify()
        except (OSError,Image.DecompressionBombError):raise ValueError('无法读取这张图片')
        ext={'PNG':'.png','JPEG':'.jpg','GIF':'.gif','WEBP':'.webp'}.get(fmt)
        if not ext:raise ValueError('支持 PNG、JPG、GIF 和 WebP')
        name=str(uuid.uuid4())+ext
        target=self.data/'media'/name
        temporary=target.with_suffix('.tmp')
        temporary.write_bytes(blob);os.replace(temporary,target)
        return '/media/'+name

    def backup_daily(self):
        path=self.data/'backups'/('archive-'+datetime.now().strftime('%Y-%m-%d')+'.sqlite3')
        with self.lock:
            with self.connect() as src, closing(sqlite3.connect(str(path)+'.tmp')) as dest:src.backup(dest)
            os.replace(str(path)+'.tmp',path)

    def export_zip(self):
        with self.lock:
            with self.connect() as c:records=[self.record_dict(r) for r in c.execute('SELECT * FROM records ORDER BY rowid')]
            buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr('records.json',json.dumps({'schemaVersion':1,'records':records},ensure_ascii=False,indent=2))
                z.writestr('catalog.json',json.dumps(self.catalog,ensure_ascii=False,indent=2))
                for image in sorted({i for r in records for i in r['images']}):z.write(self.data/image.lstrip('/'),image.lstrip('/'))
            return buf.getvalue()

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):pass
    def send(self,status,body,mime='application/json; charset=utf-8'):
        if isinstance(body,(dict,list)):body=json.dumps(body,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(body)

    def serve_file(self,root,relative):
        path=(root/unquote(relative)).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():raise KeyError('文件不存在')
        if root==self.server.archive.source and path.suffix.lower() not in {'.md','.png','.jpg','.jpeg','.webp','.gif'}:raise KeyError('文件类型不支持')
        mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        if mime.startswith('text/') or path.suffix=='.js':mime+='; charset=utf-8'
        self.send(200,path.read_bytes(),mime)

    def do_GET(self):
        archive=self.server.archive;url=urlparse(self.path);path=url.path
        try:
            if path=='/api/catalog':self.send(200,archive.catalog)
            elif path=='/api/progress':self.send(200,archive.progress())
            elif path.startswith('/api/questions/'):self.send(200,archive.question(unquote(path[15:])))
            elif path=='/api/records':self.send(200,archive.records(parse_qs(url.query).get('questionId',[''])[0]))
            elif path=='/api/backup':self.send(200,archive.export_zip(),'application/zip')
            elif path.startswith('/source/'):self.serve_file(archive.source,path[8:])
            elif path.startswith('/media/'):self.serve_file(archive.data/'media',path[7:])
            else:self.serve_file(ROOT/'web',path.lstrip('/') or 'index.html')
        except KeyError as e:self.send(404,{'error':str(e)})
        except (OSError,ValueError) as e:self.send(400,{'error':str(e)})

    def do_POST(self):
        archive=self.server.archive
        # Reject cross-site browser writes; CLI callers without Origin remain supported.
        origin=self.headers.get('Origin')
        host=self.headers.get('Host')
        if origin and origin not in ('http://'+host,'http://127.0.0.1:'+str(self.server.server_port)):
            self.send(403,{'error':'请求来源不匹配'});return
        try:
            size=int(self.headers.get('Content-Length','0'))
            limit=MAX_IMAGE if self.path=='/api/upload' else 1024*1024
            if size<0 or size>limit:raise ValueError('请求内容太大')
            body=self.rfile.read(size)
            if self.path=='/api/upload':self.send(201,{'url':archive.upload(body)})
            elif self.path=='/api/records':self.send(201,archive.submit(json.loads(body)))
            elif self.path=='/api/refresh':self.send(200,archive.refresh())
            else:self.send(404,{'error':'接口不存在'})
        except (ValueError,TypeError,KeyError) as e:self.send(400,{'error':str(e)})

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',default=str(ROOT/'config.local.json'))
    parser.add_argument('--source')
    parser.add_argument('--data')
    parser.add_argument('--port',type=int)
    args=parser.parse_args()
    config_path=Path(args.config).resolve()
    config=json.loads(config_path.read_text(encoding='utf-8-sig')) if config_path.is_file() else {}
    def resolve(value):
        path=Path(value)
        return path.resolve() if path.is_absolute() else (config_path.parent/path).resolve()
    source=Path(args.source).resolve() if args.source else resolve(config.get('source',str(DEFAULT_SOURCE)))
    data=Path(args.data).resolve() if args.data else resolve(config.get('data','data'))
    # Explicit --source uses that archive's own metadata, not a different local archive's ordering.
    settings=None if args.source else config.get('archive')
    port=args.port or config.get('port',8770)
    archive=Archive(data,source,settings)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.archive=archive
    print(f'FIELD ARCHIVE http://127.0.0.1:{port}/ | {archive.catalog["total"]} questions | {len(archive.catalog["issues"])} import issues',flush=True)
    archive.backup_daily()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
