# Plan 9 之外：普通檔案、短命程式與更笨的 daemon（astra，2026-10-03）

## 一段話結論

**Plan 9 式 namespace＋檔案伺服器不是唯一方向。**
我更建議先拆開三個需求：入口好找、權限受限、工作能交接。
普通目錄可以解第一個。
帳號與受限制的服務介面可以解第二個。
普通檔案加 tick 可以解第三個。
原提案的「檔位 1 bwrap 視野」仍值得試，但可以先留在 inst 的啟動包裝，不急著加入 daemon 模組。
`/llm/clone` 則應和短命 CLI、跨格工作佇列一起比較。
若目的只是換後端、集中金鑰與分配額度，FUSE 沒有不可替代的作用。

## 替代方案

以下都是候選設計。
新增的程式名與格式都只是示意。
實驗均未執行。

先把比較的需求分清楚：

| 想得到什麼 | 最便宜的候選 | 什麼時候原提案比較值得 |
|---|---|---|
| 固定名稱、容易找門 | 普通目錄地址簿 | 必須提供每個程序不同的絕對路徑樹 |
| shell 能呼叫 LLM | stdin／stdout 命令 | 客戶端必須只靠檔案操作，不裝專用命令 |
| 集中金鑰與額度 | 獨立帳號的有限代發程式 | FUSE 介面本身已有足夠使用收益 |
| 留下請求與結果 | 普通 spool 目錄 | 要的是活的服務檢視，而非持久工作檔 |
| 減少自行維護的喚醒機制 | systemd path／socket activation | 不願把 systemd 納入部署前提時，保留 aos-daemon |

### 方案 A：地址簿先用普通目錄，bwrap 留在啟動包裝

- **長相**

```text
agent-bob/
  .aos/inst.json
  .aos/tasks.json
  config/
    ports/
      kernel -> /srv/team/doors/kernel/s
      team   -> /srv/team/doors/team/s
    tools/
      say -> /opt/aos-tools/say
  work/
  state/
```

一格仍然跑 `aos-tick`。
任務用工作資料夾內的固定名稱找門：

```sh
aos-mq send config/ports/kernel -
```

工作目錄可能改變時，由薄包裝程式從 `AOS_TICK_CWD` 找地址簿。
`take` 仍保留 `AOS_DAEMON_INST`。

需要限制視野的成員，才在 `.aos/inst.json` 包整格 bwrap。
先沿用原提案的 bwrap 參數。
不新增 namespace 描述語言。
也不先增加 `modules.ns`。

現有 daemon 已把 inst 字面值交給 `aos-exec`。
證據是 [aos_daemon_run.py](../../../src/py/lib/aos_daemon_run.py) 第 27–36 行。
inst 已解析 `argv`、`envs` 與 `cwd`。
證據是 [aos_inst.py](../../../src/py/lib/aos_inst.py) 第 123–142 行。
MQ client 直接使用收到的 socket 路徑。
證據是 [aos_mq.py](../../../src/py/lib/aos_mq.py) 第 41–56 行。

- **比原提案好在哪**

`ls config/ports` 已能呈現通訊錄。
換門地址不用改任務。
普通地址簿不需要組裝 Python、函式庫與 `/proc` 所在的執行環境。

更重要的是，daemon 不必理解 namespace。
隔離仍是一支普通啟動包裝程式的責任。

這不是否定[原提案的實驗 A](../../proposals/2026-10-02-plan9/09-最小實驗.md)。
是替它增加一個更便宜的對照組。
也避免實驗順手就自動升格成 daemon 新模組。

- **代價與邊緣狀況**

地址簿不提供隔離。
刪掉連結，不能阻止程式直接連原路徑。
符號連結失效與工作目錄改變，也都要報得出來。

整格 bwrap 若由 agent 可修改的 inst 啟動，只能當配合式限制。
要成為強制邊界，啟動描述與包裝程式必須由管理者掌握。

包裝發生在 `aos-exec` 解析 inst 之後。
若需求包含「連 inst 解析與前置開檔都要隔離」，才有理由把邊界移到 daemon 啟動之前。

入口變少，也不會縮小已開放 socket 的能力。
現行 MQ 依請求中的 inst 名稱取信。
證據是 [aos_daemon_mq.py](../../../src/py/lib/aos_daemon_mq.py) 第 93–103 行。
因此地址簿與 bwrap 都不能單獨提供「只能取自己的信」。

成員變多時，地址簿也會變成要維護的配置。
應從同一份配置產生。
不要再手寫一份與 daemon 設定互相漂移。

- **要翻的裁定**

普通地址簿：**無**。
沿用[第二十五批](../../verdicts/11-tick-as-unit/26-1002-第二十五批.md)的 socket 路徑與資料夾權限。

可選的整格包裝：**不必翻現有核心邊界**。
它不改 tick，也不取代帳號模組。

若進一步宣稱 namespace 能取代帳號與授權判斷，就必須修訂[投件權裁定](../../verdicts/09-special-computing-os/01-方向與審稿裁定.md)第 2 條及[現行 T-08](../../../spec/terms.md)。
本方案不作這項承諾。

- **最小實驗**

半天。
同一個回聲 agent 做兩套啟動配置。
一套普通地址簿。
一套整格 bwrap。

兩套都驗固定名稱、換地址與回信。
再驗一條只有隔離方案應通過的條件：硬寫宿主原路徑，仍碰不到未授予的門。

記錄額外配置量、啟動失敗與除錯步驟。
若使用者只需要前半段，普通目錄就已足夠。

### 方案 B：以「一次命令」取代 `/llm/clone`

- **長相**

一支短命程式只做一次呼叫：

```sh
llm-call < request.json > response.part
```

輸入是一份 JSON。
輸出是一份完整 JSON。
診斷走 stderr。
成功且格式正確後，包裝程式才發布 `response.json`。

後端由配置選擇：

```text
llm-call
  ├─ fake：讀劇本
  └─ direct：執行一次 HTTP 呼叫
```

每次呼叫使用獨立工作目錄。
不要覆用上一格的結果檔。

這其實是採回[agent 提案的一次呼叫程式](../../proposals/2026-10-02-agent/04-一格做什麼.md)，再把介面縮成標準輸入輸出。
不是另一套新的 agent 架構。

現有 tick 已能接檔案串流、啟動子程序並等待結束。
證據是 [aos_tick_run.py](../../../src/py/lib/aos_tick_run.py) 第 63–88 行。
這些是現成零件。
`llm-call` 本身仍需新寫。

- **比原提案好在哪**

同樣能從 shell 呼叫。
同樣能替換假後端與真後端。
同樣能把請求與結果留成檔案。

不必先定 clone 號碼、fd 保活與回收規則。
也不必處理 request 的 close 提交語意。

**「可換後端」來自穩定的呼叫契約。**
不必先把三種後端都包成 FUSE 樹。

- **代價與邊緣狀況**

CLI 本身不會保護金鑰。
直連程式與 agent 同帳號時，仍不提供金鑰隔離。

它也不會強制跨程序的額度。
把 `llm-call` 從工具清單移除，不能阻止程式另開 HTTP 連線。

程序被殺時，`response.part` 可能只有半份。
呼叫已送到供應商時，本機退出不代表遠端停止計算。
重送可能再計費。

後面的 `act` 必須核對本次請求 ID 與成功結果。
不能只看結果檔存在。
tick 的任務非零碼不會自動阻止下一項。
證據是 [aos_tick.py](../../../src/py/lib/aos_tick.py) 第 177–188 行。

大量同時呼叫仍需要額外限流。
短命程序只是簡化介面，沒有消除排程問題。

- **要翻的裁定**

fake／direct 版本：**無**。
符合[第十五批第 4 條](../../verdicts/06-cgroup-direct-delivery.md)的直連定義。

若後來強制所有呼叫走代理，就要翻同一條的「agent 自己打 endpoint，aos 完全不管」。

若為了保留同步呼叫而另開常駐代理，就要對[11 的追答第 5 條](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md)新增例外。
不能只把它叫作基礎設施，就當作沒有翻裁定。

- **最小實驗**

半天到一天。
先做同一份假 LLM 劇本的 CLI 版本。
若仍想試 FUSE，再讓 `/llm/clone` 共用同一個假後端。

兩版都驗正常回覆、中途終止、後端失敗與半份輸出。
比较依賴、程式量、shell 用法與錯誤診斷。

若 FUSE 版只多了 `cat` 的寫法，就把它保留為介面興趣。
不要把額度強制與金鑰隔離列成已證明收益。

### 方案 C：檔案保存工作，MQ 只送提示，LLM 也在另一格內執行

- **長相**

這是最值得拿來對照 `/llm/clone` 的另一條路。

```text
exchange/bob/
  requests/
    tmp/<id>.json
    new/<id>.json
  replies/
    <id>.json

llm-worker/
  .aos/tasks.json
  config/provider.json
  state/
    running/<id>.json
    done/<id>.json
    budget.json

agent-bob/
  state/pending/<id>.json
```

第一輪只做一個 agent、一個 worker。
兩者各有自己的工作資料夾。

訊息流如下：

```text
agent 第 N 格
  → 寫 request 暫存檔
  → 同一檔案系統內 rename 發布
  → MQ 送「有工作」提示
  → 記 pending，結束本格

worker 下一格
  → 掃固定入口
  → 取一份完整請求到自己的工作區
  → 查政策，執行一次 LLM
  → 發布結果，再送提示

agent 後續一格
  → 找到相同 ID 的結果
  → act、remember
```

MQ 提示可以只有：

```json
{"type":"spool-ready","version":1}
```

提示不帶任意路徑。
worker 只讀配置允許的入口。
回覆位置也由 worker 配置決定。

這借用 Maildir「先寫 tmp，再發布到 new」的做法。
不是完整移植 Maildir 協定。[djb 原始說明](https://cr.yp.to/proto/maildir.html)

- **比原提案好在哪**

daemon 不必變成檔案伺服器。
也不必保存 LLM 請求正文。

普通檔案能直接檢查。
daemon 重啟後，已發布的工作仍可被下一格掃到。
這不等於斷電持久性保證。

LLM worker 仍在 tick 裡執行。
不需要另開格外常駐服務。
政策也仍是一個普通任務。

若採獨立帳號，金鑰可以只供 worker 讀取。
現有 daemon 已有跨帳號啟動路徑。
證據是 [aos_daemon_run.py](../../../src/py/lib/aos_daemon_run.py) 第 28–32 行。
帳號模組要求 root 啟動。
證據是 [aos_daemon.py](../../../src/py/lib/aos_daemon.py) 第 132–141 行。

**持久工作必須先落檔，再送提示。**
不能先 `take`，才把正文存下來。
現有 `take` 在產生回應前便清空信箱。
證據是 [aos_daemon_mq.py](../../../src/py/lib/aos_daemon_mq.py) 第 93–103 行。

- **代價與邊緣狀況**

代價首先是延遲。
agent 的一次思考跨越多次開格。
原提案的「同格等 LLM，再 act」要改成有 `pending` 的流程。

要靠掃描補掉遺失提示，就必須真的保留週期掃描。
永久 paused 的成員沒有這項保證。
第一輪宜讓 agent 與 worker 都有低頻保底週期。

每格處理一件最容易理解。
但一個慢請求會擋住後面的請求。
併發 worker 與公平排程應在量到需要後再加。

worker 發出 HTTP 後被殺，結果可能不明。
第一輪應留下 `unknown`，不自動重送。
本機工作 ID 不能保證供應商只計費一次。

完成工作到寫 `done` 之間中斷，仍可能重做。
這不是「恰好一次」。
也不應趁這個方案把 POC 擴成完整可靠佇列。

權限要切在真正的入口。
同 UID 的兩個目錄不能冒充兩個可信身分。
若要強制每人額度，需由受保護的入口辨識委託者。
不能相信 JSON 自報的 `from`。
agent 也不能改 worker 的程式、任務表或政策。

多收件者時，不能由第一人刪掉共享原件。
現有 MQ 是每位訂戶各拿一份。
證據是 [aos_daemon_mq.py](../../../src/py/lib/aos_daemon_mq.py) 第 104–111 行。
普通檔案版也要保留各自的消費紀錄。

檔案累積會增加掃描成本。
先限制每格處理件數。
再用實驗決定保留期與分桶。
若加 inotify，事件只能加速發現，不能取代重掃。
事件佇列可能溢位。[Linux inotify 手冊](https://man7.org/linux/man-pages/man7/inotify.7.html)

- **要翻的裁定**

應用層工作檔＋原樣 MQ：**無須翻「MQ 放記憶體」**。
MQ 仍只保存可遺失的提示。
一般檔案收件由普通任務自行處理，也符合[11 的檔案收件裁定](../../verdicts/11-tick-as-unit/02-0930-疑點裁定.md)。

跨格接回 LLM 結果：改的是[agent 提案](../../proposals/2026-10-02-agent/04-一格做什麼.md)。
它尚未成為使用者裁定。
不必因此翻「tick 是衡量基準」。

但若要承諾「能投 LLM 資料，卻不能取得 worker 的任意執行能力」，就必須明確限縮[09 第 2 條](../../verdicts/09-special-computing-os/01-方向與審稿裁定.md)與[現行 T-08](../../../spec/terms.md)的涵蓋範圍。
這是新增有限服務契約。
不是帳號不同就自然完成。

若把本方案升格成 daemon MQ 的替代，則要翻[第十二批的記憶體信箱](../../verdicts/11-tick-as-unit/14-1001-第十二批.md)與[第二十五批的送達、叫醒及狀態規則](../../verdicts/11-tick-as-unit/26-1002-第二十五批.md)。

- **最小實驗**

一天完成單帳號、假 LLM 版本。
一個 agent。
一個 worker。
worker 每格最多處理一件。

驗半份 tmp 不會被消費。
驗漏送提示後，保底週期仍能找到工作。
驗 daemon 重啟後，工作檔仍在。
驗 worker 中途被殺後，不會把舊結果當本次成功。

第二天若已有可用的兩個測試帳號，再驗私密檔與政策寫權。
沒有帳號前提，就只交付流程結論。
不宣稱已驗證金鑰隔離。

### 方案 D：讓 Linux 負責喚醒，aos 只留下 tick 與政策程式

- **長相**

這是願意翻部署方向時的候選。

```text
bob.path
  → 監看 requests/new
  → bob.service
      → aos-tick /srv/bob

bob.timer
  → 提供保底開格
```

示意配置：

```ini
# bob.path
[Path]
DirectoryNotEmpty=/srv/bob/requests/new
Unit=bob.service
```

```ini
# bob.service
[Service]
Type=oneshot
ExecStart=/opt/aos/bin/aos-tick /srv/bob
```

政策仍寫在任務表。
systemd 只承接外部喚醒與程序生命週期。

`DirectoryNotEmpty` 可啟動對應服務。
服務結束後會重新檢查條件。[systemd.path 官方文件](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.path.xml)

- **比原提案好在哪**

不必為普通檔案寫常駐 watcher。
也不用為了「有事才啟動」先造 FUSE。

若 Linux 本來就由 systemd 管理，可以比較是否值得減少自行維護的 daemon 職責。
這條路是「少寫一層監督機制」。

若另想做同步 LLM 服務，socket activation 也可每條連線啟動一個 worker。
socket 可接到標準輸入輸出。[systemd.socket 官方文件](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.socket.xml)

- **代價與邊緣狀況**

這不是 aos-daemon 的等價替換。
現有 MQ、pause、state、reload 與巢狀 daemon 行為，都要重新接線。

`new/` 一直非空時，服務會反覆啟動。
如果 tick 被擋板擋住，或工作一直失敗，就可能碰到啟動限流。
path unit 也可能因此停止監看。[systemd.path 官方文件](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.path.xml)

所以「目錄有工作」與「目前允許執行」必須分開。
不能用更快的喚醒掩蓋尚未允許的工作。

大量成員也會帶來大量 unit 與配置。
動態建立成員時，還要處理服務管理權限。
不能先假設它一定比現有 daemon 更省。

現有 daemon 不能直接加一份 socket unit 就獲得 activation。
它自行 unlink、bind、listen。
證據是 [aos_daemon_ctl.py](../../../src/py/lib/aos_daemon_ctl.py) 第 52–62 行。

- **要翻的裁定**

作為初版標準部署，明確要翻[第十五批第 1 條「初版不用 systemd」](../../verdicts/06-cgroup-direct-delivery.md)。

若只讓 systemd 啟動完整 tick，政策仍在格內。
這與[tick 由誰定期執行都可以](../../verdicts/10-tick-minimal-core/01-方向.md)一致。

若 socket activation 直接執行 LLM，則另須翻[11 追答第 5 條的格外服務限制](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md)。
短命不代表在 tick 裡。

若把帳號分配也搬到 unit，則要修訂[第十三批「切帳號只在 daemon config」](../../verdicts/11-tick-as-unit/15-1001-第十三批.md)。

- **最小實驗**

一天。
只做一個假 worker。
用 path unit 啟動現有 tick。
不遷移整個 aos。

驗正常投件。
驗服務執行中再投件。
驗工作失敗後原件仍在。
驗擋板存在時是否空轉。
再量需要多少 unit 配置與人工介入。

若它只是把簡單的 daemon 設定換成更多管理配置，就停止這条路。

## 不換方向的改良

1. **把原本的四個檔位改成可分開選的能力。**

   namespace、檔案介面、持久工作與集中代發沒有必然先後關係。
   不應讓「試過 bwrap」自然推導成「下一步 daemon 要 FUSE 化」。
   比較對象是[原提案檔位表](../../proposals/2026-10-02-plan9/08-檔位.md)。

2. **保留 bwrap，但先不新增 `modules.ns`。**

   原實驗已能從 inst 包裝開始。
   等出現必須在 inst 解析前施加的限制，再移入 daemon。
   這能保持[笨 cron 的核心方向](../../verdicts/11-tick-as-unit/07-1001-最核心daemon.md)。

3. **不要再把跨層環境清理算成 namespace 的新增收益。**

   現行 `give_env()` 已刪掉繼承的 `AOS_DAEMON_*`，再設本層值。
   證據是 [aos_daemon_run.py](../../../src/py/lib/aos_daemon_run.py) 第 163–178 行。
   其他環境仍可能繼承。
   bwrap 的完整環境白名單仍有作用，但用途已縮窄。

4. **替 `/llm/clone` 設一個能區別優劣的驗收題。**

   「shell 能呼叫假 LLM」不足以支持 FUSE。
   CLI 也能做到。
   應改驗「哪一種實際客戶端，在不用新增專用程式時明顯更好接」。

5. **若保留檔案服務，先提供沒有副作用的檢視。**

   `status`、請求結果與用量較適合先做。
   收信仍用明確的 `take`。
   避免一般查看工具讀一下，就消費了資料。
   這是[daemon 檔案樹提案](../../proposals/2026-10-02-plan9/03-daemon變成檔案伺服器.md)可獨立縮小的一刀。

6. **把新實驗的可靠性範圍寫窄。**

   發布完整 JSON，不等於斷電不丟。
   看得到工作檔，不等於外部副作用只發生一次。
   第一輪只揭露中斷結果，不補整套救援。
   這符合[POC 默認一切正常](../../verdicts/11-tick-as-unit/03-1001-POC默認一切正常.md)的方向。

## 試過但放棄的想法（各一兩句）

- **用 named pipe 直接取代所有 socket。**  
  FIFO 仍是沒有訊息邊界的位元組串流，而且不保存工作。  
  多個寫入者的大訊息還要另做分框與協調，沒有省掉主要協議成本。[Linux pipe 手冊](https://man7.org/linux/man-pages/man7/pipe.7.html)

- **只靠 inotify，事件來了就當作收到工作。**  
  事件會溢位，也不是工作完成紀錄。  
  最後仍要普通檔案與重新掃描。[Linux inotify 手冊](https://man7.org/linux/man-pages/man7/inotify.7.html)

- **以 Landlock 全面取代 bwrap。**  
  它適合限制操作，卻不提供固定虛擬路徑樹。  
  以原提案的 Linux 6.6 基準來看，也不能把一般檔案限制直接推成完整 socket 隔離。[Linux 6.6 Landlock 文件](https://docs.kernel.org/6.6/userspace-api/landlock.html)

- **只用 seccomp 表達「哪些門可以連」。**  
  一般 seccomp filter 不能解參數指標中的路徑內容。  
  它適合縮小 syscall 面，不適合單獨承擔地址與授權模型。[Linux seccomp 文件](https://docs.kernel.org/userspace-api/seccomp_filter.html)

- **全面改成預先開啟的能力 fd。**  
  方向有價值，但會新增 daemon→exec→tick→task 的 fd 傳遞契約。  
  現行 tick 啟動任務沒有一般 `pass_fds` 介面，見 [aos_tick_run.py](../../../src/py/lib/aos_tick_run.py) 第 75–76 行。

- **照搬 daemontools 整套模型。**  
  憑記憶，它值得借的是小型監督者與獨立程序的分工。  
  這裡真正未解的是 tick、訊息與政策的接法，換監督器名稱不會自動解決。

- **所有控制都改成普通檔案，等目標下一格處理。**  
  卡死或停止開格的目標無法靠自己的下一格恢復。  
  kill、恢復與外部喚醒仍需要格外控制者。

- **為了 Unix 味，把 JSON 全改成一行文字。**  
  沒有新增能力，卻多出跳脫、分框與相容成本。  
  原提案保留結構化 JSON 的判斷比較好。

## 問使用者的問題（表格：題｜選項與後果｜建議）

| 題 | 選項與後果 | 建議 |
|---|---|---|
| 「接近 Unix 極限」最想得到什麼？ | 入口一致：普通目錄即可先試。可組合：短命程式與串流。每程序不同世界：namespace。純檔案客戶端：FUSE。 | 先選要改善的使用經驗，再選機制。 |
| 檔位 1 要立刻進 daemon 嗎？ | 進模組：統一管理，但增加核心周邊契約。留 inst 包裝：較易試與撤回。 | 先留包裝，和普通地址簿做半天對照。 |
| `/llm/clone` 要驗介面，還是資源分配？ | 驗介面：FUSE 有獨立價值。驗額度與金鑰：應先做 worker 與授權邊界。 | 兩題分開，不用一次假回覆替兩者背書。 |
| 能否接受 LLM 跨格回來？ | 接受：可用普通工作檔，代發留在 tick。不同意：保留同步 CLI，或另裁格外代理。 | 先做單 worker 假實驗，量出多幾格的實際等待。 |
| 是否允許「只能提交資料」的有限服務？ | 允許：需限縮 T-08，才能承諾投件不等於任意執行。不允許：代理不能宣稱因此保住身分與金鑰。 | 把它列成獨立裁定，不混進 FUSE 選型。 |
| systemd 是否值得重開討論？ | 納入：可減少自製喚醒與監督。維持不用：部署邊界較單純。 | 本輪列對照，不列前置條件。 |
| 先試哪個？ | A＋B 最便宜，保留現有流程。C 更能驗特殊計算的交接與分配。D 改動部署方向最大。 | 先 A＋B；若重點是資源分配，再做 C。 |

本次全程唯讀。
未改檔、未 commit、未跑測試。
程式能力以本次讀到的原始碼為準。
實驗時間都是範圍受限的探索預算。