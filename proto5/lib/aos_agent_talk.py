"""aos-agent talk（aos-agent.md §1.9）：極簡來回對話——讀一行、say、等這一輪的回話、印、再讀一行。

等法跟 say --wait 同一個判準（送出前記下記憶長度 H0、等 H0 以後的回話），但每輪不退出：
印過的位置記在 shown，晚到的回話下次按 Enter 或送下一句時補印，不重印、不漏印。
回話與 slash 指令的輸出走 stdout；等待提示、逾時、卡住的原因走 stderr。
"""
import json
import os
import sys
import time

import aos_agent_info
from aos_agent_home import AgentError, read_history
from aos_agent_listen import _stopped
from aos_agent_results import UNKNOWN
from aos_agent_runtime import report
from aos_agent_say import deliver
from aos_agent_status import collect, show

POLL_SECONDS = .2
HISTORY_DEFAULT = 10
CONTEXT_RECENT = 3
PREVIEW = 80
TOOL_FAIL = ('逾時', '失敗', '無法執行', '沒跑')

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


def _err(text):
    sys.stderr.write(text + '\n')
    sys.stderr.flush()


def _out(text):
    sys.stdout.write(text + '\n')
    sys.stdout.flush()


def _one_line(text, limit=PREVIEW):
    text = ' '.join(str(text).split())
    return text if len(text) <= limit else text[:limit] + '…'


def _seconds(ms):
    value = ms / 1000
    return int(value) if value == int(value) else value


def call_line(call):
    """[呼叫 名 k=v …]：參數是 JSON 物件就攤開，不是就原樣縮短。"""
    fn = call.get('function', {})
    raw = fn.get('arguments', '')
    try:
        args = json.loads(raw) if raw else {}
    except ValueError:
        args = None
    if isinstance(args, dict):
        parts = ['%s=%s' % (k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
                 for k, v in args.items()]
        text = ' '.join(parts)
    else:
        text = raw
    text = _one_line(text)
    return '[呼叫 %s%s]' % (fn.get('name', '?'), ' ' + text if text else '')


def result_line(message, names):
    """[結果 ok N 行]；aos-agent 寫的失敗字串（§6.2）改印 [結果 失敗 …]。"""
    content = message.get('content') or ''
    name = names.get(message.get('tool_call_id'))
    if name and content.startswith('工具 %s ' % name) and any(
            content.startswith('工具 %s %s' % (name, w)) for w in TOOL_FAIL):
        return '[結果 失敗 %s]' % _one_line(content.splitlines()[0] if content else '')
    if content == UNKNOWN:
        return '[結果 不明：工具可能跑了也可能沒有]'
    lines = len(content.splitlines())
    return '[結果 ok %d 行]' % lines if content else '[結果 ok 空]'


class Talk:
    def __init__(self, agent_dir, timeout_ms, show_calls, env=None):
        self.env = os.environ if env is None else env
        self.info = aos_agent_info.load(agent_dir, env=self.env)
        self.base = self.info['dir']
        self.timeout_ms = timeout_ms
        self.show_calls = show_calls
        self.shown = len(self.info['history'])  # 記憶印到哪裡（不含）
        self.names = {}  # tool_call_id → 工具名，給結果行判失敗
        self.pending = None  # 逾時還沒回的那句：(H0, TEXT, 投遞路徑)
        self.tty_err = _isatty(sys.stderr)
        self.waiting_shown = False

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
                for call in message.get('tool_calls') or []:
                    self.names[call.get('id')] = call.get('function', {}).get('name')
                if message.get('content'):
                    self._clear_waiting()
                    _out(message['content'])
                if self.show_calls:
                    for call in message.get('tool_calls') or []:
                        self._clear_waiting()
                        _out(call_line(call))
            elif role == 'tool' and self.show_calls:
                self._clear_waiting()
                _out(result_line(message, self.names))
        self.shown = len(history)

    def peek(self):
        """不等：有晚到的就印；逾時那句這輪走完了就清掉。"""
        try:
            history = self.history()
            self.flush_new(history)
            if self.pending is not None:
                data = collect(self.base, self.env)
                if self._done(data, history, *self.pending):
                    self.pending = None
        except (AgentError, OSError, ValueError):
            pass

    def _done(self, data, history, h0, text, dropped):
        return (not dropped.exists() and not data['state_error'] and data['state'] == 'idle'
                and data['batch'] is None and not data['intake'] and len(history) > h0
                and history[-1]['role'] == 'assistant'
                and any(m['role'] == 'user' and m['content'] == text for m in history[h0:-1]))

    # ---- 等待提示 -----------------------------------------------------

    def _show_waiting(self, seconds):
        if self.tty_err:
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
        h0 = len(self.history())
        dropped = deliver(self.base, state['input'][0], text)
        self.pending = (h0, text, dropped)
        self.wait(self.timeout_ms)

    def wait(self, timeout_ms):
        """等 pending 那句這一輪走完；中途的新訊息邊到邊印。"""
        h0, text, dropped = self.pending
        start = time.monotonic()
        deadline = start + timeout_ms / 1000
        try:
            while True:
                try:
                    history = self.history()
                    self.flush_new(history)
                    data = collect(self.base, self.env)
                    if self._done(data, history, h0, text, dropped):
                        self.pending = None
                        return
                    stop = _stopped(data, self.base)
                    if stop is not None:
                        self._clear_waiting()
                        report(*stop)
                        _err('（已投入，不要再說一次；修好後 /wait 等回話，或按 Enter 看到了沒）')
                        return
                except (AgentError, OSError, ValueError):
                    pass  # 寫到一半或暫時讀不到，下一輪再讀
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
        if word in ('quit', 'exit'):
            return False
        if handler is None:
            _err('沒有這個指令，/help 看清單（要把 / 開頭的字送給模型就打兩個 //）')
            return True
        try:
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
        data = collect(self.base, self.env)
        if rest in ('-v', '--verbose'):
            show(data, verbose=True)
            return
        if rest:
            raise AgentError('Usage', '/status 只收 -v')
        if data['state_error']:
            state = 'state 讀不到'
        else:
            b = data['batch']
            state = 'state %s  batch %s' % (data['state'], '-' if b is None else '%s %s／%s' % (
                b['kind'], b['done_n'], b['total']))
        pending = len(data['pending_inputs'])
        waiting = '  還在等上一句' if self.pending is not None else ''
        _out('health %s  %s  input %s%s' % (data['health']['message'], state,
                                            '%d 個沒收' % pending if pending else '-', waiting))

    def cmd_context(self, rest):
        count = self._number(rest, CONTEXT_RECENT)
        info = aos_agent_info.load(self.base, env=self.env)
        history = info['history']
        roles = {}
        chars = 0
        for m in history:
            roles[m['role']] = roles.get(m['role'], 0) + 1
            chars += len(m.get('content') or '')
            chars += sum(len(c['function']['arguments']) for c in m.get('tool_calls') or [])
        turns = roles.get('user', 0)  # 一則 user 算一輪
        tools = [t['function']['name'] for t in info['tools']]
        tool_chars = len(json.dumps(info['tools'], ensure_ascii=False)) if tools else 0
        _out('model  %s（池 %s）' % (info['model'], info['llm']['pool']))
        _out('system %d 字' % len(info['system']))
        _out('history %d 則，%d 字（user %d／assistant %d／tool %d）' % (
            len(history), chars, turns, roles.get('assistant', 0), roles.get('tool', 0)))
        _out('tools  %d 個，%d 字：%s' % (len(tools), tool_chars, ', '.join(tools) or '-'))
        _out('合計約 %d 字，每次問模型整份送出（記憶不會自動截短）' % (len(info['system']) + chars + tool_chars))
        if history:
            _out('最近 %d 則：' % min(count, len(history)))
            for m in history[-count:]:
                _out('  ' + self._brief(m))

    def _brief(self, m, full=False):
        role = m.get('role')
        if role == 'tool':
            return result_line(m, self.names) if not full else '[結果] ' + (m.get('content') or '')
        text = m.get('content') or ''
        calls = m.get('tool_calls') or []
        for call in calls:
            self.names[call.get('id')] = call.get('function', {}).get('name')
        parts = [text if full else _one_line(text)] if text else []
        parts += [call_line(c) for c in calls]
        return '%s: %s' % (role, ' '.join(parts))

    def cmd_history(self, rest):
        count = self._number(rest, HISTORY_DEFAULT)
        history = self.history()
        if not history:
            _out('（記憶是空的）')
            return
        # 先把前面的工具名記起來，結果行才認得失敗字串
        for m in history:
            for call in m.get('tool_calls') or []:
                self.names[call.get('id')] = call.get('function', {}).get('name')
        for m in history[-count:]:
            _out(self._brief(m, full=m.get('role') != 'tool'))

    def cmd_tools(self, rest):
        tools = aos_agent_info.load(self.base, env=self.env)['tools']
        if not tools:
            _out('（沒有工具）')
        for t in tools:
            fn = t['function']
            desc = (fn.get('description') or '').splitlines()
            _out('%s  %s' % (fn['name'], desc[0] if desc else ''))

    def cmd_wait(self, rest):
        if self.pending is None:
            self.peek()
            _out('（沒有在等的話）')
            return
        if rest:
            try:
                seconds = float(rest)
            except ValueError:
                raise AgentError('Usage', '/wait 後面要是秒數：' + rest)
            if not 0 <= seconds <= 7 * 24 * 3600:
                raise AgentError('Usage', '/wait 的秒數要在 0～604800 之間：' + rest)
            self.wait(int(seconds * 1000))
        else:
            self.wait(self.timeout_ms)

    def cmd_pause(self, rest):
        from aos_agent_pause import pause
        pause(self.base)

    def cmd_continue(self, rest):
        from aos_agent_pause import resume
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

    def run(self, prompt):
        self.banner()
        try:
            while True:
                self.peek()
                try:
                    line = input(prompt)
                except EOFError:
                    if prompt:
                        _err('')
                    return 0
                text = line.strip()
                if not text:
                    continue
                if text.startswith('/') and not text.startswith('//'):
                    if not self.slash(text):
                        return 0
                    continue
                if text.startswith('//'):
                    text = text[1:]
                try:
                    self.say(text)
                except AgentError as exc:
                    report(exc.code, exc.msg)
                except OSError as exc:
                    report('io', str(exc))
        except KeyboardInterrupt:
            self._clear_waiting()
            _err('')
            return 0
        finally:
            if self.pending is not None:
                _err('（上一句還沒回；話已投入，回話會進記憶，之後 aos-agent listen --last --target %s 看）' % self.base)


def _isatty(stream):
    try:
        return stream.isatty()
    except (AttributeError, ValueError):
        return False


def talk(agent_dir, *, timeout_ms=120000, show_calls=False, env=None):
    session = Talk(agent_dir, timeout_ms, show_calls, env)
    prompt = ''
    if _isatty(sys.stdin):
        try:
            import readline  # noqa: F401  有就用：方向鍵、歷史
        except ImportError:
            pass
        prompt = '> '
    return session.run(prompt)
