# 「提供 hook 點」的介面：施工第 1 刀（宣告檔＋小庫＋兩支測試，只加不改）

← [當天索引](README.md)｜設計與計劃 [aos-hook-plan-1120](aos-hook-plan-1120/README.md)（範圍以 [09](aos-hook-plan-1120/09-施工計劃.md) 為底、[12 採納表](aos-hook-plan-1120/12-採納表.md) 為準）｜使用者已答 [13](aos-hook-plan-1120/13-使用者已答.md)｜現況調查 [aos-hook-iface-1120](aos-hook-iface-1120/README.md)

線 aos-hook-k1-1120，11-20 公司 WSL。頂層問「編譯與 hook 兩邊不用等裁定的第一刀，要現在開工嗎？」，使用者答「兩邊都開工」。頂層派、線隊長做。

## 結論

- 加了五份宣告檔、一支小庫 `aos.hook_point`、兩支測試、一份夾說明；**既有的程式、文件、知識庫一個字沒改**，執行時沒有人讀新檔（程式實際用的照舊是 `agentlib/hooks.py` 與 `kernel/hooks.py` 的 `EVENTS`）。
- 宣告逐點對過程式：三張表（agent 兩種身體各自的聯集、kernel）跟現在的 `EVENTS` 逐項相同，一致性測試鎖住。
- 手抄的那幾份（文件、self_hook 說明、知識庫）有 17 項跟程式對不上，全部是既有漂移；照任務書**不改**，列成測試裡的已知清單（下面「一致性測試」）。
- 全套測試：基準（HEAD 乾淨複本）與疊上本線改動的複本逐夾比對，結果見「測試」。

## 加了哪些檔

| 檔 | 一句話 |
|---|---|
| `py/aos/hook_point.py` | 小庫：`read_file`／`read`（驗設計 01 的五條、同名點合併）、`engine_table`（轉成引擎要的表）、`for_definition`（讀 `interfaces.json` 的 `hook_points`，收路徑字串或 `{"provider": 名字}`）、`provider_path`、錯誤 `PointsBad`；226 行，只用標準庫 |
| `py/aos/apps/hook/loop_points.json` | aos-loop 那一層四個點：after_start、after_stop（現有）、before_run、after_run（先宣告、標 `not_fired_yet`） |
| `py/aos/apps/hook/README.md` | 新夾的說明（夾裡要有一句話，index 才取得到；第 4 刀的 aos-hook 本體也放這夾） |
| `templates/agent-fsm/hook_points.json` | agent-fsm 四格的七個點 |
| `templates/start-api/agents/ann/hook_points.json` | 上一份的抄本（逐位元相同；`test_start.py` 本來就比對兩夾） |
| `py/aos/apps/eca/hook_points.json` | aos-eca-turn 的五個點 |
| `py/aos/apps/mcp/hook_points.json` | aos-mcp 的兩個點 |
| `py/tools/aos/kernel/hook_points.json` | 通用 kernel 框架的三個點 |
| `py/tests/test_hook_point.py` | 宣告檔與小庫：五份讀得過、`fired_in` 的檔在而且有那個事件名、五條驗證各有壞例、合併、`engine_table`、`for_definition` |
| `py/tests/test_hook_points_match.py` | 一致性測試：宣告＝程式現在的表，與手抄清單的比對 |

## 宣告格式多出來的兩個鍵（設計稿沒有，我加的）

不認得的鍵照 C-48 不管，所以加了不影響讀的人；小庫會驗它們的型別。

| 鍵 | 為什麼 |
|---|---|
| `if_failed` | 任務書要 loop 那份寫「失敗時怎樣」，設計 01 的格式沒有這一格。跟 `if_blocked` 同一種寫法：一句英文 |
| `not_fired_yet` | 任務書要 before_run／after_run 先宣告、標清楚（09b 原本寫「刀 5 才加」，任務書蓋過）。有這一格＝宣告了、程式還沒發；一致性測試把它們排除在「跟現在的表比」之外 |

另外欄位寫成物件時，`about`、`env` 兩格我定成必填、`type` 選填（預設 string）；設計稿只說 `env` 是非空字串、`type` 兩值之一。

## 宣告對程式核到的不一致

以程式為準寫宣告；下面是「設計稿草稿」或「文件」跟程式對不上的地方。

**設計稿 02 的草稿 vs 程式**（宣告照程式寫）：

1. `before_tool` 的 `change` 草稿寫 `{"arguments": "object"}`；程式不驗 arguments 的型別（`agentlib/hooks.py` 的 `_check` 只看 content，mcp 同）。宣告寫 `"any"`。第 2 刀把型別檢查併進引擎時，若改回 `object`＝多擋一種今天放行的回話（行為改變，要記一筆）。
2. fsm 的 `brain_failed` 草稿欄位是 name、reason、error、retry、wait_s、attempt；程式（`wait.py:576-596`）還帶 `code`、`status`（從 kernel 的 error 抄來，BrainFailed 才有）。宣告補上。
3. kernel `after_verdict` 的 `verdict` 草稿寫「pass, refuse or hold」；程式（`round.py:109-110`）新信判成 `queue` 也發，所以四種都可能（hold 只會是前一個 hook 改的）。宣告照實寫。
4. kernel `after_verdict` 的 `phase`：09b 寫「照設計預設記 before」，12 採納表（A21、B4）改成照實寫 `after`。照 12。
5. eca 的 `brain_failed`：codex 那條路只帶 name、reason；claude 那條才有 code、retry、attempt、dropped、wait_s、status、cause。宣告的欄位說明寫「claude only」。
6. mcp 的 `id` 是 JSON-RPC id 轉成字串（沒有時空字串），不是工具呼叫 id；宣告照實寫。

**文件、說明 vs 程式**（就是調查線說的漂移，加上新找到的）：見下一節的已知清單。

## 一致性測試（`test_hook_points_match.py`）

比得到的都比了：

| 比什麼 | 結果 |
|---|---|
| fsm 聯集（loop＋agent-fsm）、eca 聯集（loop＋eca＋mcp）的 `engine_table` ＝ `agentlib.hooks.EVENTS` | 相同（before_run／after_run 排除） |
| kernel 宣告的 `engine_table` ＝ `kernel/hooks.py` 的 `EVENTS` | 相同 |
| on_clock 的 `entry_keys` ＝ `CLOCK_KEYS`，而且只有 on_clock 有 `entry_keys` | 相同 |
| `hook_fire` 的 `EVENTS`、`CAUSE_KEY`、`CAUSE_ENV`、code／signal 的環境變數 | 相同 |
| gdb 的 `HOLD_EVENTS`＝phase before 的點；`key_of`、`SUBJECT` 的規則＝宣告的 `key`、`subject` | 相同 |
| self_hook `_tooldef.json` 的 `event` enum ＝ 九種 | 相同 |
| 點名與欄位名有沒有寫在：`06-hook.md` 事件表那一列、kernel `README.md` 那一列、self_hook `_tooldef.json` 說明的那一行、知識庫 `me/self_hook.json` 的 events／clock、`aos-agent hook --help`、五份範本 `hooks.json` 的 description | 17 項沒寫，全部列為已知（下表） |

已知不一致（測試裡的 `KNOWN_GAPS`；`test_no_new_gaps` 抓新的漂移、`test_known_gaps_are_still_there` 在有人補了文件時提醒拿掉、`test_hand_copies_match_fully` 標 expected failure）：

| 哪份 | 少了 |
|---|---|
| `py/aos/apps/agent/docs/06-hook.md` 事件表 | after_stop 的 `cause`；brain_failed 的 `error`、`code`、`status`、`retry`、`attempt`、`wait_s`、`dropped`、`cause`（表只寫 name、reason）；on_clock 的 `config`（只寫在選項表） |
| `py/tools/agent/self_hook/_tooldef.json` 說明 | brain_failed 的 `retry`、`attempt`、`wait_s`、`dropped`、`status`、`cause` |
| `knowledge/aos/me/self_hook.json` 的 events | after_stop 的 `cause` |

比對的極限：欄位是用「名字有沒有出現在那一列或那一行」比，所以像 self_hook 說明裡 brain_failed 那行有「the error code」，`error`、`code` 就算有寫到，其實沒講 error 物件。這類假過關沒列進清單。

證明會紅（在暫存複本裡改壞再跑）：改 agent 的 EVENTS、改 kernel 的 EVENTS、文件拿掉 tool_added 的 `path`、文件補上 after_stop 的 `cause`（已知清單變過時）、gdb 的 HOLD_EVENTS 少一個，五種都紅；還原後綠。

要不要補這 17 項是[待裁第 8 題](aos-hook-plan-1120/10-待裁題.md)的事；09b 原本把「補 06-hook.md 的漂移」放在第 1 刀，任務書說不改文件，所以沒補。

## 照設計預設寫、使用者沒裁的地方

宣告只加不接線，寫了不改變任何行為；之後翻案要改的地方列在每條後面。

1. **kernel 三個點搬成宣告檔（第 14 題「一起搬」）**：寫了 `py/tools/aos/kernel/hook_points.json`。選「先不動」＝這份檔與測試的 kernel 那段拿掉（`test_hook_point.py` 的 `KERNEL`、`test_hook_points_match.py` 的 `KERNEL` 與 `test_kernel_events`、`gaps()` 的 kernel README 段）。
2. **欄位寫進宣告當唯一來源（第 4 題「要」）**：每個點都寫了完整的 `fields`。選「宣告照寫、self_hook 照舊手抄」＝不用改；選「不要」＝宣告只留三格，五份檔的 `fields` 改成 `{}`，一致性測試的手抄比對整段拿掉。
3. **零成本旗標（第 11 題）**：宣告裡**沒寫**任何旗標相關的東西（旗標是 loop.json 與 aos-loop 的事，第 5 刀）。不用改。
4. **fsm 與 eca 各寫各的（第 3 題「各自寫清楚」）**：兩份宣告各寫各的 `when` 與欄位。選「統一」或「分名」＝改 eca／mcp 那兩份與 agent-fsm 那份。
5. **gdb 從宣告讀（第 6 題）**：這刀只是寫了 `key`、`subject`、`phase`，gdb 沒讀。選「照名字猜」或「照舊手改」＝`key`、`subject` 兩格留著也無害。
6. **掛到不會發的事件當場擋（第 5 題）**：這刀沒有擋任何東西；`for_definition` 只讀不驗清單。不用改。
7. `change` 型別、`if_blocked`、`when` 的句子：草稿寫的，我照程式改了幾處（上一節 1～6）。

## 替使用者做的選擇（施工層級）

- 加了 `if_failed`、`not_fired_yet` 兩個鍵（理由見上）。
- before_run／after_run 照任務書先宣告（09b 原本寫第 5 刀才加）。
- after_start／after_stop 的 `if_failed` 照使用者「四個點都跟著停」寫，**但現在的程式只印 warning**；句子裡寫明「until aos-loop and the wiring change, … only gives a warning」，第 5 刀做完要拿掉後半句。
- `read()` 合併後每個點多一格 `said`（每份宣告一項：provider、path、when 與 if_blocked／if_failed／not_fired_yet），上面那層的 `when` 是第一份的；設計 01 第 5 條「兩份都留著」用這個形狀實現。
- `PROVIDERS` 只有設計 01 列的四個名字（aos-loop、agent-fsm、eca、mcp）；kernel 不進表，kernel 框架以後照路徑讀自己夾那份。
- 新夾 `py/aos/apps/hook/` 加了一份 README.md（index 要一句話）。

## 跟設計稿對不上處怎麼處理

- 09b 刀 1 表裡的「改 06-hook.md 補漂移」：沒做（任務書：不為了綠去改文件），改成已知清單。
- 09b 的「after_verdict 的 phase 記 before」：照 12 寫 after。
- 09b 的「loop_points.json 只 after_start、after_stop」：照任務書四個都寫、新兩個標 `not_fired_yet`。
- 09b 測試名 `test_hook_points_docs.py`：改叫 `test_hook_points_match.py`，因為它不只比文件，也比程式裡的表（09b 的第一支測試裡「engine_table 跟 EVENTS 逐項相同」搬到這支，第一支只管格式與小庫）。
- 12 說 `read` 要認 `{"provider": 名字}`：在 `for_definition`（讀 `interfaces.json` 的清單）認；`read(paths)` 本身只收路徑，名字經 `provider_path` 換。
- `py/docs/04-共用模組.md` 沒加 `hook_point` 一節：那份被編譯線 aos-pylib-k0-1120 claim 著；第 2 刀或第 7 刀補。

## 測試

兩份乾淨複本，都從 `git archive 78ecbdcac`（開工時的 HEAD）抄出、各自在複本裡跑 `install.py`、清掉 `AOS_*` 後逐夾跑 unittest（`py/tests`、`py/tests/apps/*`、`py/tools/**/tests`、`templates/tests/*`，共 68 夾）。暫存在 `~/.aos/scratch/aos-hook-k1-1120/`。

| | 基準 `base`（只有 HEAD） | `mine2`（HEAD 疊上本線 11 個檔） |
|---|---|---|
| 退 0 的夾 | 67 | 67 |
| `py/tests` | 602 支 OK（skipped 1） | 626 支 OK（skipped 1、expected failures 1）：多出的 24 支是兩支新測試 |
| 其餘 66 夾 | 全 OK | 逐夾支數與結果跟基準一樣（含 `templates/tests/test_start.py` 的 ann 抄本比對） |
| `templates/tests/image-move-check/` | 0 支、退 5 | 同（不是 unittest，是 `check.py` 腳本，兩邊一樣，沒另外跑） |

- 複本 install 後 `lib/aos/apps/hook/loop_points.json`、`lib/aos/apps/eca/hook_points.json` 都在（09b 刀 1 的驗收）。
- 沒起任何樹、沒叫模型；開工與收尾 `pgrep -a aos` 都是空的。
- `~/.aos/scratch/aos-hook-k1-1120/mine/` 是第一次抄錯路徑留下的半成品（沒跑），沒刪。

## 第 2 刀、第 4 刀開工前要知道的

- **第 2 刀**：
  - `hook_point.open` 要接 `change` 的型別檢查時，`before_tool` 的 `arguments` 宣告是 `any`（照今天行為）；若想改成 `object` 是行為改變，要記一筆或問。
  - 合併後的點有 `said`；印事件給人看（`aos-hook points`、`self_hook events`）時從 `said` 逐份印。
  - 宣告裡 before_run／after_run 有 `not_fired_yet`；第 3 刀以前沒人讀所以無害，但**第 3 刀讓 `hook add` 照聯集驗時，要決定 `not_fired_yet` 的點算不算「可掛」**（不算＝第 5 刀前掛不上；算＝掛得上但不會跑）。第 5 刀接好後把那兩格拿掉。
  - `agentlib/hooks.py` 已 331 行（F10），把手放新檔比較好。
  - 一致性測試的 `Tables` 段比的是 `hooks.EVENTS`；第 3 刀把 EVENTS 改成由宣告算出後，這段會變成自己比自己，要改成跟固定期待值比（09b 刀 3 驗收已寫）。
- **第 4 刀**：
  - `aos-hook` 本體放 `py/aos/apps/hook/`（同夾已有 `loop_points.json` 與 README.md，README 要擴寫）。
  - 欄位物件形式的規則：`about`、`env` 必填，`type` 是 `int` 或 `string`、預設 string；`env` 有設且非空才用、轉不了整數＝`ArgumentsBad`（A14）。
  - `--points` 讀宣告用 `hook_point.read`，`--agent` 用 `for_definition`（現在所有定義夾都還沒有 `hook_points` 鍵，會回空表）。
- **兩刀都要**：install 之後新檔才進 `lib/`；在 `~/repo/aos/proto8` 跑 `install.py` 要使用者點頭（本刀沒跑）。
