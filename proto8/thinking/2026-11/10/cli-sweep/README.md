# 2026-11-10 其餘指令照 C-85 掃一遍：每支的一段白話、裝不下的東西、跨指令不一致與改法（規劃報告，未施工）

← [2026-11-10](../README.md)｜[thinking](../../../README.md)｜範本：[aos-tools-cli](../aos-tools-cli/README.md)｜原則：[C-85](../../../../docs/CONCEPTS/01-設計理念/10-C-85.md)

只讀、實跑、寫報告；沒改任何程式、沒做任何 git 寫入。實跑在 WSL `/tmp/cli-sweep/`（假腦的 llm kernel＋兩台小根＋一隻 agent-fsm＋一隻配假 claude 的 eca；做完都 `shutdown` 了、沒有殘留行程），讀的是 `ad8541e92` 的工作樹。**做到哪**：任務單 1～5 組全部掃完；1～3 組做深，4～5 組較淺（各支都實跑過基本用法）。

## 使用者原話

- 檢驗標準（11-10）：「就是說，我們能用一段白話就將他的功能描述個大概嗎」（[C-85](../../../../docs/CONCEPTS/01-設計理念/10-C-85.md)）
- 要不要掃其他指令（11-10，頂層轉達）：「要喔，還是得掃一遍。現在就可以掃」
- 指令樹（11-10，頂層轉達）：「aos體系下的指令，sub command這塊，aos-daemon-ctl和aos daemon ctl視同一樣，在設計時也必須遵守這個規則。至於為何不做aos-daemon ctl，是因為程式架構上，兩者拆開會比較好維護…名字上就隨意，至於要不要用-弄成不同程式，就是看好不好維護，就這樣」（全文在 [07](07-指令樹.md)）
- 態度（11-10）：「總之先讓aos體系能跑，能夠遷移。後續慢慢大修去修好」

## 結論

整體比 aos-tools 改之前好：零件那一層（aos-json、aos-lock、aos-post、aos-fsm、aos-exec）一段白話都講得完，錯誤訊息多半會告訴你下一步。**怪的集中在人每天打的兩支——aos-agent 與 aos-daemon-ctl**：它們各自講得通，但放在一起是「同一批動作、兩套寫法、兩套後果」，再加上每一行都要先指出是哪台 daemon。

### 最該先改的五件

1. **`-d`、`-t` 寫在哪、名字怎麼給，現在有五種規矩。** `aos-agent ctl -t ann state` 不行、`ctl state -t ann` 行；`llm set -t ann` 不行、`llm -t ann set` 行；`aos-agent ctl stop ann` 不行、`aos-daemon-ctl stop ann` 只能這樣；`ctl rm` 又只收位置。`-d` 寫在子命令後面一律不認。→ 都收（[08](08-改法與施工順序.md) 甲1、甲2、乙2、乙3）。
2. **看不出 daemon 自己有沒有在跑。** `shutdown` 之後 `ls` 照樣印表、尾行寫「root daemon (no supervisor)」；`aos-agent ctl add` 對停掉的 daemon 乾等 30 秒。→ `ls` 尾行說活著沒、寄信前先核（甲3、甲6）。
3. **aos-daemon-ctl 退 0 不代表做成，成功時印的是信名或一個數字。** `add` 撞名、`rm` 一個不存在的名字都安靜成功；每天下班打的 `shutdown` 成功時畫面上只有 `1`。→ 寄信前查表、shutdown 說一句話（甲4、甲5）。
4. **同一個字兩支後果不同：`rm`（一支留 stack、一支刪）、「已經停了再停」（一支退 0、一支退 1）、start／wake 配錯就報錯。** → 快選題 Q3、Q4、Q6。
5. **`AOS_DAEMON` 一個變數兩個意思**（人：對哪台說話；daemon 起動時：我的上司）。為了少打 `-d` 而 export 它，再起另一台根，那台會以為自己是下屬（實跑）。現在靠 README 叫人先 `unset` 三個變數。→ 快選題 Q5。

另外兩件小而確定的：`copy-out` 只給一個參數會拿它當目的地、默默用預設範本抄一份（`copy-out help` 真的抄出一個 `help/`）；`aos-agent tools add 名 路徑` 跟 `aos-tools add [--name 名] 路徑` 寫法不同（上一輪 Q4 沒做的那一半）。

### 每支指令一行

| 指令 | 級 | 一句白話 | 裝不下 | 最怪的一點 | 分檔 |
|---|---|---|---|---|---|
| aos-agent | lv5 | 跟掛在 daemon 上的一隻 agent 打交道的遙控器（說話、掛上拿下、畫面、工具、腦設定） | 9 | `-t` 的位置看子命令，help 卻說前後都行 | [01](01-aos-agent.md) |
| aos-daemon-ctl | lv2 周邊 | 管一台 daemon 表上的行程：掛上、看表、三對停與起、停整台 | 10 | 退 0 只代表信寄了；shutdown 成功只印 `1` | [02](02-aos-daemon-ctl.md) |
| aos-exec | lv1 | 把一個資料夾當程式跑：找入口、備好工作區與 stack、讀 `.env`、跑 | 8 | 會把 cwd 換到入口資料夾，help 只有三個字帶過 | [03](03-aos-exec與copy-out.md) |
| copy-out | lv5 | 把 repo 裡的範本整夾抄出去，順便把指回 repo 的路徑改成換台能用的寫法 | 7 | 一個參數＝目的地，`copy-out agent-fsm` 抄出一個叫 agent-fsm 的夾 | [03](03-aos-exec與copy-out.md) |
| aos-llm | lv4 | 問腦的窗口：寄請求給 llm kernel、等回答、列出有哪些腦 | 7 | 想問一句「hi」要手打兩層 JSON；`ask` 沒有逾時 | [04](04-aos-llm-eca-mcp.md) |
| aos-eca-turn | lv5 | 讓外部 coding agent 答一輪（loop 每圈叫它，人不打） | 6 | 定義資料夾只收絕對路徑；help 是一面牆 | [04](04-aos-llm-eca-mcp.md) |
| aos-eca-screen | lv5 | 開、關、旁觀一隻 eca 的畫面（人用 aos-agent open／close／watch） | 2 | `watch` 閒置時零輸出地等 | [04](04-aos-llm-eca-mcp.md) |
| aos-mcp | lv5 | 把工具通訊錄裡的工具變成 MCP 工具端給外部 agent | 5 | 工作區一定要給（別支都預設現在站的地方） | [04](04-aos-llm-eca-mcp.md) |
| aos-loop | lv2 | 照設定檔把一件事一圈圈重複跑，旁邊有檔可遙控 | 4 | 單獨跑一定先撞 `StackMissing`，help 沒提 `AOS_STACK` | [05](05-其餘指令.md) |
| aos-daemon | lv2 | 照設定檔照顧一群行程：起、重起、停、寫狀況 | 5 | help 12 行生命週期規則，沒有一張停與起的對照表 | [05](05-其餘指令.md) |
| aos-fsm | lv3 | 照狀態表走一步，照退出碼決定下一個狀態 | 2 | 沒有 | [05](05-其餘指令.md) |
| aos-json | lv3 | 讀寫 JSON 檔裡的一格（`檔#/路徑`），含兩種指示詞 | 4 | 沒有（訊息是全家最好的）；`where` 跟 ctl 的 `where` 不同義 | [05](05-其餘指令.md) |
| aos-directive | lv0 | 從 stdin 讀 JSON、把指示詞全解開 | 1 | 只收 stdin 不收檔名（aos-json 收檔名） | [05](05-其餘指令.md) |
| aos-lock | lv3 | 在檔或資料夾旁邊放一把鎖：拿、放、看 | 2 | 沒有 | [05](05-其餘指令.md) |
| aos-post | lv3 | 資料夾做的信箱：建、寄、領、看、結案、撤回 | 2 | 沒有 | [05](05-其餘指令.md) |
| aos-llm-kernel | lv4 | 問腦總機跑一圈（daemon 叫它，人不打） | 0 | 樹上掛在 `aos llm` 底下卻不是同類 | [05](05-其餘指令.md) |
| aos-sweeper | lv2 周邊 | 幫一台 daemon 打掃一輪（封存 stderr、清殘留） | 3 | 跟 `aos-daemon-ctl sweep` 是同一段程式、預設不同 | [05](05-其餘指令.md) |
| aos-clock | lv3 | 把鐘檔的數字加一 | 0 | 名字像「看時間」 | [05](05-其餘指令.md) |
| aos-sandbox | lv5 周邊 | 照設定把一支程式關進沙箱跑 | 2 | 設定打錯字的 key 安靜忽略 | [05](05-其餘指令.md) |
| aos-grow | lv6 | 把一格指令升級成檔／資料夾或降回去 | 2 | `--dry-run` 只能寫在動作前（沒實跑） | [05](05-其餘指令.md) |
| aos-feedback | lv6 | 收集「哪支指令哪裡難用」的回饋 | 1 | usage 寫法全家獨一份 | [05](05-其餘指令.md) |

盤點：現役 22 支（含已掃過的 aos-tools）；任務單漏列 aos-directive、aos-llm-kernel、aos-feedback（已補掃）；`aos-inst` 沒有命令列；四個未追蹤殘留夾不算現役。清單在 [05](05-其餘指令.md) 開頭。

### 跨指令不一致總表（細節 [06](06-跨指令不一致.md)）

| 編號 | 同一件事 | 現況 | 分類 |
|---|---|---|---|
| X1 | 指出對哪個東西下指令 | `-d`＋`AOS_DAEMON`＋預設 `./.stack`（永遠不中）／只有 `AOS_LLM_KERNEL`／`--file`／位置參數／只有 `AOS_STACK` | 真問題 |
| X2 | 指出哪一個名字 | 位置參數／`-t`（位置看子命令）／`--stack 名字` | 真問題 |
| X3 | 旗標能寫在哪 | 四種規矩；寫錯時訊息品質不一 | 真問題 |
| X4 | `--stack` | 四個意思（要用的路徑／開關／名字／要查的路徑） | 真問題 |
| X5 | 工作區沒給 | 現在站的地方／daemon 的／報錯 | 補說明 |
| X6 | 成功印什麼 | 句子／信名／數字／路徑／不印 | 真問題（shutdown） |
| X7 | 列表 | 都沒表頭；`PHASE` 對 `STATE`、`WS` 對 `WORKSPACE`、`QUEUED` 對 `QUEUE` | 真問題 |
| X8 | 同一種錯的代號 | `ProcMissing`／`InstanceMissing`；`DaemonMissing`／`DaemonFailed`；`ToolMissing`／`ToolsMissing` | 留大修 |
| X9 | 已經是那樣了 | aos-agent 退 0、aos-daemon-ctl 退 1 | 真問題 |
| X10 | help 長相、佔位名 | 四型；`XXX／DEF_DIR／ECA_DIR／TEMPLATE` | 補說明 |
| X11 | 逾時 | `--timeout-s` 同名、等的東西與預設五種；`aos-llm ask` 沒有 | 補說明 |
| X12 | 同字不同義 | `AOS_DAEMON`、`rm`、`ctl`、`kernel`、`queue(d)`、`where`、`warning` | `AOS_DAEMON`、`rm` 是真問題 |
| X13 | 功能重疊 | agent ctl／daemon-ctl；agent tools／aos-tools；sweeper／sweep；看回答五條路 | 方向題 |
| X14 | 相對路徑 | 只有 aos-eca-turn 不收 | 小 |
| X15 | `--envs` | aos-daemon-ctl add 沒有 | 補說明 |

一致、做得好的（別動）：錯誤行形狀、退出碼 10 的意思、`-j／-h／-y／--dry-run／--timeout-s` 與五個短旗標的名字。

### 指令樹（細節 [07](07-指令樹.md)）

照「連字號程式與子命令視同一樣」把 22 支攤成一棵樹後：**沒有**「子命令名等於另一支的尾名、卻是不相干功能」的硬撞；有三處同名節點語意不齊——`ctl`（`aos daemon ctl` 對 `aos agent ctl`，十個同名動作，最大的一項）、`tools`（`aos tools` 對 `aos agent tools`，add 寫法不同）、`llm`（`aos llm` 是問腦、`aos agent llm` 是腦設定、`aos llm kernel` 是總機本體）。`copy-out` 不在樹上。層次上可以問但不急的三點（`sweeper`／`clock` 在第一層、`mcp` 其實是 tools 的出口、`agent` 底下層數不齊）都歸留大修。

## 分檔

| 分檔 | 內容 |
|---|---|
| [01-aos-agent](01-aos-agent.md) | 白話、裝不下九樣、15 個怪點（9 真問題）附實跑 |
| [02-aos-daemon-ctl](02-aos-daemon-ctl.md) | 白話、裝不下十樣、13 個怪點（7 真問題）、三對停與起的對照表 |
| [03-aos-exec與copy-out](03-aos-exec與copy-out.md) | aos-exec（行為都不建議動，只補 help）；copy-out 5 個怪點 |
| [04-aos-llm-eca-mcp](04-aos-llm-eca-mcp.md) | aos-llm、aos-eca-turn、aos-eca-screen、aos-mcp |
| [05-其餘指令](05-其餘指令.md) | 指令盤點；其餘 13 支各一段白話與怪點 |
| [06-跨指令不一致](06-跨指令不一致.md) | X1～X15 逐項對照；一致的也列 |
| [07-指令樹](07-指令樹.md) | 樹、T1～T8、選項 |
| [08-改法與施工順序](08-改法與施工順序.md) | 甲 18 項／乙 8 項／丙 5 項，改前改後、連帶檔、級別、工量；施工順序；代定表 |

| [09-Q1補-旗標放中間目標放最後](09-Q1補-旗標放中間目標放最後.md) | 使用者答 Q1 後補做：規則出處（P-44 與 10-21 原話）、逐支對照、重擬的 Q1、對 Q7／Q8 的影響 |
| [10c-施工結果-甲6Q3Q6](10c-施工結果-甲6Q3Q6.md) | 11-10 晚：ctl 寄信前先核 daemon、`ctl rm` 預設留 stack（`--purge` 才刪）、help 第一屏三對停與起表 |
| [10d-施工結果-Q1旗標位置](10d-施工結果-Q1旗標位置.md) | 11-10 晚使用者「1.收。2.收。3.好。」：旗標寫在它那一層名字之後任何位置、ctl 名字放最後、`--` 與內容之後不解析；六支指令＋共用解析、P-44 續、knowledge |

## 使用者已答的（11-10，頂層轉達；都只記裁定、還沒施工）

- **Q1**（第一次自填）：「我記得早期有說要aos-yyy zzz --flag -f ... XXX，旗標都放中間，最後才是目標。」→ 規劃員重擬成 [09](09-Q1補-旗標放中間目標放最後.md)。
  **重擬版**（照 `aos-yyy zzz [旗標] XXX` 補到什麼程度）自填原話：「旗標也可以寫在子命令前面，但這樣就等同於aos-yyy zzz [flags] XXX [flags] QQQ。因為zzz有個意義：aos-yyy-zzz和aos-yyy zzz相等。所以其實都可以。」
  頂層的理解（**轉述，不是原話**；明天施工前由頂層再向他確認一次）：形狀是遞迴的——每一層都是「節點 [這個節點的旗標] 下一個位置參數」，子命令跟連字號程式等價（C-86），所以子命令前、子命令後都可以放旗標，各自屬於它前面那個節點；兩種寫法都收＝09 的選項 A（以這個形狀為主線、舊寫法並存），不走嚴格只留一種的 B。
- **09 的三個讀法**（目標後可接原樣交給它的內容；沒有目標的子命令不用硬湊；`-d`／`--file` 算旗標不算目標）：他選「No preference」→ 照推薦三個都成立；補進 P-44 列入明天施工項（條文改寫 opus 親寫），P-44 第 6 行 `aos-eca-screen open [--detach] ECA_DIR` 過時那句一併改對。
- **Q2**：A（分工照舊、差別收到最少）。
- **Q3**：「兩支都留 stack，要刪另外說」→ `aos-agent ctl rm` 預設留 stack、要刪加 `--purge`（先前他反問「aos-daemon-ctl竟然會留著stack？」，說明後這樣答）。
- **Q4**：A（已停再停，兩支都算成功）。
- **Q5**：先答 A（根範本自己清掉繼承來的 `AOS_DAEMON`）；頂層告知行不通（`.env` 是外層贏、清不掉）後改答「喔沒關係，root這東西本來使用者就要多注意一點。」→ **已裁不修**：不另想辦法、不動範本與 C++，只在文件提醒起根前 `unset AOS_DAEMON`。
- **Q6**：A（不動，對照表放 help 第一屏）。
- **Q7** copy-out：「範本改成必給的旗標」→ `copy-out --template 名 目的地`，沒給範本就報錯，另加 `--list`。使用者問過 copy-out 是什麼（他不熟這支）：明天 help 改寫時第一句要用一句白話講清楚它是「把範本抄出去開新 agent／新根」。
- **Q8**：「改」→ `aos-agent tools add [--name 名] 路徑`，補 `--envs`、`--env-file`，寫法跟 aos-tools add 一致；lv6 的 agents／self_tools 那幾行呼叫照「只改那幾行」的例外跟著改。

## 要使用者選的（八題，照重要程度；推薦排第一，不選就照推薦）

**Q1　名字怎麼給、旗標寫在哪？**
現在 `aos-agent ctl stop ann` 報錯（要 `-t ann`），`aos-daemon-ctl stop ann` 只能這樣寫；`-d`、`-t` 寫錯位置就不認。
- A（推薦）兩種都收：`-d`、`-t` 寫在哪都行；`ctl` 的動作也收位置名字；`aos-daemon-ctl where ann` 也行。`say`／`listen`／`chat` 照舊只用 `-t`（`say ann hi` 分不出 ann 是名字還是話）。後果：純加法，舊寫法都還能用；約一天。
- B　只修旗標位置，名字的給法各支照舊。後果：最小；兩支指令仍是兩套習慣。
- C　全部改成位置參數、拿掉 `-t`。後果：最整齊，但每天打的指令與 agents 工具都要改，`$AOS_AGENT` 的用法也要重想。

**Q2　`aos-agent ctl` 跟 `aos-daemon-ctl` 有十個同名動作，要怎麼分工？**（照你「視同一樣」的原則，這是樹上最大的一處不齊）
- A（推薦）分工照舊（一支直達 daemon、一支替人多做幾步並經判官），把同名動作的寫法與後果對齊到只剩必要的差別（就是 Q1、Q3、Q4 三題）。後果：兩支都小改，都在命令列與訊息層。
- B　`aos-agent ctl` 只留 agent 專屬的（add、rm、state、who），stop／start 等八個只留在 aos-daemon-ctl。後果：樹最乾淨；`aos-agent ctl stop` 現在會說的「還有幾封信排著、怎麼再起」要搬家或沒了；呼叫它的工具要改。
- C　不動，只在兩支 help 頂端各放一張對照表。後果：最省；差異都還在。

**Q3　`rm`：一支留 stack、一支刪 stack。**
- A（推薦）行為不動，兩支的成功行與 help 第一行都講明「stack kept」／「stack deleted」（aos-agent 已經會講，aos-daemon-ctl 補上）。後果：只動字；同一個字兩種後果這件事還在，但不會看不出來。
- B　`aos-agent ctl rm` 改成預設留 stack，要刪加 `--purge`。後果：兩支同字同義；沒人清的 stack 會累積；agents 工具（腦在用的）要跟著加旗標。
- C　`aos-agent ctl rm` 改名（例如 `delete`）。後果：字分開了；多一個要記的字。

**Q4　對一個已經停了的列再下 stop：算成功還是算錯？**
- A（推薦）兩支都算成功（退 0、印 `already stopped`），照 aos-agent 現在的做法。後果：`aos-daemon-ctl stop x && …` 重跑不會斷；靠「退 1」判斷本來就停了的腳本要改看輸出。
- B　不動（aos-daemon-ctl 退 1）。

**Q5　`AOS_DAEMON` 一個變數兩個意思（你對哪台說話／這台 daemon 的上司），export 了它再起另一台根會認錯上司。**
- A（推薦）變數不改；根 daemon 的範本自己把繼承來的 `AOS_DAEMON` 清掉（只動範本），之後再看要不要讓 aos-daemon 起動時發現「上司表上沒有我」印一行 warning（那要動 lv2 的 C++，可晚點）。後果：日常那一行不用再先 `unset`；已經抄出去的根定義要重抄或手改一行。
- B　給人用的換一個變數名。後果：兩個意思分開；但環境變數是四種對外之一，所有文件、`using-aos-agent.sh`、你的殼設定都要改。
- C　不動，靠 README 的 `unset`。

**Q6　start 只能起「stopped」、wake 只能起「sleeping」，配錯就報錯叫你換一個字。**
- A（推薦）不動，只把那張「三對停與起」的表放到兩支 help 的第一屏。後果：照你原本分開的設計；配錯時訊息已經會告訴你該打哪個。
- B　`start` 兩種都能起（`wake` 留著當同義）。後果：人只要記一個字；「它是哪一種停」只在 `ls` 看得到、不用先知道。停的那一側（stop／sleep）不變。
- 我排 A 第一是因為這兩個狀態是你自己分的（重開 daemon 時一個會自己醒、一個不會）；B 做得到、只動 Python 殼。

**Q7　`copy-out` 只給一個參數時，現在拿它當目的地、範本用預設的 agent-fsm。**
- A（推薦）兩個都必填（`copy-out 範本 目的地`），另加 `copy-out --list`。後果：`copy-out agent-fsm`、`copy-out help` 不會再默默抄一份；習慣只打目的地的要多打範本名。
- B　不動，help 第一行加粗提醒。

**Q8　`aos-agent tools add 名 路徑` 要不要改成跟 `aos-tools add [--name 名] 路徑` 一樣（並補 `--envs` 等旗標）？**（上一輪 Q4 沒做的那一半）
- A（推薦）改，但排在這輪最後、或留到明後天。後果：同名節點同寫法；腦在用的 `self_tools`、`agents` 兩支工具（lv6）要跟著改呼叫，照上次的例外辦理（只改那幾行）。
- B　留大修。後果：要給某隻 agent 的工具設環境變數時，仍得繞去打 `aos-tools --file <那隻的 stack>/tools.json add …`。

## 我代定的（實作細節，可翻案；全表在 [08](08-改法與施工順序.md) 結尾）

旗標同一個給兩次不同值＝報錯；`ls` 沿用既有 `# ` 尾行、不加行；`aos-daemon-ctl add` 撞名是報錯不寄（`--reply-to` 的程式路線不預查）；`shutdown` 成功印 `daemon stopped; N procs asleep` 並另給 `-j`；`copy-out --list` 一行一個；佔位名 `XXX` 不動；lv1～lv2 的 help 補字跟下次重建 impls 併做、不單獨重建；aos-llm 的人用寫法（lv4）、help 四型統一、錯誤代號統一、`warning:` 的用法、樹的層次都歸留大修。

## 跟既有待辦重疊的（不重報）

B01（daemon 表存相對路徑、`ctl add` 收環境變數寫法——明天第一項，跟甲6 動同一段）、B08、B09、B12、B14、B16、B23；設計-43、設計-45、設計-53～55、設計-58、設計-64（收 stderr 再印）、設計-65；坑-63、坑-68（這次發現它只補了一格，見 01 的 A1）；HANDOFF 11-10 第 2 點的「『ctl 信箱』說法」；aos-tools-cli 第一輪 Q4。

## 沒實跑、拿不準的

- **經判官的路**（`AOS_KERNEL`、`--on-queued`、`--limits`）完全沒跑；`aos-agent ctl add` 的相關行為只讀 help。
- `aos-daemon-ctl add` 的一次性程式，stdout 去了哪裡沒追到（stack 裡只有 `stderr.txt`、daemon 的輸出裡也沒有）。
- `aos-grow` 只讀 help；`aos-sandbox` 只跑 `--dry-run`（不 sudo）；`aos-sweeper` 只跑 `--dry-run`；`prune --older-than`、`sweep --purge`、`--reply-to` 沒跑。
- `aos-eca-turn` 的冷卻、換台重開對話沒重跑（two-machines 那邊測過）；`open` 只跑 `--detach`（沒有真的接上畫面）。全程用假 claude，沒叫真的 claude／codex。
- aos-mcp 不預設工作區是不是故意的，不確定。
- `aos-feedback ls` 的欄位分隔看起來是兩個空白不是 TAB，沒有用 `od` 確認。
- pause／resume 印的數字有沒有 repo 內的程式在讀，沒查（shutdown 的三處呼叫查過，都不讀）。
- 級別標籤裡把 aos-daemon-ctl、aos-sweeper 算成「lv2 的周邊」、aos-sandbox 算「lv5 周邊」、aos-clock 算 lv3，是我照任務單的分級自己對的，沒有條文可依。
- 工量是估的；連帶檔清單來自 grep，文件類可能有漏。
