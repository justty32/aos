"""驗收員關牢跑的檢查器：組 aos-jail 參數、牢裡跑並收輸出尾巴、wf_lint_strict、cmd_ok（team.json 白名單裡的專案指令）。"""
import json
import os
import shutil
import subprocess

from aos_team_verify_checks import _wf, CheckError, PROTO


JAIL_LINT = PROTO / 'tools' / 'wf' / '_jail_lint'
OUTPUT_TAIL = 600                     # cmd_ok 的輸出最後留幾個字元給修正信
KEEP_BYTES = 64 * 1024                # cmd_ok 讀輸出時牢外最多留多少位元組（邊讀邊丟前面的）


def jail_argv(project, prog_argv, setenv=(), mounts=None):
    """關牢的 argv：專案**唯讀**掛 /work/ws（起點）、不上網、清環境（aos-jail）。沒 bwrap＝CheckError，不退回不關牢。
    mounts：cmd_ok 白名單那條人寫的多掛資料夾（名字 → 路徑），一律唯讀掛 /work/<名>。"""
    import aos_agent_access
    if shutil.which('bwrap') is None:
        raise CheckError('這條要關在牢裡跑，這台找不到 bwrap（bubblewrap）')
    argv = [aos_agent_access.JAIL, '--mount-ro', 'ws=%s' % os.path.realpath(project), '--chdir', 'ws', '--net', 'off']
    for name, path in sorted((mounts or {}).items()):
        if not os.path.isdir(path):
            raise CheckError('cmd_ok 白名單要多掛的 %s（%s）不在或不是資料夾' % (name, path))
        argv += ['--mount-ro', '%s=%s' % (name, os.path.realpath(path))]
    for kv in setenv:
        argv += ['--setenv', kv]
    return argv + ['--', *prog_argv]


def jail_run(project, prog_argv, stdin_text, timeout, setenv=(), mounts=None):
    """關牢跑一支程式，回 CompletedProcess；逾時丟 subprocess.TimeoutExpired。"""
    return subprocess.run(jail_argv(project, prog_argv, setenv, mounts), input=stdin_text, capture_output=True, text=True,
                          timeout=timeout, errors='replace')


def run_tail(argv, timeout, keep=KEEP_BYTES):
    """跑 argv（stdin 空、stdout＋stderr 併一條），邊讀邊只留最後 keep 位元組（輸出再大牢外記憶體也不漲）。
    回 (退出碼或 None＝逾時被砍, 尾端文字)。逾時砍的是 aos-jail＝bwrap 本身，牢裡的行程跟著死（--die-with-parent）。"""
    import threading
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    buf = bytearray()

    def pump():
        for chunk in iter(lambda: proc.stdout.read(8192), b''):
            buf.extend(chunk)
            if len(buf) > keep:
                del buf[:len(buf) - keep]
    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        code = None
    reader.join(5)
    proc.stdout.close()
    return code, bytes(buf).decode('utf-8', 'replace')


def check_wf_lint_strict(project, args):
    """跑 wf 工具包快照裡的 wf-lint.sh --strict（不是專案裡那份），**關在牢裡**（它會跑 bash 與 git）：
    pass／fail；檢查器本身壞了＝檢查失敗。"""
    wf = _wf()
    try:
        r = jail_run(project, [str(JAIL_LINT)], json.dumps({'strict': True}), wf.LINT_TIMEOUT + 30)
    except subprocess.TimeoutExpired:
        raise CheckError('wf-lint 跑不完（牢裡超過 %d 秒）' % (wf.LINT_TIMEOUT + 30))
    try:
        res = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise CheckError('wf-lint 在牢裡沒回結果（退 %d）：%s' % (r.returncode, (r.stderr or r.stdout)[-300:]))
    if 'error' in res:
        raise CheckError('wf-lint 跑不完：%s' % res.get('message'))
    total = res['total_line'] or '（沒印 TOTAL）'
    if res['status'] == 'error':
        raise CheckError('wf-lint 本身故障（退 %d）：%s' % (res['exit'], total))
    first = '；前幾條：%s' % '／'.join(res['problems'][:3]) if res['problems'] else ''
    return res['status'] == 'pass', ('%s%s' % (total, first))[:600]


def check_cmd_ok(project, item, roster):
    """cmd_ok：跑專案自己的指令（例：測試），關在牢裡；退 0＝過、其他＝不過（附輸出最後一段）、逾時＝不過。
    白名單在名冊 team.json 的 cmd_ok（人寫）；單子上寫的 run 與 timeout_s 要對得上其中一條（開單時郵差驗過，
    這裡再驗一次：人事後拿掉了就不跑＝檢查器壞）。"""
    import aos_team_format
    entry = aos_team_format.cmd_allowed(roster, item)
    if entry is None:
        raise CheckError('指令 %s 不在 team.json 的 cmd_ok 白名單（或 timeout_s 超過白名單的）；人加進白名單再 --again'
                         % json.dumps(item.get('run'), ensure_ascii=False))
    timeout = item.get('timeout_s', entry['timeout_s'])
    shown = ' '.join(item['run'])
    # 先在同一種牢裡確認指令找得到、牢開得起來（這一步只跑 sh 的 command -v，不跑專案的東西）。
    # 之後只看退出碼：不去解析專案程式自己印的 stderr（它能假冒 bwrap 的錯誤訊息；astra w2b M1）
    try:
        probe = jail_run(project, ['sh', '-c', 'command -v -- "$1"', 'sh', item['run'][0]], '', 30,
                         mounts=entry.get('mounts'))
    except subprocess.TimeoutExpired:
        raise CheckError('「%s」：牢開不起來（確認指令在不在的那一步超過 30 秒）' % shown)
    if probe.returncode != 0 or not probe.stdout.strip():
        raise CheckError('「%s」在牢裡跑不起來：找不到指令 %s，或牢開不起來（退 %d）：%s'
                         % (shown, item['run'][0], probe.returncode, (probe.stderr or '').strip()[-300:]))
    code, out = run_tail(jail_argv(project, item['run'], ('PYTHONDONTWRITEBYTECODE=1',), entry.get('mounts')), timeout)
    tail = out.strip()[-OUTPUT_TAIL:]
    if code is None:
        return False, '「%s」跑超過 %d 秒，砍掉了%s' % (shown, timeout, '；最後的輸出：' + tail if tail else '')
    if code == 0:
        return True, '「%s」退 0' % shown
    return False, '「%s」退 %d：%s' % (shown, code, tail)
