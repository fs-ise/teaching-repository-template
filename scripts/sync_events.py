from __future__ import annotations
import argparse, hashlib, urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
try:
    from scripts import simple_yaml as yaml
except ModuleNotFoundError:
    import simple_yaml as yaml
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = 'https://raw.githubusercontent.com/fs-ise/handbook/main/data/events.yaml'
def load_yaml(path: Path) -> Any: return yaml.safe_load(path.read_text()) or []
def event_id(event: dict[str, Any]) -> str:
    if event.get('source_uid'): return str(event['source_uid'])
    raw = '|'.join(str(event.get(k,'')) for k in ('title','start','end','location'))
    return 'generated-' + hashlib.sha1(raw.encode()).hexdigest()[:12]
def normalize(event: dict[str, Any]) -> dict[str, Any]:
    start = datetime.fromisoformat(str(event['start'])); end = datetime.fromisoformat(str(event['end']))
    return {'event_id': event_id(event), 'title': str(event.get('title','')).strip(), 'date': start.date().isoformat(), 'start': start.strftime('%H:%M'), 'end': end.strftime('%H:%M'), 'location': event.get('location','TBD')}
def select(events: list[dict[str, Any]], match: Any) -> list[dict[str, Any]]:
    if not match: return []
    title_contains = match.get('title_contains') if isinstance(match, dict) else None; source_uids = set(match.get('source_uids', [])) if isinstance(match, dict) else set()
    if title_contains and source_uids: raise SystemExit('Configure either title_contains or source_uids, not both.')
    if title_contains:
        selected = [e for e in events if title_contains in str(e.get('title',''))]
        if not selected: raise SystemExit(f'No handbook events matched title_contains={title_contains!r}.')
        return selected
    if source_uids:
        selected = [e for e in events if str(e.get('source_uid')) in source_uids]; missing = source_uids - {str(e.get('source_uid')) for e in selected}
        if missing: raise SystemExit(f'Missing configured source_uids: {sorted(missing)}')
        return selected
    raise SystemExit('Unsupported handbook_event_match. Use title_contains or source_uids.')
def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument('--events'); ap.add_argument('--output', default='data/sessions.generated.yml'); ap.add_argument('--url', default=DEFAULT_URL); args=ap.parse_args(argv)
    course=yaml.safe_load((ROOT/'course.yml').read_text())
    if not course.get('schedule',{}).get('handbook_event_match'):
        sessions=course.get('sessions', [])
        out={'generated_from': 'course.yml', 'handbook_schema_note': 'No handbook_event_match configured; using sessions from course.yml. Current handbook events may lack stable course_id, session_id, and event_id fields.', 'sessions': sessions}
        path=ROOT/args.output; path.parent.mkdir(exist_ok=True); path.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True)); print(f'Wrote {path}'); return
    source=Path(args.events or course.get('schedule',{}).get('source_path','data/events.yaml'))
    if source.exists(): events=load_yaml(source); source_label=str(source)
    else:
        with urllib.request.urlopen(args.url, timeout=20) as r: events=yaml.safe_load(r.read()) or []
        source_label=args.url
    selected=select(events, course.get('schedule',{}).get('handbook_event_match')); normalized=sorted([normalize(e) for e in selected], key=lambda e:(e['date'], e['start'], e['event_id']))
    sessions=[]
    for i, base in enumerate(course.get('sessions', [])):
        merged=dict(base)
        if i < len(normalized): merged.update(normalized[i])
        sessions.append(merged)
    out={'generated_from': source_label, 'handbook_schema_note': 'Current handbook events may lack stable course_id, session_id, and event_id fields; matching is explicit and conservative.', 'sessions': sessions}
    path=ROOT/args.output; path.parent.mkdir(exist_ok=True); path.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True)); print(f'Wrote {path}')
if __name__=='__main__': main()
