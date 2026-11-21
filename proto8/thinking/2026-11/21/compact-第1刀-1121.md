compact 改進第 1 刀施工紀錄：agent-fsm 的 `/compact` 叫腦寫摘要之前，先把舊的工具輸出換成一行佔位；真模型兩份長對話實壓，摘要那次 prompt 少七成多，摘要品質小幅掉（沒有掉到接不下去）。

← [2026-11-21](README.md)｜規劃稿 [compact-改進規劃-1121](compact-改進規劃-1121/README.md)（清法照 [02](compact-改進規劃-1121/02-先清工具輸出.md)、刀序照 [04](compact-改進規劃-1121/04-施工刀序.md)）｜使用者已答 [07](compact-改進規劃-1121/07-使用者已答.md)｜進度 `compact-improve`｜線 `top-1121-compact1`

## 使用者原話（11-21，逐字）

「可以派。三題：1.照叫。2.都開。3.我還在審。」——Q1 照叫＝一律清完再摘要（第 2 刀不做）；Q3 還在審＝第 4 刀先不動。這次只做第 1 刀。

## 結論

1. **做了什麼**：`/compact` 要叫腦之前（idle 與做到一半的 brain 兩條路），body 先把舊的 `role: tool` 內容換成一行英文佔位 `[aos] tool output cleared (N chars from TOOL); the original is in history_removed.jsonl`，原文接進 `history_removed.jsonl`（`op: "clear_tools"`）。之後照舊叫腦摘要、照舊摺。壓完的樣子跟以前一樣（一則摘要）。
2. **不清的**：最後 3 則工具輸出、最後一組工具呼叫的結果、短於 300 字的、已經是佔位的、content 不是字串的；工具呼叫與 arguments 一律不動；列不刪（工具配對不斷）。
3. **真模型實壓（sol）**：skyrim-chores 摘要那次 prompt 61,507 → 15,557 token（−75%），請求檔 215,427 → 66,090 bytes；skyrim-translate 55,368 → 15,605 token（−72%），193,739 → 61,824 bytes。
4. **摘要品質**：兩份都請 sol 對照原始對話評，兩次都說「沒清的那份好一點，差距 small」；接著做要的東西（誰要什麼、信名、回信處、做完沒、下一步、交付檔）兩邊都在。掉的主要是**透過工具讀進來的規矩與細節**（讀 AGENTS.md、system.txt、brief 檔的輸出被清掉，摘要少寫了幾條常駐規矩與一些確切值）。沒有到「明顯掉品質」，照任務書交程式；這點攤給使用者看（見「摘要品質比對」）。

## 動的檔

| 檔 | 改什麼 |
|---|---|
| `py/aos/agentlib/tool_clear.py`（新） | 純函數 `clear(history, keep_last=3, min_chars=300)`：回新列表與被換掉的 (索引, 原列)；佔位字一份。第 3 刀之後共用 |
| `templates/agent-fsm/compact.py` | 新 `clear_old_tools`：讀 → 算 → 寫暫存 → 指紋沒變才改名（共用 `replace`），三次不成或 history 讀不了＝放棄清、一行 warning、照舊摘要；`ask` 先清再加要求，有清時要求多一句 `CLEARED`（清了幾則、原文在哪）；`compact.json` 的 asked 與 done 多記 `cleared`、`cleared_chars` |
| `templates/agent-fsm/idle.py`、`brain.py` | `compact.ask` 多傳 `warn`（清不成時的那行 warning 走 `aos_flags.warn`） |
| `templates/tests/agent-fsm/test_compact_clear.py`（新） | 10 支：留最後 3 則／最後一組／短的／已是佔位、arguments 與非字串 content 不動、佔位帶工具名；idle 一輪做完（請求裡是佔位、`history_removed` 有原文與原行號、compact.json 記數）；沒得清時要求字不變；做到一半壓時最後一組留著、壓完接著做；history 一直變三次後放棄、變一次會重來；壞行不清；剛清過再清不重清 |
| `templates/docs/02-agent-fsm.md`、`templates/agent-fsm/README.md`、`knowledge/aos/me/compact.json` | 「寄 /compact 會怎樣」多一步、資料格式表（compact.json、history_removed 的 op）、舊 agent 換檔要多跑 install.py |

`templates/start-api/agents/ann/README.md`：開頭那段跟 agent-fsm README 同步（同一句）。ann 夾裡的格程式舊抄本沒動：見「撞檔」。

## 替使用者做的選擇（細節照規劃稿與原則定）

- **清的位置放進 `compact.ask` 裡**，不在 idle、brain 各寫一次：兩條路都一定經過 `ask`，一處就好；idle、brain 只多傳一個 `warn`。
- **有清才在要求裡多一句**（`CLEARED`），沒清的要求字一字不差，舊測試不用改。
- **清不成不擋摘要**：history 讀不了、一直在變（三次）、寫不進＝一行 warning、照舊摘要；跟摺失敗（`WriteFailed` 停下）不同，因為清只是省錢、不是必要步驟。
- **佔位寫工具名與原本字數**，不寫行號（`history_removed.jsonl` 那列自己有 `line`）。
- **`compact not needed`（太短）時不清**：沒叫腦就沒有要變小的請求。
- **`cleared` 也記進 done 那份 compact.json**，事後查得到這次清了多少。

## 真模型實測

- 暫存樹：`~/.aos/scratch/top-1121-compact1/trees/`，四棵 start-api 樹（`chores-base`、`tr-base` 用 HEAD 原樣那份，`chores-mine`、`tr-mine` 用疊了這刀的那份；ann 的四支格程式換成各自那份 agent-fsm 的），ann 用 `sol`，經使用者起的 LiteLLM `localhost:4000`。
- 對話：11-15 真模型跑出來的兩份 agent-fsm history（`~/.aos/scratch/swap-1115/r1/ws/.stack/procs/` 的 `skyrim-alt-chores` 99 則、`skyrim-alt-l10n-translate-1115a` 79 則），pause 後換進 ann 的 `history.jsonl`、resume，再 `aos-agent ask "/compact"`。
- 叫真模型共 6 次：四次壓縮（每份清與不清各一次）、兩次評分（sol 讀整份原始對話＋兩份摘要，A／B 對調過，chores 是 A＝沒清，translate 是 A＝清過）。

| 對話 | 清掉 | 請求檔 bytes | 摘要那次 prompt_tokens | 摘要字數 | 耗時 |
|---|---|---|---|---|---|
| chores 不清 | — | 215,427 | 61,507 | 12,231 | 83 秒 |
| chores 清過 | 33 則、121,081 字 | 66,090 | 15,557（−75%） | 9,843 | 52 秒 |
| translate 不清 | — | 193,739 | 55,368 | 6,224 | 39 秒 |
| translate 清過 | 14 則、103,825 字 | 61,824 | 15,605（−72%） | 4,977 | 29 秒 |

比規劃稿用字數估的（chores 68,329→約 29,800）省得更多：規劃稿估的是整份 think 請求（含 tools 說明），摘要那次本來就不帶 tools。

## 摘要品質比對

兩份評分的結論都是「沒清的那份好一點，差距 small」。逐項（評分原文在 `~/.aos/scratch/top-1121-compact1/quality/judge-*.txt`，四份摘要在同夾）：

- **兩邊都在的**：任務做完沒、信名（收到的與回出去的）、回信處、交付檔路徑、測試與 audit 的結果、commit `ac0a977`、goal／todo 狀態、下一步（等信）。評分說兩邊在這些上面都沒有實質錯誤。
- **清過那份少的**：
  - chores：自己的 stack 路徑、幾條常駐規矩（不改定義與別人的 stack、不用 `git add -A`、PoE 凍結、只有 modpack-main）、例外清單理由的原文（改成意譯）、「原本的早退判斷沒動」、「測試 log 是點號不是 -v」的保留語。
  - translate：加註裡的 `Rancher = 牧場工`、翻譯要求（台灣繁中、Skyrim 口吻、留空白與標記）、brief 細節（版本 0.1.21、DIAL 句型 `擔任<職務>，<task>。`）、「別 git add／commit、只寄隊長」、「暫停中讀新信前先 resume goal」、三十多條設施譯名（清過那份只寫兩條、其餘指向 terms 檔）。
- **清過那份多的**：chores 多寫了「modlist 行號小的贏」這條原則；translate 多寫了最新的 goal 暫停理由。
- **讀出來的**：掉的多半是**透過工具讀進來的東西**——agent 開工時用工具讀 AGENTS.md、system.txt、brief、glossary，那幾則輸出很長、不在最後 3 則，被清成佔位；腦寫摘要時只看得到自己當時的回應，常駐規矩就少寫幾條。腦自己寫進檔的東西（arguments 不清）大多還在。另外清過的摘要本來就短兩成左右，同一個模型每次寫也有落差，兩份各一次只能當量級看。
- **沒做的補救**（只列，不做）：要求字可以多叫腦「把你讀檔讀到的規矩也寫進去」；或之後第 4 刀的 `after_compact` 補回；或某些工具（例如讀 system、讀 AGENTS 的）不清。要不要、怎麼補是使用者的事。

## 測試

`git archive` 的乾淨複本，一份原樣、一份只疊這次的檔，各自 `install.py`，清掉 `AOS_*` 後逐夾 `python3 -m unittest discover`（這台沒有 pytest），腳本與結果在 `~/.aos/scratch/top-1121-compact1/`（`bin/suite.sh`、`suite-*.txt`）。跑了兩輪：

- **第一輪**（HEAD `9d15e31a7`，只有程式與測試、知識庫）：全套 80 夾，原樣 3,111 支、改後 3,121 支；`templates/tests/agent-fsm` 220 → 230（新的 10 支），其他逐夾支數與結果相同。
- **第二輪**（HEAD `cf5ad9bf6`，borrow 交了之後，疊全部九支檔）：原樣 3,127 支、改後 3,137 支；`templates/tests/agent-fsm` 220 → 230；`templates/tests` 29 兩邊都過（含 `test_start`：ann README 以 agent-fsm README 開頭）。
- 兩輪兩邊都紅的：`py/tests/apps/eca` 4 支（`test_switch.TtySocket`）、`py/tests/apps/feedback` 1 支，原樣那份一樣，是複本環境的關係；`image-move-check`、`templates/kernel/tests` 不是 unittest（0 支、退 5）。第二輪原樣那份另有 `apps/gdb`、`cpp/aos-loop` 各一支沒過、改後那份過，是兩份同時跑太擠，跟這次無關。

## 撞檔

- `top-1121-borrow`（起手範本 ann 改動態連結 agent-fsm 的格程式）開工時還沒交、沒 claim，所以先只動 agent-fsm 自己的檔，兩份說明文件等它交了（`cf5ad9bf6`）才在新 HEAD 上改。它交了之後 ann 的 `fsm.json` 指向 `$AOS_HOME/templates/agent-fsm` 的格，夾裡留著的八支 `.py` 已沒有檔引用（它說刪檔等使用者點頭），**這次不同步那幾支舊抄本**；ann 的 README 規定要以 agent-fsm README 原樣開頭（`test_start`），所以 ann README 同一句跟著改。
- `top-1121-kdefs` 動 `py/aos/` 的 defs／kernel，跟這刀沒有同一支檔。

## 舊 agent 怎麼吃到

repo 改了不會自己換進既有的樹。要吃到：

1. 在那棵樹用的 proto8 跑 `python3 install.py`（`tool_clear.py` 在 lib 裡；只換格程式不跑 install 的話，`compact.py` import 不到它，idle 一收 `/compact` 就會停）。
2. 把新範本的 `compact.py`、`idle.py`、`brain.py` 換進定義夾（這刀只動這三支，`wait.py` 沒動）；起手範本 start-api 的 ann 若已改成動態連結 `$AOS_HOME/templates/agent-fsm`，第 1 步就夠了。

## 沒做的

- 第 2 刀（清完夠低就不摘要）：使用者 Q1 答「照叫」，不做。
- 第 3 刀（`aos-agent history clear-tools`）：不在這次範圍。
- 第 4 刀（兩個 hook 點）：使用者還在審 `hook_points.json` 格式，先不動。
- arguments 不清（規劃稿定的第一版）。
- 沒在 repo 跑 `install.py`、沒碰 `~/aos-home`。
