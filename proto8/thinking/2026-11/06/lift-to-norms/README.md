← [2026-11-06](../README.md)｜[thinking](../../../README.md)

# 把 11-03～11-06 thinking 裡使用者已定的東西寫進條文（lift-to-norms）

使用者 11-06：「感覺可以把最近幾天的thinking，其中的一些東西提取出來，拿去更新concep,normal」（＝CONCEPTS、NORMS；慣例 CONVENTION 是同一層的兄弟，裁定點名到 P-44 的一併寫）。

**一句話結論**：四天 thinking 盤出 338 項，收 105 項——開了 N-65 兩鐘規則、N-66 非同步呼叫、C-76～C-82、P-45、P-46 與名詞表「板子比喻」；同日第二輪照使用者 os-concepts 裁定再開 C-83 可遷移性與 N-67 可遷移性檢查單，其餘是既有條加註／改讀；**只收使用者原話與已裁（含「照推薦」）**，代定、未裁、排程、純實作不收；**還沒實作的一律寫「已定；實作排在 <步>」**，不寫成現況；既有句子與原話一句沒刪。

| 份 | 內容 |
|---|---|
| [01-盤點](01-盤點.md)（[csv](01-盤點.csv)） | 338 項：出處、原話／裁定、落點、已實作沒、收不收與原因、隊長最終裁定 |
| [02-改了哪些條](02-改了哪些條.md) | 每條一句改前 → 加註後，帶盤點 id |

隊員回報（逐條、跟盤點對不上的、拆了哪些檔）：`_out/X.md`（codex `gpt-6.1-sol`：NORMS、CONVENTION）、`_out/Y.md`（claude opus：CONCEPTS）。隊長逐處審過 diff，改了三處：`AOS_TICK` 從四種性質表 ① 那格拿出來（後來照下方題 2 的裁定歸 ②）、N-15 一句改讀的措辭、兩處 `py/daemon_ctl.py` 改指 S8 拆出的 `py/daemon_ctl/`。

## 打架的題（11-06 使用者已裁三題，選項框都選推薦）

1. **tick 欄位名**：Q4 照推薦的範例名 `deadline_tick`、`sent_tick` 跟 10-23 選的 C-54 R6「時間點 `<事件>_at_<單位>`」不合。使用者選「照命名法 (Recommended)」→ `sent_at_ticks`、`deadline_at_ticks`、`acquired_at_ticks`；多久的 `lease_ticks`、`stuck_after_ticks` 不變。已寫進 C-54 R6 的 11-06 註，tick-time README Q4 與 03 的記錄欄加改讀註。
2. **`AOS_TICK` 歸哪一格**：① 寫「aos-exec 每層設」、② 寫「值是資料夾、沒設＝Missing」，字面都不合。使用者選「跟 AOS_KERNEL 同類 (Recommended)」→ 歸 ② hub、當例外：值是時鐘檔路徑、沒設退回牆鐘、不報 Missing。四種性質表已照改。
3. **同一個資料夾起兩個 daemon**：11-03「這是使用者自己要承擔的風險」（不擋）對上 N-28 11-05 補④ `DaemonRunning` 退 1（代定）。使用者選「繼續擋 (Recommended)」→ N-28 加註確認擋；11-03 那句改讀成同一工作區、不同 stack 的情況（本來就不擋），procs 11 也加同樣的改讀註。
4. **範本 `wait.py` 退 11** 已由 11-07 使用者裁定 sol 審查 #29 認可：表上接住是分岔，腦設定改過對不上也可退 11；原先跟 P-19「結束碼三種」的字面落差已加註；small-thought「thought／agents 在沙箱先不支援」跟 no-pid「沙箱裡的東西只要一個信箱就夠」方向有點張力。兩件都沒動條文，等 P5 沙箱範例時再看。
   - 改讀（11-06）：沙箱那件使用者已裁「正式支援」，張力已解，見 [no-pid 13 § 使用者裁定](../../05/no-pid/13-P5實作結果.md#使用者裁定11-06)。

另外：[os-concepts](../os-concepts/README.md) 草稿暫稱的「C-76／N-65」可遷移性兩條，使用者 11-06 裁「概念＋檢查單」後由本夾寫成 **C-83、N-67**（C-76、N-65 已被第一輪用掉）；同時照使用者「不放寬」在 C-83 寫明 no-pid 那批照舊（pid 搬不走）。os-concepts 順帶的兩句建議（C-47 旁「排序由 kernel 身體做、掛不掛由 daemon 做」、板子比喻 `.env` 每一跳讀）也收了，標「說明，不是新規則」。

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
- **P-44**「沒有短旗標」→ 每支自定短名、常用表只作預設（11-07 使用者裁定 sol 審查 #22）；「Python 是 aos_flags.parse」→ 改 tool_io（J5）。
- **P-43**「stack 的副本」→ 覆蓋層；**P-19／P-35** 的例子 think 退 10 → act 退 10。

## 不收的（233 項，全在 csv 的「隊長」「原因」欄）

- **已在條文 106**：11-03 的 procs、ctl-commands、aos-post、stack-where、trace、eca-tools，no-pid P5b 今天寫的那批，stdio-unify、edge-* 裁的題，kernel-daemon 多半。
- **代定或建議 43**：human-cli H1～H16 其餘條、daemon-board 代定 1～5、body-protocol 衝突表推薦（含 C-52 例外 ④、`ping` 保留字）、json-argv 衝突 2～8、tick key 形狀細則、arch-refactor 的 inst 改名等。
- **已翻案 33**：11-03「sleep／wake 先不開放」、`AOS_DAEMON_STACK`、`.aos/agent.json`、think-as-function 的 kernel 自己跑、三格＋`AOS_BRAIN_*`、11-05 夜暫定「body＝inst」、tick Q1／Q2 原推薦、small-thought 的 `--env` 形狀等。
- **未裁 4**、**其他 47**：排程（apply-ideas、aos-serve 何時做、S8／S9）、純實作或程式 README（套件結構＝群組子資料夾是 cmd 的佈局、install.sh、kernel.json 設定值）、wf 規矩（tests-trim 在 testing.md、arch-refactor 七題在 AGENTS／wf）、叫人去測／去查而不是定一件事。
- **隊長改判 2**：A115「四個元素：argv、環境變數、json內部結構、資料夾結構」是你提問的前提句，沒收；你要收的話一句話開一條 C-。C18 C-66「指標＝AOS_WS」加知識庫根那句是推論（你裁的本體在 lib 規則 4），沒收。

## 拆檔

讓檔從 ≤8 KB 變 >8 KB 的，整條逐字搬到同夾續檔、原位留錨點與指標：C-42、C-75、P-15、P-43、P-36。本來就超過的（N-28、N-16、P-23、C-51、名詞表）照 no-pid P5b 前例不拆、直接加。

## 使用者裁定（11-07，sol 審查；以下取代同題舊代定）

11-07 使用者裁定 sol 審查 #8：「8A」——aos-agent 經判官地址指不到仍報 MailboxMissing，退回 daemon 信箱會繞過判官。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）

11-07 使用者裁定 sol 審查 #11：「11A」——信裡的毫秒指跨樹牆鐘語意而非 tick，ISO／秒格式照舊，不宣稱已改成毫秒格式。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）

11-07 使用者裁定 sol 審查 #12：「12A」——時鐘停住時，判卡住、鎖租約、tick 逾時一起停；要它們走就 resume 時鐘。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）

11-07 使用者裁定 sol 審查 #15-1：「15-1A」——被叫時間採子 ctl.json 修改時間，使用者確認可接受。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）

11-07 使用者裁定 sol 審查 #15-2：「15-2B*」——首次讀 ctl 只略過與舊 state.ctl_seq 相同的已套用指令，其餘照做並回音；PhaseBad 限制照舊。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）

11-07 使用者裁定 sol 審查 #19：「19A」——image＝stack＋ws，定義是外部原始碼；完整搬家說明集中在 C-79。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）

11-07 使用者裁定 sol 審查 #22：「22B*」——每支指令各自定短旗標，同名可不同義，共用短名表只作常用預設。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）

11-07 使用者裁定 sol 審查 #23：「23A」——同型特例再出現時問會不會更多、好處是否遠大於壞處，是才升格；次數只提醒。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）

11-07 使用者裁定 sol 審查 #25：「25A」——公開介面只限標頭、schema、interfaces.json；K2 只原件、K4 只 tick、K5 只個案。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）

11-07 使用者裁定 sol 審查 #28：「28A」——daemon 有回應機制但時限內沒回信報 DaemonFailed；DaemonMissing 留給沒設或目錄不在。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）

11-07 使用者裁定 sol 審查 #29：「29A」——表上明接的 wait 11 是分岔；腦設定改過對不上也退 11，一併認可。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）

11-07 使用者裁定 sol 審查 #30：「30A」——--env-file 維持登記當下讀檔存內容，使用者已裁。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）

11-07 使用者裁定 sol 審查 #33：「33B*」——子資料夾＝子動作已定稿，不用再等使用者看實作。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）
