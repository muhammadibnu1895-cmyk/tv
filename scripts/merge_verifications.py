#!/usr/bin/env python3
"""Merge a browser verification CSV into shared JSON, latest checkedAt wins."""
import csv, datetime as dt, json, os, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
DB=ROOT/'data/verified-channels.json'
INBOX=ROOT/'data/verification_uploads'
MAX_BYTES=2_000_000
MAX_ROWS=5000

def parse_time(v):
    try:
        d=dt.datetime.fromisoformat(str(v).replace('Z','+00:00'))
        if d.tzinfo is None: raise ValueError('missing timezone')
        return d.astimezone(dt.timezone.utc)
    except (ValueError,TypeError): return None

def main():
    file_name=os.environ.get('CSV_FILE','').strip()
    if not file_name or pathlib.Path(file_name).name!=file_name or not file_name.lower().endswith('.csv'):
        raise ValueError('CSV_FILE must be a filename ending in .csv')
    file_path=INBOX/file_name
    if not file_path.is_file(): raise ValueError('CSV file not found in data/verification-inbox')
    if file_path.stat().st_size>MAX_BYTES: raise ValueError('CSV exceeds 2 MB')
    doc=json.loads(DB.read_text(encoding='utf-8')) if DB.exists() else {'schemaVersion':1,'results':{}}
    if not isinstance(doc,dict) or not isinstance(doc.get('results'),dict): raise ValueError('Invalid existing JSON schema')
    results=doc['results']; updated=0; ignored=0
    with file_path.open('r',encoding='utf-8-sig',newline='') as fh:
        reader=csv.DictReader(fh)
        if not reader.fieldnames or not {'channel_key','status','checked_at','detail'}.issubset(reader.fieldnames):
            raise ValueError('Invalid CSV header')
        for n,row in enumerate(reader,1):
            if n>MAX_ROWS: raise ValueError('Too many rows')
            key=(row.get('channel_key') or '').strip(); status=(row.get('status') or '').strip()
            checked=parse_time(row.get('checked_at'))
            if not key.startswith(('https://','http://')) or len(key)>2048 or status not in ('ok','fail','blocked') or checked is None:
                ignored+=1;continue
            # Ignore far-future timestamps and preserve newer data already published.
            if checked>dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=10): ignored+=1;continue
            old=results.get(key)
            old_at=parse_time(old.get('checkedAt')) if isinstance(old,dict) else None
            if old_at and checked<=old_at: ignored+=1;continue
            results[key]={'status':status,'checkedAt':checked.isoformat(timespec='milliseconds').replace('+00:00','Z'),'detail':str(row.get('detail') or '')[:250]}
            updated+=1
    doc['schemaVersion']=1
    doc['source']='Admin browser verification CSV; not live uptime'
    doc['publishedAt']=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    DB.parent.mkdir(parents=True,exist_ok=True)
    DB.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Merge complete: updated={updated}, skipped={ignored}, total={len(results)}')
if __name__=='__main__':
    try: main()
    except Exception as e:
        print('Merge failed:',str(e),file=sys.stderr)
        sys.exit(1)
