← [2026-11-06](../README.md)｜[thinking](../../../README.md)

# 把 11-03～11-06 thinking 裡使用者已定的東西寫進條文（lift-to-norms）

使用者 11-06：「感覺可以把最近幾天的thinking，其中的一些東西提取出來，拿去更新concep,normal」（＝CONCEPTS、NORMS；慣例 CONVENTION 是同一層的兄弟，裁定點名到 P-44 的一併寫）。

**一句話結論**：四天 thinking 盤出 338 項，收 105 項——開了 N-65 兩鐘規則、N-66 非同步呼叫、C-76～C-82、P-45、P-46 與名詞表「板子比喻」，其餘是既有條加註／改讀；**只收使用者原話與已裁（含「照推薦」）**，代定、未裁、排程、純實作不收；**還沒實作的一律寫「已定；實作排在 <步>」**，不寫成現況；既有句子與原話一句沒刪。

| 份 | 內容 |
|---|---|
| [01-盤點](01-盤點.md)（[csv](01-盤點.csv)） | 338 項：出處、原話／裁定、落點、已實作沒、收不收與原因、隊長最終裁定 |
| [02-改了哪些條](02-改了哪些條.md) | 每條一句改前 → 加註後，帶盤點 id |

隊員回報（逐條、跟盤點對不上的、拆了哪些檔）：`_out/X.md`（codex `gpt-6.1-sol`：NORMS、CONVENTION）、`_out/Y.md`（claude opus：CONCEPTS）。隊長逐處審過 diff，改了三處：`AOS_TICK` 從四種性質表 ① 那格拿出來改記在表外（見下方題 2）、N-15 一句改讀的措辭、兩處 `py/daemon_ctl.py` 改指 S8 拆出的 `py/daemon_ctl/`。

## 要使用者裁的（兩個裁定、或裁定跟現行條文打架）

1. **tick 欄位名的形狀**：tick-time Q4 照推薦的範例名是 `deadline_tick`、`sent_tick`、`lease_ticks`；10-23 你選的 C-54 R6 是時間點 `<事件>_at_<單位>`（例 `started_at_ticks`）、多久 `<名>_<單位>`。「多久」那半對得上（`lease_ticks`），「時間點」那半不合。**推薦：照 R6**——`sent_at_ticks`、期限 `deadline_at_ticks`；條文現在只寫「帶 tick 單位、不沿用舊名」，名字等你一句（C-54 R6 的 11-06 註）。
2. **`AOS_TICK` 歸四種性質表哪一格**：它是繼承的、指一個時鐘檔的路徑，沒設＝退牆鐘不報錯；① 執行環境寫「aos-exec 每層設」、② hub 寫「值是資料夾、沒設＝Missing」，都不合字面。**推薦：歸 ② hub、當例外**（跟 `AOS_KERNEL` 沒設有退路同類），例外寫「值是檔、沒設退牆鐘」。現在先記在表外。
3. **同一個資料夾起兩個 daemon**：你 11-03 說「這是使用者自己要承擔的風險」（不擋）；現行 N-28 11-05 補④是 `DaemonRunning` 退 1（擋），翻它的是 11-05 的代定、不是你。**推薦：保留擋**——擋的是同一個 stack 起兩台、同時寫同一張表；你 11-03 那句若指的是同一個工作區、不同 stack，兩者其實不衝突。這次沒改條文。
4. （次要）**範本 `wait.py` 退 11** 是 11-05 邊緣修法、你沒裁，跟 P-19「結束碼三種」字面不合；small-thought「thought／agents 在沙箱先不支援」跟 no-pid「沙箱裡的東西只要一個信箱就夠」方向有點張力。兩件都沒動條文，等 P5 沙箱範例時再看。

另外：今天 [os-concepts](../os-concepts/README.md) 的草稿用了暫稱「C-76／N-65」，這兩號已被本次用掉，那份定稿時要另編號。

## 會動到你的概念、只加註沒重寫的

原句都留著，後面加 `11-06 改讀`：

- **N-01**「大家都要看 tick-tock 時鐘」→ 內部約時間看 tick；對人、對外、對 Linux proc 用牆鐘（你 11-05 原話）。
- **N-03**「打包由 kernel 做」→ 現況是 daemon sleep 的硬凍；軟凍現在沒有。
- **C-17**「停下來時正在跑的任務可以不被迫停止」→ 現在只有硬凍，「不被迫停止」靠 stack／state 醒來接著做，不是行程不停。
- **N-15** 名牌 pid 三欄、「flock 只拿來同機加速，不當正確性依據」、收屍、「判死活兩套並存」→ 改 flock（已定、T2）。
- **N-16**「壞信不通知寄信人」→ 只指信封壞；body 不合照 N-66 回錯誤信（跟 10-28 決定 27 字面相反，以 11-06 為準）。
- **N-17**「不從檔案的更新時間判」→ P7 讀 `responded_at` 判卡住，不衝突（判的是叫不動、不是死活）。
- **N-28**「子項結束後不自動重起」→ 多兩個規劃中的例外：`_tick`、選填 `restart_on_stuck`；收工 sleep 那句的「先不開放」已翻。
- **四種性質表 ④**「旋鈕原則上不走環境變數、現無」→ 多一個你特許的 `AOS_TICK_INTERVAL`。
- **C-42**「上限交給判官 `max_running`」→ 兩道關（工具自己數＋判官管總量）。
- **P-44**「沒有短旗標」→ 只准九個共用短名；「Python 是 aos_flags.parse」→ 改 tool_io（J5）。
- **P-43**「stack 的副本」→ 覆蓋層；**P-19／P-35** 的例子 think 退 10 → act 退 10。

## 不收的（233 項，全在 csv 的「隊長」「原因」欄）

- **已在條文 106**：11-03 的 procs、ctl-commands、aos-post、stack-where、trace、eca-tools，no-pid P5b 今天寫的那批，stdio-unify、edge-* 裁的題，kernel-daemon 多半。
- **代定或建議 43**：human-cli H1～H16 其餘條、daemon-board 代定 1～5、body-protocol 衝突表推薦（含 C-52 例外 ④、`ping` 保留字）、json-argv 衝突 2～8、tick key 形狀細則、arch-refactor 的 inst 改名等。
- **已翻案 33**：11-03「sleep／wake 先不開放」、`AOS_DAEMON_STACK`、`.aos/agent.json`、think-as-function 的 kernel 自己跑、三格＋`AOS_BRAIN_*`、11-05 夜暫定「body＝inst」、tick Q1／Q2 原推薦、small-thought 的 `--env` 形狀等。
- **未裁 4**、**其他 47**：排程（apply-ideas、aos-serve 何時做、S8／S9）、純實作或程式 README（套件結構＝群組子資料夾是 cmd 的佈局、install.sh、kernel.json 設定值）、wf 規矩（tests-trim 在 testing.md、arch-refactor 七題在 AGENTS／wf）、叫人去測／去查而不是定一件事。
- **隊長改判 2**：A115「四個元素：argv、環境變數、json內部結構、資料夾結構」是你提問的前提句，沒收；你要收的話一句話開一條 C-。C18 C-66「指標＝AOS_WS」加知識庫根那句是推論（你裁的本體在 lib 規則 4），沒收。

## 拆檔

讓檔從 ≤8 KB 變 >8 KB 的，整條逐字搬到同夾續檔、原位留錨點與指標：C-42、C-75、P-15、P-43、P-36。本來就超過的（N-28、N-16、P-23、C-51、名詞表）照 no-pid P5b 前例不拆、直接加。
