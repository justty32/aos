2026-09-25 ｜ 模型 gpt-6-astra（codex-cli 0.156.1，reasoning medium）｜ 審的範圍 `b1087729..871bd5ce`（proto5/lib 拆檔，20 個 commit）｜ 指令：`codex exec -m gpt-6-astra --sandbox read-only -C /home/lorkhan/repo/simple_tools/aos --color never -o <輸出檔> "<中文 prompt>" < /dev/null`（耗時 328 秒，78,140 tokens；astra 在唯讀沙箱裡跑不了會寫暫存目錄的測試，見 README 的補跑結果）

---

## 必修（會壞行為或 import）

**未發現可確認的必修問題。** 已逐一核對全部 20 個 commit；此範圍實際拆分 **19 支母模組**，另 1 個 commit 拆文件，與題述的 24 支不同。

19 支母模組及全部 145 支模組均 import 成功；未發現外部實際使用名稱漏匯出、既有 patch 失效、函式／預設參數遺漏或子模組缺少 global import。但完整測試受唯讀沙箱限制，**不能宣稱測試全綠**。

## 建議

- [aos_team_post_jobs.py:130](/home/lorkhan/repo/simple_tools/aos/proto5/lib/aos_team_post_jobs.py:130)、[同檔:234](/home/lorkhan/repo/simple_tools/aos/proto5/lib/aos_team_post_jobs.py:234)、[aos_team_post_watch.py:144](/home/lorkhan/repo/simple_tools/aos/proto5/lib/aos_team_post_watch.py:144)、[aos_team_task_machine.py:190](/home/lorkhan/repo/simple_tools/aos/proto5/lib/aos_team_task_machine.py:190)：母模組再匯出不會轉接子模組的 globals；patch 母模組的 `check_result`／`JOB_TIMEOUT`／`update_section`／`load` 已無法影響這些呼叫，宜說明新的 patch 位置；**repo 目前沒有這些 patch 用法**，故不列必修。

- [aos_directives_edit_persona.py:11](/home/lorkhan/repo/simple_tools/aos/proto5/lib/aos_directives_edit_persona.py:11)、[aos_directives_edit.py:24](/home/lorkhan/repo/simple_tools/aos/proto5/lib/aos_directives_edit.py:24)：兩次插入相同 `proto5/tools/files` 路徑可去重；目前只增加一筆 `sys.path`，沒有改變解析優先序，`_mdsec` 也是同一個快取模組。

- [docs/agent.md:69](/home/lorkhan/repo/simple_tools/aos/proto5/lib/docs/agent.md:69)：「九個子命令」沿襲舊文，實際 parser 有 **19 個**。

- [docs/daemon.md:16](/home/lorkhan/repo/simple_tools/aos/proto5/lib/docs/daemon.md:16)：段落仍寫「五支」，漏算 `aos_daemon_ticks`；頁首與家族表的 **六支**才正確。

## 確認沒問題的項目

下表子模組省略共同的母模組前綴及 `.py`。每列均核對函式／方法 AST、預設值、常數、import、全 repo 外部用法與現存 patch。

| Commit | 母模組 → 子模組 | 核對結果 |
|---|---|---|
| `a8bf4a55` | `aos_agent_tools_dev` → `_pack, _pyread, _wrappy, _describe, _run, _test` | 本體及產生程式字串保留；`jail_ready`／`Runner`／`os.rename` patch 有效。 |
| `84c8dadd` | `aos_agent_tools_wrapcli` → `_const, _argparse, _helptext, _check, _pack` | 解析、產包及常數保留；`HELP_TIMEOUT` 仍由母模組讀取。 |
| `2c1141ef` | `aos_team_post` → `_base, _recheck, _text, _jobs, _watch` | 方法本體保留；MRO、初始化屬性及跨類方法完整，詳見下段。 |
| `e983c4ae` | `aos_market` → `_book, _score, _grant, _close, _merge` | 計分與帳務邏輯保留；`cost.account_grant`／`co.down`／`shutil.move` patch 有效。 |
| `b67f01fd` | `aos_team_format` → `_base, _io, _cmd, _roster, _letter, _template` | 外用名稱完整；模板路徑不變，反向依賴採延遲 import。 |
| `7b4c4840` | `aos_company` → `_config, _new, _switchboard, _count` | 設定、總機及計數邏輯保留；`_run` 與 `Switchboard` 方法 patch 有效。 |
| `a5104c9a` | `aos_agent_compact` → `_plan, _archive, _summarize` | 壓縮與封存邏輯保留；`apply` 仍解析母模組的 `plan`／`_hook`。 |
| `dfdcfdad` | `aos_team_commons` → `_base, _ingest, _post` | 外用及動態 handler 名稱完整；與 format 的反向依賴在函式內。 |
| `3144e3c4` | `aos_team_cost` → `_ledger, _account, _budget` | 記帳、額度及預算邏輯保留；由 `__file__` 推導的執行檔路徑不變。 |
| `9b747901` | `aos_team_crystal` → `_stats, _rules, _llm` | 函式及常數保留；`llm → rules → stats` 單向依賴，其他反向引用延遲載入。 |
| `042a7948` | `aos_team_hr` → `_book, _count, _members` | 函式及常數保留；`trial` 的 `_team`／`check_cpus`／`time.sleep` patch 有效。 |
| `125c14fc` | `aos_team_task` → `_base, _machine` | 狀態機與外用名稱保留；`machine → base → format` 無循環。 |
| `1e086cbd` | `aos_team_beat` → `_schedule, _routines` | 排程與例行邏輯保留；現存 `start` patch 有效，post 為延遲 import。 |
| `b8890cdf` | `aos_team_verify` → `_checks, _jail` | `CHECKS` 六條全解析成功；直接呼叫的三種檢查器也完整再匯出。 |
| `3a0ab79c` | `aos_team_score` → `_read, _calc` | 六軸算法與預設值保留；外用名稱完整，`calc → read` 無循環。 |
| `0ff6ee32` | `aos_agent_cli` → `_parser, _args` | parser、預設秒數、參數再驗與分派保留，外部 `main` 入口不變。 |
| `9ba147ee` | `aos_team_toolsmith` → `_check` | 檢查函式保留；`jail_ok`／`TOOL_TIMEOUT_MS` 仍從母模組解析。 |
| `79009a7c` | `aos_directives_edit` → `_persona, _resolve` | 函式、預設值及外用名稱保留；無 import 循環，重複路徑見建議。 |
| `4e270fdc` | `aos_team_spawn` → `_check` | 檢查函式保留；`_auto_finish` patch 有效，team／hr 在函式內載入。 |

`Post` 的 MRO 實測為 `Post → _PostJobs → _PostWatch → object`，沒有方法重名。Mixin 所需資料屬性均由 `Post.__init__` 建立；`roster`／`tz` 仍在原來的 `run()` 階段填值。Jobs 所需的 `advance/now/now_iso/say/warn`，以及 Watch 所需的 `finish/load_rec/new_rec/now/say/start_rec`，全部由 `Post` 提供，沒有缺方法。

`aos_market_score`／`aos_company_config` 重複的 `LIB` 實測與母模組相等，檔案仍在同一目錄，沒有新增搜尋路徑或改變 import 解析。各家族內未發現會在載入時觸發的循環；跨家族反向引用位於函式內，全部 145 支模組也逐支以獨立程序 import 通過。

文件 commit `871bd5ce` 已核對：七個家族數量 **6＋11＋6＋13＋44＋54＋11＝145**，表列模組全部存在、沒有漏列新子模組；13 個舊 `##` 標題全部有對應 `<a id>`，文件相對連結目標均存在。測試檔 **101 個**、discover 收集 **2874 條**，與文件相符。

測試實跑 2866 條：**178 通過、0 assertion failure、2620 個測試 error、68 跳過**；另有 1 個 `setUpClass` error，使 8 條未執行。全部 **2621 errors** 都是沙箱無可寫暫存目錄；68 條跳過皆與 bwrap 不可用有關。全程未修改檔案。

實跑指令與結果：`cd proto5/lib && python3 -B -c 'import …'`（完整列入 19 支母模組）19/19 通過，另逐支獨立 import 145/145 通過；`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5/lib python3 -m unittest discover -s proto5/lib/test`：178 通過、0 failures、2621 errors、68 skipped，受唯讀環境阻擋。
---

## 附：給 astra 的 prompt（原文）

```
你是唯讀審查員。這個 repo 在 main 上剛合進一批「純結構搬移、零行為變更」的拆檔：範圍 `b1087729..871bd5ce`（20 個 commit），把 `proto5/lib/` 下 24 支模組拆成母模組＋子模組，並把 `proto5/lib/README.md` 拆成 `proto5/lib/docs/*.md`。

請先看 `git log b1087729..871bd5ce` 與 `git diff b1087729..871bd5ce -- proto5/lib`，然後逐支模組核對下面幾點（不要只抽樣，20 個 commit 每個都要看）：

(a) 母模組是否把外部用到的名字全部再匯出。對照方法：在全 repo `grep -rn` 所有 `from aos_xxx import ...`、`import aos_xxx`、`aos_xxx.名字` 的用法，以及測試裡 `patch('aos_xxx.名字')`／`patch.object(aos_xxx, '名字')` 字串，確認被 patch 的名字在母模組命名空間裡仍存在、而且母模組裡實際呼叫的是母模組命名空間的那個名字（若子模組內部直接呼叫自己的 copy，patch 母模組就打不到——這也要列出來）。
(b) 有沒有搬移時漏掉或改動的邏輯：函式本體、預設參數、模組層級副作用的順序（例如 `sys.path.insert`、常數初始化、logging 設定），母模組與子模組各自的 import 集合是否夠用（有沒有子模組用到但沒 import 的名字，只有在被呼叫時才會炸 NameError）。
(c) 循環 import 風險：子模組 import 母模組、母模組又 import 子模組；或子模組之間互相 import。要具體說會不會在 import 時炸、還是只是延遲 import 而已。
(d) 兩處非逐字搬移特別看：
   - `aos_team_post.py` 把 `Post` 類的兩段方法改成 mixin `_PostJobs`／`_PostWatch`：MRO、`self` 屬性依賴（mixin 方法用到的 `self.xxx` 是否都由 `Post.__init__` 設定）、mixin 方法之間有沒有互相呼叫但沒在該 mixin 定義的方法（靠 `Post` 提供）。
   - `aos_market_score.py`、`aos_company_config.py` 各自重複了一行 `LIB` 定義；`aos_directives_edit_persona.py` 重複 `sys.path.insert`——這些重複有沒有實際影響（路徑值是否一致、順序有沒有改變 import 解析）。
(e) `aos_team_verify` 的 `CHECKS` 表用字串指回母模組：各檢查器（check_xxx 函式）是否都在母模組再匯出，字串→函式的解析路徑有沒有漏。
(f) `proto5/lib/docs/*.md` 與 `proto5/lib/README.md` 和程式是否對得上：模組數、家族表列的模組名是否都存在、有沒有新子模組沒被列、舊的 `## 錨點` 是否都有對應 `<a id>`。

順便跑（唯讀的）：`cd proto5/lib && python3 -c "import 每支母模組"` 全部 import 一遍、以及 `python3 -m unittest discover` 或 repo 既有的測試指令（看 `proto5/lib/docs/tests.md`），把結果算進審查。

**不要改任何檔。** 輸出用中文、Markdown，分三節：
1. `## 必修（會壞行為或 import）`——每條：檔名＋行號、一句理由、以及一個可驗證的方法（一行 python 或一條 unittest 指令）。
2. `## 建議`——每條：檔名＋行號、一句理由。
3. `## 確認沒問題的項目`——逐支模組列一行（母模組 → 子模組），說核對過什麼。
最後附一行你實際跑過的指令與結果（import 全過？測試幾個過幾個失敗？）。
```
