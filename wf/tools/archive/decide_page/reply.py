"""Parse batch replies, apply answers, and format source-grouped landing text."""
import datetime
import json
from pathlib import Path
import re

from model import Error, shown_source, warn


def parse(data, text):
    text = text.strip()
    if text.startswith('['):
        header = re.match(r'\[([^\]]*)\]', text)
        if not header or header[1] != data['batch']:
            raise Error('BatchBad', 'reply header does not match the data batch')
        text = text[header.end():].strip()
    rows = {row['id']: row for row in data['rows']}
    known = '|'.join(re.escape(rid) for rid in sorted(rows, key=len, reverse=True))
    starts = list(re.finditer(r'(?:^|、)\s*(' + known + r'):', text)) if known else []
    parsed = {}
    prefix = text[:starts[0].start()] if starts else text
    _unknown(prefix)
    for i, start in enumerate(starts):
        rid = start[1]
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        body = text[start.end():end].strip()
        match = re.match(r'([A-Za-z0-9]{1,8}|-)(\*)?(\?)?', body)
        if not match:
            raise Error('ChoiceBad', f'row {rid} has an invalid choice')
        choice, star, unseen = match.groups()
        rest = body[match.end():].strip()
        note = ''
        if rest.startswith(('（備註：', '(備註:')):
            opening = '（備註：' if rest.startswith('（備註：') else '(備註:'
            closing = '）' if opening.startswith('（') else ')'
            last = rest.rfind(closing)
            if last < len(opening):
                raise Error('ArgumentsBad', f'row {rid} note has no closing parenthesis')
            note = rest[len(opening):last].strip()
            _unknown(rest[last + 1:])
        elif rest:
            if not rest.startswith('、'):
                raise Error('ArgumentsBad', f'row {rid} has malformed reply text')
            _unknown(rest)
        row = rows[rid]
        keys = {option['key'] for option in row['options']}
        if (keys and choice not in keys) or (not keys and choice != '-'):
            raise Error('ChoiceBad', f'row {rid} choice {choice} is not allowed')
        changed = bool(row['recommend'] and choice != row['recommend'])
        if bool(star) != changed:
            warn(f'Row {rid} star flag disagrees with its choice.')
        state = ('pending' if unseen else 'changed' if changed else
                 'note-only' if not keys else 'picked')
        if rid in parsed:
            warn(f'Row {rid} occurs more than once; using its last reply.')
        parsed[rid] = dict(id=rid, choice=choice, state=state, note=note,
                           flag_star=bool(star), flag_unseen=bool(unseen))
    results = [parsed.get(row['id'], dict(id=row['id'], choice='', state='missing',
               note='', flag_star=False, flag_unseen=False)) for row in data['rows']]
    missing = sum(item['state'] == 'missing' for item in results)
    if missing:
        warn(f'Reply is missing {missing} questions.')
    return results


def _unknown(text):
    for item in re.finditer(r'(?:^|、)\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*[:：]', text):
        warn(f'Unknown or malformed reply item {item[1]}.')
    if text.strip('、 \t\r\n') and not re.search(r'[A-Za-z0-9][A-Za-z0-9._-]*\s*[:：]', text):
        raise Error('ArgumentsBad', 'reply text contains no recognizable item')


def apply(data, path, results):
    today = datetime.date.today().isoformat()
    for row, answer in zip(data['rows'], results):
        if answer['state'] == 'pending':
            if row['answer_state'] in ('picked', 'changed', 'note-only'):
                continue
            row.update(answer='', answer_state='pending',
                       answer_note=answer['note'], answered_at='')
        else:
            row.update(answer=answer['choice'], answer_state=answer['state'],
                       answer_note=answer['note'], answered_at=today)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    counts = {name: sum(item['state'] == name for item in results)
              for name in ('changed', 'pending', 'missing')}
    return (f'decide_page: applied {len(results)} answers '
            f'({counts["changed"]} changed, {counts["pending"]} pending, {counts["missing"]} missing)')


def land(data, path):
    groups = {}
    pending = []
    missing = []
    for row in data['rows']:
        if row['answer_state'] == 'pending':
            line = (f'- {row["id"]}（{row["question"]}）：沒點開，仍待定'
                    f'（推薦 {row["recommend"]}）')
            if row['answer_note']:
                line += f' 備註原話：「{row["answer_note"]}」'
            pending.append(line)
            continue
        if not row['answer_state'] or row['answer_state'] == 'missing' or not row['answer']:
            missing.append(row['id'])
            continue
        source = shown_source(path, row['source_path']) or '(no source)'
        prefix = f'- **{row["id"]}**（{row["question"]}）：'
        note = row['answer_note']
        if not row['options']:
            line = prefix + f'備註原話：「{note}」'
        else:
            key = row['answer']
            label = next((o['label'] for o in row['options'] if o['key'] == key), '')
            line = prefix + f'選 {key}「{label}」。'
            if row['answer_state'] == 'changed':
                line += f' 跟推薦不同（推薦 {row["recommend"]}）。'
            if note:
                line += f' 備註原話：「{note}」'
        groups.setdefault(source, []).append(line)
    blocks = ['### ' + source + '\n\n' + '\n'.join(lines) for source, lines in groups.items()]
    if pending:
        blocks.append('### pending\n\n' + '\n'.join(pending))
    if missing:
        blocks.append('### missing\n\n' + '\n'.join('- ' + rid for rid in missing))
    return '\n\n'.join(blocks)
