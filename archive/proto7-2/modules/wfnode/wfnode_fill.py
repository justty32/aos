"""只根據已知事實填寫模板。"""
import datetime as dt
import os
from pathlib import Path
import re
import shlex


def timezone():
    if os.environ.get('TZ'):
        return os.environ['TZ']
    try:
        value = Path('/etc/timezone').read_text().strip()
        if value:
            return value
    except OSError:
        pass
    try:
        target = os.readlink('/etc/localtime')
        if 'zoneinfo/' in target:
            return target.split('zoneinfo/', 1)[1]
    except OSError:
        pass
    return None


def fill_text(text, name, today=None, zone=None, index=False):
    """只填已知事實；刪除整段模板說明，保留導入判斷。"""
    today = today or dt.date.today().isoformat()
    zone = timezone() if zone is None else zone
    run_all = Path(__file__).resolve().parents[2] / 'tests/run_all.py'
    description = f'aos node「{name}」的 agent 工作區（aos7-wfnode init 建立）'
    facts = {'專案名': name, '一句話：這專案是什麼、產出什麼': description,
             '一句話描述': description, '測試 / build / lint 指令': f'`python3 {shlex.quote(str(run_all))}`',
             '直接 commit main / 開 branch 走 PR': '不 commit main：開分支交人 merge'}
    lines = text.splitlines(keepends=True)
    if index:
        for i, line in enumerate(lines):
            if '{{src/ 或主要產出目錄}}' in line:
                lines[i] = '| `handoffs/` | 續行點：每天一份 `handoffs/<日期>/STATE.md`，[NEXT-SESSION](handoffs/NEXT-SESSION.md) 指最新一份 |\n'
            elif '{{其他頂層目錄' in line:
                lines[i] = '| `ROSTER.md`、`line-claims.json` | 誰是誰（[ROSTER](ROSTER.md)）與誰能寫哪裡（領地表，資料檔）；由 mail 包填 |\n'
    kept, i = [], 0
    while i < len(lines):
        if lines[i].startswith('>'):
            end = i + 1
            while end < len(lines) and lines[end].startswith('>'):
                end += 1
            if any('〔模板說明〕' in line for line in lines[i:end]):
                i = end
                if i < len(lines) and not lines[i].strip():
                    i += 1
                while kept and not kept[-1].strip() and i < len(lines) and not lines[i].strip():
                    i += 1
                continue
            kept.extend(lines[i:end])
            i = end
        else:
            kept.append(lines[i])
            i += 1

    def replace(match):
        key = match[1]
        if key in facts:
            return facts[key]
        if key.startswith('導入日期'):
            return today
        if ('時區' in key or key == '例：Asia/Taipei') and zone:
            return zone
        return f'（未定：{key}）'
    return re.sub(r'\{\{([^{}\n]*)\}\}', replace, ''.join(kept))

