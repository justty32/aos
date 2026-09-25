"""郵差的字：信的摘要與截斷、一行印法，以及書記改寫 SESSION-LOG／WAIT_USER 的受管區塊。"""
import os

import aos_team_format as fmt

from aos_team_post_base import EMPTY_LINE


def rec_letter(rec):
    return {'id': rec['id'], 'from': rec.get('from'), 'to': rec.get('to'), 'status': rec.get('status'),
            'reply_to': rec.get('reply_to'), 'rev': rec.get('rev'), 'text': rec.get('text'), 'at': rec.get('at')}


def trim(text):
    text = text or '（空）'
    return text if len(text) <= fmt.TEXT_LIMIT else text[:fmt.TEXT_LIMIT - 20] + '\n…（太長，後面截掉）'


def ref_text(letter):
    return '%s%s' % (letter['reply_to'], ' rev%d' % letter['rev'] if letter.get('rev') else '')


STATUS_WORDS = {'queued': '等投遞', 'sent': '已投、還沒收', 'working': '做事中', 'verifying': '驗收中',
                'reviewing': '審查中', 'blocked': '卡住', 'waiting_user': '等人回答'}


def one_line(text, limit):
    """攤成一行（換行、連續空白變一格），太長截掉：插不進新標題、新清單。"""
    text = ' '.join(str(text or '').split())
    text = text[:limit] + ('…' if len(text) > limit else '')
    return text


def session_line(t):
    nxt = {'blocked': '等 %s 決定' % (t.get('waiting_on') or '開單人'),
           'waiting_user': '等人回答 %s' % (t.get('waiting_on') or ''),
           'verifying': '等驗收結果', 'reviewing': '等審查'}.get(t['status'], '等 %s 回報' % t['assignee'])
    return '- [%s %s] %s（%s，第 %d/%d 次）→ %s：%s' % (
        t['id'], one_line(t['workflow'], 40), STATUS_WORDS.get(t['status'], t['status']), t['assignee'],
        t['attempt'], t['max_attempts'], nxt, one_line(t['goal'], 80))


def wait_line(q):
    opts = '（選項：%s）' % ' / '.join(one_line(o, 30) for o in q['options']) if q.get('options') else ''
    ref = ' [%s]' % q['reply_to'] if q.get('reply_to') else ''
    return '- [%s] %s 問：%s%s%s → aos-team answer %s "…"' % (q['id'], q['from'], one_line(q['question'], 120),
                                                           opts, ref, q['id'])


BLOCK_BEGIN = '<!-- aos-team 書記：這一段自動產生，別手改 -->'
BLOCK_END = '<!-- /aos-team 書記 -->'


def _outside_fences(lines):
    """每一行在不在 ``` 程式碼區塊外。"""
    out, inside = [], False
    for ln in lines:
        fence = ln.lstrip().startswith('```')
        out.append(not inside and not fence)
        if fence:
            inside = not inside
    return out


def update_section(path, heading, managed_lines):
    """書記只改自己的區塊（BLOCK_BEGIN～BLOCK_END 之間），區塊外逐字不動。回有沒有改。

    沒有區塊：放在標題底下（那一節只有「（目前無）」就換掉它）；標題也沒有：加在檔尾。區塊空＝寫「（目前無）」。"""
    text = path.read_text(encoding='utf-8')
    lines = text.split('\n')
    ok = _outside_fences(lines)
    block = [BLOCK_BEGIN] + (list(managed_lines) or [EMPTY_LINE]) + [BLOCK_END]
    begin = next((i for i, ln in enumerate(lines) if ok[i] and ln.strip() == BLOCK_BEGIN), None)
    end = next((i for i, ln in enumerate(lines) if ok[i] and ln.strip() == BLOCK_END
                and begin is not None and i > begin), None)
    if begin is not None and end is not None:
        new = lines[:begin] + block + lines[end + 1:]
    else:
        start = next((i for i, ln in enumerate(lines) if ok[i] and ln.strip() == heading), None)
        if start is None:
            tail = lines[:-1] if lines and lines[-1] == '' else lines
            new = tail + ([''] if tail and tail[-1].strip() else []) + [heading, ''] + block + ['']
        else:
            stop = next((i for i in range(start + 1, len(lines)) if ok[i] and lines[i].startswith('#')), len(lines))
            body = [i for i in range(start + 1, stop) if lines[i].strip()]
            if len(body) == 1 and lines[body[0]].strip() == EMPTY_LINE:
                new = lines[:body[0]] + block + lines[body[0] + 1:]
            else:
                new = lines[:start + 1] + [''] + block + lines[start + 1:]
    out = '\n'.join(new)
    if out == text:
        return False
    tmp = path.with_name('.%s.%d.tmp' % (path.name, os.getpid()))
    tmp.write_text(out, encoding='utf-8')
    os.chmod(tmp, os.stat(path).st_mode & 0o7777)
    os.replace(tmp, path)
    return True
