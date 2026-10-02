"""aos-daemon 的設定檔：讀、整份展開指示詞、拆成每項的 `Item`（從 aos_daemon.py 拆出；plan m3 步驟 1）。

對外照舊從 aos_daemon import（那裡 re-export）。
"""
import json
import os
import threading
import time

from aos_directives import Context, is_option_object, load_document, resolve_located

INST_MARK = "<inst>"
OUTPUT_MAX = 1 << 20            # exec_output_max_bytes 的預設（第十九批）


class Item:
    """清單的一項：`inst` 字面值＝`insts` 物件的鍵（原樣交給 aos-exec、也原樣印出）；index＝鍵的位置（從 0 起）。"""

    def __init__(self, index, inst, interval_ms, stop_on_nonzero, err_path, out_path=None, cgroup=None, user=None,
                 out_max=OUTPUT_MAX):
        self.index = index
        self.inst = inst
        self.interval_ms = interval_ms
        self.stop_on_nonzero = stop_on_nonzero
        self.err_path = err_path        # aos-exec 的 stderr 寫到哪（絕對路徑）；None＝丟掉（使用者 2026-10-01）
        self.out_path = out_path        # aos-exec 的 stdout 寫到哪；None＝丟掉
        self.env = None                 # 開 aos-exec 的環境；None＝照 daemon 的（控制模組沒掛）
        self.cgroup = cgroup or {}      # 這一項的 cgroup 上限 {檔名: 值}（設定的 "cgroup" 鍵；模組沒掛時不看）
        self.frame = None               # 這一項的 cgroup 框（絕對路徑）；None＝cgroup 模組沒掛
        self.user = user                # 帳號模組：這一項用哪個帳號跑（設定的 "account.user"）；None＝預設帳號
        self.out_max = out_max          # 第十九批：每次、每條串流最多留幾 bytes（超過丟最早的；頂層共用）
        self.doors = []                 # 第二十五批：訊息模組訂了哪幾扇門（設定的 "mq"，門名陣列；模組沒掛時不看）
        # m3n 步驟 2：以下狀態都在 cond 的鎖底下改；控制模組沒掛時只有 loop() 自己動它們
        self.cond = threading.Condition()
        self.running = False
        self.pending = False            # 叫醒記下的「跑一次」（叫幾次都只補一次）
        self.pending_keep = False       # 那次補跑帶不帶 keep_schedule（照最後一次叫醒）
        self.paused = False
        self.stopped = False            # 被 stop_on_nonzero 停掉
        self.last_exit = None
        self.last_end = None            # now() 格式的字串
        self.end_mono = None            # 上一次結束的 monotonic 時刻（重讀設定改週期時用）
        self.due = time.monotonic()     # 下次照週期該跑的時刻（monotonic）；剛開時立刻跑
        self.removed = False            # 重讀設定時被拿掉：跑完這次（若在跑）就結束執行緒
        self.mailbox = []               # 訊息模組的信箱 [信]（信＝寄的 JSON 原樣），先進先出；只在記憶體（m3m 模組四）
        # 第十九批 kill／restart：正在跑的那一次是誰（主程式開的＝程序群組 id；經 root 端開的＝請求 id）
        self.pid = None
        self.root_rid = None
        self.run_seq = 0                # 每開一次加 1（在 cond 底下）；kill 認「還是不是同一次」
        self.restart_seq = None         # restart 殺的是哪一次：那一次非 0 不算 stop_on_nonzero


def err_path_for(template, inst, start):
    """m3 步驟 1：`exec_err_path`／`exec_out_path` 換掉 `<inst>`（inst 是檔＝它字面上的 dirname，
    是資料夾＝照字面），相對路徑以起點為準。沒寫回 None（＝丟掉）。"""
    if template is None:
        return None
    if INST_MARK in template:
        is_dir = os.path.isdir(os.path.join(start, inst))
        template = template.replace(INST_MARK, inst if is_dir else (os.path.dirname(inst) or "."))
    return os.path.join(start, template)


def expand(value, ctx, position):
    """整份設定檔展開 aos 指示詞（`$ref`／`$fmt`／`$env`），一路走進物件與陣列。

    `$ref` 的相對檔名以設定檔所在的資料夾為準（含被引進來的檔裡再 `$ref`，中心路徑不換）；
    `$opt` 物件原樣留著不走進去（核心沒有吃選項的位置，留給模組）。循環鏈往下帶，引到祖先＝`ReferenceCycle`。
    """
    loc = resolve_located(value, ctx, position)
    v = loc.value
    if isinstance(v, dict) and not is_option_object(v):
        return {k: expand(x, loc.ctx, loc.position + [k]) for k, x in v.items()}
    if isinstance(v, list):
        return [expand(x, loc.ctx, loc.position + [str(i)]) for i, x in enumerate(v)]
    return v


def read_config(path):
    """讀設定檔、整份展開指示詞，回展開後的 JSON。讀不到、不是 JSON、指示詞錯都是 `DirectiveError`。"""
    doc = load_document(path)
    return expand(doc.root, Context(doc, base_dir=os.path.dirname(os.path.abspath(path))), [])


def load_config(path):
    """m3 步驟 1：讀設定檔（先展開指示詞），回 (起點資料夾, [Item])。"""
    return load_setup(path)[:2]


def load_setup(path):
    """m3 步驟 1 加 m3n 步驟 1：回 (起點資料夾, [Item], 控制模組 socket 絕對路徑或 None)。"""
    s = load_full(path)
    return s.start, s.items, s.sock


class Setup:
    """`load_full()` 的結果。`modules` 是展開後的 `modules`，但 `state` 換成狀態檔的絕對路徑
    （重讀設定比對「模組改了沒」用）；`state_data` 是狀態檔的內容（沒讀或不在＝`{"insts": {}}`）。"""

    def __init__(self, start, items, sock, modules, state_path, state_data, out_tmpl=None, err_tmpl=None,
                 mq_doors=None, lock_path=None):
        self.start, self.items, self.sock = start, items, sock
        self.mq_doors = mq_doors or {}  # 第二十五批：訊息模組的門 {門名: 絕對路徑}；沒掛＝{}
        self.lock_path = lock_path      # 第十九批：設定檔的鎖檔（絕對路徑）
        self.modules, self.state_path, self.state_data = modules, state_path, state_data
        self.out_tmpl, self.err_tmpl = out_tmpl, err_tmpl     # 頂層 exec_out_path／exec_err_path 原字（重讀比對用）

    @property
    def reload(self):
        return "reload" in self.modules

    @property
    def cgroup(self):
        return "cgroup" in self.modules

    @property
    def account(self):
        return "account" in self.modules


def _state_ref(raw, base_dir):
    """m3m 模組三：原始設定檔的 `modules.state` 必須是 `{"$ref": "<檔名>"}`（不帶 `#` 位置、不帶 `$at`），
    回 (狀態檔絕對路徑, 拿掉 state 之後的原始根)；沒寫 state 回 (None, 原始根)。
    相對檔名照其他 `$ref`，以設定檔所在資料夾為準。"""
    mods = raw.get("modules") if isinstance(raw, dict) else None
    if not isinstance(mods, dict) or "state" not in mods:
        return None, raw
    ref = mods["state"]
    if not (isinstance(ref, dict) and set(ref) == {"$ref"} and isinstance(ref["$ref"], str)
            and ref["$ref"] and "#" not in ref["$ref"]):
        raise ValueError('modules.state 要直接寫成 {"$ref": "<狀態檔>"}（不帶 # 位置）')
    rest = dict(raw, modules={k: v for k, v in mods.items() if k != "state"})
    return os.path.join(base_dir, ref["$ref"]), rest


def load_full(path, read_state=True, doors=None):
    """讀設定檔、展開指示詞，回 `Setup`。兩邊都沒有 interval_ms、`modules` 不是物件丟 ValueError；
    `modules.control` 沒寫 `socket` 自然丟錯。

    `modules.state` 先從原始檔拿出來（它指的檔第一次要寫時才建，不在時不能算 `$ref` 讀不到），
    其餘照整份展開；狀態檔在就照一般 `$ref` 展開讀進來，不在＝`{"insts": {}}`。
    `read_state=False`（重讀設定用）不讀狀態檔：重讀時以記憶體為準。
    `doors`（重讀設定用，開起來時掛了訊息模組才給）：每項的 `mq` 照開起來時的門核，不看新的 `modules.mq`
    （`modules` 改了不套用；第二十五批，AI 隊定）。"""
    doc = load_document(path)
    base_dir = os.path.dirname(os.path.abspath(path))
    ctx = Context(doc, base_dir=base_dir)
    state_path, raw = _state_ref(doc.root, base_dir)
    top = expand(raw, ctx, [])
    modules = top.get("modules", {})
    if not isinstance(modules, dict):
        raise ValueError("modules 要是物件")       # 核心只認得它；目前讀 control、reload、state
    if state_path is None and "state" in modules:   # 例如整個 modules 是 $ref 引進來的
        raise ValueError('modules.state 要直接寫成 {"$ref": "<狀態檔>"}（不帶 # 位置）')
    # 展開完才看 cwd（它也可以是 $ref 引進來的值）；相對的 cwd 以 daemon 啟動時的工作目錄為起點，不是設定檔的資料夾
    start = os.path.abspath(top.get("cwd", "."))
    # 第十九批：輸出上限只有頂層一個，各項共用（使用者：「上限必須共用，然後每項不覆蓋」）
    out_max = top.get("exec_output_max_bytes", OUTPUT_MAX)
    if isinstance(out_max, bool) or not isinstance(out_max, int) or out_max < 0:
        raise ValueError("exec_output_max_bytes 要是非負整數")
    items = []
    if "account" in modules:                        # m3m 模組五：模組沒掛時 "account" 照不認得的鍵忽略
        import aos_daemon_account
        user_of = aos_daemon_account.item_user
    else:
        user_of = lambda entry: None
    sock = None
    if "control" in modules:                        # m3n：有寫就開；socket 相對以起點為準
        sock = os.path.abspath(os.path.join(start, modules["control"]["socket"]))
        import aos_daemon_ctl                       # 第十九批：kill_grace_ms 不合算設定錯
        aos_daemon_ctl.grace_of(modules["control"])
    mq_doors = {}
    if doors is not None:                           # 重讀：照開起來時的門
        import aos_daemon_mq
        mq_doors = doors
        doors_of = lambda entry: aos_daemon_mq.item_doors(entry, doors)
    elif "mq" in modules:                           # 第二十五批：門名 → 路徑；每項的 mq 是訂了哪幾扇門
        import aos_daemon_mq
        mq_doors = aos_daemon_mq.doors_of(modules["mq"], start, sock)
        doors_of = lambda entry: aos_daemon_mq.item_doors(entry, mq_doors)
    else:                                           # 模組沒掛時 "mq" 照不認得的鍵忽略
        doors_of = lambda entry: []
    # insts 是物件：鍵＝inst 字面值、值＝該項設定（可為 {}）；位置照鍵的順序（JSON 讀入保序）（使用者 2026-10-01）
    for i, (inst, entry) in enumerate(top["insts"].items()):
        interval = entry.get("interval_ms", top.get("interval_ms"))
        if interval is None:
            raise ValueError("insts 的 %s 沒有 interval_ms，頂層也沒有" % json.dumps(inst, ensure_ascii=False))
        stop = entry.get("stop_on_nonzero", top.get("stop_on_nonzero", False))
        items.append(Item(i, inst, interval, stop,
                          err_path_for(top.get("exec_err_path"), inst, start),
                          err_path_for(top.get("exec_out_path"), inst, start),
                          entry.get("cgroup"), user_of(entry), out_max))
        items[-1].doors = doors_of(entry)
    state_data = {"insts": {}}
    if state_path is not None:
        modules = dict(modules, state=state_path)
        if read_state and os.path.exists(state_path):
            state_data = expand(doc.root["modules"]["state"], ctx, ["modules", "state"])
    lock = top.get("lock_path")                     # 第十九批：相對以設定檔所在資料夾為準
    if lock is not None and not (isinstance(lock, str) and lock):
        raise ValueError("lock_path 要是非空字串")
    lock_path = os.path.join(base_dir, lock) if lock else os.path.abspath(path) + ".lock"
    return Setup(start, items, sock, modules, state_path, state_data,
                 top.get("exec_out_path"), top.get("exec_err_path"), mq_doors, lock_path)

