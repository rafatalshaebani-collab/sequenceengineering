#!/usr/bin/env python3
"""Weekly GA4 + Search Console report for Sequence Engineering."""
from __future__ import annotations
import argparse, json, os, sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'config/google_properties.json'

def period(today=None):
    today=today or date.today()
    end=today-timedelta(days=today.weekday()+1)  # previous Sunday
    start=end-timedelta(days=6)
    prev_end=start-timedelta(days=1); prev_start=prev_end-timedelta(days=6)
    return start,end,prev_start,prev_end

def pct(v): return f'{v:.2f}%'
def delta(a,b):
    if b in (None,0): return 'n/a'
    return f'{((a-b)/b*100):+.1f}%'

def dry_report():
    start,end,ps,pe=period()
    return {'mode':'dry-run','period':{'start':str(start),'end':str(end),'previous_start':str(ps),'previous_end':str(pe)},'required_secrets':['GOOGLE_SERVICE_ACCOUNT_JSON','GA4_PROPERTY_ID','GSC_SITE_URL']}

def live_report():
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
    except ImportError as e:
        raise RuntimeError('Install google-auth and requests before live collection') from e
    cfg=json.loads(CONFIG.read_text(encoding='utf-8'))
    raw=os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']
    info=json.loads(raw)
    scopes=['https://www.googleapis.com/auth/analytics.readonly','https://www.googleapis.com/auth/webmasters.readonly']
    creds=service_account.Credentials.from_service_account_info(info,scopes=scopes)
    session=AuthorizedSession(creds)
    start,end,ps,pe=period()
    prop=os.environ.get('GA4_PROPERTY_ID') or cfg.get('ga4_property_id')
    site=os.environ.get('GSC_SITE_URL') or cfg.get('gsc_site_url')
    if not prop or not site: raise RuntimeError('Set GA4_PROPERTY_ID and GSC_SITE_URL')
    def post(url,payload):
        r=session.post(url,json=payload,timeout=60); r.raise_for_status(); return r.json()
    def ga_report(s,e,dimensions,metrics,limit=20):
        return post(f'https://analyticsdata.googleapis.com/v1beta/properties/{prop}:runReport',{'dateRanges':[{'startDate':str(s),'endDate':str(e)}],'dimensions':[{'name':x} for x in dimensions],'metrics':[{'name':x} for x in metrics],'limit':limit,'orderBys':[{'metric':{'metricName':metrics[0]},'desc':True}]})
    def rows(resp):
        out=[]
        for row in resp.get('rows',[]):
            out.append([x.get('value','') for x in row.get('dimensionValues',[])]+[x.get('value','') for x in row.get('metricValues',[])])
        return out
    ga={}
    for s,e,label in [(start,end,'current'),(ps,pe,'previous')]:
        total=ga_report(s,e,[],['activeUsers','sessions','screenPageViews'],1).get('rows',[{}])[0].get('metricValues',[])
        ga[label]={'totals':[float(x.get('value',0)) for x in total]}
    ga['top_pages']=rows(ga_report(start,end,['pagePath'],['screenPageViews'],20))
    ga['sources']=rows(ga_report(start,end,['sessionSourceMedium'],['sessions'],20))
    sc={}
    for s,e,label in [(start,end,'current'),(ps,pe,'previous')]:
        resp=post('https://searchconsole.googleapis.com/webmasters/v3/sites/'+__import__('urllib.parse').parse.quote(site,safe='')+'/searchAnalytics/query',{'startDate':str(s),'endDate':str(e),'dimensions':['query'],'rowLimit':50})
        sc[label]=resp.get('rows',[])
    sc['top_pages']=post('https://searchconsole.googleapis.com/webmasters/v3/sites/'+__import__('urllib.parse').parse.quote(site,safe='')+'/searchAnalytics/query',{'startDate':str(start),'endDate':str(end),'dimensions':['page'],'rowLimit':50}).get('rows',[])
    return {'mode':'live','period':{'start':str(start),'end':str(end),'previous_start':str(ps),'previous_end':str(pe)},'ga4':ga,'search_console':sc}

def markdown(data):
    p=data['period']; lines=['# Sequence Engineering Weekly Google Report','',f"Period: {p['start']} to {p['end']}",f"Previous period: {p['previous_start']} to {p['previous_end']}",'']
    if data['mode']=='dry-run':
        lines += ['## Dry run','', 'The report structure is ready. Add the required Google credentials as GitHub Secrets to collect live data.', '', 'Required secrets:']+[f'- `{x}`' for x in data['required_secrets']]
        return '\n'.join(lines)+'\n'
    cur=data['ga4']['current']['totals']; prev=data['ga4']['previous']['totals']; names=['Active users','Sessions','Page views']
    lines += ['## GA4 overview','', '| Metric | Current | Previous | Change |','|---|---:|---:|---:|']
    for n,a,b in zip(names,cur,prev): lines.append(f'| {n} | {a:,.0f} | {b:,.0f} | {delta(a,b)} |')
    lines += ['', '## Top pages by views','', '| Page | Views |','|---|---:|']
    for r in data['ga4']['top_pages'][:10]: lines.append(f'| `{r[0]}` | {float(r[1]):,.0f} |')
    lines += ['', '## Top Search Console queries','', '| Query | Clicks | Impressions | CTR | Position |','|---|---:|---:|---:|---:|']
    for r in sorted(data['search_console']['current'],key=lambda x:x.get('impressions',0),reverse=True)[:20]: lines.append(f"| {r.get('keys',[''])[0]} | {r.get('clicks',0):.0f} | {r.get('impressions',0):.0f} | {pct(r.get('ctr',0)*100)} | {r.get('position',0):.1f} |")
    opp=[r for r in data['search_console']['current'] if 8<=r.get('position',99)<=20 and r.get('impressions',0)>=10]
    lines += ['', '## SEO opportunities','', 'Queries ranking between positions 8 and 20 with at least 10 impressions are candidates for improved titles, internal links, or answer sections.','']
    for r in sorted(opp,key=lambda x:x.get('impressions',0),reverse=True)[:15]: lines.append(f"- **{r.get('keys',[''])[0]}** — position {r.get('position',0):.1f}, {r.get('impressions',0):.0f} impressions, {pct(r.get('ctr',0)*100)} CTR")
    lines += ['', '## Notes','', '- This report is descriptive and does not modify website files.', '- Recommendations should be reviewed against the current page content before creating a Pull Request.']
    return '\n'.join(lines)+'\n'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dry-run',action='store_true'); args=ap.parse_args()
    data=dry_report() if args.dry_run else live_report()
    (ROOT/'reports/google-weekly-latest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'reports/google-weekly-latest.md').write_text(markdown(data),encoding='utf-8')
    print(f"Generated {data['mode']} Google report for {data['period']['start']} to {data['period']['end']}")
if __name__=='__main__': main()
