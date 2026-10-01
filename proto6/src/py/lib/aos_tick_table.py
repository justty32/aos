"""aos-tick 的任務表（`<工作資料夾>/<狀態資料夾>/tasks.json`，預設 `.aos/tasks.json`）：開格讀一次、只解到 `tasks` 這層，
跑到某項時才把「頂層預設＋這一項」合併、展開成 inst（B-620、P-202）。

〔使用者方向 2026-10-01，待統一更新 spec〕開格只做極簡檢查（`check_table()`），不過就丟 `TableInvalid`，
tick 印一行 `bad_table: …`、回 1（算 tick 自己的錯；在換紀錄之前，不佔 seq）：讀得到、合法 JSON、頂層是物件、有 `tasks` 陣列；
每項（解一層後）是物件；合併頂層預設後有 `argv`。讀表時那一層解不開、`modules` 整個展開失敗也算 `bad_table`。其他一概不查（外層與每項的
`_metainfo`、`id`、`kind` 填不填與它們的值、值的型別、`id` 重複、陌生鍵如 `group`、`needs`、`methods`）。

〔使用者裁定 2026-10-01〕頂層 `_metainfo` 不是必填（可省，寫了也不看）。每項的 `_metainfo` 照 inst（aos-exec）的規則：
可省，沒寫＝posix 第 1 版；寫了就照 inst 規則驗（`aos_inst._metainfo`）——跑到那一項、合併後交給 `aos_inst.load_obj` 時才驗，
驗不過跟其他「跑到某項展開失敗」一樣：`load_obj` 丟錯、tick 自然丟錯回 1。讀表時不看。
沒有 `id` 的項：id＝它在 `tasks` 陣列的位置（從 0 起）轉字串，例如 "3"；跟別項撞了不管（使用者：「默認不重複」）。
不看 `user`（照 tick 自己的帳號跑，不回 125）。跑到某項才展開成 inst，那時 `load_obj` 丟錯就自然丟錯回 1。

〔使用者 2026-10-01〕頂層預設值與「只展開到 tasks」：

- 頂層可放 inst 的七個欄位（`DEFAULT_KEYS`：`argv`、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit`）當每一項的預設。
  頂層 `_metainfo` 是整份表的格式標記、`id`／`kind` 是 aos 欄位，都**不是**預設；頂層其他鍵當陌生鍵忽略（也不解）。
- 頂層可選 `modules`（使用者 2026-10-01：「tasks.json頂層也應該有modules。」比照 daemon 設定檔）：放 tick 模組的設定，
  一個模組一個鍵；目前 tick 沒有任何模組，核心照收不理。不是 inst 欄位，**不當預設合併**。〔使用者裁定 2026-10-01〕
  讀表時**整個展開**指示詞（跟 daemon 設定檔的 `expand()` 同一做法：一路走進物件與陣列，`$opt` 物件原樣留），
  展開失敗＝`bad_table`、回 1；型別不查。`$ref:""`／`#…` 指整份 tasks.json、相對檔名以工作資料夾為起點（跟讀表其他部分一致）。
- 淺層合併：項自己寫了某個鍵就整個蓋過頂層那個鍵（`envs` 也整包換掉，不逐變數合併）。
- 頂層 `cwd` 不改 tick 自己的 cwd（tick 永遠在工作資料夾跑），只是任務的預設 cwd；相對路徑以工作資料夾為起點。
- 讀表時（`read_table`）：整份文件是指示詞就先解；`tasks` 與七個預設鍵的值各解一層（`modules` 整個展開，見上）（`$ref`／`$fmt`／`$env`
  走到不是指示詞為止，選項物件 `$opt` 原樣留）；`tasks` 每一元素也解一層（整項 `$ref`）。這一步用
  `Document(表的路徑, 整份)`＋`base_dir=工作資料夾`，所以相對檔名以工作資料夾為中心、`$ref:""`／`#…` 指整份 tasks.json。
- 值的內部（`envs` 裡某個值的 `$env`、`argv` 元素的 `$fmt`、`cwd` 的 `$opt mkdir`…）讀表時**不解**。
- 跑到某項時（`load_inst`）：合併結果是一份獨立的純記憶體 inst，交給從 proto5 複製來的 `aos_inst.load_obj`
  （不改它；它跟 proto5 一樣不認得頂層 `user`，當陌生鍵忽略）照 inst 規則展開：`cwd` 先解、以工作資料夾為中心，
  其他欄位以解出的 cwd 為中心。所以合併後這一項裡的 `$ref:""`／`#…` 指**合併後的這一項**，
  不是整份 tasks.json，也不是預設值原本來自的那個檔。
"""
import json

import aos_inst
from aos_directives import Context, DirectiveError, Document, is_option_object, resolve_located

__all__ = ["TABLE_NAME", "DEFAULT_KEYS", "Table", "TableInvalid", "read_table", "check_table", "merge", "load_inst"]

TABLE_NAME = "tasks.json"          # 放在狀態資料夾（預設 `.aos`，見 aos_dirname）裡
DEFAULT_KEYS = aos_inst.FIELDS     # 頂層能當預設的鍵：inst 的七個欄位


class TableInvalid(Exception):
    """任務表不合極簡檢查；`str(e)` 是一行白話。"""


class Table:
    """讀好的任務表：`defaults`（頂層預設，已解一層）、`items`（每項，已解一層的物件）、`ids`（id 串列）、
    `modules`（頂層 `modules` 整個展開後的值，沒寫＝None；核心不用）。"""

    def __init__(self, defaults, items, ids, modules=None):
        self.defaults, self.items, self.ids, self.modules = defaults, items, ids, modules


def read_table(table, cwd):
    """讀這一格的任務表 `table`（絕對路徑）、解到 `tasks` 這層並做極簡檢查；回 `Table`。
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
    `path`＝表的路徑（`$ref:""`／`#…` 指它；None＝純記憶體）。回 `Table`。"""
    ctx = Context(Document(path, doc), base_dir=cwd)
    top = _one_layer(doc, ctx, [], "整份任務表")
    if not isinstance(top.value, dict):
        raise TableInvalid("任務表頂層要是物件、要有 tasks 陣列")
    root = top.value
    defaults = {}
    for key in DEFAULT_KEYS:
        if key in root:
            defaults[key] = _one_layer(root[key], top.ctx, top.position + [key], "頂層 %s" % key).value
    modules = None
    if "modules" in root:          # 核心照收不理：整個展開（展開失敗＝bad_table），不看型別、不當預設
        try:
            modules = _expand(root["modules"], top.ctx, top.position + ["modules"])
        except DirectiveError as e:
            raise TableInvalid("頂層 modules 展開不了：%s" % e)
    if "tasks" not in root:
        raise TableInvalid("任務表頂層要是物件、要有 tasks 陣列")
    tasks = _one_layer(root["tasks"], top.ctx, top.position + ["tasks"], "tasks")
    if not isinstance(tasks.value, list):
        raise TableInvalid("任務表頂層要是物件、要有 tasks 陣列")
    items, ids = [], []
    for i, raw in enumerate(tasks.value):
        item = _one_layer(raw, tasks.ctx, tasks.position + [str(i)], "tasks[%d]" % i).value   # 整項 `$ref` 在這裡展開
        if not isinstance(item, dict):
            raise TableInvalid("tasks[%d] 要是物件" % i)
        if "argv" not in item and "argv" not in defaults:
            raise TableInvalid("tasks[%d] 缺了 argv（項自己沒寫、頂層也沒有）" % i)
        items.append(item)
        ids.append(item["id"] if "id" in item else str(i))
    return Table(defaults, items, ids, modules)


def _one_layer(value, ctx, position, what):
    """解一層：跟著 `$ref`／`$fmt`／`$env` 走到不是指示詞為止（選項物件原樣留），不走進容器裡面。"""
    try:
        return resolve_located(value, ctx, position)
    except DirectiveError as e:
        raise TableInvalid("%s 展開不了：%s" % (what, e))


def _expand(value, ctx, position):
    """整個展開指示詞，一路走進物件與陣列（照抄 aos_daemon.expand 的做法；`$opt` 物件原樣留）。"""
    loc = resolve_located(value, ctx, position)
    v = loc.value
    if isinstance(v, dict) and not is_option_object(v):
        return {k: _expand(x, loc.ctx, loc.position + [k]) for k, x in v.items()}
    if isinstance(v, list):
        return [_expand(x, loc.ctx, loc.position + [str(i)]) for i, x in enumerate(v)]
    return v


def merge(defaults, item):
    """淺層合併：頂層預設 ＋ 這一項，項自己寫了的鍵整個蓋過。"""
    return {**defaults, **item}


def load_inst(defaults, item, cwd):
    """跑到這一項時：合併頂層預設，當成一份獨立的記憶體 inst 讀驗解（家＝工作資料夾）；回 aos_inst 的 dict。
    這一項的 `_metainfo` 也在這裡照 inst 規則驗（沒寫＝posix 第 1 版）；驗不過或展開失敗都由 `load_obj` 丟錯。"""
    return aos_inst.load_obj(merge(defaults, item), cwd)
