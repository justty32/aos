# proto8-2 併進 proto8：怎麼併（2026-10-19，fable 規劃）

← [proto8-2](README.md)｜慣例：[CONVENTION.md](../proto8/CONVENTION.md)｜裁定：[CONFLICTS.md](CONFLICTS.md)｜原話：[ideas § 11](../proto8/thinking/2026-10-19-ideas.md)｜proto8：[README](../proto8/README.md)、[CONCEPTS](../proto8/CONCEPTS.md)、[NORMS](../proto8/NORMS.md)

使用者 10-19：「然後proto8-2應該可以轉正到proto8了」→ 選 (b)：「b。這是個大工程，現行規範也要跟著改」。先例是 10-15 深夜 proto8-1 併進 proto8/lib（commit a0c7214d：程式 `git mv` 進 lib、測試進 lib/tests、demo 搬進 demo/、規範改寫、原資料夾刪）。這份只規劃、一個檔都還沒搬；每條後面括號是依據（P-xx＝CONVENTION、CONFLICTS 幾、§ 幾＝ideas 原話、C-xx／N-xx＝proto8）。

**一句話**：併完之後 `proto8/` 讀起來就是「資料夾＝程式、三個環境變數、aos-exec」這一套；10-16 那套「食譜、廚房、捷徑、門房、stdin 是正規入口」的概念與規範**正文刪掉、條號作廢**（使用者 § 9「把鐐銬拿掉」；user.md「被推翻的直接刪、舊版靠 git」）；舊 lib 那一大套程式**建議整個進 git 歷史**（決定 1，要使用者點頭）；慣例 P-05～P-39 原樣搬過去當 `proto8/CONVENTION.md`，條號不動。

## 一、盤點

逐條盤點（概念 69 條、規範 55 條、lib 27 支＋11 份說明＋12 個測試檔、bin、demo、thinking、proto8-2 自己的檔）已抽到 [MERGE/inventory.json](MERGE/inventory.json)（122 列；欄位：`id` 條號或檔名、`kind` 類別、`action` 取代／改寫／保留／刪、`basis` 依據、`reason` 一句理由）。統計：

| 類別 | 取代 | 改寫 | 保留 | 刪 | 新增 |
|---|---|---|---|---|---|
| 概念 C（69 條） | 5（C-57、C-58、C-59、C-60、C-63） | 14 | 50 | 0 | 3（C-68～C-70） |
| 規範 N（55 條，N-10 早已作廢不計） | 15 | 21 | 14 | 5（N-21、N-22、N-23、N-24、N-35） | 4（N-57～N-60） |
| lib 模組 27 支、說明 11 份、測試 12 檔 169 個、bin/aos | 0 | 0 | 0 | 全部（決定 1） | — |
| demo（daemon、fsm、paint、kernels、tasks、aos-demo） | 0 | 1（README） | 0 | 6 組（決定 1） | agent-bob、agent-ann、run.sh 搬進來 |
| thinking 31 份 | 0 | 2（README、months） | 31 | 0 | 1（10-19 ideas 搬進來） |
| 其他（README、CONCEPTS.md、NORMS.md、附錄、abbr） | 0 | 4 | 2 | 0 | — |
| proto8-2 自己的檔 | — | — | — | README／CONFLICTS／PLAN／MERGE 刪（內容併入） | CONVENTION、bin、demo、tests、thinking 搬 |

「取代」的判準：CONVENTION 或 CONFLICTS 1～7 直接說反了的。「改寫」：原則還對、但條文裡綁著舊機制的字（TARGET、窗、捷徑、門房、stdout JSON、`times`）要換成新做法的字。「保留」：一個字不動或只改引用。「刪」：純粹是舊程式的語法糖、新程式沒有對應物（命令列 TARGET／旗標／`檔#/位置`）。

幾條值得先知道的：

- **C-63「結束碼只是參考」整條作廢**（CONFLICTS 4）；N-43 改寫成「0＝正常、10＝正常停、其他非 0＝失敗；aos 自己的錯一律退 1；每層只說自己；透明轉交保留」（P-19、P-04、P-21）。
- **N-05「先寫暫存再改名」保留，但新程式沒照做**：`aos-fsm` 寫 state、`brain.py` 寫 current 都直接開檔。使用者 10-12 定的、10-19 沒推翻，所以程式要改（步驟 5，各一行）。
- **N-43「正常退出不寫 stderr」保留，`aos-loop` 跑滿 `max` 那句 stderr 提醒要拿掉**（P-19 說「跑滿 max 以 0 結束並在 stderr 提一句」，跟使用者 10-15 親口的「正常退出不會在 stderr 噴東西」撞；10-19 沒碰這條，所以照 N-43：退 0、不寫；要知道有沒有跑滿看 `trace.jsonl` 行數）。P-19 跟著改字。
- **窗一族（N-06～N-09、N-11、N-13～N-17、N-32、N-33）**：ctl／state 的精神（反覆跑的東西用檔控制、內部狀態外顯成檔）留給以後的 daemon；跟 agent 這層撞的只有「位置由 stdin 參數指定、名字統一、內容 JSON」（N-13、N-14、N-19），這三處改寫或作廢，其餘條文加一句「現無實作、daemon 重寫時再對」。
- **`$ref` 沒了、只有 `$env`**（P-31）：C-48、N-45 改寫。

## 二、併完之後 proto8 長什麼樣

```
proto8/
  README.md          入口（改寫）：現況＝10-19 併入後；怎麼跑；指向下面每一項；舊 lib 在 git 的 commit 一行
  CONCEPTS.md        概念入口：分檔表、條號→檔表（作廢的條號留在表上標「作廢（10-19，由 X 取代）」）
  CONCEPTS/          01 設計理念（C-63 刪、C-68～C-70 新）、02 時空（不動）、03 基礎設施（C-57／C-59／C-60 刪，
                     C-65～C-67 改寫，「定義與工作區」段改名「資料夾程式、工作區與 stack」）、04 kernel（不動）、
                     05 agent（C-58 刪，C-46／C-50／C-61／C-62 改寫）、附錄1 名詞（改寫）、附錄2（不動）、abbr.json（不動）
  NORMS.md           規範入口：主題表、條號→檔表（作廢的同上）、各批出處加 10-19 一段
  NORMS/             01 總則（N-12／N-29／N-52 刪，N-43 改寫，N-35 刪）、02 時空（不動）、03 inst（N-24／N-26 刪，
                     N-25／N-27／N-30 改寫＝新 aos-inst 單子）、04 loop 與 daemon（N-31／N-44 刪，N-28／N-54 加「現無實作」）、
                     05 窗（N-19 刪，N-13／N-14 改寫，其餘加「現無實作」）、06 指示詞（N-21～N-23 刪，N-45 改寫＝只有 $env）、
                     07 組合子（N-37／N-40 刪，N-36／N-38／N-39／N-41 改寫；tasks N-34 改寫＋待重寫）、08 待定（清帳）、
                     09 kernel（不動）、10 資料夾程式與執行（檔名沿用「定義與工作區」不改，正文整份重寫：N-57～N-60，
                     N-55 留，N-46～N-51／N-56 刪，N-53 改寫）
  CONVENTION.md      aos agent 慣例 P-05～P-39（原 proto8-2/CONVENTION.md，條號不動；第一節改成指 N-57～N-60）
  bin/               aos-exec、aos-inst、aos_inst.py、aos-loop、aos-fsm（原 proto8-2/bin）＋ README.md（逐支說明，
                     從 proto8-2 README「原型怎麼跑」搬來）
  demo/              agent-bob/（含 act/tools/cathy/act/tools/stamp/）、agent-ann/、run.sh、README.md（改寫）
  tests/             test_exec.py（原 test_proto8_2.py）、test_inst.py、test_fsm.py——62 個
  thinking/          原 31 份不動 ＋ 2026-10-19-ideas.md；README／months/2026-10.md 加一列
```

**CONCEPTS／NORMS 怎麼重組**（依據：user.md「被推翻的直接刪、不標刪除線、舊版靠 git」；10-15 使用者定「條號不重編、條文原樣搬」；STRUCTURE「整檔拆資料夾時原路徑保留當入口」）：

1. **條號沿用、作廢不補洞、新條接著編。** 取代／刪的條，正文整段刪掉（不留「原本…」、不劃線），只在 CONCEPTS.md／NORMS.md 的「條號→檔」表留一列：`C-59 ｜ 作廢（10-19，由 N-58 取代；原文見 git fc3e6e5d 之前）`。新概念 C-68～C-70、新規範 N-57～N-60 接在最後。這跟 10-16 N-10 的做法一樣（條號留作錨點）。
2. **P-01～P-04 升成規範 N-57～N-60**，寫進 NORMS/10；CONVENTION 第一節改成一句「aos 保證的底是規範 N-57～N-60，見 NORMS」，不重複正文。P-05～P-39 **維持慣例層、條號不動**，整檔搬成 `proto8/CONVENTION.md`——使用者 § 4、§ 7 自己分的層：「aos 只訂環境變數」是底（規範），「我們 aos agent 的慣例」是範本（照抄的標準形狀，不是大家都要守的）。NORMS.md 的三層表改成四層：概念／規範／慣例（CONVENTION）／程式（bin、demo）。
3. **改寫的條只換字、不換意**：把 TARGET、窗、捷徑、門房、stdout JSON、`times`、frame 這些字換成子資料夾、`$AOS_STACK` 的檔、`tools/<名>`、aos-exec、結束碼、`max`、stack，括號裡附「10-19 改，P-xx」。每個分檔第一行的「概念／規範／實作」三連結照新位置改。
4. **CONFLICTS 七條裁定**各一句併進 `thinking/2026-10-19-ideas.md` § 9（它們是決定）；AI 的「撞在哪」分析不留；方向問題甲（agent 當工具時題目怎麼交）進 NORMS/08 待定，預設 (a) 各看各的說明。CONFLICTS.md 刪。
5. **NORMS/08 待定清帳**：10-19 已經有答案的刪（AOS_DIRNAME、aos exec 邊緣、--say／intake／agent 定義形狀／binding／格庫瘦身／stub、agent 當工具誰包 loop＝P-35、小格命名＝P-17 工具名、ws 捷徑與 AOS_WS 誰設＝P-02、say 印回答＝P-11 out/、tasks 用 code＝看碼、fsm 每拍記時間＝P-38 要、argv[0] 規矩裡的 setsid 項＝P-36）；留下的：kernel 評估納入錯誤路徑、kernel 公告、`_metainfo`、SIGINT 比照 SIGTERM、ctl_seq 回音；新進：方向問題甲。
6. **proto8/thinking 的 31 份不動**（user.md：thinking 留原文與決定；10-16 的決定是那天的決定，被 10-19 推翻這件事記在 10-19 那份 § 9，不回頭改舊檔）。例外：連到被刪的 lib／demo 檔的連結改成純文字＋「見 git 歷史 <hash>」，跟 10-16 修壞連結（6fac6c34）同一做法；約 40 份要碰一行。要不要順手清 AI 提案稿，見決定 3。
7. **proto8-2/ 資料夾最後刪掉**：README（內容併進 proto8 README／bin README／demo README）、CONFLICTS（併進 ideas）、PLAN、MERGE.md 與 MERGE/（做完的計畫不留——10-15 使用者對 proto8 PLAN 說「刪掉」是先例；commit hash 記在 ideas § 11 與 session log 一行）；其餘全 `git mv`。

## 三、舊 lib 程式與測試怎麼辦

**決定（建議，等使用者點頭＝決定 1）：27 支模組、11 份說明、12 個測試檔（169 個）、`bin/aos`、六組 demo 全部刪，進 git 歷史；併完後 proto8 的測試＝62 個（test_exec 36、test_inst 16、test_fsm 10），全綠。**

理由，白話講：

- 拆不開。所有舊模組都壓在 `aos_cli`（TARGET、旗標、stdin JSON、`檔#/位置`、`$ref`）→ `aos_inst`（stdout 吐結果 JSON）上，kernel 的信就是舊 inst 的形、tasks 起的是 `aos_inst.py` 讀它的 stdout。這一層正是 CONFLICTS 1～4 裁掉的東西（§ 9「帶著鐐銬跳舞」）。要留 daemon 就得連 `aos_cli`、`aos_inst`、`aos_loop`、窗一起留——等於 proto8 裡同時住兩套 inst、兩套 loop、兩套 fsm，README、NORMS 得同時講兩種，違反 C-56（最後的減法）與 C-54（一次記住、全體系通用）。
- 有先例。aos_tree、aos_agent_call、PLAN、proto8-1 資料夾、ollama 腦、KISS 批次 1 砍的十幾項，全都是「刪、靠 git」；10-11 使用者定「proto7-2 的東西不搬過來，要用再去拿」。
- 沒有新版的那幾樣（daemon、兩種 kernel、tasks、tick、窗）**不是現在重寫**：10-11 規矩「程式等想法穩了才開」——「daemon 怎麼管一群資料夾程式」「kernel 的信長什麼樣」在新做法下還沒討論過。概念（C-36、C-09～C-15、C-47、C-41、C-44）與規範（N-28、N-54、N-42、N-34、N-15～N-17、N-01～N-03）**留著**，各加一句「現無實作；照『資料夾＝程式』重寫時再對」。tick、seq／par／if 都是幾十行的資料夾程式，有需要時半天內做完。
- 真正會丟掉、以後要重做的只有一塊：**腦的工具呼叫**（think 把 `tool_calls` 接進 history、tool 格照順序跑工具、回 tool 訊息）。brain.py 現在只問答、不帶工具。要做時從 git 拿 `aos_agent_lib.py` 的 think／tool 兩段改成新範本的格。這點寫進 NORMS/08 待定「腦的工具呼叫，照新範本重做」。

若使用者選「保留」（另一條路）：舊 lib 原地不動、`lib/README.md` 第一行標「舊實作（10-16 那套），照新做法重寫前的參考；新程式在 bin/」，169 個測試照跑、全綠；步驟 2 改成「只改標註、不刪」，步驟 6 的 thinking 連結不必改。代價是上面說的兩套並存。

## 四、wf 入口要同步的

| 檔 | 改法 |
|---|---|
| [wf/WORKFLOWS.md](../wf/WORKFLOWS.md) | 第 19、20、49、50 列的落點照舊指 proto8 CONCEPTS／NORMS／thinking（路徑不變）；「寫 spec」列加 CONVENTION（慣例）。 |
| [wf/INDEX/01-repo-layout.md](../wf/INDEX/01-repo-layout.md) | `proto*/` 列：proto8 的括號改成「bin：aos-exec／aos-inst／aos-loop／aos-fsm；demo：agent-bob、agent-ann；舊 lib 10-19 進 git」；proto8-2 那句刪。 |
| [wf/workflows/common/code-map.md](../wf/workflows/common/code-map.md) 第 51 行、[code-map/README.md](../wf/workflows/common/code-map/README.md) 第 34 列 | 「逐檔表在 proto8/lib/README.md」改成「在 proto8/bin/README.md」；一句話總覽的括號改成新四支。 |
| [wf/workflows/common/code-map/proto8.md](../wf/workflows/common/code-map/proto8.md) | 整份重寫：bin 五支一句、demo 三項一句、tests 三檔；舊 lib 一行「10-19 進 git 歷史 <hash>」。鐵律 3 在這裡落地。 |
| [wf/workflows/common/user.md](../wf/workflows/common/user.md) 「少用 sh」段 | 第二段例子「stack：定義掛成 .aos、交給門房 aos exec stack 定義」改成「資料夾程式：aos-exec DIR [WS]，工作區由 AOS_WS 給、狀態由 AOS_STACK 給」，連結改指 NORMS/10 新正文（檔名不變，連結不斷）。 |
| [wf/workflows/dev-env/01-跨機與外部工具.md](../wf/workflows/dev-env/01-跨機與外部工具.md) | 10-15「允許在公司這台用 LM Studio 試 agent」底下加 10-19：「放棄跑本機模型」（整台當機，§ 6）；demo 一律假腦、`AOS_BRAIN_URL` 指遠端才用真腦。 |
| [wf/SESSION-LOG.md](../wf/SESSION-LOG.md) | proto8-2 那條改成「已併進 proto8（commit）」後刪；「frame 與工作區分開」「KISS 重審五件」「定義與工作區」「inst 重設計」四條 open 的「程式待改」全部結案（被 10-19 取代，不再改程式）→ 刪；「KISS 大掃除暫停」條刪（批次 2～6 的對象已不存在）；留一條新的 open：「待照新做法重寫：daemon、兩種 kernel、tasks、tick、腦的工具呼叫；等使用者說要哪個」。 |
| [wf/session_logs/README.md](../wf/session_logs/README.md)、[2026-10-19.md](../wf/session_logs/2026-10/2026-10-19.md) | 10-19 列一句話補「併進 proto8」；日誌加「併入」一段（做了什麼、幾批、hash、代定清單）。 |
| [wf/session_logs/2026-10/2026-10-13.md](../wf/session_logs/2026-10/2026-10-13.md)、[10-15](../wf/session_logs/2026-10/2026-10-15.md)、[10-16](../wf/session_logs/2026-10/2026-10-16.md) | 連到 proto8/lib、proto8/demo 被刪檔的連結改純文字（同 6fac6c34）。 |
| [wf/HANDOFF.md](../wf/HANDOFF.md) | 最新一條加「10-19 proto8-2 已併進 proto8；10-16 那套概念規範作廢」；舊條不動。 |
| [wf/workflows/planning.md](../wf/workflows/planning.md)、[decisions.md](../wf/workflows/decisions.md)、[investigation.md](../wf/workflows/investigation.md)、[feature-dev/README.md](../wf/workflows/feature-dev/README.md)、[ideas/README.md](../wf/workflows/ideas/README.md)、[conventions.md](../wf/workflows/common/conventions.md)、[STRUCTURE.md](../wf/STRUCTURE.md) | 只指 proto8 的 CONCEPTS／NORMS／thinking，路徑不變，不用動；feature-dev 第 36 列「proto8 的 CONCEPTS／NORMS」加「／CONVENTION」。 |
| `.gitignore` | 不用動：`!proto8/bin/` 已在，搬進去就不再被擋（proto8-2/bin 原本要 `git add -f`）。`!proto8/demo/bin/` 那行隨 aos-demo 刪掉一起拿掉。 |
| [wf/workflows/tidy/reports/2026-10-13-proto8-wf.md](../wf/workflows/tidy/reports/2026-10-13-proto8-wf.md) | 歷史報告，不動。 |

## 五、分批步驟（每批一個 commit、WSL 測試全綠、`sh proto8/demo/run.sh` 跑通、wf-lint `proto8 wf` broken=0）

| 批 | 做什麼 | 相依 | 做完的樣子 |
|---|---|---|---|
| 1 | **搬程式**：`git mv` proto8-2/bin/* → proto8/bin/、demo/agent-bob、agent-ann、run.sh → proto8/demo/、tests/* → proto8/tests/（test_proto8_2.py 改名 test_exec.py）、thinking/2026-10-19-ideas.md → proto8/thinking/；新寫 proto8/bin/README.md（從 proto8-2 README「原型怎麼跑」逐支搬）；proto8-2 的 README／CONVENTION／CONFLICTS／PLAN 連結先改指新位置 | 無 | `python3 -m unittest discover -s proto8/tests` 62 綠、`sh proto8/demo/run.sh` 印整棵樹；舊 lib 169 也照樣綠（還沒動）；proto8-2 只剩四份 md＋MERGE |
| 2 | **刪舊 lib**（決定 1）：`git rm` lib/、bin/aos、demo/{run.py,daemon.json,once,tick,bin,fsm,paint,kernels,tasks}；thinking 約 40 份與 wf session_logs 三份連到它們的連結改純文字＋「見 git 歷史 <批 1 的 hash>」；proto8 README、demo README、code-map 先改成一行指標（正式改寫在批 6、7） | 1 | `proto8/` 底下只剩 README、CONCEPTS*、NORMS*、bin、demo（agent-bob、agent-ann、run.sh、README）、tests、thinking；62 綠；wf-lint broken=0 |
| 3 | **CONCEPTS 重組**：C-57／C-58／C-59／C-60／C-63 正文刪、表上標作廢；14 條改寫；C-68～C-70 新增；附錄1 名詞表改；CONCEPTS.md 分檔表與條號表重排、加 10-19 段 | 2 | CONCEPTS 裡搜不到「捷徑」「門房」「食譜」「廚房」（只在 10-19 段落的「作廢」註裡出現）；wf-lint broken=0 |
| 4 | **NORMS 重組＋CONVENTION 搬進來**：15 條作廢、5 條刪、21 條改寫、N-57～N-60 新增（NORMS/10 整份重寫）；NORMS/08 待定清帳；NORMS.md 四層表、條號表、各批出處；`git mv` CONVENTION.md → proto8/CONVENTION.md（第一節改指 N-57～N-60、連結重算、P-23 連結改指 thinking 10-15 topics/02、P-19 跟著批 5 改字）；CONFLICTS 七條裁定併進 ideas § 9、方向問題甲進待定、CONFLICTS.md 刪 | 3 | NORMS 條號表每一條都有「檔」或「作廢（由 X 取代）」；`grep -c 實作待改 proto8/NORMS` 為 0（全部換成「現無實作」或刪）；wf-lint broken=0 |
| 5 | **小程式修**：aos-fsm 寫 state 改成先寫 `.state` 再 rename、brain.py 寫 current 同（N-05）；aos-loop 跑滿 max 不寫 stderr（N-43）；bin/README、CONVENTION P-19 改字；測試各補一條（state 寫法原子、跑滿 max stderr 空） | 1 | 64 個測試綠；run.sh 跑通 |
| 6 | **proto8 README 改寫、thinking 索引**：README 入口段、現況、怎麼跑、舊 lib 在 git 那一行；thinking/README 份數、months/2026-10.md 加 10-19 列；demo/README 重寫 | 2、4 | 從 proto8/README 出發三步內點得到每一份；wf-lint broken=0 |
| 7 | **wf 同步＋刪 proto8-2**：第四節表格逐項做；`git rm` proto8-2/（README、PLAN、MERGE.md、MERGE/）；session log 補「併入」段與代定清單；SESSION-LOG 條目結案 | 1～6 | `ls proto8-2` 不存在；`grep -rl proto8-2 wf AGENTS.md`（排除 session_logs 歷史）為 0；wf-lint `proto8 wf .claude/commands` broken=0；ctest 全綠（proto 不進 CMake，順手確認） |

批 3、4 可以跟批 5 平行；批 2 一定在批 1 之後（先把新程式放好再拆舊的，中間任何一點都能跑）。若決定 1 選「保留」，批 2 改成只在 lib/README.md 標舊、不刪，批 6 的 thinking 連結不必動。

## 六、要使用者決定的

**1. 舊 lib 那一大套（27 支、169 個測試、六組 demo）：刪進 git，還是留著標舊？**
背景：第三節講過，它們壓在 `aos_cli`→`aos_inst` 上拆不開，而這一層正是 10-19 裁掉的 stdin JSON、TARGET、窗那套。小例子：留著的話 `proto8/` 會同時有 `lib/aos_inst.py`（吐結果 JSON、串流預設接 /dev/null）和 `bin/aos_inst.py`（碼透明轉交、串流預設接呼叫者），兩個同名、兩種行為，README 得解釋哪個是哪個。刪的話，daemon、kernel、tasks、tick、腦的工具呼叫都要等以後照新做法重寫（概念與規範留著）。
AI 建議：**刪**（進 git、README 記 hash；user.md「刪檔一定先問」所以列在這）。

**2. N-52「收到 SIGTERM＝優雅收工、退 0」要不要跟著作廢？**
背景：這是使用者 10-16 親口定的原則（「退0……重點在於把該做的事情做一做後才結束，這塊也可以當原則」）。10-19 P-36 說被外層逾時殺掉（SIGTERM 整群）的那格＝失敗、碼 128＋訊號、trace 記 `timed_out`，上面停下來等人——CONFLICTS 7 列了、預設走 P-36，使用者還沒答。小例子：bob 的 act 包 10 分鐘叫 cathy、cathy 的腦卡住；照 N-52 cathy 退 0、bob 以為她做完了、去 `cp` 她的答案才失敗，錯誤往後飄一格；照 P-36 bob 當場看到 143、trace 寫 `timed_out`。
AI 建議：**作廢 N-52、照 P-36**（結束碼已經是正式訊號了，被殺就該是非 0；要保留「收好子程式再死」這半句的話，寫進 P-36 當慣例，不當退 0 的理由）。

**3. proto8/thinking 裡 10-15～10-16 的大份 AI 提案稿（kiss/ 八份 140 KB、inst-exec 三版 55 KB、agent-inherit 105 KB）這次要不要順手照 user.md 10-12 規矩清成只剩原文與決定？**
背景：user.md 說 thinking 只留「原文、決定、結論」，AI 分析與被推翻的方案不留。這幾份是提案稿、裡面夾著使用者的拍板段；10-19 之後提案的那半大多作廢。小例子：agent-inherit 105 KB 裡使用者決定只在 § 四（約 5 KB），其餘是捷徑、門房、兩層參數的 AI 推演。
AI 建議：**這次不碰**（併入已經是大工程，一次做一件；這些稿不擋任何連結，清不清不影響併入；要清另開一批、逐份留 § 四那種「使用者決定」段）。

沒有第 4 條。方向問題甲（agent 當工具時題目怎麼交）照 CONFLICTS 的預設 (a) 進待定，不在這裡重問。

## 七、fable 自己定的小地方（列出讓他知道、可翻）

- P-05～P-39 維持「慣例」層、不升成 N 條、條號不重編；只有 P-01～P-04 升成 N-57～N-60。依據 § 4、§ 7 使用者自己分的「aos 只訂環境變數」與「我們的慣例」。
- 作廢條號的寫法：正文刪、表上一列「作廢（10-19，由 X 取代）」，不留舊文、不劃線（user.md 10-12 夜）。
- 新概念只開三條（C-68 資料夾＝程式與入口、C-69 aos 只訂環境變數、C-70 巢狀由程式自己訂子 stack），都是 § 1～§ 4、§ 10 的原話；「不跑本機模型」是環境規矩，寫 dev-env 不寫概念。
- aos-loop 跑滿 max 改成不寫 stderr（照 N-43）；aos-fsm／brain.py 寫檔改先暫存再改名（照 N-05）。兩個都是使用者定過、10-19 沒推翻的規範，程式跟上去。
- NORMS/10 檔名沿用「定義與工作區」、正文全換（連結不斷，10-16 夜同樣做法）；CONCEPTS/03 那一段標題改「資料夾程式、工作區與 stack」。
- test_proto8_2.py 改名 test_exec.py（C-54 檔名要說它測什麼）。
- 「腦的工具呼叫（tool_calls）照新範本重做」記進 NORMS/08 待定，是刪舊 lib 唯一真正會丟掉、以後要重做的功能。
