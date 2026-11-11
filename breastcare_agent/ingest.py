"""Local document ingestion. No documents are uploaded by this command."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

SOURCES = [
 ('NCI: Breast Cancer Treatment PDQ (health professional)', 'https://www.cancer.gov/types/breast/hp/breast-treatment-pdq'),
 ('NCI: Breast Cancer Biomarker Tests', 'https://www.cancer.gov/types/breast/diagnosis/breast-cancer-biomarker-tests'),
 ('UCI: WDBC dataset and nuclear feature definitions', 'https://archive.ics.uci.edu/dataset/17/breast-cancer-wisconsin-diagnostic'),
]

def chunks(text, size=1400, overlap=180):
    text = ' '.join(text.split())
    for start in range(0, len(text), size-overlap):
        part = text[start:start+size]
        if len(part) >= 60:
            yield part

def records(title, source, version, pages):
    for page, text in pages:
        for i, piece in enumerate(chunks(text)):
            identity = f'{source}|{version}|{page}|{i}|{piece}'
            yield {'id': 'S'+hashlib.sha256(identity.encode()).hexdigest()[:12],
                   'title': title, 'source': source, 'version': version,
                   'page': page, 'text': piece}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--nci', action='store_true', help='Fetch official NCI and UCI public reference pages')
    parser.add_argument('--manifest', type=Path, help='JSON list of local PDF records: path,title,source,version')
    args = parser.parse_args()
    if not args.nci and not args.manifest:
        parser.error('Use --nci or --manifest FILE')
    path = Path(__file__).resolve().parent / 'corpus.json'
    rows = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    new = []
    replaced = set()
    if args.nci:
        from bs4 import BeautifulSoup
        version = 'Web snapshot UTC ' + datetime.now(timezone.utc).isoformat(timespec='seconds')
        for title, url in SOURCES:
            req = Request(url, headers={'User-Agent': 'BreastCare-Education/1.0'})
            with urlopen(req, timeout=45) as response:
                html = response.read(8_000_001)
            if len(html) > 8_000_000:
                raise ValueError('Source exceeds size limit')
            soup = BeautifulSoup(html, 'html.parser')
            main_node = soup.find('main') or soup.find('article')
            if main_node is None:
                raise ValueError('Cannot identify article: ' + url)
            for node in main_node.select('script,style,nav,header,footer,form'):
                node.decompose()
            content = main_node.get_text(' ', strip=True)
            if len(content) < 500:
                raise ValueError('Article content incomplete: ' + url)
            new.extend(records(title, url, version, [(None, content)]))
            replaced.add(url)
            print('Loaded:', title)
    if args.manifest:
        from pypdf import PdfReader
        manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
        for entry in manifest:
            if not all(entry.get(k) for k in ('path','title','source','version')):
                raise ValueError('Each PDF requires path, title, source and version')
            pdf = (args.manifest.resolve().parent / entry['path']).resolve()
            pages = [(i+1, p.extract_text() or '') for i,p in enumerate(PdfReader(pdf).pages)]
            if not pages or any(len(t.strip()) < 40 for _,t in pages):
                raise ValueError('PDF has blank/image pages; OCR and review before import: '+str(pdf))
            new.extend(records(entry['title'], entry['source'], entry['version'], pages))
            replaced.add(entry['source'])
    rows = [r for r in rows if r['source'] not in replaced] + new
    if not new:
        raise ValueError('No reference text imported')
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)
    print('Ready:', len(rows), 'passages. Review document dates and contents before clinical discussion.')

if __name__ == '__main__':
    main()
