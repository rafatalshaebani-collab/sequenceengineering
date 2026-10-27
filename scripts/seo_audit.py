#!/usr/bin/env python3
from __future__ import annotations
import json, re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
BASE='https://sequenceengineering.com.au'
PAGES=[p for p in ROOT.rglob('*.html') if '.git' not in p.parts and p.name not in {'404.html','500.html'}]

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.title=''; self.desc=''; self.h1=[]; self.h2=[]; self.links=[]; self.images=[]; self.canonical=''; self.og_title=''; self.og_desc=''; self.schema=0; self._tag=''; self._capture=''
    def handle_starttag(self, tag, attrs):
        a=dict(attrs); self._tag=tag
        if tag=='title': self._capture='title'
        if tag=='meta':
            key=a.get('name') or a.get('property'); val=a.get('content','')
            if key=='description': self.desc=val
            elif key=='og:title': self.og_title=val
            elif key=='og:description': self.og_desc=val
        if tag=='link' and a.get('rel')=='canonical': self.canonical=a.get('href','')
        if tag=='h1': self._capture='h1'
        if tag=='h2': self._capture='h2'
        if tag=='script' and a.get('type')=='application/ld+json': self.schema += 1
        if tag=='a' and a.get('href'): self.links.append(a['href'])
        if tag=='img': self.images.append((a.get('src',''),a.get('alt','')))
    def handle_endtag(self, tag):
        if tag in {'title','h1','h2'}: self._capture=''
        self._tag=''
    def handle_data(self, data):
        text=' '.join(data.split())
        if not text: return
        if self._capture=='title': self.title += text
        elif self._capture=='h1': self.h1.append(text)
        elif self._capture=='h2': self.h2.append(text)

def page_url(path):
    rel=path.relative_to(ROOT).as_posix()
    if rel=='index.html': return BASE+'/'
    return BASE+'/'+rel.removesuffix('.html')

def audit(path):
    p=Parser(); p.feed(path.read_text(encoding='utf-8',errors='ignore'))
    issues=[]; notes=[]
    if not p.title: issues.append('Missing title')
    elif not 30 <= len(p.title) <= 65: issues.append(f'Title length {len(p.title)} (target 30-65)')
    if not p.desc: issues.append('Missing meta description')
    elif not 120 <= len(p.desc) <= 170: issues.append(f'Description length {len(p.desc)} (target 120-170)')
    if len(p.h1)!=1: issues.append(f'Expected 1 H1, found {len(p.h1)}')
    if not p.canonical: issues.append('Missing canonical')
    if not p.og_title or not p.og_desc: issues.append('Incomplete Open Graph metadata')
    if p.schema==0: issues.append('No JSON-LD structured data found')
    missing_alt=sum(1 for _,alt in p.images if not alt.strip())
    if missing_alt: issues.append(f'{missing_alt} image(s) missing alt text')
    local_links=sum(1 for href in p.links if href.startswith('/') or href.startswith(BASE))
    if local_links < 2: notes.append('Add more relevant internal links')
    return {'file':path.relative_to(ROOT).as_posix(),'url':page_url(path),'title':p.title,'description':p.desc,'h1':p.h1,'h2_count':len(p.h2),'schema_blocks':p.schema,'images':len(p.images),'internal_links':local_links,'issues':issues,'notes':notes}

def main():
    results=[audit(p) for p in sorted(PAGES)]
    total_issues=sum(len(r['issues']) for r in results)
    out=ROOT/'reports/seo-audit-latest.md'
    lines=[f'# Sequence Engineering SEO / AEO / GEO Audit', '', f'Generated: {date.today().isoformat()}', '', 'This is a review report. It does not change or publish site content.', '', '## Summary', '', f'- Pages checked: {len(results)}', f'- Issues found: {total_issues}', f'- Pages with no issues: {sum(not r["issues"] for r in results)}', '', '## Page checks', '']
    for r in results:
        lines += [f'### [{r["file"]}]({r["url"]})', '', f'- Title: `{r["title"] or "MISSING"}`', f'- Description: `{r["description"][:180] or "MISSING"}`', f'- H1 count: {len(r["h1"])}', f'- JSON-LD blocks: {r["schema_blocks"]}', f'- Images / internal links: {r["images"]} / {r["internal_links"]}']
        if r['issues']: lines += ['- Issues: ' + '; '.join(r['issues'])]
        if r['notes']: lines += ['- Opportunities: ' + '; '.join(r['notes'])]
        if not r['issues'] and not r['notes']: lines += ['- Status: baseline checks passed']
        lines += ['']
    lines += ['## AEO/GEO review queue', '', '- Add concise answer blocks to service pages for high-intent questions.', '- Keep claims specific and evidence-based; do not generate unsupported project, client, or capability claims.', '- Add or refine Service, Organization, Article, BreadcrumbList, and FAQPage JSON-LD only where the visible page content supports it.', '- Strengthen internal links from relevant Insights articles to the matching service pages.', '- Review target keywords in `config/seo_targets.json` quarterly against Search Console data.']
    out.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (ROOT/'reports/seo-audit-latest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Checked {len(results)} pages; found {total_issues} issue(s).')
    print(out)
if __name__=='__main__': main()
