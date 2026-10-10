"""選單的檔案與外部呼叫；動作由驅動先登記意圖。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import secrets
import stat
import sys

TOP = Path(__file__).resolve().parents[2]
PACK = Path(__file__).resolve().parent
sys.path[:0] = [str(TOP / 'lib'), str(TOP / 'packs/budget'), str(TOP / 'packs/llmcall')]
from aos7_fs import N, OK, fact, now
import aos7_budget
from aos7_llmcall_exit import answered, delivered
from aos7_menu_check import MenuError, normalize_out

SYSTEM = '你在走一份選單。每次只回答這一層。所需資料都在下面，不用找檔案或工具。照回法回，不要多寫別的。'


class Stop(Exception):
    """keep=False：這次停下不寫進 state（例：帳任務沒在跑，起好後照原樣再跑會接續）。"""
    def __init__(self, code, why, keep=True):
        self.code, self.why, self.keep = code, why, keep
        super().__init__(why)


def read(path, own=False):
    st, obj = fact(str(path))
    if st != OK:
        if own or st not in (N, 'bad'):
            raise Stop(3, f'不確定：{path} 讀不到或壞掉，原檔留著。請人看過，再照原樣跑一次')
        if st == N:
            raise MenuError(f'{path} 不在。給存在的 JSON 檔，例如 hello/menu.json')
        # fact 已確認是可讀的一般檔；重讀只為拿 JSON 的行、字位置。
        try:
            return json.loads(Path(path).read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            raise MenuError(f'{path} 第 {e.lineno} 行第 {e.colno} 字不是合法 JSON。改好 JSON 再跑') from None
        except UnicodeDecodeError as e:
            before = e.object[:e.start].decode('utf-8')
            line, column = before.count('\n') + 1, len(before.rsplit('\n', 1)[-1]) + 1
            raise MenuError(f'{path} 第 {line} 行第 {column} 字不是合法 JSON。存成 UTF-8 的 JSON 再跑') from None
    return obj


def save(directory, state):
    # log 是 state 的投影；重啟時再寫一次，補上 state rename 後被殺的紀錄。
    atomic_text(directory / 'state.json', json.dumps(state, ensure_ascii=False) + '\n')
    atomic_text(directory / 'log.jsonl', ''.join(
        json.dumps(r, ensure_ascii=False) + '\n' for r in state.get('journal', [])))


def event(state, kind, layer, **extra):
    row = dict(at=now(), step=len(state.get('journal', [])) + 1, layer=layer, kind=kind, call_id=None,
               prompt_chars=0, reply_chars=0, used=None, rc=0, why=None)
    row.update(extra)
    state['step'] = row['step']
    state.setdefault('journal', []).append(row)


def practice(menu_path, k):
    obj = read(menu_path.parent / 'practice.json')
    replies = obj.get('replies') if isinstance(obj, dict) and obj.get('v') == 1 else None
    if not isinstance(replies, list) or not all(isinstance(r, str) for r in replies):
        raise MenuError('practice.json 要有 v:1 與 replies 字串清單。照 hello 範例填')
    if k >= len(replies):
        raise Stop(1, '練習腳本用完了。換 --run 重走，並補足 practice.json 的回覆')
    return replies[k]


def ai(node, directory, menu_path, state, prompt, model):
    k = len(state['calls'])
    if not model:
        return practice(menu_path, k), 0, 0
    bud = aos7_budget.Bud(node / 'budget/llm')
    if not aos7_budget.ledger_running(bud):
        raise Stop(1, aos7_budget.not_running(bud), keep=False)
    grant = read(node / 'budget/llm/grant.json')
    if not isinstance(grant, dict) or not isinstance(grant.get('holder'), str) or not grant['holder']:
        raise MenuError('grant.json 缺 holder。給非空持有人，例如 menu')
    gateway = grant.get('gateway')
    if gateway == 'llm.fake':
        request = {'fake': {'mode': 'ok', 'usage': (len(SYSTEM) + len(prompt)) // 3 + 1,
                            'text': practice(menu_path, k)}}
    elif gateway == 'llm.litellm':
        request = {'litellm': {'model': model, 'messages': [
            {'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': prompt}]}}
    else:
        raise MenuError('gateway 不支援。給 llm.fake 或 llm.litellm')
    call_id = state['pending']['call_id']
    call = 'menu-' + hashlib.sha256((state['nonce'] + '\n' + call_id).encode()).hexdigest()[:32]
    path = directory / '.request.json'
    atomic_text(path, json.dumps(request, ensure_ascii=False) + '\n')
    p = subprocess.run([sys.executable, str(TOP / 'packs/llmcall/bin/aos7-llmcall'), 'call', 'budget/llm',
                        '--holder', grant['holder'], '--call', call, '--logical', 'menu/' + state['run'],
                        '--request', str(path), '--reserve', '20000', '--deadline', '600'],
                       cwd=node, capture_output=True, text=True)
    said = next((s.strip().removeprefix('aos7-llmcall: ') for s in reversed(p.stderr.splitlines()) if s.strip()), '')
    if not delivered(p.returncode):
        rc = 1 if p.returncode in (1, 2) else 3   # 1／2＝確定沒做成（同 FX1 B10-11），其餘當不確定
        raise Stop(rc, said or ('不確定：llmcall 沒有確定結果，pending 留著。照原樣再跑一次' if rc == 3
                              else 'llmcall 沒有交付。看 llmcall 的證據再跑'))
    try:
        receipt = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise Stop(3, '不確定：llmcall 回條讀不出來，pending 留著。照原樣再跑一次') from None
    if not answered(p.returncode, receipt):
        rc = 1 if isinstance(receipt, dict) and receipt.get('outcome') not in (None, 'answered') else 3
        raise Stop(rc, 'llmcall 沒有可確認的回答。查看 llmcall 的證據再跑')
    return receipt['text'], receipt.get('used'), p.returncode


def safe_path(directory, relative):
    path = directory / 'out' / normalize_out(relative)
    for part in (path, *path.parents):
        if part.is_symlink():
            raise MenuError('寫檔路徑有符號連結。改用 out/ 裡的普通資料夾與檔案')
    return path


def atomic_text(path, text):
    """逐段以 dirfd/no-follow 開資料夾；隨機同目錄暫存檔完成後 rename。"""
    path = path.absolute()
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    tmp = None
    try:
        for part in path.parts[1:-1]:
            try:
                os.mkdir(part, dir_fd=fd)
            except FileExistsError:
                pass
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except OSError as error:
                try:
                    mode = os.stat(part, dir_fd=fd, follow_symlinks=False).st_mode
                except OSError:
                    raise error
                if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                    raise MenuError('寫檔路徑有符號連結或不是資料夾。改用普通資料夾') from None
                raise
            os.close(fd)
            fd = child
        try:
            if stat.S_ISLNK(os.stat(path.name, dir_fd=fd, follow_symlinks=False).st_mode):
                raise MenuError('寫檔路徑有符號連結。改用普通檔案')
        except FileNotFoundError:
            pass
        for _ in range(100):
            candidate = '.' + path.name + '.' + secrets.token_hex(16) + '.tmp'
            try:
                tmpfd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                0o600, dir_fd=fd)
                tmp = candidate
                break
            except FileExistsError:
                continue
        else:
            raise Stop(3, '不確定：暫存檔名一直衝突。原檔留著，再跑一次')
        with os.fdopen(tmpfd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path.name, src_dir_fd=fd, dst_dir_fd=fd)
        tmp = None
    finally:
        if tmp is not None:
            os.unlink(tmp, dir_fd=fd)
        os.close(fd)


def action(node, directory, act, tools):
    if 'write' in act:
        path = safe_path(directory, act['write'])
        atomic_text(path, act['text'])
        return {'ok': True}
    checking = 'check' in act
    name = act.get('check', act.get('tool'))
    args = dict(act.get('args', {}))
    if checking:
        path = directory / '.check/slot.txt'
        atomic_text(path, act['text'])
        args = {'path': str(path)}
    tool = tools['tools'][name]
    values = dict(args, py=sys.executable, top=str(TOP), pack=str(PACK), node=str(node), run_dir=str(directory))
    argv = [s.format_map(values) for s in tool['argv']]
    try:
        p = subprocess.run(argv, cwd=node, capture_output=True, text=True, timeout=tool.get('timeout', 300))
    except (subprocess.TimeoutExpired, UnicodeError) as e:
        raise Stop(3, f'不確定：工具 {name} 沒有可確認的結果，pending 留著。照原樣再跑一次') from e
    rc, out = p.returncode, {}
    if rc not in (0, 1, 2):
        raise Stop(3, f'不確定：工具 {name} 退 {rc}，pending 留著。照原樣再跑一次')
    if rc == 2:
        raise Stop(2, f'工具 {name} 的參數不合。查看工具用法，修好後再跑')
    if tool.get('out') == 'json-line' and (rc == 0 or p.stdout.strip()):
        try:
            out = json.loads(next(s for s in reversed(p.stdout.splitlines()) if s.strip()))
            if not isinstance(out, dict):
                raise ValueError()
        except (ValueError, StopIteration):
            raise Stop(3, f'不確定：工具 {name} 沒印一行 JSON 物件，pending 留著。修好工具，再照原樣跑一次') from None
    err = next((s for s in reversed(p.stderr.splitlines()) if s.strip()), '')[:200]
    return {'rc': rc, 'out': out, 'err': err}
