"""aos-tick 的任務表（`<工作資料夾>/<狀態資料夾>/tasks.json`，預設 `.aos/tasks.json`）：開格讀一次、**整份展開**（第二十批），
跑到某項時只把「頂層預設＋這一項」淺層合併、交給 `aos_inst.load_obj` 驗（B-620、P-202）。

〔使用者方向 2026-10-01〕開格只做極簡檢查（`check_table()`），不過就丟 `TableInvalid`，
tick 印一行 `bad_table: …`、回 1（算 tick 自己的錯；在換紀錄之前，不佔 seq）：讀得到、合法 JSON、頂層是物件、有 `tasks` 陣列；
每項是物件；合併頂層預設後有 `argv`；`hooks` 各掛點、`modules["tasks-blocked"]` 的形狀（同樣的規則）。任何一個要展開的鍵展開失敗也算 `bad_table`。
其他一概不查（外層與每項的 `_metainfo`、`id`、`kind` 填不填與它們的值、值的型別、`id` 重複、陌生鍵如 `group`、`needs`、`methods`）。

〔使用者裁定 2026-10-01〕頂層 `_metainfo` 不是必填（可省，寫了也不看）。每項的 `_metainfo` 照 inst（aos-exec）的規則：
可省，沒寫＝posix 第 1 版；寫了就照 inst 規則驗（`aos_inst._metainfo`）——跑到那一項、合併後交給 `aos_inst.load_obj` 時才驗，
驗不過 `load_obj` 丟錯、tick 自然丟錯回 1。讀表時不看、不解。
沒有 `id` 的項：id＝它在陣列的位置（從 0 起）轉字串，例如 "3"；跟別項撞了不管（使用者：「默認不重複」）。
不看 `user`（照 tick 自己的帳號跑，不回 125）。

**展開**〔使用者 2026-10-01 第二十批：「tasks.json改成全部解完」「除了陌生鍵和_metainfo」〕：開格時就把已知的鍵整個展開
（一路走進物件與陣列，跟 daemon 設定檔的 `expand()` 同一做法；選項物件 `$opt` 的 `$opt` 原樣留、`$val` 也展開），
用 `Document(表的路徑, 整份)`＋`base_dir=工作資料夾`：

- 整份文件本身是指示詞就先解一層；頂層的陌生鍵與 `_metainfo` 不解、原樣留。
- 頂層七個預設鍵（`DEFAULT_KEYS`：`argv`、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit`）：整個展開。
- `tasks`、`hooks` 的各掛點（`before_all`、`after_task.<id>`、`after_every_task`、`after_all`）、`modules["tasks-blocked"].insts`：
  陣列（與 `hooks`、`after_task` 物件）本身解一層，每一元素整項解一層（整項 `$ref`），再把元素裡**已知的鍵**
  （七個 inst 欄位、`id`、`kind`）整個展開；元素裡的 `_metainfo` 與陌生鍵不解（`_metainfo` 留給 `load_obj` 照 inst 規則驗）。
  `hooks` 裡不認得的鍵照收不理、不解。
- `modules`：整個展開（不看型別、不當預設）；`tasks-blocked` 只是 insts 照上一條的規則，物件裡的陌生鍵不解。

語意（第二十批改了的地方）：`$ref:""`／`#…` 一律指整份 tasks.json（整項 `$ref` 引進來的元素裡則指被引用的那份檔），
不再指「合併後的這一項」；相對檔名一律以工作資料夾為準，不以那一項的 cwd 為準；`$env`／`$fmt`／`$ref` 讀到的是開格那一刻的值，
前面的任務改了檔或環境，後面的項看不到；讀不到的 `$ref`（例如指向前面任務才會產生的檔）開格就是 `bad_table`。
跑到某項時已經沒有指示詞可解，剩下的是 inst 規則本身（路徑相對那一項的 cwd、選項物件、`_metainfo`、型別）。

- 淺層合併：項自己寫了某個鍵就整個蓋過頂層那個鍵（`envs` 也整包換掉，不逐變數合併）。
- 頂層 `cwd` 不改 tick 自己的 cwd（tick 永遠在工作資料夾跑），只是任務的預設 cwd；相對路徑以工作資料夾為起點。
- 頂層可選 `modules`（使用者 2026-10-01：「tasks.json頂層也應該有modules。」比照 daemon 設定檔）：一個模組一個鍵；
  目前 tick 只認 `tasks-blocked`（B-636，第二十批由 `tasks_blocked` 改名跟檔名一樣：`{"insts": [...]}`，發現 tasks-blocked 時跑的一串，
  結果在 `Table.on_blocked`），其他照收不理。
- 頂層可選 `hooks`（掛點；使用者 2026-10-01 第六批：「就不讓他當模組了，直接讓他變頂層key」，spec B-635）。
"""
import json

import aos_inst
from aos_directives import Context, DirectiveError, Document, is_option_object, resolve_located

__all__ = ["TABLE_NAME", "DEFAULT_KEYS", "Table", "TableInvalid", "read_table", "check_table", "merge", "load_inst"]

HOOK_POINTS = ("before_all", "after_task", "after_every_task", "after_all")   # 第十七批；紀錄的鍵也照這個順序
TABLE_NAME = "tasks.json"          # 放在狀態資料夾（預設 `.aos`，見 aos_dirname）裡
DEFAULT_KEYS = aos_inst.FIELDS     # 頂層能當預設的鍵：inst 的七個欄位
ITEM_KEYS = tuple(DEFAULT_KEYS) + ("id", "kind")   # 每一項開格時整個展開的鍵；`_metainfo` 與陌生鍵不解（第二十批）
BLOCKED_KEY = "tasks-blocked"      # B-636 模組鍵（第二十批由 tasks_blocked 改名，跟檔名一樣）


class TableInvalid(Exception):
    """任務表不合極簡檢查；`str(e)` 是一行白話。"""


class Table:
    """讀好的任務表：`defaults`（頂層預設，已整個展開）、`items`（每項，已知的鍵已整個展開）、`ids`（id 串列）、
    `modules`（頂層 `modules` 整個展開後的值，沒寫＝None；核心不用）、
    `after_all`（頂層 `hooks.after_all` 的 [(項, id)]；沒寫 `hooks` 或沒寫 `after_all`＝None，B-635）、
    `on_blocked`（`modules["tasks-blocked"].insts` 的 [(項, id)]；沒掛這個模組＝None，B-636）、
    第十七批的 `before_all`、`after_every_task`（[(項, id)] 或 None）與 `after_task`（{任務 id: [(項, id)]} 或 None）。
    `hook_points`：寫了的掛點名，照 before_all、after_task、after_every_task、after_all 的順序（紀錄用）。"""

    def __init__(self, defaults, items, ids, modules=None, after_all=None, on_blocked=None,
                 before_all=None, after_task=None, after_every_task=None):
        self.defaults, self.items, self.ids, self.modules = defaults, items, ids, modules
        self.after_all = after_all
        self.on_blocked = on_blocked
        self.before_all, self.after_task, self.after_every_task = before_all, after_task, after_every_task

    @property
    def hook_points(self):
        return tuple(p for p in HOOK_POINTS if getattr(self, p) is not None)


def read_table(table, cwd):
    """讀這一格的任務表 `table`（絕對路徑）、整份展開（第二十批）並做極簡檢查；回 `Table`。
    相對檔名以工作資料夾（cwd）為中心。"""
    try:
        with open(table, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        raise TableInvalid("%s 讀不到或不是合法 JSON：%s" % (table, e))
    return check_table(doc, cwd, table)


def check_table(doc, cwd, path=None):
    """使用者 2026-10-01：「該填的沒填，然後不符合 {"tasks":[]} 這樣的格式，其他就不檢查。」
    「最外層不用檢查_metainfo，每一項也只需要檢查argv」（頂層預設加進來後：合併後有 argv）。
    「沒寫id的時候，那就是以其在tasks陣列中的index做id。直接數字轉字串。默認不重複」
    第二十批：「tasks.json改成全部解完」「除了陌生鍵和_metainfo」——開格時把已知的鍵整個展開。
    `path`＝表的路徑（`$ref:""`／`#…` 指它；None＝純記憶體）。回 `Table`。"""
    ctx = Context(Document(path, doc), base_dir=cwd)
    top = _one_layer(doc, ctx, [], "整份任務表")
    if not isinstance(top.value, dict):
        raise TableInvalid("任務表頂層要是物件、要有 tasks 陣列")
    root = top.value
    defaults = {}
    for key in DEFAULT_KEYS:       # 頂層七個預設鍵：整個展開
        if key in root:
            defaults[key] = _full(root[key], top.ctx, top.position + [key], "頂層 %s" % key)
    modules, on_blocked = None, None
    if "modules" in root:          # 整個展開，不看型別、不當預設；tasks-blocked 的 insts 每項照任務的規則（B-636）
        mods = _one_layer(root["modules"], top.ctx, top.position + ["modules"], "頂層 modules")
        if isinstance(mods.value, dict):
            modules = {}
            for k, v in mods.value.items():
                if k == BLOCKED_KEY:
                    on_blocked, modules[k] = _tasks_blocked(mods, defaults)
                else:
                    modules[k] = _full(v, mods.ctx, mods.position + [k], "modules.%s" % k)
        else:
            modules = _full(mods.value, mods.ctx, mods.position, "頂層 modules")
    if "tasks" not in root:
        raise TableInvalid("任務表頂層要是物件、要有 tasks 陣列")
    tasks = _one_layer(root["tasks"], top.ctx, top.position + ["tasks"], "tasks")
    if not isinstance(tasks.value, list):
        raise TableInvalid("任務表頂層要是物件、要有 tasks 陣列")
    items, ids = _items(tasks, "tasks", defaults)
    found = {}
    if "hooks" in root:            # B-635：掛點；每一元素照任務的規則
        hooks = _one_layer(root["hooks"], top.ctx, top.position + ["hooks"], "hooks")
        if not isinstance(hooks.value, dict):
            raise TableInvalid("hooks 要是物件")
        for point in ("before_all", "after_every_task", "after_all"):
            if point in hooks.value:
                found[point] = _hook_list(hooks, [point], "hooks." + point, defaults)
        if "after_task" in hooks.value:     # 第十七批：{任務 id: [inst…]}；不存在的 id＝永遠不跑，不報錯
            at = _one_layer(hooks.value["after_task"], hooks.ctx, hooks.position + ["after_task"], "hooks.after_task")
            if not isinstance(at.value, dict):
                raise TableInvalid("hooks.after_task 要是物件（鍵＝任務 id）")
            found["after_task"] = {k: _hook_list(at, [k], "hooks.after_task.%s" % k, defaults) for k in at.value}
    return Table(defaults, items, ids, modules, found.get("after_all"), on_blocked,
                 found.get("before_all"), found.get("after_task"), found.get("after_every_task"))


def _hook_list(parent, path, what, defaults):
    """掛點的一串（parent.value[path[0]]）：解一層、要是陣列，每一元素照 `_items`。回 [(項, id)]。"""
    loc = _one_layer(parent.value[path[0]], parent.ctx, parent.position + path, what)
    if not isinstance(loc.value, list):
        raise TableInvalid("%s 要是陣列" % what)
    return list(zip(*_items(loc, what, defaults))) if loc.value else []


def _tasks_blocked(mods, defaults):
    """B-636 `modules["tasks-blocked"]`：`{"insts": [...]}`，每一元素照任務的規則展開。
    回 ([(項, id)], 展開後放進 `Table.modules` 的值)。物件裡其他鍵是陌生鍵，原樣留、不解。"""
    what = "modules.%s" % BLOCKED_KEY
    tb = _one_layer(mods.value[BLOCKED_KEY], mods.ctx, mods.position + [BLOCKED_KEY], what)
    if not isinstance(tb.value, dict):
        raise TableInvalid("%s 要是物件" % what)
    if "insts" not in tb.value:
        raise TableInvalid("%s 要有 insts 陣列" % what)
    insts = _one_layer(tb.value["insts"], tb.ctx, tb.position + ["insts"], what + ".insts")
    if not isinstance(insts.value, list):
        raise TableInvalid("%s.insts 要是陣列" % what)
    items, ids = _items(insts, what + ".insts", defaults)
    return list(zip(items, ids)), dict(tb.value, insts=items)


def _items(loc, what, defaults):
    """`tasks`、各掛點或 `modules["tasks-blocked"].insts` 的每一元素：整項解一層（整項 `$ref` 在這裡展開）、要是物件；
    已知的鍵（inst 七個欄位、`id`、`kind`）整個展開，`_metainfo` 與陌生鍵原樣留、不解（第二十批）；
    合併預設後要有 argv。回 (項串列, id 串列)；沒寫 id 的用位置轉字串。"""
    items, ids = [], []
    for i, raw in enumerate(loc.value):
        name = "%s[%d]" % (what, i)
        one = _one_layer(raw, loc.ctx, loc.position + [str(i)], name)
        if not isinstance(one.value, dict):
            raise TableInvalid("%s 要是物件" % name)
        item = {k: (_full(v, one.ctx, one.position + [k], "%s.%s" % (name, k)) if k in ITEM_KEYS else v)
                for k, v in one.value.items()}
        if "argv" not in item and "argv" not in defaults:
            raise TableInvalid("%s 缺了 argv（項自己沒寫、頂層也沒有）" % name)
        items.append(item)
        ids.append(item["id"] if "id" in item else str(i))
    return items, ids


def _one_layer(value, ctx, position, what):
    """解一層：跟著 `$ref`／`$fmt`／`$env` 走到不是指示詞為止（選項物件原樣留），不走進容器裡面。"""
    try:
        return resolve_located(value, ctx, position)
    except DirectiveError as e:
        raise TableInvalid("%s 展開不了：%s" % (what, e))


def _full(value, ctx, position, what):
    """整個展開，失敗＝`TableInvalid`。"""
    try:
        return _expand(value, ctx, position)
    except DirectiveError as e:
        raise TableInvalid("%s 展開不了：%s" % (what, e))


def _expand(value, ctx, position):
    """整個展開指示詞，一路走進物件與陣列（照 aos_daemon.expand 的做法）。
    第二十批「全部解完」：選項物件（`$opt`）的 `$opt` 原樣留，但 `$val` 也整個展開，所以展開完只剩選項物件、沒有取值指示詞。"""
    loc = resolve_located(value, ctx, position)
    v = loc.value
    if is_option_object(v):
        if "$val" not in v:
            return v
        return dict(v, **{"$val": _expand(v["$val"], loc.ctx, loc.position + ["$val"])})
    if isinstance(v, dict):
        return {k: _expand(x, loc.ctx, loc.position + [k]) for k, x in v.items()}
    if isinstance(v, list):
        return [_expand(x, loc.ctx, loc.position + [str(i)]) for i, x in enumerate(v)]
    return v


def merge(defaults, item):
    """淺層合併：頂層預設 ＋ 這一項，項自己寫了的鍵整個蓋過。"""
    return {**defaults, **item}


def load_inst(defaults, item, cwd):
    """跑到這一項時：合併頂層預設，當成一份獨立的記憶體 inst 讀驗（家＝工作資料夾）；回 aos_inst 的 dict。
    第二十批起內容在開格時已整個展開（只剩選項物件），`load_obj` 只做驗證、拆選項與路徑換算。
    這一項的 `_metainfo` 也在這裡照 inst 規則驗（沒寫＝posix 第 1 版）；驗不過由 `load_obj` 丟錯。"""
    return aos_inst.load_obj(merge(defaults, item), cwd)
