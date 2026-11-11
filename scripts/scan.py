#!/usr/bin/env python3
"""INU TV V3.9.1: bounded IPTV source discovery and rotating ffprobe scan."""
import argparse
import concurrent.futures
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import tempfile
import urllib.request
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
SOURCES = [('Indonesia','id'),('Malaysia','my'),('Singapura','sg'),('Amerika Serikat','us'),('Jepang','jp'),('Korea Selatan','kr'),('Thailand','th'),('Filipina','ph'),('India','in'),('Inggris','uk'),('Australia','au')]
MAX_SOURCES = 3

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent':'INU-TV-Scanner/3.9.1','Accept':'*/*'})
    with urllib.request.urlopen(req, timeout=25) as res:
        return res.read(12_000_000).decode('utf-8','replace')

def parse(text, country):
    result, meta = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('#EXTINF:'):
            attrs = dict(re.findall(r'([\w-]+)="([^"]*)"',line))
            meta = {'name':line.rsplit(',',1)[-1].strip() or attrs.get('tvg-name','Tanpa Nama'), 'country':country, 'tvgId':attrs.get('tvg-id',''), 'group':attrs.get('group-title',''), 'logo':attrs.get('tvg-logo','')}
        elif meta and line and not line.startswith('#'):
            if re.match(r'^https?://',line,re.I):
                result.append({**meta,'url':line})
            meta = None
    return result

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf8'))
    except (FileNotFoundError, ValueError):
        return default

def write_json(path, data):
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix='.scan-', suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2)
            f.write('\n')
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def probe(item, timeout):
    cmd=['ffprobe','-v','error','-rw_timeout',str(timeout*1000000),'-analyzeduration','3000000','-probesize','1500000','-show_entries','stream=codec_type,codec_name','-of','json',item['url']]
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout+3)
        if p.returncode==0:
            streams=json.loads(p.stdout or '{}').get('streams',[])
            video=[s for s in streams if s.get('codec_type')=='video']
            if video: return 'ok','ffprobe mendeteksi stream video',video[0].get('codec_name','')
            return 'fail','Tidak ditemukan stream video',''
        return 'fail',(p.stderr or 'ffprobe gagal').strip()[-180:],''
    except subprocess.TimeoutExpired: return 'fail','Timeout ffprobe',''
    except (OSError,ValueError) as exc: return 'fail',str(exc)[:180],''

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--batch',type=int,default=200)
    ap.add_argument('--timeout',type=int,default=12)
    ap.add_argument('--workers',type=int,default=4)
    args=ap.parse_args()
    if not 1<=args.batch<=1000 or not 1<=args.workers<=8 or args.timeout<1:
        ap.error('invalid batch/workers/timeout')
    previous=load_json(DATA/'scan-results.json',{})
    results=previous.get('results',{}) if isinstance(previous,dict) else {}
    if not isinstance(results,dict): results={}
    old_data=load_json(DATA/'channels.json',{})
    old_catalog=old_data.get('channels',[]) if isinstance(old_data,dict) else []
    catalog=[]
    seen=set()
    counts=Counter()
    source_errors=[]
    metrics=Counter()

    def add(ch, source):
        if not isinstance(ch,dict): return False
        url=ch.get('url','')
        if not isinstance(url,str) or not re.match(r'^https?://',url,re.I) or url in seen:
            return False
        cid=ch.get('tvgId','')
        cid=cid.strip().lower() if isinstance(cid,str) else ''
        if cid and counts[cid]>=MAX_SOURCES:
            metrics['limit_skipped']+=1
            return False
        catalog.append(ch)
        seen.add(url)
        if cid: counts[cid]+=1
        metrics[source]+=1
        return True

    # Preserve existing URLs first, so a discovery refresh cannot displace working sources.
    for ch in old_catalog:
        add(ch,'preserved')

    for country,code in SOURCES:
        try:
            for ch in parse(fetch(f'https://iptv-org.github.io/iptv/countries/{code}.m3u'),country):
                add(ch,'playlist_added')
        except Exception as exc:
            source_errors.append(f'{country}: {str(exc)[:160]}')

    # Match only exact tvg-id. No fuzzy name matching or header-restricted streams.
    by_id={}
    for ch in catalog:
        cid=ch.get('tvgId','')
        if isinstance(cid,str) and cid.strip():
            by_id.setdefault(cid.strip().lower(),ch)
    try:
        api=json.loads(fetch('https://iptv-org.github.io/api/streams.json'))
        if not isinstance(api,list): raise ValueError('API response is not a list')
        metrics['api_entries']=len(api)
        for entry in api:
            if not isinstance(entry,dict): continue
            cid=entry.get('channel') or ''
            cid=cid.strip().lower() if isinstance(cid,str) else ''
            url=entry.get('url') or ''
            if not cid or cid not in by_id: continue
            if entry.get('referrer') or entry.get('user_agent'):
                metrics['header_skipped']+=1
                continue
            add({**by_id[cid],'url':url},'api_added')
    except Exception as exc:
        source_errors.append('API alternatif: '+str(exc)[:160])

    if not catalog:
        raise SystemExit('No playlist data available; refusing to overwrite results')

    multi=Counter(ch.get('tvgId','').strip().lower() for ch in catalog if isinstance(ch.get('tvgId'),str) and ch['tvgId'].strip())
    multi2=sum(n==2 for n in multi.values())
    multi3=sum(n==3 for n in multi.values())
    discovery={'maxSourcesPerChannel':MAX_SOURCES,'preserved':metrics['preserved'],'playlistAdded':metrics['playlist_added'],'apiAdded':metrics['api_added'],'apiEntries':metrics['api_entries'],'skippedByLimit':metrics['limit_skipped'],'skippedCustomHeaders':metrics['header_skipped'],'channelsWith2Sources':multi2,'channelsWith3Sources':multi3,'channelsWithAlternatives':multi2+multi3,'alternativeUrls':sum(n-1 for n in multi.values() if n>1)}
    write_json(DATA/'channels.json',{'generatedAt':now(),'total':len(catalog),'channels':catalog,'sourceErrors':source_errors,'discovery':discovery})
    print('Multi-Source Discovery:',json.dumps(discovery,ensure_ascii=False),flush=True)
    for error in source_errors: print('Source warning:',error,flush=True)

    def priority(ch):
        r=results.get(ch['url'])
        if not r: return (0,'')
        return (1 if r.get('status')=='fail' else 2,r.get('checkedAt',''))

    batch=sorted(catalog,key=priority)[:args.batch]
    print(f'Catalog {len(catalog)} URLs; checking {len(batch)}; errors {len(source_errors)}',flush=True)
    def check(ch):
        status,detail,codec=probe(ch,args.timeout)
        return ch['url'],{'status':status,'detail':detail.strip(),'codec':codec.strip(),'checkedAt':now(),'name':ch['name'],'country':ch['country'],'url':ch['url']}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for url,result in pool.map(check,batch):
            old=results.get(url,{})
            result['checks']=int(old.get('checks',0))+1
            result['lastOkAt']=result['checkedAt'] if result['status']=='ok' else old.get('lastOkAt')
            results[url]=result
    tested=sum(ch['url'] in results for ch in catalog)
    ok=sum(results[ch['url']]['status']=='ok' for ch in catalog if ch['url'] in results)
    fail=tested-ok
    output={'schemaVersion':1,'generatedAt':now(),'testMethod':'ffprobe-stream-detection (not browser playback)','total':len(catalog),'tested':tested,'ok':ok,'fail':fail,'untested':len(catalog)-tested,'batchSize':len(batch),'sourceErrors':source_errors,'discovery':discovery,'results':results}
    write_json(DATA/'scan-results.json',output)
    print(f'Done: {tested}/{len(catalog)} tested, {ok} video streams, {fail} failures',flush=True)

if __name__=='__main__': main()
