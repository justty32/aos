#!/usr/bin/env python3
"""Assemble the apprentice's files and run the author gates (stdlib only)."""
import json
import errno
import importlib.util
from itertools import combinations
import signal
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
_summary_spec = importlib.util.spec_from_file_location(
    '_aos_tool_summary', Path(__file__).with_name('summary.py'))
_summary_module = importlib.util.module_from_spec(_summary_spec)
_summary_spec.loader.exec_module(_summary_module)
one_line, summary = _summary_module.one_line, _summary_module.summary
_check_spec = importlib.util.spec_from_file_location(
    '_aos_tool_menu_check', Path(__file__).resolve().parents[2] / 'aos7_menu_check.py')
_check_module = importlib.util.module_from_spec(_check_spec)
_check_spec.loader.exec_module(_check_module)

AUTHOR = Path(__file__).resolve().parents[3] / 'author' / 'bin'
TIMEOUT = 1100  # Registered menu-tool timeout is 1200 seconds.
class Problem(Exception):
    def __init__(self, code, message, gate=None):
        super().__init__(message)
        self.code, self.gate = code, gate
def strict_json(text):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('JSON 鍵重複')
            out[key] = value
        return out
    def constant(value):
        raise ValueError('JSON 含非標準數值：' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)

def request(path):
    try:
        req = strict_json(path.read_text(encoding='utf-8'))
    except OSError as exc:
        code = 2 if exc.errno in (errno.ENOENT, errno.ENOTDIR, errno.EISDIR) else 3
        raise Problem(code, 'REQUEST 無法讀取。檢查需求路徑、權限或檔案系統後重跑') from exc
    except (ValueError, UnicodeError) as exc:
        raise Problem(2, 'REQUEST 讀不到或不是合法 JSON。請檢查需求檔') from exc
    if (not isinstance(req, dict) or req.get('kind') != 'aos-tool'
            or not isinstance(req.get('name'), str)
            or not re.fullmatch(r'[a-z][a-z0-9]{1,15}', req['name'])):
        raise Problem(2, 'REQUEST 不是 aos-tool 需求。請提供工具需求與合法 name')
    if (type(req.get('v')) is not int or req['v'] != 1
            or not isinstance(req.get('rid'), str)
            or not re.fullmatch(r'[A-Za-z0-9_]{1,23}', req['rid'])):
        raise Problem(2, 'REQUEST 身分欄位不合。請提供 v=1 與合法 rid')
    return req
def sections(run, name):
    out = run / 'out'
    if out.is_symlink():
        raise Problem(1, 'schema out/：不能用符號連結交件。請交一般檔', 1)
    missing = [key for key in ('row', 'report')
               if not (out / key).is_file() or (out / key).is_symlink()]
    if missing:
        raise Problem(1, 'schema ' + '、'.join(missing) + '：缺少一般檔。請先交 row 與 report', 1)
    files = []
    packs = out / 'packs'
    if packs.is_dir() and not packs.is_symlink():
        def walk_error(exc):
            raise exc
        for folder, dirs, names in os.walk(packs, followlinks=False, onerror=walk_error):
            base = Path(folder)
            dirs[:] = [d for d in dirs if d != '__pycache__' and not (base / d).is_symlink()]
            for filename in names:
                path = base / filename
                if filename != '__pycache__' and stat.S_ISREG(path.lstat().st_mode):
                    files.append(path)
    ordered = sorted(files, key=lambda p: p.relative_to(out).as_posix())
    ordered += [out / 'row', out / 'report']
    chunks = []
    for path in ordered:
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeError as exc:
            raise Problem(1, 'format ' + path.relative_to(out).as_posix()
                          + '：不是 UTF-8 文字。請交文字檔', 1) from exc
        collision = re.search(r'^=== ([^\s]+) ===(?:\r?\n|$)', content, re.M)
        if collision:
            line = content[:collision.start()].count('\n') + 1
            raise Problem(1, f'format {path.relative_to(out).as_posix()} 第{line}行：'
                          '內容裡不能有段頭行（=== … ===），改寫那一行', 1)
        chunks.append('=== ' + path.relative_to(out).as_posix() + ' ===\n'
                      + content.rstrip('\r\n') + '\n')
    return ''.join(chunks)
def save_candidate(path, text):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                         dir=path.parent, prefix='.candidate-', delete=False) as stream:
            tmp = Path(stream.name)
            stream.write(text)
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()
def run_gates(reqpath, candidate, review):
    if review == 'rules':
        entry = os.environ.get('AOS7_AOS_TOOL_GATES', str(AUTHOR / 'aos7-gates'))
        argv = [sys.executable, entry, 'check', str(reqpath), str(candidate), '--reviewer', 'rules']
    else:
        entry = os.environ.get('AOS7_AOS_TOOL_AUTHOR', str(AUTHOR / 'aos7-author'))
        argv = [sys.executable, entry, 'propose', str(reqpath), '--candidate', str(candidate),
                '--review-llm', review, '--budget', 'budget/llm']
    if os.environ.get('AOS7_AOS_TOOL_NO_SCOPE') == '1':
        argv.append('--no-scope')
    try:
        timeout = float(os.environ.get('AOS7_AOS_TOOL_TIMEOUT', TIMEOUT))
        if not 0 < timeout <= TIMEOUT:
            raise ValueError('timeout')
    except ValueError as exc:
        raise Problem(2, '測試 timeout 必須大於 0 且不超過 1100。請修正環境變數') from exc
    with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True) as proc:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            # start_new_session makes this child the leader of our own new group.
            if proc.pid > 1 and proc.pid != os.getpgrp():
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            proc.communicate()
            raise Problem(3, '子程序逾時，已終止本次子程序群組。照原樣再跑') from exc
    if proc.returncode not in (0, 1, 2):
        raise Problem(3, '子程序未完成。檢查 gates／author 後照原樣再跑')
    if proc.returncode == 2:
        try:
            if strict_json(stdout.decode('utf-8')).get('why') == 'unknown':
                raise Problem(3, '子程序結果不明。檢查 gates／author 後照原樣再跑')
        except (ValueError, UnicodeError, AttributeError):
            pass
        raise Problem(2, '需求或子程序參數不對。請檢查 REQUEST 與 gates／author 參數')
    try:
        result = strict_json(stdout.decode('utf-8'))
        if not isinstance(result, dict) or type(result.get('ok')) is not bool:
            raise ValueError('不是檢查回條')
        check = result if review == 'rules' else result.get('check', {})
        if not isinstance(check, dict) or not isinstance(check.get('gates', {}), dict):
            raise ValueError('check 壞掉')
        gate = check.get('failed_gate')
        if gate is not None and (type(gate) is not int or gate not in (1, 2, 3)):
            raise ValueError('failed_gate 壞掉')
        if any(not isinstance(g, dict) or not isinstance(g.get('issues', []), list)
               for g in check.get('gates', {}).values()):
            raise ValueError('gates 壞掉')
        if result['ok']:
            if (check.get('ok') is not True or gate is not None
                    or any(check.get('gates', {}).get(str(n), {}).get('ok') is not True for n in (1, 2, 3))):
                raise ValueError('成功回條沒有三關全過的證據')
        elif review == 'rules' and not result.get('unknown'):
            if gate is None or check.get('gates', {}).get(str(gate), {}).get('ok') is not False:
                raise ValueError('失敗回條沒有失敗關號')
    except (ValueError, UnicodeError, TypeError) as exc:
        raise Problem(3, '子程序輸出讀不懂。檢查 gates／author 後照原樣再跑') from exc
    why = result.get('why')
    if why == 'unknown' or result.get('unknown'):
        raise Problem(3, one_line(result.get('error', result.get('unknown', '子程序結果不明')))
                      + '。照原樣再跑')
    if result['ok'] and proc.returncode == 0 and why is None:
        return 0, None, ''
    if review != 'rules' and gate is None:
        raise Problem(3, '第3關審查沒完成：帳或審查模型沒做成。檢查帳與模型後照原樣重驗')
    if gate is None or check.get('gates', {}).get(str(gate), {}).get('ok') is not False:
        raise Problem(3, '沒有候選未通過的證據。檢查 gates／author 後照原樣再跑')
    fallback = result.get('error') or stderr.decode('utf-8', 'replace').strip()
    return 1, gate, summary(check, fallback, gate)

def reject_brief_headers(value, number=1):
    if isinstance(value, str):
        if any(re.fullmatch(r'=== .+ ===', line) for line in value.splitlines()):
            raise Problem(2, f'需求第 {number} 條有一行長得像段頭（=== … ===），請改寫那一行')
    elif isinstance(value, dict):
        for item in value.values():
            reject_brief_headers(item, number)
    elif isinstance(value, list):
        for index, item in enumerate(value, 1):
            reject_brief_headers(item, index)

def brief(req):
    reject_brief_headers(req)
    try:
        maximum = req['scope'].get('max_files')
        if maximum is not None and type(maximum) is not int:
            raise TypeError('max_files 必須是整數')
        head = '\n'.join(['任務：' + req['task'], '目標：' + req['goal'],
                          '只准：' + '、'.join(req['scope']['only'])
                          + (f'（最多 {maximum} 個檔）' if maximum is not None else ''),
                          '不碰：' + '、'.join(req['scope']['not'])])
        work = req['work']
        if not isinstance(work, list) or any(not isinstance(item, str) for item in work):
            raise TypeError('work 必須是字串清單')
        accept = '\n'.join(['驗收：'] + ['- ' + item for item in req['accept']])
        tools = '\n'.join(['工具：'] + ['- ' + t['tool'] + '：' + t['use'] for t in req['tools']])
        if 'deliver' in req:
            tools += '\n交付：' + req['deliver']
    except (KeyError, TypeError) as exc:
        raise Problem(2, '需求摘要欄位不合。請補 task／goal／scope／work／accept／tools') from exc

    too_long = '需求摘要切成 4 段仍有一段超過 1500 字。請把那條 work 寫短再跑'
    selected = None
    for count in range(1, min(4, max(1, len(work))) + 1):
        best = None
        for cuts in combinations(range(1, len(work)), count - 1):
            bounds = (0,) + cuts + (len(work),)
            parts = [work[bounds[i]:bounds[i + 1]] for i in range(count)]
            texts = ['\n'.join([f'工作（第 {i}／{count} 段，共 {count} 段）：']
                               + ['- ' + item for item in part])
                     for i, part in enumerate(parts, 1)]
            longest = max(len(text) for text in texts)
            if len(head) + 1 + len(accept) + 1 + longest > 1500:
                continue
            if best is None or longest < best[0]:
                best = (longest, parts, texts)
        if best is not None:
            _, parts, texts = best
            selected = parts, texts
            break
    if selected is None:
        raise Problem(2, too_long)
    parts, texts = selected
    count = len(parts)
    for width in range(60, 14, -1):
        toc = '\n'.join(['需求各段在講什麼：'] + [
            f'第 {i} 段：' + '；'.join(
                item[:width] + ('…' if len(item) > width else '') for item in part)
            for i, part in enumerate(parts, 1)])
        if len(head) + 1 + len(toc) <= 1500:
            break
    else:
        raise Problem(2, '需求目錄加任務摘要超過 1500 字。請把需求條目寫短再跑')
    if [item for part in parts for item in part] != work:
        raise Problem(2, '需求摘要切段未保留原工作條目。請檢查切段程式')
    sections = [('head', head), ('accept', accept), ('tools', tools)]
    sections += [(f'work{i}', text) for i, text in enumerate(texts, 1)]
    sections += [('toc', toc)]
    if any(len(text) > 1500 for _, text in sections):
        raise Problem(2, too_long)
    output = ''.join(f'=== {name} ===\n{text}\n' for name, text in sections)
    try:
        parsed = _check_module.brief_sections(output)
    except _check_module.MenuError as exc:
        raise Problem(2, '需求摘要段頭不合。請檢查摘要產生程式') from exc
    if (parsed is None or list(parsed) != [name for name, _ in sections]
            or any(parsed[name] != text.strip('\r\n') for name, text in sections)
            or any(item not in parsed[f'work{i}']
                   for i, part in enumerate(parts, 1) for item in part)):
        raise Problem(2, '需求摘要重新解析後未保留原工作條目。請檢查摘要產生程式')
    print(output, end='')

def main(argv):
    if argv == ['--help']:
        print('用法：build.py check RUN_DIR REQUEST [--review rules|MODEL]')
        print('      build.py brief REQUEST')
        return 0
    candidate = None
    is_check = bool(argv and argv[0] == 'check')
    code, gate, issues = 0, None, ''
    try:
        if argv and argv[0] == 'brief' and len(argv) == 2 and not argv[1].startswith('--'):
            brief(request(Path(argv[1]).resolve()))
            return 0
        if (not is_check or len(argv) not in (3, 5)
                or any(a.startswith('--') for a in argv[1:3])
                or (len(argv) == 5 and (argv[3] != '--review' or not argv[4]
                                       or argv[4].startswith('--')))):
            raise Problem(2, '用法：build.py check RUN_DIR REQUEST [--review rules|MODEL]；brief REQUEST。請照用法重跑')
        run = Path(argv[1]).resolve()
        candidate = run / 'candidate.txt'
        if not run.is_dir():
            raise Problem(2, 'RUN_DIR 不在或不是資料夾。請先建立選單 run')
        reqpath = Path(argv[2]).resolve()
        req = request(reqpath)
        save_candidate(candidate, sections(run, req['name']))
        code, gate, issues = run_gates(reqpath, candidate, argv[4] if len(argv) == 5 else 'rules')
        if code:
            print('aos-tool-gates: 候選沒過。照 issues 修好再交', file=sys.stderr)
    except Problem as exc:
        code, gate = exc.code, exc.gate
        issues = summary({}, str(exc), gate) if code == 1 else one_line(exc)
        prefix = '不確定：' if code == 3 else ''
        print('aos-tool-gates: ' + prefix + one_line(exc), file=sys.stderr)
    except OSError as exc:
        code, issues = 3, '檔案或子程序無法存取。修好後照原樣再跑'
        print('aos-tool-gates: 不確定：' + issues, file=sys.stderr)
    if is_check:
        print(json.dumps({'ok': code == 0, 'gate': gate, 'issues': issues,
                          'candidate': str(candidate) if candidate else None}, ensure_ascii=False))
    return code
if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
