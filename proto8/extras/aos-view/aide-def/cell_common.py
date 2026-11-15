"""cell_common - agent-fsm 的格共用的開頭幾步：四格的 on_clock 看時鐘（clock_tick），brain、act 的讀 history.jsonl 與決定用哪份工具登記檔。

錯誤行由呼叫端那支的 die 印（程式名、格式照它自己），這裡只給代號與原因；hooks 模組與 warn 由呼叫端傳進來，不 import aos_flags、hooks，跟 atomic_file 一樣只靠標準庫。
"""
import json
import os


def clock_tick(hooks, stack, warn, die):
    """時鐘走到了的 on_clock hook 才跑（hooks.clock_tick）；hook 停下＝這格的錯（HookFailed／HooksBad）、退 1。"""
    try:
        hooks.clock_tick(os.environ.get("AOS_CD") or ".", stack, warn=warn)
    except (hooks.HookFailed, hooks.HooksBad) as e:
        die(type(e).__name__, str(e))


def read_history(history_path, die):
    """對話：一行一則 OpenAI message（C-46、P-41），只附加；檔不在＝空；有一行不是 JSON 物件或讀不了＝HistoryBad。"""
    history = []
    try:
        with open(history_path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if line.strip():
                    try:
                        m = json.loads(line)
                    except ValueError:
                        m = None
                    if not isinstance(m, dict):
                        die("HistoryBad", "history.jsonl line %d is not a JSON object" % n)
                    history.append(m)
    except FileNotFoundError:
        pass
    except OSError as e:
        die("HistoryBad", "cannot read history.jsonl: %s" % e)
    return history


def tools_file(opts, files, stack, die):
    """用哪份 aos-tools 登記檔：--tools（相對從 AOS_CD 算；不在＝ToolsMissing），否則 interfaces.json 宣告的 tools——
    $AOS_STACK/<宣告相對路徑> 在＝這隻自己那份，否則定義那份；都沒有＝None。"""
    tools_rel = opts.get("--tools", files.get("tools"))
    tools_file = os.path.join(os.environ.get("AOS_CD") or ".", tools_rel) if tools_rel else None
    if "--tools" in opts and not os.path.isfile(tools_file):
        die("ToolsMissing", "tool registry not found: %s" % tools_file)
    own = os.path.join(stack, tools_rel) if tools_rel and "--tools" not in opts else None
    if own and os.path.isfile(own):                   # 這隻自己那份（$override 定義那份，aos-tools 疊；11-10 aos-tools-cli 步 4）在就用它
        tools_file = own
    return tools_file
