"""aos-agent talk（aos-agent.md §1.9）：極簡來回對話——讀一行、say、等這一輪的回話、印、再讀一行。

等法跟 say --wait 同一個判準（送出前記下記憶長度 H0、等 H0 以後的回話），但每輪不退出：
印過的位置記在 shown，晚到的回話下次按 Enter 或送下一句時補印，不重印、不漏印。
回話與 slash 指令的輸出走 stdout；提示符、等待提示、逾時、卡住的原因走 stderr。
"""
import contextlib
import os
import signal
import sys
import threading
import time

import aos_agent_info
from aos_agent_home import AgentError, read_history
from aos_agent_listen import _stopped
from aos_agent_listen_render import call_line, call_names, note_calls, result_line
from aos_agent_runtime import report
from aos_agent_say import deliver
from aos_agent_status import collect, show

POLL_SECONDS = .2
HISTORY_DEFAULT = 10
CONTEXT_RECENT = 3
PREVIEW = 80
MAX_WAIT_SECONDS = 7 * 24 * 3600

HELP = [
    ('/status [-v]', '狀態一行；-v 印整段 aos-agent status'),
    ('/context [N]', '現在送給模型的東西：人格、記憶、工具的大小，加最近 N 則（預設 3）'),
    ('/history [N]', '記憶最後 N 則（預設 10）'),
    ('/tools', '列出工具'),
    ('/wait [秒]', '上一句逾時還沒回：再等一次（不帶數字＝跟 --wait 一樣）'),
    ('/pause', '手動暫停（同 aos-agent pause）'),
    ('/continue', '解除暫停（同 aos-agent continue）'),
    ('/help', '這張表'),
    ('/quit', '離開（Ctrl-C、Ctrl-D 也一樣）'),
]
NO_ARGS = ('tools', 'pause', 'continue', 'help', 'quit', 'exit')


def _err(text):
    sys.stderr.write(text + '\n')
    sys.stderr.flush()


def _out(text):
    sys.stdout.write(text + '\n')
    sys.stdout.flush()


def _cut(text, limit=PREVIEW):
    return text if len(text) <= limit else text[:limit] + '…'


def _seconds(ms):
    value = ms / 1000
    return int(value) if value == int(value) else value


def _isatty(stream):
    try:
        return stream.isatty()
    except (AttributeError, ValueError):
        return False


@contextlib.contextmanager
def no_interrupt():
    """短提交區：Ctrl-C 先記著，做完這一組才丟 KeyboardInterrupt（不留半截）。"""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    hit = []
    old = signal.signal(signal.SIGINT, lambda *_: hit.append(True))
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, old)
    if hit:
        raise KeyboardInterrupt


class Pending:
    """逾時／卡住還沒回的那一句。"""

    def __init__(self, h0, text, path, inode):
        self.h0, self.text, self.path, self.inode = h0, text, path, inode

    def gone(self):
        """原路徑上已經不是我投的那份（被收走了；別人再投同名檔不算我的）。"""
        try:
            return os.stat(self.path).st_ino != self.inode
        except FileNotFoundError:
            return True


class Talk:
    def __init__(self, agent_dir, timeout_ms, show_calls, env=None):
        self.env = os.environ if env is None else env
        self.info = aos_agent_info.load(agent_dir, env=self.env)
        self.base = self.info['dir']
        self.timeout_ms = timeout_ms
        self.show_calls = show_calls
        self.shown = len(self.info['history'])  # 記憶印到哪裡（不含）
        self.pending = None
        self.tty = _isatty(sys.stdin) and _isatty(sys.stderr)  # 等待提示只在兩邊都是終端時印
        self.waiting_shown = False
        # tool_call_id → 工具名，跟 listen 共用（aos_agent_listen_render.note_calls／call_names）；
        # 先用已有的記憶做種，之後每看到一則 assistant 就更新。
        self.tool_names = call_names(self.info['history'], self.shown)

    # ---- 讀記憶、補印 -------------------------------------------------

    def history(self):
        return read_history(aos_agent_info.load(self.base, env=self.env)['history_path'])

    def flush_new(self, history):
        """把 shown 以後的新訊息印出來：assistant 的字、（--show-calls）呼叫與結果；user 不回印。"""
        if len(history) < self.shown:
            self.shown = len(history)  # 記憶被人改短：從新長度算
        for message in history[self.shown:]:
            role = message.get('role')
            if role == 'assistant':
                note_calls(self.tool_names, message)  # 先記 id→名，結果可能緊接著就到
                if message.get('content'):
                    self._clear_waiting()
                    _out(message['content'])
                if self.show_calls:
                    for call in message.get('tool_calls') or []:
                        self._clear_waiting()
                        _out(call_line(call))
            elif role == 'tool' and self.show_calls:
                self._clear_waiting()
                name = self.tool_names.get(message.get('tool_call_id'), '?')
                _out(result_line(name, message.get('content')))
        self.shown = len(history)

    def check(self):
        """看一次：回 (data 或 None, 這句回完了沒)。先看檔、再看 state、最後讀記憶——

        檔已不是我的、之後 state 是 idle 又沒 intake，代表我那句已經接進記憶而且那一輪走完了（§8 的順序），
        之後讀到的記憶一定含我那句；所以同樣的字送兩次也不會拿前一句的回話充數。
        """
        pending = self.pending
        gone = pending.gone() if pending is not None else False
        data = None
        try:
            data = collect(self.base, self.env)
        except (AgentError, OSError, ValueError):
            pass
        try:
            history = self.history()
        except (AgentError, OSError, ValueError):
            return data, False  # 寫到一半或暫時讀不到，下一輪再讀；停止原因照看
        self.flush_new(history)
        if pending is None:
            return data, False
        if len(history) < pending.h0:
            self.pending = None
            self._clear_waiting()
            _err('（記憶被改短了，追不到剛才那句；/history 看現在的記憶）')
            return data, False
        done = (gone and data is not None and not data['state_error'] and data['state'] == 'idle'
                and data['batch'] is None and not data['intake'] and len(history) > pending.h0
                and history[-1]['role'] == 'assistant'
                and any(m['role'] == 'user' and m['content'] == pending.text
                        for m in history[pending.h0:-1]))
        if done:
            self.pending = None
        return data, done

    def peek(self):
        """不等：有晚到的就印；那句這一輪走完了就不再算在等。"""
        self.check()

    # ---- 等待提示 -----------------------------------------------------

    def _show_waiting(self, seconds):
        if self.tty:
            sys.stderr.write('\r\033[K（等回話 %d 秒… Ctrl-C 離開）' % seconds)
            sys.stderr.flush()
            self.waiting_shown = True

    def _clear_waiting(self):
        if self.waiting_shown:
            sys.stderr.write('\r\033[K')
            sys.stderr.flush()
            self.waiting_shown = False

    # ---- 一句話 -------------------------------------------------------

    def say(self, text):
        state = aos_agent_info.load_state(self.base, env=self.env)
        self.peek()  # 先把晚到的印掉，shown 才對
        h0 = len(self.history())
        with no_interrupt():  # 投進去了就一定記成 pending，Ctrl-C 等這之後才生效
            path, inode = deliver(self.base, state['input'][0], text, with_inode=True)
            self.pending = Pending(h0, text, path, inode)
        self.wait(self.timeout_ms)

    def wait(self, timeout_ms):
        """等 pending 那句這一輪走完；中途的新訊息邊到邊印。"""
        start = time.monotonic()
        deadline = start + timeout_ms / 1000
        try:
            while self.pending is not None:
                data, done = self.check()
                if done:
                    return
                stop = _stopped(data, self.base) if data is not None else None
                if stop is not None and self.pending is not None:
                    self._clear_waiting()
                    report(*stop)
                    _err('（已投入，不要再說一次；修好後 /wait 等回話，或按 Enter 看到了沒）')
                    return
                now = time.monotonic()
                if now >= deadline:
                    self._clear_waiting()
                    _err('（還在想：等了 %s 秒。/wait 再等；按 Enter 看到了沒；離開後 aos-agent listen --last --target %s 也看得到）'
                         % (_seconds(timeout_ms), self.base))
                    return
                self._show_waiting(now - start)
                time.sleep(min(POLL_SECONDS, deadline - now))
        finally:
            self._clear_waiting()

    # ---- slash 指令 ---------------------------------------------------

    def slash(self, line):
        """回 False＝要離開。"""
        word, _, rest = line[1:].partition(' ')
        rest = rest.strip()
        handler = {
            'status': self.cmd_status, 'context': self.cmd_context, 'history': self.cmd_history,
            'tools': self.cmd_tools, 'wait': self.cmd_wait, 'pause': self.cmd_pause,
            'continue': self.cmd_continue, 'help': self.cmd_help,
        }.get(word)
        if handler is None and word not in ('quit', 'exit'):
            _err('沒有這個指令，/help 看清單（要把 / 開頭的字送給模型就打兩個 //）')
            return True
        try:
            if word in NO_ARGS and rest:
                raise AgentError('Usage', '/%s 不收參數：%s' % (word, rest))
            if handler is None:
                return False
            handler(rest)
        except (AgentError, OSError, ValueError) as exc:
            report(getattr(exc, 'code', 'io'), getattr(exc, 'msg', str(exc)))
        return True

    def _number(self, rest, default):
        if not rest:
            return default
        if not rest.isdigit() or int(rest) == 0:
            raise AgentError('Usage', '要一個正整數：' + rest)
        return int(rest)

    def cmd_help(self, rest):
        for name, text in HELP:
            _out('%-14s %s' % (name, text))
        _out('其他字直接送給模型；空行＝不送，只看有沒有晚到的回話；// 開頭＝把 / 開頭的字送出去')

    def cmd_status(self, rest):
        if rest not in ('', '-v', '--verbose'):
            raise AgentError('Usage', '/status 只收 -v')
        data = collect(self.base, self.env)
        if rest:
            show(data, verbose=True)
            return
        b = data['batch']
        if data['state_error']:
            state = 'state ?  batch ?'
        else:
            state = 'state %s  batch %s' % (data['state'], '-' if b is None else '%s %s／%s' % (
                b['kind'], b['done_n'], b['total']))
        pending = len(data['pending_inputs'])
        waiting = '  還在等上一句' if self.pending is not None else ''
        _out('health %s  %s  input %s%s' % (data['health']['message'], state,
                                            '%d 個沒收' % pending if pending else '-', waiting))

    def cmd_context(self, rest):
        # 算法與 aos-agent context 同一份（aos_agent_context.lines）
        from aos_agent_context import lines
        count = self._number(rest, CONTEXT_RECENT)
        for line in lines(aos_agent_info.load(self.base, env=self.env), recent=count):
            _out(line)

    def _brief(self, m, names, full=False):
        from aos_agent_context import brief
        return brief(m, names, full)

    def cmd_history(self, rest):
        count = self._number(rest, HISTORY_DEFAULT)
        history = self.history()
        if not history:
            _out('（記憶是空的）')
            return
        names = call_names(history, len(history))
        for m in history[-count:]:
            _out(self._brief(m, names, full=True))

    def cmd_tools(self, rest):
        tools = aos_agent_info.load(self.base, env=self.env)['tools']
        if not tools:
            _out('（沒有工具）')
        for t in tools:
            fn = t['function']
            desc = (fn.get('description') or '').splitlines()
            _out('%s  %s' % (fn['name'], desc[0] if desc else ''))

    def cmd_wait(self, rest):
        timeout = self.timeout_ms
        if rest:
            try:
                seconds = float(rest)
            except ValueError:
                raise AgentError('Usage', '/wait 後面要是秒數：' + rest)
            if not 0 <= seconds <= MAX_WAIT_SECONDS:  # 也擋掉 nan、inf
                raise AgentError('Usage', '/wait 的秒數要在 0～%d 之間：%s' % (MAX_WAIT_SECONDS, rest))
            timeout = int(seconds * 1000)
        if self.pending is None:
            self.peek()
            _out('（沒有在等的話）')
            return
        self.wait(timeout)

    def cmd_pause(self, rest):
        from aos_agent_pause import pause
        with no_interrupt():
            pause(self.base)

    def cmd_continue(self, rest):
        from aos_agent_pause import resume
        with no_interrupt():
            resume(self.base, self.env)

    # ---- 主迴圈 -------------------------------------------------------

    def banner(self):
        try:
            health = collect(self.base, self.env)['health']
        except (AgentError, OSError, ValueError) as exc:
            health = {'code': 'bad', 'message': '讀不到狀態（%s）' % exc}
        _err('talk %s  health %s（/help 看指令，Ctrl-C 或 Ctrl-D 離開）' % (self.base, health['message']))
        if health['code'] not in ('ok', 'recovering', 'retrying', 'resuming'):
            _err('（照這樣說話會先投進去、等修好才處理）')

    def read_line(self, prompt):
        """提示符寫 stderr（stdout 只留對話）；stdout 也是終端時交給 input()，readline 才排得好。"""
        if not prompt:
            return input()
        if _isatty(sys.stdout):
            return input(prompt)
        sys.stderr.write(prompt)
        sys.stderr.flush()
        return input()

    def loop(self, prompt):
        while True:
            self.peek()
            try:
                line = self.read_line(prompt)
            except EOFError:
                if prompt:
                    _err('')
                return
            text = line.strip()
            if not text:
                continue
            if text.startswith('/') and not text.startswith('//'):
                if not self.slash(text):
                    return
                continue
            if text.startswith('//'):
                text = text[1:]
            try:
                self.say(text)
            except AgentError as exc:
                report(exc.code, exc.msg)
            except OSError as exc:
                report('io', str(exc))

    def farewell(self):
        """離開前再看一次（晚到的補印）；還沒回才提醒。"""
        if self.pending is None:
            return
        try:
            with no_interrupt():
                self.check()
        except KeyboardInterrupt:
            pass
        if self.pending is not None:
            _err('（上一句還沒回；話已投入，回話會進記憶，之後 aos-agent listen --last --target %s 看）' % self.base)


def talk(agent_dir, *, timeout_ms=120000, show_calls=False, env=None):
    session = None
    try:
        session = Talk(agent_dir, timeout_ms, show_calls, env)
        prompt = ''
        if _isatty(sys.stdin):
            try:
                import readline  # noqa: F401  有就用：方向鍵、歷史
            except ImportError:
                pass
            prompt = '> '
        session.banner()
        session.loop(prompt)
    except KeyboardInterrupt:
        if session is not None:
            session._clear_waiting()
        _err('')
    if session is not None:
        session.farewell()
    return 0
