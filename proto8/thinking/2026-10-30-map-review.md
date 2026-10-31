# 2026-10-30 使用者看現況地圖後的想法：plan 9 式檔案串流、round 的定位、外部 agent 平級、aos-hub 通用化、掛 daemon 的指令、kernel 與 gate 改名

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜相關：[10-28 agent-round](2026-10-28-agent-round.md)（`parts.json` 在 [§ 1 佈局](2026-10-28-agent-round.md#1-佈局)、round 在 [§ 2](2026-10-28-agent-round.md#2-round一輪本身)）、[10-30 agent-lifecycle](2026-10-30-agent-lifecycle.md)、[10-28 hub-kernel](2026-10-28-hub-kernel.md)

規矩見 [thinking/README](README.md)。10-30 早頂層做了一份「aos 現況地圖」網頁給使用者（在他桌面、不在 git），他看完講了下面五點，說「好了我還在看」，接著又回第 4、5 點、再講第 6～9 點，說「剩下的我覺得之後有遇到再說」，再補第 10、11 點。本檔放原文與決定；每點現在的去向見 [§ 結論（10-31 補）](#結論10-31-補)。

## 使用者原文（10-30，逐字）

1. 「1.程式之間說話的方式，感覺還有一種，就是純粹的寫檔案、讀檔案，途中可以設置串流，這就是plan 9那種方式。這一塊我們aos好像沒有用到，之後可以考慮。不過這個感覺只能一對一？多對一的話就得用上鎖了。」
2. 「2.關於一隻agent長怎樣，其中的agent資料夾中的round那是啥？我原本以為他是一個可用於aos agent的語法糖，也就是開啟aos loop跑fsm，直到fsm停在idle且沒有新訊息的時候，就停掉aos loop。用在其他coding agent上的時候也不用多做啥，就是claude -p就好，他跑完會自己結束(只是說後續可能會有在他跑的期間push新訊息的需求)，喔等等我看到了，他是先前那套pseudo code的顯化...emmm，是可以啦，不過他能否待在aos-loop/fsm的框架下去實現？假如先暫不考慮claude code cli那些外部coding agent的話。」
3. 「3.關於"腦用claude -p"，這也是可以啦，不過我一直以為claude code cli這類外部agent，它本質上是可以用來代替aos agent的，兩者是平級的關係，但你要把它當成aos agent brain...有點....。然後其中討論的"射後有理"、"訊息queue"等機制，我建議是分成兩塊看與比較，也就是在aos agent體系下這怎麼做、外部agent下怎麼做，然後找出共同點，以aos agent為主，做成通用介面如aos-say/listen。」
4. 「4.然後格與格之間的通訊錄...這是啥？parts.json是啥？」
5. 「5.aos-hub感覺是個很通用的東西，他不該只拿來管外部coding agent。或許可以改個名字？也就是我們先把一些通用的東西摘出來，然後弄一個aos-eca-hub(aos-extern-coding-agent-hub)，也就是基於通用aos-hub進行擴展，弄出aos-eca-hub...除此之外還有aos-eca XXX這類的指令。」

最後一句：「...好了我還在看」

接著回（頂層答第 4 點：`parts.json` 是 agent 自己的器官清單、腦看不到；答第 5 點：aos-hub 通用那層（常駐 kernel、add／stop 實例、信箱收題、pause）跟 aos-daemon 信箱模式幾乎重疊，摘出來可能就是 daemon）：

「好，parts我覺得OK。aos-hub既然摘出來就是daemon，那就不做aos-hub，而是aos-eca-hub。aos-hub這個名字保留到以後使用」

再接著講（同一段話，逐字照順序切成 6～9 點）：

6. 「我發現我們得弄一個指令。就是說，我們現在跑aos-exec XXX，等同於把這個proc掛到linux這個原生proc管理器上。假如我們想要掛在daemon上呢？或許是aos-daemon-ctl add XXX這樣，然後會自動識別XXX是否為loop，不是的話就max:1這樣？」
7. 「然後關於aos-post/aos-lock，感覺他這個還沒完善，要不要弄一些aos-post/get, aos-lock/unlock？不用的話也OK。」
8. 「aos-ai是啥？aos-gate又是啥？」
9. 「aos-kernel-llm是否可以換成aos-llm-kernel？也就是他是屬於llm這個領域下的kernel功能，和"屬於kernel領域下的llm特種"比起來，我其實更prefer前者，因為以後會有一大堆領域，而kernel作為基底，他就是算...lib？」

最後一句：「剩下的我覺得之後有遇到再說」——使用者看地圖這輪到此。

再接著回（同一段話，逐字；前段「好，我覺得OK。」、後段「然後簡單跟我說說wait user那些」是問題、頂層已答、不記內容）：

「好，我覺得OK。關於那個aos-daemon-ctl，他應該是要吃環境變數+argv來確定daemon home在哪裡的(要用哪個daemon)。然後aos-gate這個名字不太直觀，換個名字吧。然後簡單跟我說說wait user那些」

10. （接第 6 點）「關於那個aos-daemon-ctl，他應該是要吃環境變數+argv來確定daemon home在哪裡的(要用哪個daemon)。」
11. 「然後aos-gate這個名字不太直觀，換個名字吧。」

## 決定（10-30）

- **第 4 點已定**：`parts.json` 的設計 OK，[10-28 agent-round](2026-10-28-agent-round.md) 決定 16 那套維持。
- **第 5 點已定**：不再叫 aos-hub；**現有的 aos-hub 改名 aos-eca-hub**（extern coding agent hub），通用的那層就是 aos-daemon；**`aos-hub` 這個名字保留到以後用**。
- **第 6 點方向已定**：要一個把 proc 掛到 aos-daemon 的指令（像 `aos-daemon-ctl add XXX`），自動識別 XXX 是不是 loop、不是就包成 `max: 1`。名字與細節由實作隊長代定、可翻案（[agent-lifecycle](2026-10-30-agent-lifecycle.md) 第 7 步 `execs` 的命令列面）。
- **第 9 點已定**：**aos-kernel-llm 改名 aos-llm-kernel**——領域在前、kernel 是基底（像 lib），以後會有很多領域。
- **第 10 點已定**（接第 6 點）：掛到 daemon 的指令靠**環境變數＋argv** 決定用哪個 daemon（daemon home）。變數名、argv 蓋過環境變數等細節交實作隊長照 N-63 代定、可翻案。
- **第 11 點已定要改名**：aos-gate 換名字。名字照頂層建議用 **`aos-llm-send`**（備選 `aos-llm-call`；照 `aos-<領域>-<功能>`、與 aos-llm-kernel 成對），使用者未反對即採用——**頂層建議、代定可翻案**。
- **eca 規劃的衝突六條與方向題三條都照建議**（使用者 10-30「都照建議」）→ [10-30 eca § 決定（10-30）](2026-10-30-eca/09-方向題.md#決定10-30)。
- **第 2 點已定**（使用者 10-30 澄清）：round 改成 **`aos-round`**——裡面的迴圈用 aos-loop／fsm 實作、外面用到的函數換成 aos 函數，整個是包在 aos loop／fsm agent 上的一層薄殼；「能否待在 aos-loop／fsm 框架下」答＝要（eca 方向題 1「留骨架」作廢）；接著又定 **fsm 的 `next` 照結束碼分岔（選甲、改 N-36，乙不走）**，「把 round 拆散放進每一格」留作特定情況用的一種實作；怎麼做交 fable 規劃 → [10-30 eca § 翻案](2026-10-30-eca/11-10-31-使用者想法-turn-改名-把-tu.md#翻案round-化作-aos-round-薄殼10-30使用者澄清)。
- 第 7 點（aos-post／aos-lock 要不要補 `get`／`unlock`）開著、不急；第 8 點已答。

## 結論（10-31 補）

每點：是什麼 → 狀態 → 落在哪。

1. **plan 9 式檔案串流**（純寫檔讀檔、途中串流；多對一要上鎖）→ **開著**：使用者「之後可以考慮」，沒定要做。現況是 10-28 [medium § 決定與結論](2026-10-28-medium.md#決定與結論10-28-晚) 決定 12～14：管線、檔案串流、訊號都不寫進標準，檔案串流目前沒有東西依賴它，要用由 proc 自己定。
2. **round 是啥、能不能待在 aos-loop／fsm 框架下** → **已定、已做**。round 現況頂層已答；隊長查過（[agent-lifecycle § 使用者問](2026-10-30-agent-lifecycle.md#使用者問round-能不能放在-aos-loopfsm-的框架下實現10-30只查沒改)）；使用者澄清 round 化作 `aos-round` 薄殼、fsm 的 `next` 照結束碼分岔（選甲，改 N-36）、「拆散放進每一格」留作特定情況用（[eca § 翻案](2026-10-30-eca/11-10-31-使用者想法-turn-改名-把-tu.md#翻案round-化作-aos-round-薄殼10-30使用者澄清)）；規劃「都照建議」（[aos-round § 決定](2026-10-30-aos-round.md#決定10-30)），10-30 做完第 1～7 步（c06a841c～ef379dc7，第 8 步只記不做），條文 N-36 改口、N-39／N-43／P-20／P-35 加註（ef379dc7）。還開著：`aos_ws.py` 失敗判法等使用者裁（WAIT_USER）。
3. **外部 coding agent 跟 aos agent 平級、射後有理／queue 分兩塊比較再做通用介面** → **已定、已做**：[eca](2026-10-30-eca.md) 規劃，使用者「都照建議」（[eca § 決定](2026-10-30-eca/09-方向題.md#決定10-30)）；共同點＝queue／history／ctl 三樣（P-42），外部 agent＝aos-loop 包 `lib/eca/turn`、範本 `demo/eca-claude`、`demo/eca-codex`；10-30 九步做完（9fa46097～2f47400c，新 P-43）。agent-lifecycle 暫停的第 6、9 步由 eca 第 3、6、8 步接手。還開著：停著改 history 再繼續（[eca § 之後再改](2026-10-30-eca/09-方向題.md#之後再改停著時改-history-再繼續10-30使用者先記下)，使用者「先記下來吧，之後再改」）。
4. **格與格之間的通訊錄、`parts.json`** → **已定**：`parts.json` 是 agent 自己的器官清單、腦看不到；使用者「parts我覺得OK」，[agent-round § 1](2026-10-28-agent-round.md#1-佈局) 決定 16 維持。
5. **aos-hub 通用化、aos-eca-hub** → **已定、已做**：通用層就是 aos-daemon，現有 aos-hub 改名 aos-eca-hub，`aos-hub` 名字保留；怎麼改照 [eca § 決定](2026-10-30-eca/09-方向題.md#決定10-30) 2、4（不設 hub 自己的 kernel、`AOS_HUB` 退場改用 `AOS_DAEMON`）；6070ff6e（`extras/cli_hub` → `extras/eca_hub`、`bin/aos-eca-hub`），N-63 實例拿掉 `AOS_HUB`（2f47400c）。「aos-eca XXX 這類的指令」現在是 aos-eca-hub 的子命令（add／ls／state／open／close／stop／watch），沒有另外的 aos-eca 指令。
6. **把 proc 掛到 daemon 的指令** → **已做（代定可翻案）**：`aos-daemon-ctl add|rm|ls`（def6f2a3，[bin README](../bin/README.md)、[agent-lifecycle § 第 7、8 步與 aos-daemon-ctl](2026-10-30-agent-lifecycle.md#第-78-步與-aos-daemon-ctl) D-8～D-16）。自動識別＝XXX 是資料夾且有 `loop.json` 就當 loop；其他掛成 daemon 原生 `execs`（跑一次、不重起，照 [10-29 agent-bob](2026-10-29-agent-bob.md) 決定 34「daemon 可以掛 aos-exec」）；`max: 1` 是使用者說的底線，留作 `--kind max1`。N-28 補一句指過去（[NORMS loop 與 daemon](../docs/NORMS/04-基礎設施-loop與daemon.md)）。
7. **aos-post／aos-lock 要不要補 get／unlock** → **開著、不急**（使用者「不用的話也OK」，沒定）。現有子命令：aos-post `init`／`send`／`claim`／`claim-all`／`check`／`finish`／`withdraw`，aos-lock `acquire`／`release`／`show`。
8. **aos-ai、aos-gate 是啥** → **已答**：aos-ai 是給 AI 用的 aos 命令列（起 agent、丟題、看狀態、生成 JSON，每次一行 JSON；[ai_tools README](../extras/ai_tools/README.md)）；aos-gate 把一張單子寄進 kernel 的信箱、等回信、原樣交回，10-30 改名 aos-llm-send（第 11 點）。
9. **aos-kernel-llm 改名 aos-llm-kernel** → **已做**：c0e6c01c（行為不變）。由它推出的命名慣例寫成 [C-54](../docs/CONCEPTS/01-設計理念/C-54-命名方法.md) R13「程式名＝`aos-<領域>-<功能>`」（eca F-21、使用者「都照建議」，2f47400c；頂層推論、可翻案）；aos-round 那批補一句「標準庫層級的單字程式可不帶領域」（ef379dc7）。
10. **掛 daemon 的指令靠環境變數＋argv 決定 daemon home** → **已做（代定可翻案）**：`--daemon D` ＞ `$AOS_DAEMON`，值＝那個 daemon 的 `$AOS_STACK` 資料夾，都沒有＝`DaemonMissing`（D-9，照 N-63；def6f2a3）；aos-eca-hub 用同一套。
11. **aos-gate 換名字** → **已做（頂層建議、可翻案）**：f9fc45ae 改名 aos-llm-send（行為不變）。
