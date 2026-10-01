import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Archive,Handler,ThreadingHTTPServer
from importer import scan,metadata
from record import submit_record

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.source=self.root/'source'
        self.fixture=self.source/'数据的表示和运算/数制与编码/第4题/题目与答案.md'
        self.fixture.parent.mkdir(parents=True)
        self.fixture.write_text('# 2.1 数制与编码 - 第4题\n\n## 题目信息\n- **题型**：单项选择题\n\n## 题目描述\n对真值 0 表示唯一的是？\n\n### 选项\n- A. 原码\n- B. 补码\n- C. 反码\n- D. 以上都不对\n\n## 参考答案\n**B**\n\n## 详细解析\n$0$ 有唯一表示。\n',encoding='utf-8')
        self.archive=Archive(self.root/'data',self.source)
        self.qid=self.archive.catalog['questions'][0]['id']
    def tearDown(self):self.temp.cleanup()
    def payload(self,**values):return {'questionId':self.qid,'state':'做错了','note':'记录 $a+b$','images':[],'selectedOption':'A','requestId':'test-request'}|values

    def test_parse_and_stable_id(self):
        q=self.archive.question(self.qid)
        self.assertEqual([o['label'] for o in q['options']],list('ABCD'))
        self.assertNotIn('A. 原码',q['stem'])
        self.assertIn('$0$',q['explanation'])
        self.fixture.write_text(self.fixture.read_text(encoding='utf-8').replace('对真值','对于真值'),encoding='utf-8')
        self.archive.refresh()
        self.assertEqual(self.archive.catalog['questions'][0]['id'],self.qid)

    def test_history_restart_and_refresh(self):
        a=self.archive.submit(self.payload())
        b=self.archive.submit(self.payload(state='做对了',requestId='second'))
        restarted=Archive(self.archive.data,self.source)
        self.assertEqual([r['id'] for r in restarted.records(self.qid)],[a['id'],b['id']])
        self.assertEqual(restarted.progress()[self.qid]['state'],'做对了')
        self.assertEqual(restarted.progress()[self.qid]['attempts'],2)

    def test_idempotency_and_reused_id_conflict(self):
        a=self.archive.submit(self.payload())
        self.assertEqual(self.archive.submit(self.payload())['id'],a['id'])
        with self.assertRaises(ValueError):self.archive.submit(self.payload(note='不同内容'))
        self.assertEqual(len(self.archive.records(self.qid)),1)

    def test_roman_numeral_statements_are_not_options(self):
        raw=self.fixture.read_text(encoding='utf-8').replace('对真值 0 表示唯一的是？','对真值 0 表示唯一的是？\nI. 条件一\nII. 条件二')
        self.fixture.write_text(raw,encoding='utf-8')
        self.archive.refresh()
        question=self.archive.question(self.qid)
        self.assertIn('I. 条件一',question['stem'])
        self.assertEqual([o['label'] for o in question['options']],list('ABCD'))

    def test_invalid_input_no_partial_records(self):
        for change in [{'state':'错误状态'},{'images':['/media/../../server.py']},{'selectedOption':'E'},{'note':3}]:
            with self.assertRaises(ValueError):self.archive.submit(self.payload(**change))
        self.assertEqual(self.archive.records(self.qid),[])

    def test_image_and_backup(self):
        buffer=io.BytesIO();Image.new('RGB',(10,10),(160,150,140)).save(buffer,format='PNG')
        url=self.archive.upload(buffer.getvalue())
        self.archive.submit(self.payload(images=[url]))
        with zipfile.ZipFile(io.BytesIO(self.archive.export_zip())) as backup:
            self.assertEqual(backup.read(url.lstrip('/')),buffer.getvalue())
            self.assertEqual(json.loads(backup.read('records.json'))['records'][0]['images'],[url])
        with self.assertRaises(ValueError):self.archive.upload(b'not an image')
        self.assertTrue(list((self.archive.data/'backups').glob('*.sqlite3')))

    def test_concurrent_append(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda n:self.archive.submit(self.payload(requestId='thread-'+str(n))),range(8)))
        self.assertEqual(len({r['id'] for r in results}),8)
        self.assertEqual(len(self.archive.records(self.qid)),8)

    def test_temporarily_invalid_source_preserves_data_and_records(self):
        self.archive.submit(self.payload())
        other=self.source/'数据的表示和运算/数制与编码/第5题/题目与答案.md'
        other.parent.mkdir();other.write_text(self.fixture.read_text(encoding='utf-8'),encoding='utf-8')
        self.fixture.write_text('# 编辑中',encoding='utf-8')
        result=self.archive.refresh()
        self.assertEqual(result['total'],2)
        self.assertEqual(len(result['issues']),1)
        self.assertEqual(len(self.archive.records(self.qid)),1)

    def test_http_contract_and_path_boundary(self):
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler);http.archive=self.archive
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(http.server_port)
        try:
            with urllib.request.urlopen(base+'/api/questions/'+self.qid) as response:self.assertEqual(json.load(response)['id'],self.qid)
            req=urllib.request.Request(base+'/api/records',data=json.dumps(self.payload()).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req) as response:self.assertEqual(json.load(response)['questionId'],self.qid)
            for route in ['/source/%2e%2e/server.py','/media/%2e%2e/archive.sqlite3']:
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(base+route)
                self.assertEqual(error.exception.code,404)
            req=urllib.request.Request(base+'/api/records',data=json.dumps(self.payload(requestId='cross')).encode(),headers={'Origin':'https://another-site.example'})
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
            self.assertEqual(error.exception.code,403)
        finally:http.shutdown();http.server_close();thread.join()

    def test_cli_image_retry_does_not_duplicate_record_or_image(self):
        image=self.root/'note.png'
        Image.new('RGB',(12,12),(170,160,150)).save(image)
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler);http.archive=self.archive
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(http.server_port)
        try:
            first=submit_record(base,self.qid,'做错了','CLI 笔记',[image],'A','cli-retry')
            second=submit_record(base,self.qid,'做错了','CLI 笔记',[image],'A','cli-retry')
            self.assertEqual(first['id'],second['id'])
            self.assertEqual(len(self.archive.records(self.qid)),1)
            self.assertEqual(len(list((self.archive.data/'media').iterdir())),1)
            with self.assertRaises(ValueError):
                submit_record(base,self.qid,'做对了','CLI 笔记',[image],'A','cli-retry')
            Image.new('RGB',(12,12),(20,30,40)).save(image)
            with self.assertRaises(ValueError):
                submit_record(base,self.qid,'做错了','CLI 笔记',[image],'A','cli-retry')
        finally:http.shutdown();http.server_close();thread.join()

class ActualSourceTests(unittest.TestCase):
    def test_all_source_files_import_without_content_rewriting(self):
        project=Path(__file__).resolve().parents[1]
        root=project/'examples/foundations'
        questions,issues=scan(root)
        self.assertEqual(issues,[])
        self.assertEqual(len(questions),6)
        self.assertEqual(len({q['id'] for q in questions}),len(questions))
        self.assertTrue(all(not q['warnings'] for q in questions))
        self.assertEqual({q['chapterNumber'] for q in questions},{1,2,3})
        self.assertEqual(len(next(q for q in questions if q['id']=='demo-code-binary-search')['options']),5)

    def test_explicit_json_id_survives_rename_and_subject_is_configurable(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);question=root/'original/question.json';question.parent.mkdir()
            question.write_text(json.dumps({'id':'chemistry-atom-1','chapter':'原子结构','section':'电子','number':1,'type':'填空题','stem':'电子带什么电？','answer':'负电'}),encoding='utf-8')
            (root/'archive.json').write_text(json.dumps({'id':'chemistry','subject':'化学','code':'CHEM','chapters':[{'name':'原子结构','number':4,'sections':['电子']}]}),encoding='utf-8')
            archive=Archive(root/'data',root)
            self.assertEqual(archive.catalog['archive']['subject'],'化学')
            self.assertEqual(archive.catalog['chapters'][0]['number'],4)
            archive.submit({'questionId':'chemistry-atom-1','state':'做对了','note':'检查','requestId':'chem-attempt'})
            question.parent.rename(root/'renamed')
            archive.refresh()
            self.assertEqual(archive.catalog['questions'][0]['id'],'chemistry-atom-1')
            self.assertEqual(len(archive.records('chemistry-atom-1')),1)

    def test_duplicate_id_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('one','two'):
                p=root/name/'question.json';p.parent.mkdir();p.write_text(json.dumps({'id':'duplicate','stem':'题干','answer':'答案'}),encoding='utf-8')
            questions,issues=scan(root)
            self.assertEqual(len(questions),1)
            self.assertIn('id 重复',issues[0]['reason'])

if __name__=='__main__':unittest.main()
