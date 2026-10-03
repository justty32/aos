"""Read-only artifact/process checks; writes only final-check.json beside this file."""
import datetime
import json
import os
from pathlib import Path
import re

base = Path(__file__).resolve().parent
report = base.parent / '2026-10-03-astra-4-infra.md'
remaining = []
for d in Path('/proc').iterdir():
    if not d.name.isdigit() or int(d.name) == os.getpid():
        continue
    try:
        argv = (d / 'cmdline').read_bytes().split(b'\0')
        env = (d / 'environ').read_bytes().split(b'\0')
        belongs = any(a.startswith(b'/tmp/astra4-') for a in argv)
        belongs |= any(e.startswith(b'AOS7_ROOT=/tmp/astra4-') for e in env)
        belongs |= any(e.startswith(b'AOS7_TASK=/tmp/astra4-') for e in env)
        if belongs:
            state = (d / 'stat').read_text().rsplit(')', 1)[1].split()[0]
            remaining.append({'pid': int(d.name), 'state': state,
                              'argv': [a.decode(errors='replace') for a in argv if a]})
    except (OSError, ValueError, IndexError):
        pass

files = [p for p in base.rglob('*') if p.is_file()]
oversized = [str(p.relative_to(base)) for p in files if p.stat().st_size >= 200000]
bad_json = []
for p in files:
    try:
        if p.suffix == '.json':
            json.loads(p.read_text())
        elif p.suffix == '.jsonl':
            for line in p.read_text().splitlines():
                json.loads(line)
    except (ValueError, UnicodeError) as exc:
        bad_json.append({'path': str(p.relative_to(base)), 'error': str(exc)})

bad_links = []
for p in [report, base / 'README.md']:
    for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', p.read_text()):
        if '://' in link or link.startswith('#'):
            continue
        target = p.parent / link.split('#')[0]
        if not target.exists():
            bad_links.append({'file': str(p), 'target': link})

tmp = sorted(str(p) for p in Path('/tmp').glob('astra4-*'))
check = {
    'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'remaining_tmp_paths': tmp,
    'remaining_matching_processes': remaining,
    'process_check': 'Readable /proc cmdline tokens and AOS7_ROOT/AOS7_TASK environment; '
                     'agent cleanup evidence additionally verifies owned children were reaped.',
    'evidence_file_count_before_this_write': len(files),
    'max_evidence_file_bytes': max(p.stat().st_size for p in files),
    'oversized_files_ge_200000_bytes': oversized,
    'invalid_json_or_jsonl': bad_json,
    'broken_links_main_report_and_evidence_readme': bad_links,
    'unfilled_report_markers': re.findall(r'<!--.*?-->', report.read_text()),
}
check['passed'] = not any([tmp, remaining, oversized, bad_json, bad_links,
                          check['unfilled_report_markers']])
(base / 'final-check.json').write_text(json.dumps(check, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(check, ensure_ascii=False))
raise SystemExit(0 if check['passed'] else 1)
