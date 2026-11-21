"""hooks - agent 的 hook 共用模組：事件表、讀 hooks 清單（定義那份疊 stack 那份、驗形狀，含 on_clock 格的鍵）、tool_added 的名單；挑出符合事件的 hook、用 aos-exec 跑、解回話交給共用引擎 py/aos/hook_run.py。

圖紙：proto8/thinking/2026-11/10/self-family/hook/01-圖紙.md（使用者 11-10 晚「self_hook……事件發生時，執行指定aos函數」）。
發事件的程式（agent-fsm 的四格、aos-eca-turn、aos-mcp）經 agent_hooks.open 的遙控器叫這裡；aos-agent hook、編譯（agent_spec_hooks）
直接用讀清單、驗格那幾個。on_clock 的看時鐘在 hook_clock.py（11-20 從這裡搬出，只因檔案大小）。純標準庫，lib 不 import py；
不印東西、不 sys.exit：錯丟 HooksBad（清單壞）／HookFailed（on_error stop 的 hook 自己失敗），由呼叫方說自己那一行。
引擎是 py/aos/hook_run.py（11-13 kernel-framework 批 1b；通用 kernel 框架也用它）：驗格的共通鍵、補預設值、比 condition、寫 event.json、
用 aos-exec 跑 handler、解回話、on_error 都在那裡，只有一份。這裡留 agent 自己的：事件表、清單從哪讀與兩份怎麼疊、
on_clock 專用的鍵與檢查、content 的回話要求、tool_added 的名單。HooksBad／HookFailed 就是引擎的那兩個類別。

對外（另兩條線要用，改了要一起改）：
    EVENTS[事件] = {"condition": 事件 JSON 裡拿來比 condition 的欄位名或 None（不收 condition）,
                    "intercept": 能改的鍵（tuple）, "block": 能不能攔（結束碼 10）}
                    11-20 第 3 刀起由宣告算出（aos 自己帶的 aos-loop、agent-fsm、eca、mcp 四份合起來、去掉 not_fired_yet）；
                    只拿來驗清單的事件名與給 gdb 列種類（第 6 刀才改讀宣告）
    points(def_folder) -> 這隻 interfaces.json 的 hook_points 讀出的點（hook_point.for_definition）；沒寫＝{}；壞＝HooksBad
    table(def_folder) -> 這隻發事件用的引擎表（有 hook_points＝由它算；沒寫＝EVENTS，load 會擋有 hook 的）
    DEFAULTS = {"intercept": True, "async": False, "on_error": "stop", "timeout_ms": 60000}
                    （intercept 預設開：11-10 深夜使用者「3.幫我改成預設是開」；不能改的事件、async 的 hook＝自然不看回話、不報錯）
    格的鍵（11-10 深夜改名，使用者「hook這塊，主要走A, 但filter改condition。」）：event、handler、condition、intercept、async、on_error、timeout_ms
    declared(def_folder) -> 宣告的相對路徑字串 | None
    load(def_folder, stack) -> {名字: 格}；格＝原格的鍵＋DEFAULTS 補齊＋"from"（來自哪份檔的絕對路徑）＋"base"（解 exec 相對路徑的資料夾）；
                    有 hook 卻沒寫 hook_points＝HooksBad
    nulled(def_folder, stack) -> [stack 那份設成 null 的名字]（排好）
    validate_entry(entry) -> None；不對丟 HooksBad（原因不含名字，呼叫方自己加）
    check_clock(entry) -> None：只驗 on_clock 專用鍵的值（validate_entry 的後半）；不對丟 HooksBad
    layers(def_folder, stack) -> [定義那份, stack 那份] 的清單絕對路徑；沒宣告 hooks＝[]
    has(event, def_folder, stack) -> 有沒有 on==event 的 hook（不看 match）
    fire(event, data, def_folder, stack, warn=None) -> {"data": 改過的 data（新 dict）, "changed": [改過的鍵],
                    "blocked": bool, "hook": 攔下的 hook 名或 None, "text": 攔下那個 hook 的 stdout（字串）或 ""}
    tools_added(stack, tools, has_hook) -> [(name, path)]：這次比上次多出來的工具（tools＝[(name, path)]）
    hook 遙控器（11-20 hook 介面第 2 刀，thinking/2026-11/20/aos-hook-plan-1120/04）：agent_hooks.open(def_folder, stack, fail, warn)
                    ＝開一次、之後每個點一行（fire、has、names、clock_tick、take_letter、guard_tool、announce_tools），錯一律交 fail。
                    發事件的程式都改叫它了（第 2 刀後半）；第 3 刀起遙控器的點讀這隻的 hook_points。fire、has 這兩個模組函式
                    還留著（hook_clock 與幾支測試在用），表也照 table(def_folder)。

11-11（thinking/2026-11/11/clock-hook）：事件多 after_start、after_stop（aos-loop 的 on_start／on_stop 發；11-21 起經 aos-hook fire --agent，
使用者「hook 要加的事件：起來與停下」）與 on_clock（看時鐘在 hook_clock.py）。on_clock 才收的鍵＝CLOCK_KEYS。
11-15（compact-1115）：on_clock 的格可以多寫一個 config（任意 JSON，hooks.py 不驗），原樣放進事件的 config 給 handler 自己讀
（context_wrap 的門檻就寫在這裡；stack 那份同名蓋過＝這隻自己改）。
"""
import json
import os

from aos.declared_files import declared_files

from aos import hook_point
from aos import hook_run   # 共用引擎（11-13 kernel-framework 批 1b）

AGENT_PROVIDERS = ("agent-fsm", "eca", "mcp", "aos-loop")   # aos 自己帶、agent 一家用的提供者（hook_point.PROVIDERS 的名字；這個順序＝錯誤句列事件的順序，身體的在前）


def _shipped():
    """aos 自己帶的 agent 一家宣告合起來、去掉 not_fired_yet 的點（還沒有程式發）。"""
    points = hook_point.read([hook_point.provider_path(p) for p in AGENT_PROVIDERS])
    return {n: p for n, p in points.items() if "not_fired_yet" not in p}


# 11-20 hook 第 3 刀：不再寫死，由宣告算出（aos-hook-plan-1120/12：留到第 6 刀 gdb 改讀宣告才拿掉）。
# 驗清單的格用它（事件名要是 agent 一家有人發的）；這隻 agent 實際發哪些點看它自己 interfaces.json 的 hook_points（points()）。
# 掛到這隻不會發的事件＝掛得上、不跑、不報錯（使用者 11-20 待裁第 5 題「照舊不管」）。
EVENTS = hook_point.engine_table(_shipped())
CLOCK_EVENT = "on_clock"                        # 事件名集中在這裡（11-11 先代定 clock_due，使用者改裁 on_clock）
CLOCK_KEYS = ("clock", "every_cycles", "every_ms")   # 只有 on_clock 收
DEFAULTS = hook_run.DEFAULTS                     # {"intercept": True, "async": False, "on_error": "stop", "timeout_ms": 60000}
BLOCK = hook_run.BLOCK                           # 10：攔下（N-43：10＝「不要」，不是錯）
CELLS = hook_run.CELLS                           # 小格：$AOS_STACK/hooks/<名>/
SEEN = "hook_tools_seen.json"                    # tool_added 上次看到的工具名單


HooksBad = hook_run.HooksBad                     # hooks 清單（或 interfaces.json 的宣告）讀不了、形狀不對（ValueError 的子類）
HookFailed = hook_run.HookFailed                 # on_error: stop 的 hook 自己失敗（結束碼不是 0／10、逾時、起不來、回話不合）


def declared(def_folder):
    """interfaces.json 的 aos-agent 宣告的 hooks 相對路徑；沒宣告＝None。宣告壞＝HooksBad。"""
    try:
        return declared_files(def_folder).get("hooks")
    except ValueError as e:
        raise HooksBad(str(e)) from e


def validate_entry(entry):
    """單格驗證；不認得的鍵不管（C-48）。不對＝HooksBad。共通的鍵由引擎驗，on_clock 專用的鍵排在它後面驗
    （一格同時有兩種錯時先報共通鍵的那句；使用者 11-13「4可以。」）。"""
    hook_run.validate_entry(entry, EVENTS)
    if entry["event"] == CLOCK_EVENT:
        check_clock(entry)
    else:
        for key in CLOCK_KEYS:
            if key in entry:
                raise HooksBad("%s is only for event %s" % (key, CLOCK_EVENT))


def check_clock(entry):
    """on_clock 專用鍵的值（every_cycles／every_ms 恰好一個、正整數；clock 非空字串）；別的事件的格＝不管。不對＝HooksBad。
    validate_entry 與照宣告讀清單的（aos-hook --agent，宣告的 entry_keys 已擋「只能寫在 on_clock」）共用。"""
    on = entry["event"]
    if on != CLOCK_EVENT:
        return
    given = [k for k in ("every_cycles", "every_ms") if k in entry]
    if len(given) != 1:
        raise HooksBad("event %s needs exactly one of every_cycles, every_ms" % on)
    n = entry[given[0]]
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        raise HooksBad("%s must be a positive integer" % given[0])
    if "clock" in entry and not (isinstance(entry["clock"], str) and entry["clock"]):
        raise HooksBad("clock must be a non-empty string (a proc name, or the path of a clock file or of a folder with one)")


def _read(path):
    """一份清單 → {名字: 格或 None}；不在＝{}。"""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise HooksBad("cannot read %s: %s" % (path, e)) from e
    if not isinstance(doc, dict):
        raise HooksBad("%s must be a JSON object" % path)
    table = doc.get("hooks", {})
    if not isinstance(table, dict):
        raise HooksBad("hooks in %s must be a JSON object" % path)
    for name, entry in table.items():
        try:
            hook_run.validate_name(name)
        except HooksBad as e:
            raise HooksBad("hook name %r in %s %s" % (name, path, e)) from None
        if entry is not None:
            try:
                validate_entry(entry)
            except HooksBad as e:
                raise HooksBad("hook %s in %s: %s" % (name, path, e)) from None
    return table


def layers(def_folder, stack):
    """[定義那份, stack 那份] 的絕對路徑（interfaces.json 宣告的 hooks 相對路徑，各從兩處算）；沒宣告＝[]。"""
    rel = declared(def_folder)
    if not rel:
        return []
    return [os.path.abspath(os.path.join(def_folder, rel)), os.path.abspath(os.path.join(stack, rel))]


def _layers(def_folder, stack):
    paths = layers(def_folder, stack)
    if not paths:
        return None, {}, {}
    return tuple(paths), _read(paths[0]), _read(paths[1])


def points(def_folder):
    """這隻 agent 宣告的 hook 點（interfaces.json 的 hook_points，hook_point.for_definition）；沒寫＝{}。宣告壞＝HooksBad。"""
    try:
        return hook_point.for_definition(def_folder)
    except hook_point.PointsBad as e:
        raise HooksBad(str(e)) from None


def load(def_folder, stack):
    """定義那份疊 stack 那份（同名蓋過、null＝關掉）；回 {名字: 格}，格帶 from／base 與預設值。沒宣告或檔不在＝{}。
    有 hook 生效卻沒寫 hook_points＝HooksBad（沒有點可掛；第 3 刀起不留「沒寫就當全部」）。"""
    paths, base, top = _layers(def_folder, stack)
    out = {}
    for path, table in ((paths and paths[0], base), (paths and paths[1], top)):
        for name, entry in table.items():
            if entry is None:
                out.pop(name, None)
                continue
            out[name] = hook_run.complete(entry, path)
    if out and not points(def_folder):
        raise HooksBad("%s declares no hook_points, so hooks %s have no point to listen to: add \"hook_points\" "
                       "to its aos-agent (like [{\"provider\": \"aos-loop\"}, {\"provider\": \"agent-fsm\"}])"
                       % (os.path.join(def_folder, "interfaces.json"), ", ".join(sorted(out))))
    return out


def table(def_folder):
    """這隻 agent 發事件用的引擎表：宣告了 hook_points＝那幾份算出的；沒寫＝EVENTS（反正沒人能掛，load 會擋）。"""
    declared_points = points(def_folder)
    return hook_point.engine_table(declared_points) if declared_points else EVENTS


def nulled(def_folder, stack):
    """stack 那份設成 null 的名字（排好；給 aos-agent hook ls -l）。"""
    return sorted(n for n, e in _layers(def_folder, stack)[2].items() if e is None)


def has(event, def_folder, stack):
    return any(e["event"] == event for e in load(def_folder, stack).values())


def _check(event, key, value):
    """hook 改回來的值合不合（引擎的 check 口）：content 要是字串，before_queue 的還不能是空的。不合丟 ValueError。"""
    if key == "content" and not (isinstance(value, str) and (value.strip() or event != "before_queue")):
        raise ValueError("content in stdout must be a %sstring" % ("non-empty " if event == "before_queue" else ""))


def fire(event, data, def_folder, stack, warn=None, only=None, entries=None):
    """跑 on==event、match 符合的 hook（照名字排序；前一個改過的後一個看得到；被攔下就停）。
    沒宣告、沒有符合的＝什麼都不做（不起子行程）。warn＝收一行英文的函式（on_error continue 時叫）；None＝不說。
    only＝只跑這些名字（clock_tick 一個一個發）；entries＝已讀好的清單（不重讀）。跑的那段在引擎 hook_run.fire。"""
    events = table(def_folder)
    if event not in events:
        raise ValueError("unknown hook event %s" % event)
    entries = load(def_folder, stack) if entries is None else entries
    return hook_run.fire(event, data, entries, stack, events, warn=warn, only=only, check=_check)


def tools_added(stack, tools, has_hook):
    """tool_added 的「多了誰」：有 hook 生效＝記這次的名單到 $AOS_STACK/hook_tools_seen.json，回比上次多出來的 [(name, path)]；
    第一次（檔不在或壞了）只記不回；沒有 hook＝刪檔、回 []。寫不成丟 OSError。"""
    path = os.path.join(stack, SEEN)
    if not has_hook:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return []
    try:
        with open(path, encoding="utf-8") as f:
            seen = json.load(f)
        if not (isinstance(seen, list) and all(isinstance(x, str) for x in seen)):
            seen = None
    except (OSError, ValueError):
        seen = None
    names = sorted({n for n, _ in tools})
    if seen != names:
        tmp = os.path.join(stack, ".%s.%d.tmp" % (SEEN, os.getpid()))
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(names, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    if seen is None:
        return []
    return [(n, p) for n, p in tools if n not in set(seen)]
