"""Local, source-labelled retrieval. The caller decides which excerpts to send."""
import math
import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree


def extract(path):
    path = Path(path)
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('Please use a document smaller than 20 MB.')
    extension = path.suffix.lower()
    if extension == '.txt':
        text = path.read_text(encoding='utf-8-sig')
    elif extension == '.docx':
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo('word/document.xml')
            if info.file_size > 30 * 1024 * 1024:
                raise ValueError('Document content is too large.')
            root = ElementTree.fromstring(archive.read(info))
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            text = '\n'.join(''.join(p.itertext()) for p in root.findall('.//w:p', ns))
    elif extension == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError('Use an unencrypted PDF.')
        text = '\n\n'.join(f'[Page {i+1}]\n{page.extract_text() or ""}' for i, page in enumerate(reader.pages))
        if len(re.sub(r'\[Page \d+\]', '', text).strip()) < 30:
            raise ValueError('No readable PDF text. Scanned PDFs need OCR, which is not connected yet.')
    else:
        raise ValueError('Supported documents: TXT, DOCX and text-based PDF.')
    if not text.strip():
        raise ValueError('The document has no readable text.')
    return text


def tokens(text):
    stop={'the','a','an','and','or','of','to','in','on','for','with','is','are','was','were','be','been','your','you','my','i','me','we','our','it','this','that','what','which','how','why','tell','about','can','could','would','please','project','projects'}
    return [word for word in re.findall(r'[a-z0-9+#]+', text.lower()) if word not in stop]


def retrieve(question, documents, limit=5):
    """Rebuild from the current edited documents, preventing stale resume context."""
    chunks = []
    for kind, text in documents.items():
        paragraphs = re.split(r'\n\s*\n', text.strip())
        index = 0
        file_heading = ''
        for paragraph in paragraphs:
            if kind.startswith('GitHub ') and paragraph.startswith('FILE '):file_heading=paragraph.split('\n',1)[0]
            for offset in range(0, len(paragraph), 900):
                part = paragraph[offset:offset+1000].strip()
                if part:
                    if file_heading and not part.startswith(file_heading):part=file_heading+'\n'+part
                    index += 1
                    chunks.append((kind, index, part, tokens(part)))
    query = set(tokens(question))
    if not chunks or not query:
        return []
    average = sum(len(c[3]) for c in chunks) / len(chunks)
    document_frequencies = Counter()
    for _, _, _, words in chunks:
        document_frequencies.update(set(words))
    ranked = []
    for kind, index, text, words in chunks:
        frequencies = Counter(words)
        score = 0.0
        for token in query:
            frequency = frequencies[token]
            if not frequency:
                continue
            df = document_frequencies[token]
            idf = math.log(1 + (len(chunks)-df+0.5)/(df+0.5))
            score += idf * frequency * 2.2 / (frequency + 1.2*(0.25+0.75*len(words)/max(1, average)))
        if score:
            ranked.append({'source': kind, 'section': index, 'text': text, 'score': score})
    return sorted(ranked, key=lambda c: c['score'], reverse=True)[:limit]


def utf8_limit(text, budget):
    text=re.sub(r'[\x00-\x08\x0b-\x1f]', ' ', text)
    return text.encode('utf-8')[:budget].decode('utf-8', errors='ignore')


def coverage(text, budget):
    """Keep normal documents whole; sample across long documents, including the end."""
    if len(text.encode('utf-8'))<=budget:return text
    parts=[p.strip() for p in re.split(r'\n\s*\n|(?=\n[^\n]{3,70}\n)',text) if p.strip()]
    if len(parts)<4:
        parts=[text[i:i+800] for i in range(0,len(text),800)]
    count=min(len(parts),24)
    indices=sorted({round(i*(len(parts)-1)/max(1,count-1)) for i in range(count)})
    amount=max(50,(budget-80)//max(1,len(indices)))
    return utf8_limit('\n[Document overview, distributed across all sections]\n'+'\n…\n'.join(utf8_limit(parts[i],amount) for i in indices),budget)


def evidence(question, documents, budget, limit, preferred=()):
    ranked=retrieve(question,documents,limit=100)
    if preferred:
        ranked.sort(key=lambda row: row["score"] * (1.5 if row["source"] in preferred else 1), reverse=True)
    chosen=[];seen=set()
    for row in ranked:
        if row['source'] not in seen:
            chosen.append(row);seen.add(row['source'])
        if len(chosen)>=limit:break
    for row in ranked:
        if len(chosen)>=limit:break
        if row not in chosen:chosen.append(row)
    allowance=max(150,budget//max(1,len(chosen))-120)
    return [{'source':x['source'],'section':x['section'],'text':utf8_limit(x['text'],allowance)} for x in chosen]


def answer_context(question,documents,history=(),session_memory=()):
    """A byte-bounded, source-separated view of current evidence. No prefix-only fallback."""
    import json
    resume=documents.get('Resume','')
    jd=documents.get('Job description','')
    projects={k:v for k,v in documents.items() if k.startswith('GitHub ')}
    query=question
    if re.search(r'\b(that|this|it|same|previous)\b',question,re.I):
        query+=' '+ ' '.join(history[-2:])[-600:]
    # Explicit names get a boost, while a generic word such as "model"
    # cannot exclude more relevant implementation evidence from other repos.
    preferred = set()
    for source in projects:
        slug = source.rsplit('/', 1)[-1]
        name = r'[-_\s]+'.join(re.escape(part) for part in re.split(r'[-_]+', slug))
        if re.search(r'(?<!\w)(?:' + (name if '-' in slug or '_' in slug else r'(?:project|repo(?:sitory)?)\s+' + name) + r')(?!\w)', query, re.I):
            preferred.add(source)
    result={
        'current_turn':utf8_limit(question,1600),
        'earlier_heard_evidence':evidence(query,{f'Heard turn {i+1}':t for i,t in enumerate(history[:-3])},1400,2),
        'earlier_suggestion_evidence':evidence(query,{f'Unverified suggested answer {i+1}':t['question']+'\n'+t['suggested_answer'] for i,t in enumerate(session_memory[:-2])},1000,2),
        'resume_overview':coverage(resume,7000),
        'role_requirements':coverage(jd,3800),
        'resume_evidence':evidence(query,{'Resume':resume},2300,3),
        'role_evidence':evidence(query,{'Job description':jd},1800,3),
        'project_catalog':[{'source':k,'overview':utf8_limit(v,300)} for k,v in projects.items()],
        'repository_evidence':evidence(query, projects, 6200 if preferred else 4200, 5 if preferred else 4, preferred),
        'recent_heard_turns':[utf8_limit(t,450) for t in history[-3:]],
        'recent_suggestions_not_spoken':[{'question':utf8_limit(t['question'],200),'suggested_answer':utf8_limit(t['suggested_answer'],500)} for t in session_memory[-2:]],
    }
    # Preserve all source groups even in pathological Unicode/escaped text.
    while len(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode('utf-8'))>26000:
        if result['recent_suggestions_not_spoken']:result['recent_suggestions_not_spoken'].pop(0)
        elif result['recent_heard_turns']:result['recent_heard_turns'].pop(0)
        else:
            choices=[(result,'resume_overview'),(result,'role_requirements')]
            for field in ('resume_evidence','role_evidence','repository_evidence','earlier_heard_evidence','earlier_suggestion_evidence'):
                choices.extend((row,'text') for row in result[field])
            choices.extend((row,'overview') for row in result['project_catalog'])
            parent,key=max(choices,key=lambda pair:len(pair[0][pair[1]].encode('utf-8')))
            current=parent[key]
            if not current:raise ValueError('Context source framing exceeds its byte budget.')
            parent[key]=utf8_limit(current,max(0,len(current.encode('utf-8'))-300))
    return result
