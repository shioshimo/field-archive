"""Read subject archives without altering source files."""
import hashlib
import json
import re
from pathlib import Path

QUESTION_FILES=('question.json','question.md','题目与答案.md')

def parts(markdown):
    matches=list(re.finditer(r'^##\s+(.+?)\s*$',markdown,re.M))
    return {m[1].strip():markdown[m.end():matches[i+1].start() if i+1<len(matches) else len(markdown)].strip() for i,m in enumerate(matches)}

def metadata(root,override=None):
    path=Path(root)/'archive.json'
    value=json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}
    if not isinstance(value,dict):raise ValueError('archive.json 必须是 JSON 对象')
    value.update(override or {})
    value.setdefault('id',Path(root).name);value.setdefault('subject',Path(root).name);value.setdefault('code','STUDY');value.setdefault('chapters',[])
    if not all(isinstance(value[k],str) and value[k] for k in ('id','subject','code')):raise ValueError('题库 id、subject、code 必须是非空文字')
    if not isinstance(value['chapters'],list):raise ValueError('chapters 必须是数组')
    chapter_names=set();chapter_numbers=set()
    for i,ch in enumerate(value['chapters'],1):
        if not isinstance(ch,dict) or not isinstance(ch.get('name'),str):raise ValueError('章节需要 name')
        ch=dict(ch);value['chapters'][i-1]=ch;ch.setdefault('number',i);ch.setdefault('sections',[])
        if not isinstance(ch['number'],int) or ch['number']<1 or ch['name'] in chapter_names or ch['number'] in chapter_numbers:raise ValueError('章节名称、编号须唯一且编号为正整数')
        chapter_names.add(ch['name']);chapter_numbers.add(ch['number'])
        seen_names=set();seen_numbers=set()
        for j,s in enumerate(ch['sections'],1):
            s={'name':s} if isinstance(s,str) else dict(s)
            s.setdefault('number',j);ch['sections'][j-1]=s
            if not isinstance(s.get('name'),str) or not isinstance(s['number'],int) or s['number']<1 or s['name'] in seen_names or s['number'] in seen_numbers:raise ValueError('小节名称、编号须唯一且编号为正整数')
            seen_names.add(s['name']);seen_numbers.add(s['number'])
    return value

def raw_question(path,root):
    raw=path.read_text(encoding='utf-8-sig');relative=path.relative_to(root)
    if path.suffix=='.json':
        q=json.loads(raw)
        if not isinstance(q,dict):raise ValueError('question.json 必须是 JSON 对象')
        for name in ('stem','answer'):
            if not isinstance(q.get(name),str) or not q[name].strip():raise ValueError('缺少 '+name)
        for name in ('explanation','reference','diagnostic','title'):
            if name in q and not isinstance(q[name],str):raise ValueError(name+' 必须是文字')
        options=q.get('options',[])
        if not isinstance(options,list):raise ValueError('options 必须是数组')
        labels=[]
        for option in options:
            if not isinstance(option,dict) or not isinstance(option.get('label'),str) or not re.fullmatch('[A-Z]',option['label']) or not isinstance(option.get('markdown'),str):raise ValueError('选项需 label（A–Z）和 markdown')
            labels.append(option['label'])
        if len(set(labels))!=len(labels):raise ValueError('选项标签重复')
        if 'id' in q and (not isinstance(q['id'],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,119}',q['id'])):raise ValueError('id 只能使用字母、数字、点、下划线和短横线，最多120字')
        q=q|{'options':options}
    else:
        blocks=parts(raw)
        def block(*names):return next((blocks[n] for n in names if n in blocks),'')
        stem=block('题目描述','题目','Question');answer=block('参考答案','答案','Answer')
        if not stem or not answer:raise ValueError('缺少题目描述或参考答案')
        options=[]
        option_matches=list(re.finditer(r'^\s*(?:[-*]\s*)?([A-Z])[.．、]\s*',stem,re.M))
        # Roman-numeral statements before option A are part of the question, not choices.
        first_a=next((m.start() for m in option_matches if m[1]=='A'),None)
        option_matches=[m for m in option_matches if first_a is not None and m.start()>=first_a]
        info=block('题目信息','Metadata');type_match=re.search(r'题型[^：:]*[：:]\s*(.+)',info)
        kind=type_match[1].replace('**','').strip() if type_match else ('综合应用题' if '综合' in path.parent.name else '单项选择题' if option_matches else '问答题')
        if '选择' in kind:
            if len(option_matches)<2 or [m[1] for m in option_matches]!=list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')[:len(option_matches)]:raise ValueError('无法唯一切分选项，保留原文件待确认')
            for i,m in enumerate(option_matches):
                end=option_matches[i+1].start() if i+1<len(option_matches) else len(stem)
                options.append({'label':m[1],'markdown':stem[m.end():end].strip()})
            stem=re.sub(r'\n###\s*(?:选项|Options)\s*$','',stem[:option_matches[0].start()].rstrip()).strip()
        title=re.search(r'^#\s+(.+)',raw,re.M);diagnostic=path.parent/'诊断报告.md'
        q={'stem':stem,'options':options,'answer':answer,'explanation':block('详细解析','解析','Explanation'),
           'reference':block('原书图表与页面对照','参考资料','Reference'),'diagnostic':diagnostic.read_text(encoding='utf-8-sig') if diagnostic.is_file() else '',
           'type':kind,'title':title[1] if title else path.parent.name}
    q.setdefault('chapter',relative.parts[0] if len(relative.parts)>=3 else '未分章')
    q.setdefault('section',relative.parts[1] if len(relative.parts)>=3 else '未分节')
    if not all(isinstance(q[k],str) and q[k] for k in ('chapter','section')):raise ValueError('chapter、section 必须是非空文字')
    folder_number=re.search(r'\d+',path.parent.name);q.setdefault('number',int(folder_number[0]) if folder_number else 1)
    if not isinstance(q['number'],int) or q['number']<1:raise ValueError('number 必须是正整数')
    q.setdefault('type','单项选择题' if q['options'] else '问答题')
    if not isinstance(q['type'],str) or not q['type']:raise ValueError('type 必须是非空文字')
    q.setdefault('title',path.parent.name);q['sourceFile']=relative.as_posix();q['sourceDir']=relative.parent.as_posix()
    q['sourceHash']=hashlib.sha256(raw.encode()).hexdigest();q['warnings']=[]
    image_text=raw if path.suffix!='.json' else '\n'.join(q.get(k,'') for k in ('stem','answer','explanation','reference','diagnostic'))+'\n'+'\n'.join(o['markdown'] for o in q['options'])
    for ref in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',image_text):
        if re.match(r'https?://',ref):continue
        ref=ref.split(' "')[0].strip('<>');image=(path.parent/ref).resolve()
        if not image.is_relative_to(root) or not image.is_file():q['warnings'].append('图片引用不存在或超出题库：'+ref)
    for key in ('explanation','reference','diagnostic'):q.setdefault(key,'')
    return q

def scan(root,override=None):
    root=Path(root).resolve();settings=metadata(root,override);questions=[];issues=[]
    for path in sorted(p for p in root.rglob('*') if p.name in QUESTION_FILES):
        try:questions.append(raw_question(path,root))
        except (ValueError,OSError,IndexError,TypeError) as e:issues.append({'file':path.relative_to(root).as_posix(),'reason':str(e)})
    configured={c['name']:c for c in settings['chapters']}
    unknown=sorted({q['chapter'] for q in questions}-configured.keys());next_ch=max((c['number'] for c in configured.values()),default=0)+1
    for i,name in enumerate(unknown):configured[name]={'name':name,'number':next_ch+i,'sections':[]}
    section_maps={}
    for name,ch in configured.items():
        section_map={s['name']:s['number'] for s in ch['sections']}
        unknown_sections=sorted({q['section'] for q in questions if q['chapter']==name}-section_map.keys());next_sec=max(section_map.values(),default=0)+1
        section_map.update({s:next_sec+i for i,s in enumerate(unknown_sections)});section_maps[name]=section_map
    seen=set();valid=[]
    for q in questions:
        q['chapterNumber']=configured[q['chapter']]['number'];q['sectionNumber']=section_maps[q['chapter']][q['section']];q['sectionId']=f"{q['chapterNumber']}.{q['sectionNumber']}"
        if 'id' not in q:
            digest=hashlib.sha256(q['sourceFile'].encode()).hexdigest()[:8]
            if settings.get('legacyIdPrefix'):q['id']=f"{settings['legacyIdPrefix']}-{q['chapterNumber']:02d}-{q['sectionNumber']:02d}-{('c' if q['type']=='综合应用题' else 'q')}{q['number']:03d}-{digest}"
            else:q['id']='field-'+hashlib.sha256(settings['id'].encode()).hexdigest()[:8]+'-'+digest
        if q['id'] in seen:issues.append({'file':q['sourceFile'],'reason':'题目 id 重复：'+q['id']});continue
        seen.add(q['id']);valid.append(q)
    valid.sort(key=lambda q:(q['chapterNumber'],q['sectionNumber'],bool(not q['options']),q['number'],q['id']))
    return valid,issues

def build_catalog(questions,issues,settings=None):
    settings=settings or {};chapters=[]
    for number in sorted({q['chapterNumber'] for q in questions}):
        grouped=[q for q in questions if q['chapterNumber']==number];name=grouped[0]['chapter']
        configured=next((c for c in settings.get('chapters',[]) if c['name']==name),{});sections=[]
        for sid in dict.fromkeys(q['sectionId'] for q in grouped):
            members=[q for q in grouped if q['sectionId']==sid];sections.append({'id':sid,'name':members[0]['section'],'count':len(members)})
        chapters.append({'number':number,'name':name,'shortName':configured.get('shortName',name[:4]),'count':len(grouped),'sections':sections})
    summaries=[{k:q[k] for k in ('id','chapter','chapterNumber','section','sectionId','number','type','title','sourceFile')}|{'search':re.sub(r'\s+',' ',q['stem'])[:1000]} for q in questions]
    return {'schemaVersion':1,'total':len(questions),'chapters':chapters,'questions':summaries,'issues':issues,'archive':{k:settings.get(k,'') for k in ('id','subject','code')},'types':list(dict.fromkeys(q['type'] for q in questions))}
