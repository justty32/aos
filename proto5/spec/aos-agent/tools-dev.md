← [aos-agent](README.md)｜[spec](../README.md)｜實作：[tools_dev](../../lib/aos_agent_tools_dev.py)｜來源：[catalog E](../../notes/2026-09-24-tool-era/catalog.md)｜[續](tools-llm.md)

# 1.8（續）`tools new`／`test`／`wrap-py`（09-24 tool-era 第二波）

```
aos-agent tools new     NAME [--out DIR] [--force]
aos-agent tools test    NAME|DIR [--tool T] [--args JSON] [--case FILE] [--no-jail] [--json]
aos-agent tools wrap-py FILE.py [--only f,g] [--name PACK] [--out DIR] [--force]
```

一句話：**生工具包骨架、在牢裡驗工具包合不合契約、把 Python 函式包成工具包。** 不叫模型、**不需要 agent 家**（不收 `--target`）。包格式見 [tools.md](tools.md)，契約見 [tools README](../../tools/README.md)。

## 共通

- 用法錯退 2：參數個數、空字串、選項給錯動作、`--target`、`--args` 不是 JSON／配 `--case`／對到多支沒 `--tool`。其他錯：stderr `aos-agent: 代號: 白話`，退 1。
- new／wrap-py：整包寫進 `DIR/.NAME.new-<pid>-…/` 再 rename 成 `DIR/NAME/`。`--force`：舊的先改名 `.NAME.old-<pid>-…`，新的就位才刪；新的沒就位就把舊的改回來。開始前清掉 pid 已死的殘渣（`.old` 在、正式包不在＝改回正式名），stderr 印一行。
- 包名 `[A-Za-z0-9_][A-Za-z0-9_-]*`，且不能讓必要檔撞名（new 的 `config`、`cases`；wrap-py 的 `wrap`、`config`），不合＝`BadName`。已在＝`AlreadyExists`（`--force` 蓋，但不蓋檔或連結）；`--out`（預設目前資料夾）不在＝`NotFound`。

## `tools new NAME`

生 `DIR/NAME/`：`NAME.json`（範例工具：必填 `text` string、選填 `count` integer ≥ 1；`_meta.argv`＝`["tools/NAME/NAME"]`；不寫 `_jail`＝預設關牢）、`NAME`（可執行 python3，`from _common import run, arg, fail`，本體留 `# TODO`）、`_common.py`（base 副本）、`config.json`（`{"root": "workspace"}`）、`cases.json`（四條）、`README.md`。印生了哪些檔與兩行下一步。

## `tools test NAME|DIR`

不含 `/`＝`proto5/tools/NAME/`；含 `/`＝那個資料夾（要有 `<資料夾名>.json`，否則 `NotFound`）。工具檔照 agent §3.3 驗，壞＝`ToolInvalid`。`--tool T` 只測一支。

**怎麼跑**：臨時假 agent 家（跑完一定刪），包複製進 `tools/NAME/`、另建 `workspace/`；照 aos-agent 送件解 `_meta`（中心＝家）、cwd＝家、stdin＝arguments。

- **預設關牢**：`aos-jail -- true` 跑得起來才算有牢；照 aos-agent 的 `jail_argv` 包成 `aos-jail --mount ws=<家>/workspace --chdir ws --net off -- <程式> …`。
- 沒 bwrap 或 `--no-jail`：直接跑（拿掉 `AOS_TOOL_ROOT`／`AOS_TOOL_FENCE`）；**跑任何程式之前** stderr 先印 `沒關牢（原因）：…`。
- 上限：逾時＝`_timeout_ms` 封頂 30 秒，到了 SIGKILL 整個群組、再等 5 秒；主行程結束後管子被子孫握著最多再收 2 秒；stdout、stderr 各留最後 1 MB（註明丟了多少）；殺不掉就寫明、不等。

**跑什麼**（依序）：

1. 有 `wrap.json`：`run --check-import`（案例 `import`，要退 0）。
2. 每支 `program`：`_meta` 解得開、`argv[0]` 的檔在且可執行（不含 `/` 時不關牢要在 PATH 上）。不過就不跑那支。
3. 自動案例（必填給樣本：string `"x"`／`"x2"`…、integer 取 minimum 或 1、number 1.5、boolean true、enum 第一個、array `[]`、object `{}`）：`ok` 只給必填，**照契約回話就過**（退 0，或退 1 且最後一行 JSON、代號不是 `InternalError`／`BadArguments`）；`type:<參數>` 給錯型別（string→123，其他→`"x"`）、`missing:<參數>`、`not-object`（`[]`）都期待 `BadArguments`。
4. 固定案例：`--case FILE`，沒給用包裡的 `cases.json`。

stdout 有 `Traceback`、逾時、跑不起來都算沒過。

**案例檔**：JSON 陣列，每條 `{"tool", "args", "expect", "contains"?, "name"?, "files"?}`。`args` 原樣當 stdin；`expect`＝`"ok"`（退 0）或錯誤代號（退 1 且最後一行 JSON 的 `error` 是它）；`contains`＝stdout 要含的片段；`files`＝`{相對路徑: 內容}`，跑前寫進 workspace：不收絕對路徑與 `..`，從 workspace 逐層開、不跟符號連結、有硬連結不寫，寫不進去那條＝FAIL。案例共用 workspace。格式不對＝`CasesInvalid`。

**輸出**：跑之前先印表頭（包名、幾支、關不關牢；每支 `描述  工具  約 N token`，> 300 註明資源軸扣分；`_common.py` 跟 base 不同＝警告），然後每條跑完就印 `PASS/FAIL  工具  案例  (毫秒)`，FAIL 下一行縮排 `期待 …；得到 …`（截 200 字）；最後 `N 條，M 條沒過`。全過退 0，否則 1。

**`--json`**（第 1 版，之後只加鍵）：`{"_type": "aos_agent_tools_test", "_version": 1, "package", "dir", "jail", "jail_note", "warnings", "tools": [{"name", "tokens", "over"}], "cases": [{"tool", "case", "pass", "ms", "expect", "got", "exit_code"}], "total", "failed"}`。

**`--args JSON`**：只跑一次。stdout＝工具 stdout 原樣；stderr＝工具 stderr＋`（工具：退出碼 N，M 毫秒）`。工具退 0 就退 0，否則 1。配 `--json`：`_type: aos_agent_tools_run`，鍵 `tool jail jail_note exit_code ms timed_out error dropped stdout stderr`。

## `tools wrap-py FILE.py`

用 `ast` 靜態讀（**不 import、不執行**），只挑**直接寫在模組頂層**、非底線開頭、每個參數都有支援型別註解的函式。

| 註解 | 給模型的 schema | run 驗法 |
|---|---|---|
| `str` `int` `float` `bool` | string／integer／number／boolean | int 不收 bool；float 收整數 |
| `list[X]`（不帶 X 也收） | array＋`items` | 逐項 |
| `dict[str, X]`（不帶也收） | object＋`additionalProperties` | 逐值 |
| `Literal[…]`（同型別常值） | 那型別＋`enum` | 值與型別都要對 |
| `X \| None`／`Optional[X]`／`Union[X, None]` | 只寫 X | 收 `null` |

`typing.` 寫法與字串註解都收；keyword-only 也行。沒預設＝必填；預設是常值就寫進 `default`。選填給 `null`＝沒給；必填給 `null`＝型別錯；多給＝`BadArguments`。

**拒收（說原因）**：沒註解、`*args`、`**kwargs`、positional-only、不支援的型別、`async def`、有 decorator、名字不是 `[A-Za-z0-9_]{1,64}`、同名再定義（前面的拒收）、在函式或類別裡、在頂層 `if`／`for`／`try`／`with` 等區塊裡（import 後不一定有）。底線開頭「跳過（私有）」；`--only` 沒點名的一律「跳過」，點了頂層沒有的＝`NotFound`。

**描述**：docstring 第一段 → `description`；參數說明取 Google `Args:` 或 NumPy `Parameters`＋`---`。沒寫＝警告（描述改用函式名）。

**產出** `DIR/PACK/`（PACK 預設＝檔名去 `.py`、怪字換 `_`）：

- `PACK.json`：每支 `_meta.argv`＝`["tools/PACK/run", "<函式名>"]`，不寫 `_jail`。
- `run`：照 `wrap.json` 驗型別 → chdir 到工作根目錄 → 載 `src/` 副本 → 叫函式。str 原樣印，其他 `json.dumps`（不能＝`ResultNotJSON`）；函式丟出**任何** `BaseException`（含 `KeyboardInterrupt`、`SystemExit`）＝`PythonError`（`類別: 訊息`＋`exception`，不噴 Traceback）；import 失敗＝`ImportFailed`；沒這支＝`UnknownFunction`。`print` 走 stderr。`run --check-import` 只試 import。
- `src/<原檔名>`、`wrap.json`（原檔路徑、`sha256`、時間、簽名、`rejected`、`skipped`）、`_common.py`、`config.json`、`README.md`（收了哪些、拒收表、關牢：不需額外掛載，套件要在牢裡的 python3 找得到）。

印一張表（收／拒收／跳過＋原因、警告）。收到一支以上才寫檔；一支都沒＝`NothingToWrap`。讀不到＝`NotFound`／`ReadFailed`，語法錯＝`SyntaxError`。

## 這一節沒管的

- catalog 的 `new --lang sh`、`test_NAME.py`；`--describe-with-llm`、`tool_try`／`tool_draft`（第三波）。
- `tools test` 只驗契約；參數有連動或先驗設定的工具，自動案例會誤判沒過。
- 原檔改了要 `--force` 重包；套件牢裡找不到靠 `tools test` 跑出來。
