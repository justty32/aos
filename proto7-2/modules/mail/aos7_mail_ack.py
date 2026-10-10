"""以本地已確認游標掃 must；有進展才用一次公開 CLI 確認。"""
import json
from pathlib import Path
import subprocess
import sys
from aos7_mail import HERE, inbox, load, letters, letter, events_read, write_json, test_point
from aos7_events_store import load_state


def acked_upto(events):
    """events 目前確認到哪（唯讀不鎖）；讀不到或格式不合回 0＝不讓過任何別人事件。"""
    st = load_state(str(events))
    try:
        upto = st['channels']['must']['acked_upto']
    except (TypeError, KeyError):
        return 0
    return upto if type(upto) is int and upto > 0 else 0


def ack(root, me):
    box = inbox(root, me)
    events = Path(root) / me / 'events'
    if not events.is_dir():
        return
    marker = box / '.acked'
    try:
        local = load(marker, 0)
    except ValueError as e:
        raise OSError('必達提醒游標 .acked 壞了，請恢復原檔再試') from e
    if type(local) is not int or local < 0:
        raise OSError('必達提醒游標 .acked 要是非負整數，請恢復原檔再試')
    upto, cursor, unsure = local, local + 1, False
    others_acked = 0
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
            if rec['seq'] == cursor and rec.get('kind') != 'mail.request':
                if rec['seq'] > others_acked:
                    others_acked = acked_upto(events)  # 別人可能剛確認；遇到才重讀
                if rec['seq'] <= others_acked:  # 別人的事件已被它的主人確認：讓過
                    upto, cursor = rec['seq'], rec['seq'] + 1
                    continue
                stopped = True  # 別人還沒確認：停下，不替它確認
                break
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
    p = subprocess.run([sys.executable, str(HERE.parent / 'events/aos7-events'), 'ack',
                        '--events', str(events), str(upto)], capture_output=True, text=True)
    if p.returncode == 0:
        return json.loads(p.stdout)['acked_upto']
    print('aos7-mail: 必達提醒確認失敗（' + ' '.join(p.stdout.splitlines()) + '）。信是權威，下次 read 或 done 會再試', file=sys.stderr)
    return None

