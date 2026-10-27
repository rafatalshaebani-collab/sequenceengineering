#!/usr/bin/env python3
"""Apply only deterministic, approved SEO additions. Never removes or rewrites content."""
from __future__ import annotations
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
BASE='https://sequenceengineering.com.au'
PAGES=[p for p in ROOT.rglob('*.html') if '.git' not in p.parts and p.name not in {'404.html','500.html'}]

class HeadParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.has_canonical=False; self.has_robots=False; self.head_end=False
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='link' and a.get('rel')=='canonical': self.has_canonical=True
        if tag=='meta' and a.get('name','').lower()=='robots': self.has_robots=True
    def handle_endtag(self, tag):
        if tag=='head': self.head_end=True

def canonical_for(path):
    rel=path.relative_to(ROOT).as_posix()
    return BASE+'/' if rel=='index.html' else BASE+'/'+rel.removesuffix('.html')

def add_safe_metadata(path):
    text=path.read_text(encoding='utf-8',errors='ignore')
    parser=HeadParser(); parser.feed(text)
    additions=[]
    if not parser.has_canonical and '</head>' in text.lower():
        tag=f'  <link rel="canonical" href="{canonical_for(path)}">\n'
        text=re.sub(r'</head>', tag+'</head>', text, count=1, flags=re.I)
        additions.append('canonical')
    if not parser.has_robots and '</head>' in text.lower():
        tag='  <meta name="robots" content="index, follow">\n'
        text=re.sub(r'</head>', tag+'</head>', text, count=1, flags=re.I)
        additions.append('robots')
    if additions:
        path.write_text(text,encoding='utf-8')
    return additions

def main():
    changed=[]
    for path in sorted(PAGES):
        additions=add_safe_metadata(path)
        if additions: changed.append((path.relative_to(ROOT).as_posix(), additions))
    report=ROOT/'reports/optimizer-changes.md'
    lines=['# Safe SEO Optimizer Changes','',f'Generated: {date.today().isoformat()}','', 'Only deterministic metadata additions were allowed. Existing page copy, CSS, links, and URLs were not rewritten.', '']
    if changed:
        for file, additions in changed: lines.append(f'- `{file}`: added '+', '.join(additions))
    else:
        lines.append('- No safe additions were needed.')
    report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Files changed: {len(changed)}')
    for file, additions in changed: print(file, ','.join(additions))
if __name__=='__main__': main()
