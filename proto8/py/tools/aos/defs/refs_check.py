"""refs_check - defs check 的「叫的東西在不在」：工具路徑、會被執行的程式（入口、loop、狀態格、hook）、腦設定的型別（線 aos-check-refs-1119）。

使用者 11-19 下午選項框（對照 C 第 1 題）選「只放進檢查指令」：「編譯不管，跑 agent_def check 才查。要記得跑。」——agent.py --compile 不動。
缺口出處：proto8/thinking/2026-11/19/aos-vs-c-1119 的 G1。規則照執行時：
- 工具：交給 aos-tools --file 表 ls -l（agent 跑起來拿工具清單的同一支，$override 照疊、指示詞照解）；它標 broken 的那支＝problem
  （執行時那支會被略過、只在 stderr 留一行，腦看不到它）。
- 程式：入口（aos-agent.entry）的 argv；入口是 aos-loop／aos-fsm 時跟著讀它的設定檔：loop 的 exec、on_start、on_stop、on_before_run、on_after_run，exec 指到的
  狀態表每格的 exec；被勾清單（interfaces.json 最外層 hookeds 的相對檔，11-21）每格的 handler。相對路徑照執行時的基準：單子（{"argv": …}）從它的 cwd 欄、沒寫從寫它的檔的
  資料夾；字串目標、[目標, 參數…] 的目標與 handler 從寫它的檔的資料夾；aos-exec 的「補找 .json」「檔#/指標」照認。
  argv 是任意命令列，只查分得出是檔的位置：argv[0]、直譯器（python3、bash…）後第一個不是旗標的字（-m、-c、-e 之後不查）、aos-loop／aos-fsm 的
  設定檔，以及任何位置寫成 {"$env": "AOS_HOME", "$path": …} 的（std 的檔不會是輸出）。
- 指示詞：{"$env": X, "$path": P}＝X 的值接上 P（同 aos-directive 的字串拼接）；AOS_CD／AOS_CF＝寫它的檔的資料夾／檔本身（執行時 aos-loop、aos-fsm 給的值）；
  AOS_STACK、AOS_CO 只在執行時才有＝不查；其他變數這裡沒設＝warning（照實說沒查，不當 problem）。只有 $env 沒有 $path 的、$ref 等其他寫法不查。
  AOS_HOME 沒設時用放這份 lib 的資料夾（同 catalog 的 tool-packs 合併）。
- 指令名（不帶 /）在這裡的 PATH 上找不到＝warning（agent 跑時的 PATH 可能不同）。
- 腦設定：llm.json 每個鍵照執行時 brain.py 的 llm_settings.body_fields 轉型（用 $AOS_HOME/lib/aos/apps/agent_fsm/llm_settings.py；不執行定義夾裡的程式），
  轉不了＝problem；轉完 max_tokens < 1、temperature < 0、top_p 不在 0～1＝problem；interfaces.json 有 llm_keys 時，不在裡面的鍵（description 以外）＝warning
  （body 不讀它）。model 的名字對不對要問 kernel 才知道（kernel 的 endpoint 包），這裡不查。
只讀：不寫檔、不起 agent；aos-tools 不給 AOS_STACK（不留 tooldef 快取）。"""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil

from catalog import HOME_OF_LIB, Unresolved, run_env, tools_ls

INTERP_RE = re.compile(r'(python[0-9.]*|bash|sh|dash|zsh|node|perl|ruby)\Z')
NO_SCRIPT = {'-m', '-c', '-e', '-'}          # 直譯器這些旗標後面不是檔
CONFIG_TAKERS = {'aos-loop', 'aos-fsm'}      # 唯一的位置參數是設定檔
RUNTIME_ONLY = {'AOS_STACK', 'AOS_CO', 'AOS_STACK_IN_CALLER'}
BROKEN_RE = re.compile(r'aos-tools: warning: tool (\S+) skipped: (\w+) \(([^)]*)\)')
LIMITS = {'max_tokens': (1, None), 'temperature': (0, None), 'top_p': (0, 1)}


def esc(key):
    return str(key).replace('~', '~0').replace('/', '~1')


class Refs:
    def __init__(self, defdir, problem, warn):
        self.defdir = Path(defdir)
        self.problem, self.warn = problem, warn
        self.env = run_env()
        self.seen = set()

    def shown(self, p):
        """Inside the definition: relative to it; elsewhere: as is."""
        rel = os.path.relpath(str(p), str(self.defdir))
        return str(p) if rel == '..' or rel.startswith('../') else rel

    def at(self, file, pointer):
        return '%s#%s' % (self.shown(file), pointer)

    def resolve(self, value, base, file):
        """('path', absolute path) | ('unset', NAME) | ('skip', None): the same reading aos-directive / aos-exec give it."""
        if isinstance(value, str):
            return ('path', os.path.normpath(os.path.join(str(base), value))) if value else ('skip', None)
        if not (isinstance(value, dict) and isinstance(value.get('$env'), str) and value['$env']
                and set(value) <= {'$env', '$path'} and isinstance(value.get('$path'), str)):
            return ('skip', None)
        name = value['$env']
        if name in RUNTIME_ONLY:
            return ('skip', None)
        if name == 'AOS_CD':
            got = str(Path(file).parent)
        elif name == 'AOS_CF':
            got = str(file)
        else:
            got = self.env.get(name)
            if not got:
                return ('unset', name)
        return ('path', os.path.normpath(os.path.join(str(base), got + value['$path'])))

    def need(self, value, base, file, pointer, what):
        """value must name something that exists; returns its path when it does (else None)."""
        kind, got = self.resolve(value, base, file)
        if kind == 'unset':
            self.warn('%s: %s %s not checked: environment variable %s is not set here (it is read when the agent runs)'
                      % (self.at(file, pointer), what, json.dumps(value, ensure_ascii=False), got))
            return None
        if kind != 'path':
            return None
        plain = got.split('#/', 1)[0]
        for p in (plain, plain + '.json'):     # aos-exec 補找 .json
            if os.path.exists(p):
                return p if '#/' not in got else got
        self.problem('%s: %s %s does not exist (looked for %s)'
                     % (self.at(file, pointer), what, json.dumps(value, ensure_ascii=False), self.shown(plain)))
        return None

    def argv(self, argv, cwd, file, pointer):
        """Check the places of an argv that are known to be files; returns the config file of aos-loop / aos-fsm (to follow)."""
        if not isinstance(argv, list) or not argv:
            return None
        a0, head = argv[0], None
        if isinstance(a0, str) and a0 and '/' not in a0:
            if shutil.which(a0, path=self.env.get('PATH')) is None:
                self.warn('%s: command %s is not on PATH here (it may be where the agent runs)'
                          % (self.at(file, pointer + '/0'), json.dumps(a0)))
            head = a0
        else:
            got = self.need(a0, cwd, file, pointer + '/0', 'program')
            head = os.path.basename(got) if got else None
        done, config = {0}, None
        if head and (INTERP_RE.match(head) or head in CONFIG_TAKERS):
            for i, v in enumerate(argv[1:], 1):
                if isinstance(v, str) and v.startswith('-'):
                    if v in NO_SCRIPT and head not in CONFIG_TAKERS:
                        break
                    continue
                got = self.need(v, cwd, file, '%s/%d' % (pointer, i), 'config file' if head in CONFIG_TAKERS else 'script')
                done.add(i)
                if head in CONFIG_TAKERS:
                    config = got
                break
        for i, v in enumerate(argv):
            if i not in done and isinstance(v, dict) and v.get('$env') == 'AOS_HOME':
                self.need(v, cwd, file, '%s/%d' % (pointer, i), 'file')
        return config

    def exec_value(self, value, base, file, pointer):
        """A loop / fsm exec: a target string, [target, args...], a directive, or an inst {"argv": ...}. Returns what to follow."""
        if isinstance(value, str) or (isinstance(value, dict) and '$env' in value):
            return self.need(value, base, file, pointer, 'target')
        if isinstance(value, list) and value:
            return self.need(value[0], base, file, pointer + '/0', 'target')
        if isinstance(value, dict):
            cwd = base
            if value.get('cwd') is not None:
                kind, got = self.resolve(value['cwd'], base, file)
                if kind != 'path':
                    return None
                cwd = got
            return self.argv(value.get('argv'), cwd, file, pointer + '/argv')
        return None

    def follow(self, file):
        """A loop or state-table JSON file the agent runs: check what it runs, and follow a loop's exec into its table."""
        if not file or '#/' in file:
            return
        if not file.endswith('.json') and os.path.isfile(file + '.json'):
            file += '.json'
        real = os.path.realpath(file)
        if real in self.seen or not os.path.isfile(real) or not real.endswith('.json'):
            return
        self.seen.add(real)
        try:
            with open(file, encoding='utf-8') as f:
                obj = json.load(f)
        except (OSError, ValueError, UnicodeError):
            return                               # 讀不了的設定檔由跑它的那支報（CfgBad）
        if not isinstance(obj, dict):
            return
        base = os.path.dirname(os.path.abspath(file))
        states = obj.get('states')
        if isinstance(states, dict):
            for name in sorted(states):
                cell = states[name]
                if isinstance(cell, dict) and 'exec' in cell:
                    self.exec_value(cell['exec'], base, file, '/states/%s/exec' % esc(name))
        elif 'exec' in obj:
            self.follow(self.exec_value(obj['exec'], base, file, '/exec'))
        for key in ('on_start', 'on_stop', 'on_before_run', 'on_after_run'):   # 兩個 _if 是旗標檔（不在＝沒人掛），不查
            if key in obj:
                self.exec_value(obj[key], base, file, '/' + key)

    def entry(self, agent):
        name = agent.get('entry')
        if not isinstance(name, str) or not name:
            return
        file = str(self.defdir / name)
        if not os.path.isfile(file):
            self.problem('aos-agent.entry %s does not exist' % json.dumps(name))
            return
        if not file.endswith('.json'):
            return
        try:
            with open(file, encoding='utf-8') as f:
                obj = json.load(f)
        except (OSError, ValueError, UnicodeError) as error:
            self.problem('aos-agent.entry %s cannot be read: %s' % (json.dumps(name), error))
            return
        self.seen.add(os.path.realpath(file))
        if isinstance(obj, list):               # agent-fsm 的 body.json：整份就是一個 argv
            self.follow(self.argv(obj, os.path.dirname(file), file, ''))
        elif isinstance(obj, dict) and 'argv' in obj:
            self.follow(self.exec_value({k: obj[k] for k in ('argv', 'cwd') if k in obj},
                                        os.path.dirname(file), file, ''))

    def hooks(self, agent):
        try:
            with open(self.defdir / 'interfaces.json', encoding='utf-8') as f:
                value = json.load(f).get('hookeds')
        except (OSError, ValueError, UnicodeError, AttributeError):
            return
        for name in (value if isinstance(value, list) else [value]):
            if not isinstance(name, str) or not name or os.path.isabs(name) or not (self.defdir / name).is_file():
                continue                         # 指示詞與定義外的檔不在這裡查
            file = str(self.defdir / name)
            try:
                with open(file, encoding='utf-8') as f:
                    table = json.load(f)
            except (OSError, ValueError, UnicodeError):
                continue
            if not isinstance(table, dict):
                continue
            for hook in sorted(table):
                e = table[hook]
                if isinstance(e, dict) and e.get('handler') is not None:
                    self.need(e['handler'], os.path.dirname(file), file, '/%s/handler' % esc(hook), 'handler')

    def tools(self, agent):
        name = agent.get('tools')
        table = self.defdir / name if isinstance(name, str) and name else None
        if table is None or not table.is_file():
            return                               # describe reported it
        try:
            override = '$override' in json.loads(table.read_text(encoding='utf-8'))
        except (OSError, ValueError, UnicodeError, TypeError):
            return
        try:
            stdout, stderr = tools_ls(table)
        except Unresolved as error:
            if not override:                     # 疊 $override 的那份 describe 已經報過
                self.warn(str(error))
            return
        except ValueError as error:
            if override:
                return
            if 'not on PATH' in str(error):
                self.warn('tool paths not checked: aos-tools is not on PATH (source $AOS_HOME/env.sh)')
            else:
                self.problem('%s: %s' % (name, error))
            return
        why = {m.group(1): (m.group(2), m.group(3)) for m in BROKEN_RE.finditer(stderr)}
        for line in stdout.splitlines():
            cols = line.split('\t')
            if len(cols) < 5 or cols[1] != 'broken':
                continue
            code, because = why.get(cols[0], ('Broken', 'it cannot be read'))
            src, _, pointer = cols[3].partition('#')
            self.problem('tool %s cannot be used (%s: %s): path %s resolves to %s (%s); when the agent runs it is left out of the tool list'
                         % (cols[0], code, because, cols[4], self.shown(cols[2]), self.at(src, pointer)))

    def llm(self, agent):
        name = agent.get('llm')
        if not isinstance(name, str) or not name:
            return
        try:
            cfg = json.loads((self.defdir / name).read_text(encoding='utf-8'))
        except (OSError, ValueError, UnicodeError):
            return                               # describe reported it
        if not isinstance(cfg, dict):
            return
        keys = agent.get('llm_keys') if isinstance(agent.get('llm_keys'), list) else None
        mod, missing = settings()
        unchecked = []
        for k in sorted(cfg):
            if k == 'description':
                continue
            if keys is not None and k not in keys:
                self.warn('%s: key %s is not one of llm_keys in interfaces.json (%s), so the body does not read it'
                          % (name, json.dumps(k), ', '.join(map(str, keys))))
                continue
            if mod is None:
                unchecked.append(k)
                continue
            if k != 'model' and k not in getattr(mod, 'TUNING', {}):
                continue
            try:
                _, params = mod.body_fields({k: cfg[k]})
            except ValueError as error:          # llm_settings 的原因已經說了是 llm.json 的哪個鍵
                self.problem(str(error))
                continue
            v, (lo, hi) = params.get(k), LIMITS.get(k, (None, None))
            if isinstance(v, (int, float)) and ((lo is not None and v < lo) or (hi is not None and v > hi)):
                self.problem('%s: %s must be %s, not %s' % (name, k, 'at least %s' % lo if hi is None else 'between %s and %s' % (lo, hi),
                                                            json.dumps(cfg[k])))
        if unchecked:
            self.warn('%s: %s not checked: %s' % (name, ', '.join(unchecked), missing))


_settings = {}


def settings():
    """The llm_settings module agent-fsm's brain.py uses ($AOS_HOME/lib/aos/apps/agent_fsm; AOS_HOME unset = the folder holding this lib).
    Returns (module, None) or (None, why not)."""
    home = os.environ.get('AOS_HOME') or str(HOME_OF_LIB)
    p = os.path.join(home, 'lib', 'aos', 'apps', 'agent_fsm', 'llm_settings.py')
    if p not in _settings:
        try:
            spec = importlib.util.spec_from_file_location('defs_check_llm_settings', p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _settings[p] = (mod, None)
        except (OSError, ImportError, SyntaxError) as error:
            _settings[p] = (None, 'cannot load the brain settings rules %s: %s' % (p, error))
    return _settings[p]


def check(path, agent, problem, warn):
    refs = Refs(path, problem, warn)
    refs.tools(agent)
    refs.entry(agent)
    refs.hooks(agent)
    refs.llm(agent)
