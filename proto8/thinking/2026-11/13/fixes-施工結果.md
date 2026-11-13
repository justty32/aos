# 線庚施工結果（11-13）：eca_main 第 7、6、3、1 項與外部 MCP 實測三題都修了、各一個 commit，set-def 做了但 daemon 有一個缺口；全套測試只紅既有的

← [11-13 日索引](README.md)｜評估：[eca-main-six-fixes](eca-main-six-fixes.md)、[external-mcp-real-server](external-mcp-real-server.md)

## 結論

| 項 | commit | 修了什麼 | 什麼時候生效 |
|---|---|---|---|
| 第 7 項 codex 子 agent thread | `a89759e57` | 畫面 hook 認出子 agent 的 thread（對話檔第一行有 `parent_thread_id`）就不理；`session.txt` 已記到子 thread 時，非互動那條改接它的主對話、提醒一行 | repo 存檔即生效 |
| 第 6 項 重複旗標 | `ee906d9ee` | `cli.json` 的 `flags`／`print_flags` 寫了 aos 自己會加的旗標＝讀設定時 `CfgBad`（信留在 queue、不進冷卻）；文件加一張表 | repo 存檔即生效 |
| 第 3 項 rm／stop 要 ws | `57b7539cb` | 工作區不在時改拿 stack 當工作區去關畫面、提醒一行，不再被 `WsMissing` 擋 | repo 存檔即生效 |
| 第 1 項 找 aos-tools | `0b0aaf106` | `lib/aos/defs/catalog.py` 改從 PATH 找 aos-tools，找不到給清楚原因 | 要重抄 lib 進 aos-home |
| 外部 MCP 第 2 題 圖片路徑 | `a4ae7d573` | `mcp_tool` 的存檔提示改印 `$AOS_STACK/tools/<登記名>/檔`（從腦自己的 stack 算） | 要重抄 lib 進 aos-home |
| 外部 MCP 第 3 題 改名 | `1b9fcec2b` | `aos-mcp-import sync` 遇到「匯入後改名／抄成別名」的檔報 `PackBad`；README 寫重新匯入的步驟 | repo 存檔即生效 |
| 外部 MCP 第 1 題 server 起不來 | `f225b4754` | 起 CLI 前先看 stdio server 的指令找不找得到、能不能執行，不行＝warning 跳過那台；claude 非互動那條讀開場事件，外部 server 沒連上＝warning 一行 | repo 存檔即生效 |
| 測試收行程 | `88c571674` | `test_rm_keep.py` 不再用 `pkill -f`，改成只收 cwd 在自己暫存夾裡的 pid | 只是測試 |
| 第 4 項 set-def | `ab19068d0` | 新增 `aos-agent ctl set-def [--restart] NAME DEF` | repo 存檔即生效 |

沒做：第 2 項 rename、第 5 項（等使用者裁）；「AOS_HOME 指什麼」的條文與知識庫字句沒動。

## 各項要記的事

- **第 7 項**：子 agent 還能再開子 agent，所以非互動那條是一路往上找到主對話（`codex_main_thread`）。gpt-price 的 `session.txt` 在修之前已經自己換到一段新的 exec 對話（不是子 thread），不用手動處理；被清掉的 history 原文在它 stack 的 `history_removed.jsonl`（5 筆 `op: clear`），aos 不會自動放回去；它跟畫面上那段主對話（`01a1d280…`）已經分開，要接回那段得人自己決定。
- **第 6 項**：claude 身也擋（`-p`、`--print`、`--output-format`、`--session-id`、`--resume`、`-r`、`--continue`、`-c`）。活樹七份 `cli.json` 都沒有這些旗標（唯讀看過），不會有人因此停下。
- **第 1 項**：只修程式。沒設 `AOS_HOME` 時的預設值跟原本一樣（放這份 lib 的資料夾）。
- **外部 MCP 第 2 題**：隊員原本改成印絕對路徑，審的時候改掉——結果行會進 history，N-67 ⑦ 說不落絕對路徑。現在的做法是 `mcp_tool` 看自己的小格是不是 `tools/<名>/` 這個形狀（aos-tools 給 call 的小格），是就印從上兩層算的路徑。`tool_io.place` 與 aos-tools 沒動；其他工具印的 `$AOS_STACK/…` 仍是工具小格的意思（同一類問題，沒處理）。
- **外部 MCP 第 3 題**：叫工具那一刻認不出來——抄出來的檔，`tools` 的指標還指著舊檔，aos-tools 照指標跑舊檔那一格，`mcp_tool` 手上的 `--pack`、`AOS_CF`、cwd 全都一致。要在叫的那一刻擋，得改 aos-tools 多傳「是哪份檔登記的」，沒做。
- **外部 MCP 第 1 題**：兩半都做了，都只是 stderr 一行 warning。codex 的 `--json` 沒有連線狀態的事件；server 起來之後才壞的（握手失敗、中途死掉）仍只有 CLI 知道。施工中一次失誤：`stdio_ready` 第一版存檔時少了把 lib 放進 `sys.path`，約一分鐘內「列了 stdio 外部 server 的 eca」會 `ModuleNotFoundError`；那段時間活樹唯一列 `mcp_servers` 的 gpt-price 是 http server、沒走到。
- **set-def**：用 daemon 本來就收的「同名 `procs_added`」。實測發現 daemon 一個缺口：換的設定只活在跑著的 daemon 裡，表上那列要到那隻重起才換；**還沒重起、daemon 自己先重啟＝回到舊定義**（在跑的、停著的都一樣）。沒改 C++，寫進 `--help`、提醒行、README，並留兩支 `expectedFailure`。`--restart`（或自己 stop＋start）之後就寫進表、不會掉。

## 代定（可翻案）

- 第 6 項 claude 身的八個旗標也擋（照評估）。
- 外部 MCP 第 2 題印 `$AOS_STACK/tools/<名>/檔` 而不是絕對路徑（守 N-67 ⑦；代價是 `mcp_tool` 認得 aos-tools 的小格形狀）。
- 外部 MCP 第 3 題的 `PackBad` 放在 `aos-mcp-import sync`（叫工具那一刻做不到）。
- 外部 MCP 第 1 題的連線提醒只看 cli.json 列的外部 server，不看 aos 自己那台、也不看使用者 CLI 自己設的。
- set-def 不看新定義宣告的 `limits`，表上原本的照舊；在跑又沒給 `--restart` 時照收、提醒一行（不是拒絕）。

## 要使用者裁的

1. **set-def 的缺口怎麼收**：(a) 維持現狀，文件寫明「設完要重起才算數」；(b) set-def 改成「停→拔→用同一個 stack 掛回」（表馬上換、不怕 daemon 重啟，但中間有一小段不在表上，寄給它的信會被退）；(c) 改 daemon，讓同名 `procs_added` 直接改表（要動 C++）。建議 (c)，在那之前先 (a)。
2. **工具印的 `$AOS_STACK/…` 到底從誰的 stack 算**：現在工具印的是自己小格的，腦讀到會當成自己的 stack。這次只修了 `mcp_tool` 的存檔提示。要不要全家一起改（aos-tools 多給工具一個「叫我的那方的 stack」，`tool_io.place` 照它算）？建議改，另開一條線。
3. **抄成別名的 server 檔要不要在叫工具時就擋**：要的話 aos-tools 得多傳一個變數給工具（新增對外格式）。建議先不做，`sync` 已經會報。

## 測試

- 每項都先寫能重現的測試、在未修的程式上看它紅，再修到綠（set-def 是新功能，測試跟程式一起寫）。新增的例名寫在各 commit 訊息裡。
- 收線前全套（10:38～10:51，66 夾逐夾跑、環境裡的 `AOS_*` 全拿掉）：**1412 例，只紅既有 4 支**——`cmd/aos-agent/tests` 的 `test_daemon_down` 2 支（`test_add`、`test_stop`）、`lib/aos/box_check/tests` 的 `test_acceptance` 2 支（`test_measure_boxed_passes`、`test_real_boxed_whitelist_and_writes`）；另有 `test_set_def` 2 支與 `templates/tests` 2 支是預期失敗。
- 沒驗：真 codex／真 claude 上的實跑（都用假 CLI）；`set-def` 對 `--ws-json`／`--stack-json` 指示詞掛的 agent。
