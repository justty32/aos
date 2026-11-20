編譯程式庫第 0 刀（共用的底 `spec_base.py`）施工紀錄（11-20，線 aos-pylib-k0-1120）：做了什麼、跟設計稿對不上處怎麼處理、驗收輸出、下一刀開工前要知道的事。

← [2026-11-20](README.md)｜設計稿：[aos-pylib-plan-1120](aos-pylib-plan-1120/README.md)（第 0 刀在 [07b](aos-pylib-plan-1120/07b-施工計劃-第0到2刀.md#第-0-刀-共用的底)）｜使用者答案：[12-使用者已答](aos-pylib-plan-1120/12-使用者已答.md)

使用者 11-20 被問「編譯與 hook 兩邊不用等裁定的第一刀，要現在開工嗎？」答「兩邊都開工」。這是編譯這邊的第 0 刀；hook 那邊的第 1 刀是另一條線（aos-hook-k1-1120），兩線不碰對方的檔。

## 一句話

新檔 `py/aos/spec_base.py` 收了兩邊原本各寫一份的東西（例外、推名字、`--compile`／`--dry-run` 多給參數那幾行、寫檔），`agent_spec`、`tool_spec`、`tools_def` 改用它；**兩個骨架重新編譯的產物、各旗標的 stdout／stderr／結束碼與改動前逐 byte 相同**，既有測試一條沒改、全過。外面看不出不同；寫法（大寫常數＋`defs.main(...)`、`ts.main(...)`、`defs.extern` 的手寫檔意思）全部照舊。

## 動了哪些檔

| 檔 | 做什麼 |
|---|---|
| `py/aos/spec_base.py`（新，95 行） | `SpecBad`、`DefBad`；`prog_name(script, 主檔名)`；`location(...)`（`--compile [位置]`／`--dry-run` 後面多給＝`ArgumentsBad`，沒給＝腳本那一夾）；`write_files(夾, {檔名: 內容}, last=)`：內容四種（文字、JSON、`Program` 程式檔 755、`Link` 連結），檔名可帶一層子夾 |
| `py/tests/test_spec_base.py`（新，154 行，14 條） | 見下「驗收」 |
| `py/aos/agent_spec.py`（461 → 441） | `write()` 只留兩條政策（`_metainfo.json` 合併、`README.md` 不在才寫），寫檔交給後端；`main` 的推名字與「多給參數」改叫 `spec_base`；例外從 `spec_base` 轉出；檔頭補一句 |
| `py/aos/agent_spec_parts.py`（344 → 337） | 兩個例外類別搬走，改從 `spec_base` import（`parts.SpecBad` 照舊叫得到，`agent_spec_lib` 不用改）；檔頭那句改 |
| `py/aos/agent_spec_load.py` | 例外改從 `spec_base` import |
| `py/aos/tool_spec.py`（300 → 284） | `SpecBad` 改用 `spec_base` 的（跟 agent 那邊同一個類別）；`_write_file` 拿掉，寫資料夾的兩份改叫 `write_files`；推名字、多給參數改叫 `spec_base`；寫進 JSON 指標（`aos-json set`）那條沒動 |
| `py/tools/agent/tools_def/_entry` | `add_entry` 原本叫私有的 `tool_spec._write_file`，改叫 `spec_base.write_files`（設計稿意見 2）；權限 755 照舊 |
| `py/README.md`、`py/docs/04-共用模組.md`、`py/docs/01-分層等.md` | 各加一句／一列講 `spec_base`；`01-分層等.md:14` 查過是手寫的（code block 裡的列表），加一行 |

`git grep -nE '_write_file|class SpecBad|class DefBad' proto8/py` 只剩 `spec_base.py` 兩行（交件後）。

## 寫檔後端的規矩（`write_files`）

- 先全部寫成同夾的暫存檔 `.<名>.tmp-<pid>`（連結也是先建暫存連結），最後照 `last`（agent 那邊傳 `RENAME_LAST`）連著 `os.replace`。
- 寫暫存檔時失敗＝清掉暫存檔、清掉這次新建又空著的子夾，夾裡不變；改名時才失敗＝前面幾份已換上（照舊）。
- 判斷在不在、清暫存一律 `lexists`（斷掉的暫存連結用 `exists` 判會漏）；建暫存檔或暫存連結前，同名殘留先清掉。
- 原檔在就把它的權限抄給新的文字與 JSON（照舊，用 `os.path.exists`）；程式檔一律 755；連結不設權限、不碰目標。
- 夾不是資料夾＝`OSError("… is not a folder")`（原本在 `agent_spec.write` 裡，搬進後端）。

## 跟設計稿對不上、或邊界有疑問的地方（都選最小、不改行為的做法）

1. **`agent_spec_load._prog()` 是第三份推名字**，設計稿沒列。它從 `sys.argv[0]` 推，碰到連結時跟 `prog_name` 的算法差一點（`agent.py` 是連結時看的是哪個名字），換掉會改到錯誤行開頭，**沒動**。
2. **「同名殘留先清掉」設計稿只寫連結**，我對文字、JSON、程式檔也照做：否則上一次留下的暫存連結會讓 `open(…, "w")` 順著寫到別處。正常情況（沒有殘留）一行不差。
3. **程式檔的權限**：設計稿同時寫「程式檔（755）」與「沿用原檔的權限」，我定成程式檔一律 755、其餘照抄原檔。程式檔今天沒人用。
4. **小旗標殼只做 `location()` 一支**：只管多給參數與預設位置（設計稿意見 8「做小、不硬合」）；`--help`、`--static`／`--dynamic`、`--tooldef`／`--metainfo`、「不給參數」各自留在原地。訊息照舊各自不同的 usage 字串。
5. **`tool_spec.write` 寫資料夾時仍是一份一份寫**（兩次 `write_files`，每份各自原子），沒有合成一次：合成一次會改到「第二份失敗時第一份已換上」這個行為。
6. **`tool_spec.SpecBad` 與 `defs.SpecBad` 變成同一個類別**：接其中一個也會接到另一個。今天沒有程式同時用兩邊，`tools_def` 的 `except tool_spec.SpecBad` 照樣接得到。
7. **行數**：`agent_spec.py` 441、`agent_spec_parts.py` 337 仍超過 300（設計稿已排：第 2 刀拆 `agent_spec`、第 3 刀拆 `parts`）；`tool_spec.py` 降到 284。
8. **`tools_def` 寫 `_entry.json` 時夾不在**：原本是 `open` 的錯，現在是「is not a folder」的錯，都報 `WriteFailed`；這條路只在 `loc["kind"] == "dir"` 時走，平常到不了。

沒做的（設計稿排在後面的刀）：`Unit`／`main(物件)` 的殼（第 2 刀）、`fn`（第 1 刀）、連結真正接到 `defs.extern`（第 4 刀）、`defs.write`／`defs.compile` 拿掉（第 2 刀）。

## 驗收（實際指令與結果）

環境：`git archive HEAD proto8`（HEAD＝`c19e5da0a`，本線第一筆之後、還沒有程式改動）抄到 `~/.aos/scratch/aos-pylib-k0-1120/src`，在複本裡 `install.py`；跑任何東西都經 bash 腳本先 unset 所有 `AOS_*`，再 `env -i PATH=<複本>/bin:/usr/bin:/bin HOME=… PYTHONDONTWRITEBYTECODE=1 AOS_HOME=<複本>`；TMPDIR 用預設。改動前跑一次留底（`cap-base`），把本線的檔疊上去、再 `install.py`，同一支腳本、同一個工作路徑再跑一次（`cap-new`）。

**產物一字不差**：

- `agent.py`：`--dry-run`、`--dry-run --static`、`--dry-run --dynamic`、`--compile`（進自己那夾）、`--compile 另一夾`、不給參數、`--dry-run x`（多給）。
- `tool.py`：`--compile`、`--dry-run`、`--tooldef`、`--metainfo`、`--compile a b`（多給）、`--compile obj.json#/x`、餵 `{"a":2,"b":3}` 直接執行（印 `5`）。
- 14 個情況的 stdout、stderr、結束碼共 42 份，加一份檔案權限清單，`cmp` 全同；寫出的三個夾（agent 骨架、agent 另一夾、tool 骨架＋`obj.json`）`git diff --no-index` 無差（含權限）；改動前後兩次重新編譯的骨架檔，跟 repo 提交的那份也都無差。

**測試**（逐夾 `python3 -m unittest discover`，改動前／改動後）：

| 夾 | 改動前 | 改動後 |
|---|---|---|
| `py/tests`（含 `test_agent_spec.py`、`test_tool_spec.py`、`test_aos_py.py`） | 602 條 OK（skip 1） | 616 條 OK（skip 1；多的 14 條是 `test_spec_base.py`） |
| `templates/tests/tool-python` | 4 OK | 4 OK |
| `py/tools/agent/tools_def/tests` | 12 OK | 12 OK |
| `py/tools/aos/defs/tests`（`defs.load` 相關） | 27 OK | 27 OK |
| `py/tools/agent/agent_def/tests` | 30 OK | 30 OK |
| `py/tests/apps/*` 十六夾 | 除 feedback 外全 OK | 同左 |

- `py/tests/apps/feedback` 兩邊都是 18 條 error：測試要讀 repo 的 `wf/advices/feedback/raters.json`，乾淨複本只抄了 `proto8/`，跟本線無關，沒修。
- 改動前那輪的 `apps/gdb` 之後幾夾，跑的時候本線的檔已疊上複本（兩輪有一段重疊），所以「改動前」那幾夾不算純的；跟本線有關的五夾（表上前五列）都在疊檔前跑完。
- `test_spec_base.py` 十四條：一個例外類別各模組共用；`prog_name`；`location`（預設位置、多給＝`ArgumentsBad` 與訊息）；四種內容寫得出讀得回；程式檔蓋舊檔也是 755；文字保留原檔權限；連結與普通檔互相蓋、目標不動、不寫穿；中途失敗夾裡不變不留暫存檔；**連結之後下一項失敗：不留暫存連結（斷掉的）、不留空的 `fn/`**，原本就在的 `fn/` 留著；成功時子夾留著；同名殘留（指向別處的暫存連結）被清掉、沒寫穿；改名照 `last` 排；改名失敗清掉暫存檔與新建的子夾；壞檔名與「不是資料夾」。
- 既有測試一行沒改（`test_agent_spec.py` 的 `test_rename_order_and_cleanup` 用 mock 改 `os.replace`／`os.unlink`，後端照樣過）。

## 下一刀開工前要知道的

- 第 1 刀（`fn`）不再被擋：待裁第 4 題使用者 11-20 選了「新名字 fn」。第 2 刀本來就不被擋。兩刀都還要使用者另外點頭才開線。
- 第 2 刀會照設計稿做「`.compile(夾)` 寫、`.dry_run()` 只算」與「欄位小寫」——這兩題（第 2、3 題）使用者只是聽過、沒有明確裁，而且會改掉 11-19 教的寫法（`defs.compile`／`defs.write`、`base.TOOLS`）；開工前值得再明確問一次。
- `spec_base` 的 `Program`、`Link`、子夾今天只有測試在用；第 3 刀（`fn/<名>.py`）、第 4 刀（連結版 `extern`）直接用 `write_files(夾, {"fn/add.py": Program(...), "system.txt": Link(目標)})`。
- 第 2 刀要在 `spec_base` 加 `Unit` 與 `main(物件)` 的殼；`agent_spec_load._prog()` 那份推名字可以那時一起看要不要收。
- hook 介面線（aos-hook-k1-1120）同時在做，只加新檔；本線沒碰 `loop.json` 那段與 `interfaces.json` 的 `hook_points`，照設計稿 07「後開工的那條帶」。
- 改的是 `py/`：**活樹要在 `~/repo/aos/proto8` 跑 `install.py` 才吃到**，那要使用者點頭；本線沒跑。不改持久格式，不用重建什麼。
