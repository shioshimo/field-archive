"""Small AI-friendly CLI. No UI code or database edits required."""
import argparse
import json
import sys
import urllib.request
import urllib.error
import uuid
from pathlib import Path
from urllib.parse import quote

def request(base,route,payload=None,blob=None):
    body=blob if blob is not None else json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
    req=urllib.request.Request(base.rstrip('/')+route,data=body,headers={'Content-Type':'application/octet-stream' if blob is not None else 'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
    except urllib.error.HTTPError as e:
        raise ValueError(json.load(e).get('error',str(e)))

def submit_record(base,question,state,note,image_paths=(),selected_option=None,request_id=None):
    blobs=[Path(p).read_bytes() for p in image_paths]
    if request_id:
        history=request(base,'/api/records?questionId='+quote(question))
        existing=next((r for r in history if r['requestId']==request_id),None)
        if existing:
            same=(existing['state']==state and existing['note']==note
                  and existing['selectedOption']==selected_option
                  and len(existing['images'])==len(blobs))
            if same:
                for url,blob in zip(existing['images'],blobs):
                    with urllib.request.urlopen(base.rstrip('/')+url,timeout=30) as response:
                        if response.read()!=blob:
                            same=False;break
            if not same:raise ValueError('这个 requestId 已用于另一份记录')
            return existing
    images=[request(base,'/api/upload',blob=blob)['url'] for blob in blobs]
    payload={'questionId':question,'state':state,'note':note,'images':images,
             'selectedOption':selected_option,'requestId':request_id or str(uuid.uuid4())}
    return request(base,'/api/records',payload)

def main():
    parser=argparse.ArgumentParser(description='给 Field Archive 添加一次独立的做题记录')
    parser.add_argument('--base',default='http://127.0.0.1:8770')
    parser.add_argument('--list',action='store_true',help='列出题号、ID、源文件路径')
    parser.add_argument('--section',help='例如 2.1')
    parser.add_argument('--question',help='catalog.json 中的稳定题目 ID')
    parser.add_argument('--state',choices=['未做过','做错了','做对了'])
    parser.add_argument('--note',default='')
    parser.add_argument('--note-file',type=Path,help='UTF-8 Markdown 笔记文件')
    parser.add_argument('--image',action='append',type=Path,default=[])
    parser.add_argument('--selected-option',choices=list('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
    parser.add_argument('--request-id',help='重试时复用同一个值，防止重复提交')
    parser.add_argument('--history',action='store_true')
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    if args.refresh:result=request(args.base,'/api/refresh',{})
    elif args.list:
        catalog=request(args.base,'/api/catalog')
        result=[{'id':q['id'],'section':q['sectionId'],'number':q['number'],'type':q['type'],'path':str(Path(catalog['sourceRoot'])/q['sourceFile'])} for q in catalog['questions'] if not args.section or q['sectionId']==args.section]
    elif args.history:
        if not args.question:parser.error('--history 需要 --question')
        result=request(args.base,'/api/records?questionId='+quote(args.question))
    else:
        if not args.question or not args.state:parser.error('提交需要 --question 和 --state；也可用 --list 查询')
        note=args.note_file.read_text(encoding='utf-8-sig') if args.note_file else args.note
        result=submit_record(args.base,args.question,args.state,note,args.image,args.selected_option,args.request_id)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,urllib.error.URLError) as e:
        print('没有完成：'+str(e),file=sys.stderr);sys.exit(1)
