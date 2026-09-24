← [aos-agent](README.md)｜[spec 總導航](../README.md)｜實作：[lib/aos_agent_tools_dev.py](../../lib/aos_agent_tools_dev.py)｜來源：[catalog E](../../notes/2026-09-24-tool-era/catalog.md)

# 1.8（續）`tools new`／`test`／`wrap-py`（09-24 tool-era 第二波）

```
aos-agent tools new     NAME [--out DIR] [--force]
aos-agent tools test    NAME|DIR [--tool T] [--args JSON] [--case FILE] [--no-jail] [--json]
aos-agent tools wrap-py FILE.py [--only f,g] [--name PACK] [--out DIR] [--force]
```

一句話：**生工具包骨架、在牢裡驗工具包合不合契約、把 Python 函式包成工具包。** 不叫模型、**不需要 agent 家**（不收 `--target`）。包格式見 [tools.md](tools.md)，契約見 [tools README](../../tools/README.md)。

## 共通

- 用法錯退 2：參數個數、空字串、選項給錯動作、`--target`、`--args` 不是 JSON／配 `--case`／對到多支沒 `--tool`。
- 其他錯：stderr `aos-agent: 代號: 白話`，退 1。
- new／wrap-py：整包寫進 `DIR/.NAME.new-XXXX/` 再 rename 成 `DIR/NAME/`（`--force` 時舊的先改名、就位後刪）。包名 `[A-Za-z0-9_][A-Za-z0-9_-]*`，不合＝`BadName`；已在＝`AlreadyExists`（`--force` 蓋，但不蓋檔或連結）；`--out`（預設目前資料夾）不在＝`NotFound`。

## `tools new NAME`

生 `DIR/NAME/`：`NAME.json`（範例工具 `NAME`：必填 `text` string、選填 `count` integer ≥ 1；`_meta.argv`＝`["tools/NAME/NAME"]`；不寫 `_jail`＝預設關牢）、`NAME`（可執行 python3，`from _common import run, arg, fail`，本體留 `# TODO`）、`_common.py`（base 逐字副本）、`config.json`（`{"root": "workspace"}`）、`cases.json`（四條固定案例）、`README.md`。印生了哪些檔與兩行下一步。生的包 `tools test` 全過、`tools add` 後 `check` 過。

## `tools test NAME|DIR`

不含 `/`＝`proto5/tools/NAME/`；含 `/`＝那個資料夾（要有 `<資料夾名>.json`，否則 `NotFound`）。工具檔照 agent §3.3 驗，壞＝`ToolInvalid`。`--tool T` 只測一支。

**怎麼跑**：臨時假 agent 家，包複製進 `tools/NAME/`、另建 `workspace/`；照 aos-agent 送件解 `_meta`（中心＝家）、cwd＝家、stdin＝arguments、逾時＝`_timeout_ms` 封頂 30 秒。

- **預設關牢**：`aos-jail -- true` 跑得起來才算有牢；照 aos-agent 的 `jail_argv` 包成 `aos-jail --mount ws=<家>/workspace --chdir ws --net off -- <程式> …`。
- 沒 bwrap 或 `--no-jail`：直接跑（拿掉環境的 `AOS_TOOL_ROOT`／`AOS_TOOL_FENCE`）；輸出**第一行** `沒關牢（原因）：…`。

**跑什麼**（依序）：

1. 有 `wrap.json`：`run --check-import` 一次（案例 `import`，要退 0）。
2. 每支 `program`：`_meta` 解得開、`argv[0]` 的檔在且可執行（不含 `/` 時不關牢要在 PATH 上）。不過就不跑那支的案例。
3. 自動案例（必填給樣本：string `"x"`／`"x2"`…、integer 取 minimum 或 1、number 1.5、boolean true、enum 第一個、array `[]`、object `{}`）：`ok` 只給必填，**照契約回話就過**（退 0，或退 1 且最後一行 JSON、代號不是 `InternalError`／`BadArguments`）；`type:<參數>` 給錯型別（string→123，其他→`"x"`）、`missing:<參數>` 缺一個必填、`not-object` 給 `[]`，都期待 `BadArguments`。
4. 固定案例：`--case FILE`，沒給用包裡的 `cases.json`（沒有就不跑）。

stdout 有 `Traceback`、逾時、跑不起來都算沒過。

**案例檔**：JSON 陣列，每條 `{"tool", "args", "expect", "contains"?, "name"?, "files"?}`。`args` 原樣當 stdin（可以不是物件）；`expect`＝`"ok"`（退 0）或錯誤代號（退 1 且最後一行 JSON 的 `error` 是它）；`contains`＝stdout 要含的片段；`name` 省略＝`case<序號>`；`files`＝`{相對路徑: 內容}`，跑前寫進 workspace（不收絕對路徑與 `..`）。案例共用同一個 workspace。格式不對＝`CasesInvalid`。

**輸出**：開頭包名、幾支、關不關牢；每支 `描述  工具  約 N token`（`function` 那段 JSON 粗估，> 300 註明資源軸扣分）；`_common.py` 跟 base 不同＝`警告：…`（不算失敗）。然後一條一行 `PASS/FAIL  工具  案例  (毫秒)`，FAIL 下一行縮排 `期待 …；得到 退 N，最後一行：…`（截 200 字，必要時加 stderr 最後一行）；最後 `N 條，M 條沒過`。全過退 0，否則 1。

**`--json`**（第 1 版，之後只加鍵）：`{"_type": "aos_agent_tools_test", "_version": 1, "package", "dir", "jail", "jail_note", "warnings": [], "tools": [{"name", "tokens", "over"}], "cases": [{"tool", "case", "pass", "ms", "expect", "got", "exit_code"}], "total", "failed"}`。

**`--args JSON`**：只跑一次。stdout＝工具 stdout 原樣；stderr＝工具 stderr＋`（工具：退出碼 N，M 毫秒）`（沒關牢多一行）。工具退 0 就退 0，否則 1。配 `--json`：`_type: aos_agent_tools_run`，鍵 `tool jail jail_note exit_code ms timed_out error stdout stderr`。

## `tools wrap-py FILE.py`

用 `ast` 靜態讀（**不 import、不執行**），挑頂層、非底線開頭、每個參數都有支援型別註解的函式。

| 註解 | 給模型的 schema | run 驗法 |
|---|---|---|
| `str` `int` `float` `bool` | string／integer／number／boolean | int 不收 bool；float 收整數 |
| `list[X]`（不帶 X 也收） | array＋`items` | 逐項 |
| `dict[str, X]`（不帶也收） | object＋`additionalProperties` | 逐值；鍵不是 `str` 拒收 |
| `Literal[…]`（同一種型別的常值） | 那型別＋`enum` | 值與型別都要對 |
| `X \| None`／`Optional[X]`／`Union[X, None]` | 只寫 X | 收 `null` |

`typing.` 寫法與字串註解都收。一般參數、keyword-only 都行。沒預設＝必填；有預設＝選填，預設是常值就寫進 `default`。選填給 `null`＝沒給；必填給 `null`＝型別錯（除非 `X | None`）；多給＝`BadArguments`。

**拒收（說原因）**：沒註解、`*args`、`**kwargs`、positional-only、不支援的型別（自訂類別、`tuple`、`Any`、兩種以上聯集…）、`async def`、有 decorator、名字不是 `[A-Za-z0-9_]{1,64}`、同名再定義（前面那個拒收）、包在函式或類別裡（「不是頂層」）。底線開頭「跳過（私有）」；`--only` 沒點名的「跳過」，點了沒有的＝`NotFound`。

**描述**：docstring 第一段 → `description`；參數說明取 Google `Args:`（`name (type): 說明`）或 NumPy `Parameters`＋`---`。沒 docstring、參數沒說明＝警告（描述改用函式名）。

**產出** `DIR/PACK/`（PACK 預設＝檔名去 `.py`、怪字換 `_`）：

- `PACK.json`：每支 `_meta.argv`＝`["tools/PACK/run", "<函式名>"]`，不寫 `_jail`。
- `run`：照 `wrap.json` 驗型別 → chdir 到工作根目錄 → importlib 載 `src/` 副本 → 叫函式。str 原樣印，其他 `json.dumps`（`allow_nan=False`，不能＝`ResultNotJSON`）；例外＝`PythonError`（`類別: 訊息`＋`exception` 格，不噴 Traceback）；import 失敗＝`ImportFailed`；沒這支＝`UnknownFunction`。`print` 改走 stderr。`run --check-import` 只試 import。
- `src/<原檔名>`（副本）、`wrap.json`（原檔路徑、`sha256`、產生時間、每支簽名、`rejected`、`skipped`）、`_common.py`、`config.json`、`README.md`（收了哪些、拒收表、關牢：不需額外掛載，套件要在牢裡的 python3 找得到）。

印一張表（收／拒收／跳過＋原因、警告）。收到一支以上才寫檔、退 0；一支都沒＝`NothingToWrap`。讀不到＝`NotFound`／`ReadFailed`，語法錯＝`SyntaxError`。

## 這一節沒管的

- catalog 的 `new --lang sh`、`test_NAME.py`：沒做，改用 `cases.json`。
- `--describe-with-llm`、模型版 `tool_try`／`tool_draft`：第三波。
- `tools test` 只驗契約，不驗做對事（靠 `contains`）。參數有連動（`op` 決定必填）或先驗設定再驗參數的工具，自動案例會誤判沒過。
- 原檔改了要 `wrap-py --force` 重包。套件牢裡找不到、碰 `/work` 以外的檔：靠 `tools test` 在牢裡跑出來。
