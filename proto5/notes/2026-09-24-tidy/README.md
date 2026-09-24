# 整理 wf／proto5 notes（2026-09-24 tidy）

← [notes 索引](../README.md)｜[proto5 README](../../README.md)

使用者原話：「重構拆檔＋tidy，目標是 wf 和 proto5。」`proto5/spec/` 另一隊在拆，這隊不碰 spec、也不碰指向 spec 的連結。
沒動任何程式（`proto5/lib` 只看了 README，沒改），所以沒跑全套測試。

## 改了什麼

**wf/**

- [SESSION-LOG](../../../wf/SESSION-LOG.md)：4095 → 約 2.6 KB。09-24 那條整段原文搬到 [session_logs/2026-09.md 的 2026-09-24 節](../../../wf/session_logs/2026-09.md#2026-09-24)（放最上面，連結多一層 `../`，尾巴註明 fix-r4 已合）。SESSION-LOG 只留一行 open：fix-r5、cpu 動態增減六點、spec 拆檔、C-7／C-8、WAIT_USER A.14～A.18、`tools`／`init --template`、打遊戲不碰 GPU 走 LiteLLM、每 commit 推。fix-r4 已合，從 open 拿掉；09-22 那行的「backlog 八件」已在 09-24 清光，改成註記。
- [session_logs/README](../../../wf/session_logs/README.md)：補 09-24、09-23 兩列（09-23 那節早就在封存檔裡，只是索引沒列）。
- [WAIT_USER](../../../wf/WAIT_USER.md)：A 段開頭註明「編號固定、拍掉的不回收，所以跳號」（別處用「WAIT_USER 第 N 條」引用，不能重編）；A.14(e) `pause` 標成 fix-r4 已做掉（暫停中連回音也不收），(d) fail 狀態等其餘七題照舊待拍；A.9（T-01～T-77「都 OK」、只是可翻案）不是等人拍的事，移到 C 段；A.13 補連結；C 段尾巴那條「08-24 已整條解掉」的完成紀錄刪掉，只留「細節記在 roadmap」那句指路。
- [INDEX](../../../wf/INDEX.md)：開頭「第一個小專案是 core/inst」與 `core/` 列「目前只有 inst/」都過時（實際是 exec／wire／loop／llm／agent／tick＋tool），改成指 core/README；`proto*/` 列換成 proto5 現況（spec／lib／cli、notes 索引），補 proto5.1、proto4-7；補漏列的頂層 `reference/`。
- `wf/workflows/ideas/archive/` 底下 102 條死連結：檔案搬進 `archive/` 時深了一層、相對路徑少一個 `../`。逐條試加一層，加了能找到檔才改，102 條全部解掉（wf-lint 預設不掃 archive，所以之前沒報）。

**proto5/**

- 新增 [notes/README.md](../README.md)：按日期分組的索引（09-21 開場、09-22 四份調查的「任務書／astra 報告／精簡總結」對照表、09-23～24 重架構與試玩）。
- [2026-09-23-rearch/README](../2026-09-23-rearch/README.md) 的表漏了 `impl-findings.md`、`backlog-cleanup.md` 兩份，補上；其餘每列的檔都在。
- play／daemon-crash／rearch 三個 README 的頂端導覽加「notes 索引」。
- [proto5 README](../../README.md)：通讀一遍，`AOS_K`、`aos-kernel stop`、`last` 只出現在「取代舊的 last」與「從舊版升上來」兩處，都是刻意寫舊名，不用改；指令表對照 `cli/* -h`（aos-daemon boot／halt、aos-kernel 九個子命令、aos-agent 九個、aos-llm call、aos-exec、aos-cpu）都對得上；「30 個測試檔、1100 條」用 unittest 載入數過，也對。只把「筆記」段的 notes 連結改指新索引。
- [lib/README](../../lib/README.md)：敘述段與現況一致（二十九支模組、fix-r4 的 `--target`、listen），沒改。

## 搬檔

**沒搬。** notes 根目錄的十幾份散檔維持原位，理由寫在 [notes 索引](../README.md#為什麼散檔沒收進子資料夾2026-09-24-tidy-判斷)：09-22 那批帶約 700 條指向 `spec/`／`lib/` 的連結，搬一層就得全改，正好跟拆 spec 那隊改同一批連結、一定撞；notes-brief 與 proto5.1 也連進來。spec 拆完後可以再考慮。

## 壞連結

檢查用 repo 的 `wf/tools/wf-lint.sh`（只掃指定資料夾、不掃 archive）加上一支 scratchpad 小腳本（全 repo 所有 `.md`，分「檔不存在／`路徑:行號` 寫法／絕對路徑／錨點不存在」四類）。

| | 修前 | 修了 | 剩 |
|---|---:|---:|---:|
| proto5/notes：`[文字](路徑:行號)` 寫法（檔在，但 `:行號` 讓連結打不開） | 804 | 545 | 259（全指 spec） |
| proto5/notes：檔不存在 | 15 | 10 | 5（全是 `spec/exec.md`，已改名 aos-exec.md） |
| proto5/notes：絕對路徑 | 15 | 2 | 13（全指 spec） |
| wf/session_logs：`proto5/backlog/` 已刪 | 2 | 2 | 0 |
| wf/workflows/ideas/archive：少一層 `../` | 102 | 102 | 0 |
| 合計（我的領地） | 938 | **661** | **277，全部指向 proto5/spec** |

- `路徑:行號` 的改法：行號搬進連結文字（文字已經有同一個行號就只剝掉目標尾巴），例如 `[aos_cpu.py:102](../../proto4-2/aos_cpu.py)`——照 [fix-abs-links](../2026-09-24-fix-abs-links.md) 之後「行號留在連結文字裡」的做法。
- 指向已刪 `backlog/` 的（decisions、backflow、09-23 review1 的六個 backlog 檔、session_logs 兩處）：改成純文字加「（已刪，見 backlog-cleanup）」連到 [09-24 清光筆記](../2026-09-24-backlog-cleanup.md)；`cpu-simpler`、`kill-tree-exceptions` 兩件在 09-24 那份沒提，連到 [09-23 那輪](../2026-09-23-rearch/backlog-cleanup.md)。
- 其他：`protos4-5` 打錯字改 `proto4-5`；timeout 報告兩條連到本機 `/usr/lib/python3.12/…` 的改成行內 code（不是 repo 裡的檔）。

**留給拆檔隊的 spec 連結**：277 條，逐條在 [spec-links.tsv](spec-links.tsv)（類別、來源檔:行、目標）。分三種：

1. **LINENO 259 條**：`](../spec/xxx.md:行號)` 或 `](../../spec/xxx.md:行號)`，spec 檔都在，只是 `:行號` 讓連結壞掉；拆檔後行號本來也會失效，建議拆完一起改成新檔＋章節。集中在 09-23 rearch 的 review1～4、review-agent1 報告與 09-22 四份 astra 報告。
2. **MISSING 5 條**：`../spec/exec.md:行號`（2026-09-22-daemon-kernel-report-astra.md 4 條、timeout-report-astra.md 1 條），目標早已改名 `aos-exec.md`。
3. **ABS 13 條**：`2026-09-23-rearch/review-agent4-report.md` 用了 `/home/lorkhan/repo/simple_tools/aos/proto5/spec/…:行號` 絕對路徑。

**不在領地、沒動的死連結**（118 條）：`proto4/notes` 54、`proto4-7/notes` 16、`proto4-6/notes` 4 條絕對路徑；`docs/archive/roadmap/` 42 條（跟 ideas/archive 一樣是搬檔少一層，指向 wf／reference）；`proto/README.md`（`bin/aos`）、`reference/PORTING.md`（`core/inst/docs/cxxapi.md`）各 1 條。

## 順手看到、留給使用者的

- **fix-r5 的「八條」沒有成文清單**：SESSION-LOG 只寫「r4 兩份共同痛點八條」，play 表和 notes 裡都找不到這八條逐條列出；開 fix-r5 前要先從 [r4 astra](../play/2026-09-24-r4-astra.md)／[r4 Opus](../play/2026-09-24-r4-opus.md) 兩份報告整理出來。
- WAIT_USER A.3～A.13 都是 proto2／workshop 時代（08-24～09-07）的題目，proto5 之後可能已經不相關；要不要整批移到 C 段由使用者說。
- `proto5/notes-brief/` 不在這次領地，它的 README 仍是 09-22 的樣子（23 題總表），沒改。

## 審查

codex gpt-6-astra 唯讀審一輪：[任務書](review-task.md)、[回報](review-report.md)。結論：非 spec 的死連結 0、archive 那 102 條都指對檔、行號搬進文字沒弄壞表格、索引沒漏、SESSION-LOG 的 open 與 (a)～(f) 全在、09-24 全文除了連結多一層 `../` 外逐字、WAIT_USER 沒丟內容。挑出三條，都修了：

1. （真問題，舊的）proto5 README 第 3 段說「`aos-kernel add` 退 0 代表 kernel 收了單、回了音」，但 `add --once` 沒帶 `--wait-ms` 時只印單名與回音路徑就退 0、不等回音——補上這個例外。
2. （小，舊的）第 5 段「三行各印 `stopped`」：`aos-agent stop` 實際印 `stopped agent-bob`——改正。
3. （小）session_logs 索引「WAIT_USER 集中說明」只連到「最小原型」那節——拆成兩列，各連自己的節。
