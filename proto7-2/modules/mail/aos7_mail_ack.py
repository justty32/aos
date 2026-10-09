"""以本地已確認游標掃 must；有進展才用一次公開 CLI 確認。"""
import json
from pathlib import Path
import subprocess
import sys
from aos7_mail import HERE, inbox, load, letters, letter, events_read, write_json, test_point


def ack(root, me):
    box = inbox(root, me)
    events = Path(root) / me / 'events'
    if not events.is_dir():
        return
    marker = box / '.acked'
    local = load(marker, 0)
    upto, cursor, unsure = local, local + 1, False
    ended = {l['id'] for p in letters(box / 'done')
             if (l := letter(p))['status'] == 'REQUEST'}
    while True:
        result = events_read(events, 'must', cursor=cursor)
        gaps = result['gaps']
        if result['errors'] or any(g.get('kind') != 'retention' for g in gaps):
            unsure = True  # 讀不清（可能 events 半路中斷待復原）：不越過
            break
        # retention 只會淘汰 events 已 ack 的段；本地可能落後。
        gap = next((g for g in gaps if g['from'] <= cursor <= g['to']), None)
        if gap:
            upto, cursor = gap['to'], gap['to'] + 1
            continue
        records = result['records']
        stopped = False
        for rec in records:
            if rec['seq'] != cursor:
                gap = next((g for g in gaps if g['from'] <= cursor <= g['to']), None)
                if gap:
                    upto, cursor = gap['to'], gap['to'] + 1
            if rec['seq'] != cursor or rec.get('kind') != 'mail.request' or rec.get('payload', {}).get('id') not in ended:
                stopped = True
                break
            upto, cursor = rec['seq'], rec['seq'] + 1
        if stopped or len(records) < 100:
            break
    if upto > local or unsure:  # 讀不清時以原值 ack 一次：讓 events 自行復原、拿回真值，仍不越過
        confirmed = event_ack(events, upto)
        if confirmed is not None:
            test_point('mail.after_event_ack')
            write_json(str(marker), confirmed)


def event_ack(events, upto):
    p = subprocess.run([sys.executable, str(HERE.parent / 'events/aos7-events'), 'read',
                        '--events', str(events), '--channel', 'must', '--ack', str(upto)], capture_output=True, text=True)
    if p.returncode == 0:
        return json.loads(p.stdout)['acked_upto']
    print('aos7-mail: 必達提醒確認失敗（' + ' '.join(p.stdout.splitlines()) + '）。信是權威，下次 read 或 done 會再試', file=sys.stderr)
    return None

