把進度檔 42 條 open 與條文 5 條待定逐條對新模型掃過：28 條不相干、6 條會變簡單、8 條要重想（施工中可能白做的只有 idle-polling 的後段）、4 條是新模型自己或它的前置、1 條衝突（subuid 分帳號對上 `/proc/<PID>/cwd` 入口，已實測）。

# 17　open 進度總掃描：四十二條進度與五條條文待定，各自受不受新模型影響

← [架構規劃入口](../README.md)

寫這份的是這批的第 17 隻子 agent（fable）。只讀：沒改進度檔、沒改任何既有的檔。做了一個小實測，只碰 `~/.aos/scratch/aos-proc-arch-1125/17/`，起的行程都收掉了。

- 材料：`wf/progress.json` 的 `open`（42 條，全讀）；`proto8/docs/NORMS/08-待定.md` 與 `08-待定/` 三份；新模型 `proto8/thinking/2026-11/25/9p-proc-1125.md`（下面簡稱 9p-proc）。
- 三種話：「」裡加「使用者」的是他的原話（逐字）；帶 `檔名:行號` 或 commit 號的是查到的；標「推論」的是我想的。
- 條目名後面括號裡的數字，是它在 `wf/progress.json` 的行號。「筆記」指 `wf/ws/eca-aos/notes.md`。路徑沒寫開頭的從 repo 根算。
- 同夾別的報告：我只讀了已經交出來的十二份（01～06、12～16、18）的結論，碰到它們範圍的地方指過去，不重做；內文沒對。07～11、19、20 與原型沒看到。

## 1. 結論

1. **分類**：42 條 open 加 5 條條文待定共 47 條——不相干 28、會變簡單 6、會白做或要重想 8、是新模型自己或它的前置 4、衝突 1。
2. **唯一的衝突是 `subuid-1119`**。新模型的入口 `/proc/<PID>/cwd` 只有同一個 Linux 帳號走得進去；換成子帳號的 proc（程式 11-19 已交、公司這台真機驗過）走不進根、也走不進別隻，只有真實路徑走得到（第 7 節實測；報告 02、15 也測到）。使用者 11-21 說過「真的要硬防，那就要多依賴linux的權限體系」，這兩件要一起看。
3. **正在施工而可能白做的，只有 `idle-polling` 的後段**。第 0～3 刀不受影響（使用者 11-25 已經說「照做，閒置輪詢繼續。」）；第 5 刀（wait 格）與第 6 刀的 inotify 項，跟新模型「活著走 unix socket」解的是同一件事，建議等那塊定了再排。`compact-improve`、`eca-bg-mail-1124` 不會白做；`agent-fsm-py-folder` 是暫停的，前半已被 11-24 的三分做掉。
4. **條文大修（`norms-text`）要排在新模型之後**。已定的 N-14（窗的內容是 JSON）、N-13（外顯的檔落在 `$AOS_STACK`）、N-17（其他人不碰 pid）字面都會被改；17 題新待裁裡有三題會改題。
5. **四條在講同一件事**：`relative-paths-1124`、`fs-tmpfs-1124`、`plan9-ns-1124` 都寫著等 proc 介面，可以併進 `proc-interface-spec`。但 11-25 早上那句錨點定義裡的「stack」，當天稍後改了意思，要請使用者重讀一次（第 9 節第 3 題）。
6. **「等使用者」的十條裡，有五條可以改掛「等新模型」**（`norms-text`、`aos-kres`、`waiting-1121` 的第 4、5 題、`aos-init-kernel` 的可選件、`subuid-1119` 的後續刀），他現在要答的量會少一截。
7. **不用重談的**：ctl 有哪些字、收到與做完分開、信長什麼樣、信箱位置誰定、睡著的誰叫醒、寄件人怎麼認、status 分哪幾類——進度檔與條文裡都有現成的答案（第 5 節）。
8. **進度檔自己落後六處**（跟新模型無關，順手列在第 8 節）。

## 2. 總表

### 2.0 代號與反查

下面各表用方括號代號指 9p-proc「定了的」那幾條（`9p-proc-1125.md:23`～`36`）。右欄是碰到它的條目，等於反過來查。

| 代號 | 定了的（行號） | 碰到的條目 |
|---|---|---|
| 〔persist 自己說〕 | persist 在哪以 proc 自己說的為準（23） | `fs-tmpfs-1124`、`eca-main-obs-1124` |
| 〔普通實作〕 | 介面基於 9P；aos-loop／daemon 退成普通實作之一（24） | `idle-polling`、`overview-page`、`norms-text` |
| 〔純文字〕 | ctl、status 純文字；`_metainfo` 照舊用 json（25） | `norms-text`（N-14）、`kb-md-leftovers`（N-69）、`aos-goals-1124` |
| 〔收到〕 | 寫 ctl 回來＝收到，做完沒看 status（26） | `aos-compile`（gdb 的 `wait=`）、`waiting-1121` 第 4 題 |
| 〔status〕 | 一行一個「名稱: 值」，目前只給 status（27） | `aos-htop-1119`、`overview-page`、`mine-arena-dir-1123` ③、條文待定「kernel 公告」 |
| 〔token〕 | 用量各自報、放自己目錄（28） | `aos-htop-1119`、`eca-main-obs-1124` |
| 〔橋〕 | daemon＝橋，也是 aos proc，多一個 procs 夾（29） | `aos-init-kernel`、`design-tails-1113`、`norms-text`（N-54） |
| 〔kernel〕 | kernel＝普通 aos proc（30） | `aos-init-kernel`、`aos-kres`、`arena-feedback-1124` ③、`aos-compile`、條文待定「kernel 公告」 |
| 〔同指一處〕 | `proc` 與 `procs` 指同一處（31） | `design-tails-1113`（index 三題） |
| 〔入口〕 | 給根 daemon 的 PID，`AOS_ROOT`（32） | `subuid-1119`、`relative-paths-1124`、`overview-page`、`aos-user-home`、`norms-text`（N-17） |
| 〔stack 改義〕 | `.stack` 沒有了，stack＝活著的身體（33） | `fs-tmpfs-1124`、`relative-paths-1124`、`idle-polling` 第 2 刀、`agent-fsm-py-folder`、`workspace-stack-alloc`、`norms-text`（N-13）、`aos-inherit` |
| 〔persist〕 | 要留的各自處理，推薦 `procs/<名>/persist`（34） | `fs-tmpfs-1124`、`relative-paths-1124`、`compact-improve` |
| 〔兩條路〕 | 活著走 unix socket，掛了問信箱在哪、改走寄信（35） | `idle-polling` 第 4～6 刀、`eca-rest`、`waiting-1121` 第 5 題、`aos-kres`、`arena-feedback-1124` ③、`eca-bg-mail-1124` |
| 〔叫醒〕 | 要不要順手叫醒＝daemon 的可選設定（36） | `arena-feedback-1124` ③、`idle-polling` |

### 2.1 衝突（1 條）

| 條目 | 它是什麼 | 新模型的哪一條碰到它的哪一部分 | 現況 |
|---|---|---|---|
| `subuid-1119`（193）等使用者 | daemon 能免 root 把一支 proc 換成使用者名下的子帳號（`limits.user: "sub:N"`）。程式已交（368719e7a、72bc0c67c），公司這台真機驗過，等使用者在家機補一行 `setfacl`。後面排著三刀：信箱用 aos-share 開、看信夾擁有者認寄件人（K9）、子 daemon 沿用父的群組（K18） | 〔入口〕要過核心的讀取權限檢查，只認同帳號。實測：換成子帳號的 proc 對根與別隻的 `/proc/<PID>/cwd` 一律 `Permission denied`，同一個夾走真實路徑讀得到。所以開了 `sub:N` 的 proc 用不了 `AOS_ROOT`，也到不了 `procs/<名>/sock`。後面三刀都建在帳號不同上，跟同帳號才走得通的入口方向相反。同類的還有沙箱：關進 bwrap 的行程也走不進去（報告 12 結論 8、報告 06 結論 8；整件事報告 15 結論 2、3 講得最全） | 沒人在做。已交的程式預設不開、不會壞。往下做之前要先定第 9 節第 1 題 |

### 2.2 會白做或要重想（8 條）

照要緊程度排。「局部」＝只有條目裡的一部分受影響。

| 條目 | 它是什麼 | 新模型的哪一條碰到它的哪一部分 | 有沒有人在做、會不會白做 |
|---|---|---|---|
| `idle-polling`（452）open，**施工中**，局部 | 閒著的 agent 每拍照樣起 Python、吃 CPU。使用者：「先記下來，這會是以後一段時間的我們的開發重點。」規劃分第 0～6 刀，用 C++ 的閘擋掉 | 〔兩條路〕的「活著走 unix socket」＝有事才醒，跟後段幾刀解同一件事。〔stack 改義〕會動到閘認的檔名 | 見下面分刀表。前四刀不白做；第 5 刀與第 6 刀的 inotify 項最可能白做 |
| `norms-text`（25）等使用者 | 條文等使用者大修（「條文這東西以後我會大修，現在不用這麼急」），另掛 17 題新待裁 | 〔純文字〕改掉 N-14「內容是 JSON」（`proto8/docs/NORMS/05-基礎設施-窗/03-N-13～N-14.md:11`～`12`）。〔stack 改義〕改掉 N-13「外顯的檔落在 `$AOS_STACK` 底下」（同檔 5 行）。〔入口〕碰 N-17「其他人不碰 pid」（`06-N-17/01-誰判死活與例外.md:4`）。〔橋〕碰 N-54 的 daemon 手把。17 題裡第 7 題（N-54 的 slept 語意）、第 8 題（N-13 的格式選 A 還是 B）、第 17 題（`AOS_HOME` 那句）會改題 | 沒人在做。現在動條文＝之後再動一次。建議只累積待改清單 |
| `fs-tmpfs-1124`（496）open | 短期目標：整棵 `.stack` 放 tmpfs、定期同步回硬碟（使用者：「或許短期目標會是我說的，把東西放/tmp，定期同步到硬碟。」） | 〔stack 改義〕＋〔persist〕：身體本來就跟行程一起沒，要顧的只剩 persist；而 9p-proc 第 7 段說預設的 persist 就開在 `/tmp`。題目從整棵搬，變成 persist 放哪、放 tmpfs 的要不要同步。11-25 量到的數字（省的是每次 fsync 約 10 ms，不是 CPU）照樣有效 | 沒人在做。條目自己已寫「要等相對路徑／proc 介面定」 |
| `agent-fsm-py-folder`（315）暫停 | agent 定義夾裡八支 `.py` 收進子夾、重新規劃架構 | 前半已被 11-24 三分做掉：格程式搬到 `proto8/py/aos/apps/agent_fsm/`（九支共 2,312 行），`proto8/templates/agents/agent-fsm/` 裡已經沒有 `.py`。後半「重新規劃架構」正是新模型要對 agent-fsm 做的事：〔入口〕站進自己的身體、〔純文字〕、〔兩條路〕收 socket | 沒人在做（使用者：「明天再說，甚至可能延後。反正程式能跑就別動他」）。單獨重構會白做，該併進新模型對 agent-fsm 的改造（報告 03） |
| `waiting-1121`（340）等使用者，局部 | 11-21 念過、還沒答的八題 | 第 4 題（kernel 攔截 daemon 存取）：今天 kernel 只攔得到走信的起停掛拆，直接寫 `ctl.json` 的 pause／resume 攔不到（`proto8/thinking/2026-11/21/kernel-攔截daemon存取-1121/README.md:7`、`9`）。〔收到〕〔兩條路〕讓更多動作變成直接寫 ctl 或連 socket，那張 20 列的逐項表要重對。第 5 題（驗寄件人，暫定 1D、2C、3C、4A）只蓋到信（看信夾擁有者）；socket 那條路要另外認人。其餘六題不相干 | 沒人在做（使用者 11-25：「我現在沒空」）。這兩題等新模型定了重問 |
| `aos-kres`（286）等使用者，局部 | kernel 的資源基底與排程介面。剩兩個尾巴：條目寫的「寄信問 kernel、kernel 框架自動回」要不要做；宣告規則的那份 json 叫什麼、放哪 | 〔兩條路〕裡的「問它的 daemon 或某個 kernel 信箱在哪」本身就是一種「問 kernel」。〔kernel〕有自己的目錄之後，問法還多一種：讀它目錄裡的檔。兩個尾巴該跟新模型一起定，不要先做一個只走信的（報告 14 結論 6 把這兩樣算成被新模型取代：多半變成讀 kernel 目錄裡的一個檔） | 沒人在做 |
| `mine-arena-dir-1123`（430）open，排隊中，局部 | mine_arena 六題的方向已定。排著要做：① 最小定義範本、③ 資源回報（有效限制、peak、OOM 看得到）、② scope 收乾淨、⑤ 知識庫 | ③：今天的出口是 `aos-agent ctl state` 的 resources 那一類，〔status〕做了之後出口是 status 的行。量的那半（讀 cgroup）不白做，印的那半要搬一次。①：範本若讓工具包走沙箱，沙箱裡走不進〔入口〕（報告 12 結論 8），驗過的範本要在新入口下再驗一次 | 還沒開工。開工時把「量」跟「印」分開寫 |
| `eca-rest`（67）open，局部 | eca 剩的雜項：codex 身、a2a 實測、回合中收信 | 只有三小項碰到：live_mail 回合中併信、codex 身回合中收信的研究、fsm「先更新交接檔再壓」（條目寫「要先決定思考中途收不收一般信」）。〔兩條路〕讓回合中有訊息到變成常態，這三項該併成新模型的一題（第 6 節觀察 1）。其餘不相干 | 沒人在做（使用者 11-18：「先留著」） |

**`idle-polling` 分刀**（刀序與估計出自 `proto8/thinking/2026-11/24/閒置輪詢C++重寫-1124/04-分刀與順序.md:21`～`29`；核數都是規劃的估計）

| 刀 | 做什麼 | 狀態 | 新模型來了之後 |
|---|---|---|---|
| 0 | `install.py` 補 `.pyc` | 已交 5e79d6f0b | 不白做。什麼實作起 Python 都省 |
| 1 | aos-loop、aos-daemon 認 `gate` 鍵 | 已交 c2eb8f3fe | 不白做。落檔的普通實作還在跑就用得到 |
| 2 | `aos-idle`（C++ 閘）＋ on_clock 摘要檔 | core 施工中（工作樹 `proto8/cpp/aos-idle/` 未交） | 不白做。它認的是今天 stack 的檔名（`queue/new`、`queue/cur`、`cooldown.json`、`goal.json`、`history.jsonl`、`state.json`、`stage.txt`…，`proto8/cpp/aos-idle/src/idle/idle.cpp`），〔stack 改義〕分出 persist 時要照表改一次路徑。socket 不影響它：aos-loop 的身體是每圈一支的短命行程，socket 送進來的訊息還是得先落檔（報告 01 結論 9），閘照樣看得到 |
| 3 | 範本掛 gate、context_wrap 改 60 秒 | 等 core 回 PROGRESS | 不白做。數字這刀才掉（估 4.3 核降到 0.3～0.45 核） |
| 4 | kernel 掛閘 | 沒排 | 小（估省 0.24 核）。〔kernel〕若改成聽 socket 的常駐 proc 就用不到。可緩 |
| 5 | wait 格：等腦回信時不起 Python | 沒排 | **最可能白做**（推論）。2～3 天，規劃自己標風險最高（要先把六百多行的 `wait.py` 逐條列，同檔 `:100`～`110`）。它省的是每拍起一支 Python 去問回信到了沒；回信改成到了才叫醒，這套判斷大半用不到 |
| 6 | 量過再決定的幾項，含「閘改行程內＋inotify」 | 沒排 | inotify 那項動的是引擎的 `nap`（定時醒改成等事件，`03-優化方向.md:61`～`76`），跟「活著走 unix socket」是同一處。規劃自己寫「到時再出一份設計給使用者看」（`04-分刀與順序.md:121`）。併進新模型，不單獨設計 |

細節歸報告 11（`11-閒置成本、時鐘與等待.md`）。

### 2.3 新模型自己的條目與前置（4 條）

五選一的話這四條都算「前置」；分開列是因為它們就是新模型的本體、前情與上位。

| 條目 | 它是什麼 | 跟新模型的關係 | 現況 |
|---|---|---|---|
| `proc-interface-spec`（529）等使用者 | 把 proc 介面寫成規格 | 新模型自己的條目。what 已寫進 11-25 的摘要 | 使用者主導、還在談。當總條目留著 |
| `relative-paths-1124`（507）暫停 | aos 盡量用相對路徑；使用者 11-25 選了具名錨點 | **前置**。〔入口〕的 `/proc/<PID>` 每次起都不同，所以會留下來的檔（〔persist〕）裡不能寫它，只能寫相對某個錨點的路徑——「希望」變成「必須」（報告 06 結論 4 量到這台 PID 約七、八小時繞一圈）。打雜工 sol-4 的盤點（`wf/ws/eca-aos/temp/eca-aos-sol-4/report-relpaths.md`：父 daemon 狀態、鐘與事件 hook 的內容、eca 抄下的 env 與 MCP 設定、部分 exec 的 argv 與 envs 還存絕對路徑；而且沒有單一基準，表、hook、筆記、CLI 小格、回信各用各的）就是遷移清單 | 暫停、等新模型。錨點那句要重讀（第 9 節第 3 題） |
| `plan9-ns-1124`（518）暫停 | 11-24 聊 FUSE／9P 與每隻 agent 各自命名空間的紀錄 | **前情**。ctl 檔、proc＝目錄介面、FUSE 當其中一種實作、socket 取代 aos-post，都已被 11-25 接手。只剩一項 11-25 沒談：使用者「或是獨特命名空間這個特性，plan 9的，這可以之後想想。」 | 暫停。可併（第 4 節） |
| `aos-goals-1124`（561）等使用者 | 使用者 11-24 口述的六層目標，留三題 | **上位**。新模型是它第四層（aos proc 界面）的展開。三題的 ①（界面要不要先寫成一頁規格）已有答案：11-25「先不寫」，但形狀口述了。② 九軸、③ 拿非 LLM 資源實測，不受影響（〔純文字〕明說 `_metainfo` 照舊） | 等使用者 |

### 2.4 會變簡單（5 條＋條文待定 1 條）

| 條目 | 它是什麼 | 新模型的哪一條讓它變簡單 | 現況 |
|---|---|---|---|
| `aos-htop-1119`（232）暫停 | aos 版 htop 的發想：kernel 替每個 proc 記什麼、怎麼分 | 發想自己列的兩個缺口，新模型直接給：沒有一處把各家的紀錄收成一個 proc 一筆（`proto8/thinking/2026-11/19/aos-htop-1119/README.md:7`）＝〔status〕；eca-claude 的花費完全不經過 llm kernel（同檔 16 行）＝〔token〕自己報在自己目錄（今天 eca 兩邊都沒帳，報告 14 結論 5）。「欄位不能寫死」（同檔 12 行）也合一行一個「名稱: 值」 | 暫停。新模型做了，它只剩一支讀目錄的小工具 |
| `overview-page`（48）open | 前端（全景頁）大修，盤點 14 項 | 盤點第 9 項卡在「前端是否只准走官方指令」、「還是可以直接讀 stack 的檔」（`proto8/thinking/2026-11/21/frontend-備妥-1121.md:73`，盤點的人寫的）：目錄本身就是官方介面，讀 `procs/<名>/status` 就好。第 3 項「起前端不用自設 `AOS_DAEMON`」（同檔 67 行）＝〔入口〕一個 `AOS_ROOT` 走到全部 | 沒人在做（使用者 11-25：「前端大修之後再說」）。現在開工的話，取資料那層會做兩次 |
| `arena-feedback-1124`（485）open，局部 | mine_arena 的七條使用意見。剩 ① 權限、③ 資源鎖往 kernel 想（五題等使用者）、④ fsm 看圖 | ③：〔入口〕讓「持有者死了」不用問人（那條路當場斷）；〔kernel〕有目錄後，誰在用、誰在等是它目錄裡的檔；發想第 4 題推薦的「位址用環境變數往下傳」變成 `$AOS_ROOT/procs/<名>`；第 3 題（同步等，還是輪到再叫醒）就是〔兩條路〕。①（工具層的路徑前綴）、④（看圖）不相干 | ④ 排隊歸 core，不白做。③ 的五題等送訊息那塊定了再答比較省 |
| `aos-init-kernel`（243）等使用者 | 初始 kernel＝最小核心＋llm 件＋權限件，另有一串可選件（待定） | 〔kernel〕＝普通 aos proc，所以可選件「怎麼裝」就是在 `procs/` 底下多掛一隻。起手範本已經這樣放（llm kernel 掛在根上一列 `llm/`、權限站 `perm/`）。但 11-20 第 6 題定過鐘、清道夫「算核心」，〔橋〕沒說 daemon 自帶不帶（第 6 節觀察 3） | 可選件清單沒人在做 |
| `eca-main-obs-1124`（441）open | eca_main 回報的六點。條目寫「剩 core 那三件要查做了沒」 | 三件 11-24 已交（506cfe678、6ca662af3、db97bc983；筆記 393 行）。新模型下各有更短的路：遞迴列出＝沿 `procs/` 走；表外殘留的 stack（報告 13 結論 2 數到活樹上有 34 個）＝身體跟行程一起沒，只剩 persist 要列；llm kernel 每拍寫的 `slots.json`，是〔token〕那條（kernel 發出去多少記在 kernel 自己的目錄）的現成例子 | 只剩回 eca_main 一封 |
| 條文待定【kernel】kernel 公告（`proto8/docs/NORMS/08-待定/01-待定之一.md:10`） | 公告欄在哪、格式、看到的人要做什麼、「逾時不候」之後怎麼辦；10-15 起擱著 | 〔kernel〕有自己的目錄：公告欄就是那個目錄裡一個只有它能寫的檔（N-14 本來就把公告算成「只有一人能寫的窗」），格式可以跟〔status〕同一種。四問剩後兩問 | 擱置 |

### 2.5 不相干（24 條＋條文待定 4 條）

前面八條是正在做、排著做或剛做完的。

| 條目 | 它是什麼 | 為什麼不相干（有的話，順帶一提） |
|---|---|---|
| `compact-improve`（302）open，**施工中** | compact 改進。剩第 3 刀 `aos-agent history clear-tools`，派了 core，排在 idle-polling 第 3 刀後 | 動的是 history（agent 自己的東西，新模型歸〔persist〕），不碰 ctl、status、送信。不會白做 |
| `eca-bg-mail-1124`（541）open，**施工中** | 開著 Claude Code 背景 Bash 時，新信叫不醒 eca | 這是訊息的最後一哩（怎麼進到 Claude Code 的對話），前面走檔案還是 socket 都一樣要修。`-p` 那半 11-25 已交（6f8fd99a6；筆記 526、541 行），剩開著畫面那半與過期通知。不會白做。它對新模型的提醒見第 6 節觀察 1 |
| `narr-amber-fb-1124`（552）open | listen 三件已修，剩真 session 驗一次 | 修的是 aos-mcp 同時處理呼叫、listen 認信。新模型沒動這層 |
| `ops-feedback-1124`（463）open | guanyu/ops 的七條意見，全部採用。剩知識庫補字、④ 狀態機收尾提醒（排隊）、冷卻階梯 | 都在 agent 內部。① 新加的 `ctl retry`、③ say 帶來源，是第 5 節的材料 |
| `eca-tool-mcp-idea`（474）open | eca 自產的工具要不要另起一個 MCP；答案是不另起，做 `self_tools` 用幾次就拿掉的選項 | 工具層。看起來已做完（第 8 節） |
| `pages-trial-1116`（132）open | GitHub Pages 正式上線，今天 16:55 push | 首頁沒有 stack、daemon 這些字；提到 `AOS_STACK`、`state.json` 的只有三個子頁共六行（`docs/zh/get-started.html`、`docs/zh/manual/troubleshooting.html`、`docs/zh/tutorials/first-tree.html`）。推上去不會把舊模型講死；新模型做了這三頁要跟 |
| `org-template-1123`（418）open | org 範本與 templates 三分 | 三分已切完（第 8 節）。順帶：那次切換連搬 stack，改了 48 個檔，另外 64 處加外部 51 處路徑，再對 37 列 161 個路徑驗一遍（筆記 451、459 行），正是 `relative-paths-1124` 要解的痛 |
| `findings-1123`（406）open | 11-23 查出的 aos 問題。剩 `reviewer/tools.json` 一行、兩處純文字 | 工具與文件的小尾巴 |
| `aos-compile`（155）等使用者 | 用 Python 寫定義再編譯成定義夾、Python 庫入口與 gdb 把手；等使用者親手試 | 編譯產物是定義夾，新模型沒動定義。`defs.Kernel(body=defs.loop()／defs.daemon())` 跟〔kernel〕對得上。gdb 的 `wait=` 是第 5 節的材料；把手以後要改接新介面，寫法不用變 |
| `aos-hook-iface`（255）open | hook 點的介面。剩條文補字 | 併 `norms-text` 一起等。它的原則是第 5 節的材料 |
| `aos-ns`（205）open | 工具庫的名字空間（`std`、`庫名_` 前綴），編譯時展開 | 只動編譯。注意撞名：這條的「命名空間」不是 Plan 9 的每行程命名空間 |
| `aos-inherit`（218）open | 定義衍生（`defs.load`），只在編譯時 | 只動編譯。使用者 11-20 問過 `defs.load` 能不能指 stack，後來說之後再說；〔stack 改義〕後這題若重提，指的會是 persist |
| `kb-md-leftovers`（327）open | 知識庫換 md 後沒跟上的六處條文 | 知識庫路徑寫法的事。其中 N-69 會被新模型再改一次（proc 目錄裡也放 `_metainfo`），一起改較省 |
| `design-tails-1113`（95）open | 11-13 前的設計尾巴四件 | 兩點順帶：P1「`--envs` 改成指 env 檔」跟 9p-proc「還沒談到的」daemon 加一列怎麼寫是同一處，等它定；index 三題的「同一節點多處 index 聽誰的」在〔同指一處〕之後更常遇到（報告 12） |
| `aos-user-home`（360）等使用者 | aos-user（使用者專區的工具）剩的五件 | 專區是使用者的信箱，不是 proc。只有起法說明裡的 `AOS_DAEMON=…/.stack` 以後要跟〔入口〕改 |
| `workspace-stack-alloc`（81）等使用者 | `_stack`、`.stack` 那串的收尾，剩家機清暫存 | 剩的是刪暫存。這條記的 11-22～11-23 `.stack` 定案（改名、git 忽略、每台一份）被〔stack 改義〕蓋過，是使用者自己改的 |
| `org-1123`（394）open | wf/org 分工的尾巴（規矩卡超過 8 KB、位子定義夾、標〔提案〕的幾條） | 組織與文件。位子的定義夾是定義，不受影響 |
| `company-wsl-1123-verify`（372）open | 公司 WSL 的真模型端點、第二帳號沒驗 | 機器環境 |
| `sol-high-pack`（383）open | 端點包名 sol-high 對不上 | llm kernel 的包名 |
| `eca-lab-1118`（143）open | eca-claude 小試驗教學 13～19 | 教學檔。看起來已做完（第 8 節）。這 19 份教的是親手動 `ctl.json`、複製 stack，新模型做了要整批重寫（報告 13） |
| `wrapup-1115`（36）暫停 | guard 工具接不接線、回答配對交件 | 工具與交件流程 |
| `refactor-tidy-inventory`（13）open | thinking 11-13 起先提取再精簡 | 整理討論紀錄 |
| `arcagi`（110）暫停 | arcagi，條目只寫「等 aos 大修完」 | 內容無關。但它等的「大修完」又被新模型往後推 |
| `arknights-kb`（121）凍結 | 凍結到至少 12-14 | 無關 |
| 條文待定【daemon、kernel、tasks、時鐘】照「資料夾＝程式」重寫（`01-待定之一.md:7`） | 只剩 tasks 的 seq／par／if（N-34）沒實作 | 組合子不在新模型範圍。這條列的「已重寫的」（aos-daemon、aos-loop、llm kernel、信箱、鎖）以後要改口成普通實作 |
| 條文待定【kernel】kernel 評估納入錯誤路徑（同檔 8 行） | 量「出問題之後的行為」有多複雜；量法、寫在哪、拿來做什麼都沒定 | 要寫的話是寫在 `_metainfo`，〔純文字〕說它照舊 |
| 條文待定【kernel】token 額度快見底時留一段只給 `high`（同檔 9 行） | llm kernel 的保底策略，沒有採納紀錄 | llm kernel 內部怎麼排 |
| 條文待定【總則】argv[0] 程式的規矩：錯誤寫 stderr（`02-待定之二.md:3`） | 擱置；結束碼已歸 N-43 | 是給被執行的程式的規矩。順帶：寫 ctl 的人沒有 stderr 可看，ctl 的錯怎麼回不能照這條 |

另有 `01-續-metainfo.md`：已落成 N-68、N-69，只留轉址，不算待定；〔純文字〕那條說 `_metainfo` 照 aos 現有的，指的就是這兩條。

### 2.6 正在做或排著做的：白不白做（速查）

| 條目 | 誰在做、做到哪 | 會白做的 | 不會白做的 |
|---|---|---|---|
| `idle-polling` | core：第 0、1 刀已交已裝，第 2 刀施工中，第 3 刀等 eca-aos 一句 | 第 5 刀；第 6 刀的 inotify 項。第 4 刀看 kernel 以後怎麼收請求，可能用不到 | 第 0～3 刀 |
| `compact-improve` | core：第 3 刀排隊 | 無 | 全部 |
| `eca-bg-mail-1124` | core：原因已查出、`-p` 那半已交 | 過期的新信通知那一小項可能自己消失（推論：活著的訊息直接送到，就不是先通知再去讀） | 有背景任務時送不進畫面的修法 |
| `agent-fsm-py-folder` | 沒人（暫停） | 單獨做「重新規劃架構」會 | 前半已被三分做掉 |
| `mine-arena-dir-1123` | 排隊：kb ⑤、templates＋core ①、core ③、② | ③ 的「印在哪」；① 的範本要在新入口下再驗 | ②⑤、③ 的「怎麼量」 |
| `arena-feedback-1124` ④ | 排隊：core 做 fsm 看圖工具 | 無（動的是問腦訊息的內容，不是怎麼送） | 全部 |
| `ops-feedback-1124` ④ | 排隊：core 做狀態機收尾提醒 | 無 | 全部 |
| `pages-trial-1116` | 今天 16:55 push | 無 | 以後三個子頁六行要跟 |

## 3. 建議協調者先處理的五件

**一、`idle-polling` 做到第 3 刀就先停。** 這是唯一正在施工又會被新模型碰到的線。使用者已經說「照做，閒置輪詢繼續。」（筆記 531 行），前四刀也確實不受影響：只要落檔的普通實作還在跑，閘就省得到，而且數字要第 3 刀才掉。要提醒他的只有後段：第 5 刀最貴、最險，它省的那種等待在新模型下會直接不存在；第 6 刀的 inotify 項跟 socket 動的是引擎同一處。core 第 3 刀前會回 PROGRESS 等一句，正好那時把第 4～6 刀改成等送訊息那塊定了再排。

**二、`subuid-1119` 對上入口，是已交的程式跟新模型的唯一衝突。** 9p-proc 自己寫了「以後要用分帳號做權限時這條會被擋」（`9p-proc-1125.md:56`，當時沒測）。要讓使用者知道的是：分帳號不是以後的事，11-19 就做了一半；而且他兩次把擋得住的那道牆指到 Linux 帳號：一次是 11-20 選「明寫」的那句（起手範本裡的「權限件是給守規矩的人用的規矩，不是牆；牆是換 Linux 帳號」，`proto8/templates/starts/start-api/README.md:41`），一次是 11-21 的「真的要硬防，那就要多依賴linux的權限體系」（`proto8/thinking/2026-11/21/kernel-攔截daemon存取-1121/README.md:42`）。選了 `/proc/<PID>/cwd` 當入口，就要同時決定分帳號的 proc 怎麼進樹。沙箱（bwrap）是同一類問題。細節歸報告 15（它的結論 2、3：能靠 `/proc` 入口互通，跟彼此之間有牆，是同一件事的正反面）。

**三、條文先不要動，把大修時要一起改的記成清單。** 新模型改掉三條已定條文的字面：N-14 的窗是 JSON、N-13 的外顯檔落在 `$AOS_STACK`、N-17 的其他人不碰 pid。N-17 的出處是使用者 11-05「所有牽涉到linux原生行程的機制，都以daemon爲界面」；新模型精神上接得住（別人只拿根的 PID，其餘走 daemon 顧的名字），字面要改。這些都是使用者自己改的方向，不是誰做錯。`kb-md-leftovers` 的 N-69、`aos-hook-iface` 要補的字、17 題新待裁，都併進同一次大修。逐條對照歸報告 16：它列了六處真衝突，其中 A（別人不碰 pid）、E（窗是 JSON）就是這裡的 N-17、N-14；它也引了使用者 11-17 的通則「新的覆蓋舊的」，照那條 11-25 的話預設就算數。

**四、今天早上的錨點那句要重讀，四條講同一件事的條目併成一條。** 使用者 11-25 早上：「我希望是用具名錨點，一個最重要最根本的錨點就是離自己最近的頭上的那個daemon的stack。沒有的話那你就是root daemon，你是特殊存在。」同一天稍後，stack 改成指活著的 proc 的身體（9p-proc 第 6 段）。這句裡的 stack 是活的目錄、還是留在硬碟的那份，決定了會留下來的檔裡路徑怎麼寫。這是他同一天兩句話之間的縫，別人補不了（第 9 節第 3 題）。順手把 `relative-paths-1124`、`fs-tmpfs-1124`、`plan9-ns-1124` 併進 `proc-interface-spec`，免得四條各自漂。

**五、排著要開工的三件，開工前先對一下新模型。** 三件都還沒動工，現在說最便宜：
- `mine-arena-dir-1123` 的 ③（資源回報）：請 core 把「量」跟「印」分開，印的那半等 status 的行表。
- `arena-feedback-1124` ③ 的資源鎖五題與 `aos-kres` 的兩個尾巴：選項裡都寫著信怎麼寄、位址怎麼給、誰等誰，新模型定了選項會變，建議跟使用者說這幾題改成之後重問。
- agent-fsm 的重整（`agent-fsm-py-folder` 的後半）：併進新模型對 agent-fsm 身體的改造，不單獨排。

通則（推論）：在 ctl 的字表與 status 的行表定下來之前，新派的工作凡是要多印一項狀態、或多一個 ctl 動作的，請對方集中寫在一處，之後好搬。

## 4. 新模型一旦做了，可以拿掉或合併的

**現在就可以併的**（都已經寫著等 proc 介面）：

| 條目 | 併到哪 | 留下什麼 |
|---|---|---|
| `plan9-ns-1124` | `proc-interface-spec` | 留一句：每隻 agent 各自命名空間這項，11-25 沒談 |
| `relative-paths-1124` | `proc-interface-spec` | 錨點規則變成規格的一節；sol-4 的盤點當遷移清單 |
| `fs-tmpfs-1124` | `proc-interface-spec` | 變成一節：身體放哪、persist 放哪、放 tmpfs 的要不要同步；量測報告的連結留著 |
| `aos-goals-1124` 的第 ① 題 | 劃掉、指到 `proc-interface-spec` | ②③ 留著 |

**新模型做了之後可以拿掉或縮小的**：

| 條目 | 做了哪一塊之後 | 變成什麼 |
|---|---|---|
| `aos-htop-1119` | status 與 token 各自報 | 拿掉，或縮成一件小事：寫一支讀 `procs/*/status` 的小工具 |
| `overview-page` 盤點第 3、9 項 | 入口與 status | 兩項劃掉；大修剩 12 項 |
| `agent-fsm-py-folder` | agent-fsm 改成新介面的身體 | 併進那件，拿掉 |
| `waiting-1121` 第 4 題 | ctl 與送訊息定了 | 舊的 20 列逐項表作廢，在新模型底下重問 kernel 還攔得到什麼 |
| `waiting-1121` 第 5 題、`subuid-1119` 的後續刀 | 入口怎麼給分帳號的 proc 定了 | 重排；或照第 9 節第 1 題的答案凍結 |
| `aos-kres` 的兩個尾巴 | 怎麼問 daemon 或 kernel 定了 | 併成新模型的一節 |
| `arena-feedback-1124` ③ 的五題 | 送訊息兩條路定了 | 第 3 題（等的方式）併進兩條路；第 4 題只剩放哪一台，位址怎麼給不用問了 |
| `idle-polling` 第 5、6 刀 | socket 做了 | 第 5 刀不做；第 6 刀的 inotify 項併進 socket |
| 條文待定「kernel 公告」 | kernel 的目錄定了 | 前兩問可以落條文 |
| `eca-main-obs-1124` | 不用等新模型 | 回完 eca_main 就能刪 |

## 5. 進度檔與條文裡已經有答案的（省得重談）

對著 9p-proc「還沒談到的」（`9p-proc-1125.md:130`～`135`）逐題列。字表、行表的具體寫法歸報告 18，信與 socket 的細節歸報告 05、20；這裡只指出哪裡已經定過。

| 還沒談到的 | 已經有的答案（出處） | 還剩什麼沒答 |
|---|---|---|
| ctl 收哪些字 | 使用者 11-03：「所以相關指令就是start/stop/add/rm/pause/resume」「所以add/rm是動作，相關的狀態就是started/stopped」「只有指令叫醒。然後loop就是原生支援暫停和休眠的」（N-54，`proto8/docs/NORMS/04-基礎設施-loop與daemon/03-N-54/01-手把與認的key.md:3`）。今天 `aos-agent ctl` 的字：add rm set-def start stop sleep wake pause resume retry ls state status where who（`proto8/py/aos/apps/agent/ctl/__init__.py:8`～`11`）。新動作怎麼加：`ops-feedback-1124` ① 的 retry，使用者 11-24「做一個立刻重試的動作，但不要做成工具，並盡可能納入現有指令，成為子指令。」（筆記 376 行） | 哪些是每個 aos proc 都要認的、哪些是各家自己加的 |
| 「收到」與「做完」分開 | `aos-compile`（併進來的 aos-gdb-1120）：使用者 11-20 問 `a.stop()` 是不是阻塞，選了暫停加 `wait=`，不等的時候「回一個可以查的物件。用is_done()」（`proto8/thinking/2026-11/20/aos-gdb-問答-1120.md:87`）。跟〔收到〕是同一個切法，Python 庫那邊已經做了 | 無 |
| ctl 的錯怎麼回 | 錯誤一行的格式早定了：`程式名: error: 代號 原因`（N-43）。不認得的字：C-48 是「只處理認得的 key」（`proto8/docs/CONCEPTS/01-設計理念/01-C-01～C-48.md:11`）；N-54 對放錯地方的 key 也是忽略、不提醒（使用者 11-03「當沒看到」） | 舊規矩是不認得就當沒看到；9P 的寫有回應，不認得的字回錯才自然。兩邊有縫，要問（歸報告 18） |
| status 有哪些行 | 今天 `aos-agent ctl state` 的總覽就是每類一行，十一類：who state tools llm system hooks history mailbox subagents resources time，而且 `status` 已經是它的別名（`proto8/py/aos/apps/agent/ctl/state.py:16`～`33`）。`mine-arena-dir-1123` ③ 定了資源那幾項要看得到（有效限制、peak、OOM）。`aos-htop-1119`：欄位不寫死、照各家宣告。kernel 的帳今天的樣子：llm kernel 的 `slots.json` 與 `aos-llm ls` 的尾行（506cfe678） | 哪幾行是必備的 |
| socket 上講什麼、信的格式 | 信的格式早定了（N-16，`proto8/docs/NORMS/05-基礎設施-窗/05-N-16/01-信箱與信封.md`）：`letter.json` 必有 sender、sent_at、body，選填 reply_to、in_reply_to；信箱是 tmp／new／cur。使用者 11-05「信件是IPC手段，然後我們的"非同步呼叫aos函數"又是基於這個手段的。」、11-06「所以不要去與aos-post耦合太深。」（同檔 6 行）——所以 socket 只是換一種送法，上面那層可以原樣搬（推論）。帶來源：`ops-feedback-1124` ③ say 帶 `[say from 名字]`（7ebe15b7e）。回信怎麼配：`narr-amber-fb-1124` 的 listen 認同一個 in_reply_to（bc8938198） | socket 上用不用同一個信封；9P 還是別的 |
| 信箱在哪、誰定 | N-16 同檔 4 行：信箱「位置由擁有者定、不強制在 `$AOS_STACK`」，別人靠變數或明給找到。跟〔persist 自己說〕是同一個意思。現成的例子：eca 的筆記放工作區（`notes_path`）；ops 的做法是派遣工的累積放 repo 不放 stack（`ops-feedback-1124` 分享的做法） | 無 |
| 問 daemon 或 kernel「東西在哪」 | `waiting-1121` 第 4 題，使用者 11-21：「一個很值得走的道路是"寄一封信給kernel，kernel返回他想要存取的daemon的東西的位置"，這可能是kernel幫他取來，放在他能存取的地方，也可能是kernel暫時讓他具有權限，或是兩者皆有」（`kernel-攔截daemon存取-1121/README.md:46`）。今天就有一個：查詢信回的是路徑（同檔結論 4）。`aos-kres` 第 5 題：「先不定。但是可以先做寄信問kernel，然後我們的kernel框架也可以弄一個自動回這種信的東西。算是基礎協議吧。」（`proto8/thinking/2026-11/20/aos-kres-1120/08-使用者已答.md:67`） | 問法是寄信、讀檔還是連 socket（報告 02 結論 7：今天寄信的人自己讀表，不經 daemon） |
| 睡著的誰叫醒 | 使用者 11-03「只有指令叫醒。」（N-54 同上）；sleep＝行程收掉、列留著，wake 或 daemon 開門才醒（`02-N-28/06-收工-收子項-log.md:6`）。所以〔叫醒〕這個可選設定，預設照舊就是不叫（推論） | 設定叫什麼、放哪 |
| 寄件人怎麼認 | 三處定過同一個態度：`aos-htop-1119` 第 3 題選「照舊自報，風險自擔」；`mine-arena-dir-1123` 隔離等級「甲，先只防失誤」，⑥ 寄件人驗證先不做；`waiting-1121` 第 5 題暫定每個收信方都拿得到信夾擁有者這個事實，只有 kernel 會擋（他選的 2C，`proto8/thinking/2026-11/21/驗寄件人-規劃-1121/09-使用者已答.md`） | socket 那條路上，對方是誰拿什麼當事實（第 8 節第 3 點） |
| 等回信等多久 | 使用者 11-05「寄信不回，等同於呼叫失敗」；11-06「由寄信者自己設定。然後30秒？這不該是固定值，同樣該由寄信者自己設定。判官會輔助。」（N-17，`06-N-17/01-誰判死活與例外.md:4`～`5`） | 無 |
| PID 被別人拿去用 | 使用者 11-09：「pid被別的程式重用...這是使用者自己要承擔的風險，但我們確實也會做一些護欄，就是你說的這些。」（N-17 同檔 6 行）。護欄今天有：pid＋啟動時間＋開機 id 三樣對過才送訊號 | 入口用 PID 之後護欄放哪（報告 06 結論 4、5） |
| socket 那條不落檔、丟了算不算 | `plan9-ns-1124`，使用者 11-24：「持久性/單點故障沒差，我們可以定期保存。」（9p-proc 已引） | 無 |
| 怎麼宣告自己支援哪些介面 | `aos-hook-iface`，使用者 11-21：「剛剛那個hook我覺得OK，畢竟hook體系的唯一約定，就是要在interfaces.json中宣告，有宣告就能用，至於怎麽實作的，就是各家自己的事情。」跟〔普通實作〕是同一個原則。另一面：`aos-kres` 第 8 題他說「另外一個json吧。interfaces和hook都是另外的用途。」——新用途傾向另開一個檔，不往 `interfaces.json` 塞 | `settings` 是新檔還是 `interfaces.json` 的延伸、用什麼格式（報告 12） |
| daemon 自己的 ctl | 今天是兩個手把加一個信箱：使用者 10-28「一個控制loop面向和自身屬性，一個控制管轄的aos函數」（N-54 同上）。管轄那個認的字：procs、procs_added、procs_removed、procs_stopped、procs_started、procs_slept、procs_woken | 新模型下併成一個 ctl 還是照舊兩個；加一列那包設定怎麼用文字帶（報告 02 結論 6） |
| 規格什麼時候寫、誰寫 | 使用者 11-25「先不寫」；條文那邊 11-17「條文這東西以後我會大修，現在不用這麼急」。誰動筆已有分工（`org-1123`：kb 管知識庫，條文誰動筆由 eca-aos 派） | 時機，等使用者說 |

## 6. 新模型還缺哪些決定（推論）

以下五條都是我看完 47 條之後的推論，沒有使用者的話。

1. **「活著」「收到」指的是哪一層。** 今天一列 aos proc 不是一個行程：表上的 PID 有四成是外殼（報告 02 結論 2）；eca 是 loop 加外面的 Claude Code，畫面那棵不是 daemon 的子孫、loop 停了它還活著（報告 04 結論 1；筆記 469 行）。`eca-bg-mail-1124` 是活生生的例子：行程活著、信卻兩小時沒進到腦。`eca-rest` 擱著的「思考中途收不收一般信」也是同一題。所以「寫回來＝收到」要講明是常駐那支收下、還是腦讀到；「proc 活著」要講明看的是哪一個 PID。
2. **最小必備是哪幾樣，落檔的實作要不要也聽 socket。** 新模型說活著走 unix socket，但今天沒有任何 aos proc 在聽（報告 05 結論 2、3）。如果 socket 是必備，aos-loop 要先長出來才算 aos proc；如果是選配，寄的人就得先知道對方有沒有，活著但沒開 socket 的 proc 要有第三條路。9p-proc 的邊緣提過「標準規範可以很小」，但沒列出必備與選配。
3. **daemon 這座橋自帶什麼。** `aos-init-kernel` 11-20 定過：初始 kernel 的核心含鐘、清道夫（使用者選「算核心」；身分、信箱、daemon 是當時頂層的假設，他沒反對也沒明說）。新模型說 daemon 不管帳、kernel 是普通 aos proc，但沒說鐘、清道夫、回答「信箱在哪」、叫不叫醒，各歸 daemon 還是歸底下的一隻 proc。
4. **分帳號、沙箱與入口的關係。** 見第 2.1 節。要不要保留「牆是換 Linux 帳號」這條路；保留的話，入口除了 `/proc/<PID>/cwd` 還要一條不靠它的。
5. **「stack」這個詞的舊話怎麼讀，連同 `AOS_STACK`。** 早上的錨點那句（第 3 節第四件）是一例；`aos-inherit` 裡 `defs.load` 能不能指 stack 那一問、知識庫第 1 條規則的 touch another agent's stack（`proto8/knowledge/aos/_description.md:20`）、`findings-1123` 修過的寫檔工具擋自己的 stack，都是。報告 06 結論 6 查到 `AOS_STACK` 今天身兼三職。新模型要給一張舊話對新詞的對照，不然每條舊定案都要個別重讀。

另外三個小的，各一句：`settings` 用純文字還是 json（〔純文字〕只點名 ctl、status、`_metainfo`；報告 12 結論 5 量到純文字檔進不了現有的 json 工具）；不認得的 ctl 字是忽略還是回錯（第 5 節）；kernel 今天只攔得到走信的請求，動作改成直接寫 ctl 之後，攔截面要搬到哪（`waiting-1121` 第 4 題）。

## 7. 實測：換成子帳號的 proc 走不走得進入口

9p-proc 那一行標「沒測」。報告 02 用真的 daemon 起的 `sub:N` 子項測過子往根走那一格（它的結論 9）。我這裡是純 Python 照 daemon 的做法模擬（子行程自己開 user namespace，父跑 `newuidmap`／`newgidmap`，子換身分後 exec），多測了三格：子帳號之間、daemon 往下看、socket 上看到的對方身分。公司 WSL2，核心 6.6.114.1，`ptrace_scope` 1，`/etc/subuid` 是 `guanyu:100000:65536`。

| 誰（帳號） | 走哪條路 | 結果 |
|---|---|---|
| daemon（1000） | `/proc/<a>/cwd`，a 是 100004 | 讀得到 |
| daemon（1000） | `/proc/<daemon>/cwd/procs/a/status` | 讀得到 |
| daemon（1000） | 連 `/proc/<daemon>/cwd/procs/a/sock` | 連得上、有回 |
| 同帳號的 proc（1000，對照組） | `/proc/<daemon>/cwd/…`、`/proc/<b>/cwd/…` | 全部讀得到 |
| a（100004） | `readlink /proc/<daemon>/cwd` | `Permission denied` |
| a（100004） | `/proc/<daemon>/cwd/status`、`/proc/<daemon>/cwd/procs/b/status` | `Permission denied` |
| a（100004） | `/proc/<b>/cwd/status`，b 是 100005 | `Permission denied` |
| a（100004） | daemon 與 b 的夾的**真實路徑** | 讀得到；socket 連得上（測試夾開成誰都進得去；真的 daemon 把小格設成 0700＋ACL，會更嚴） |
| b（100005）收到連線時看對方身分（`SO_PEERCRED`） | 對方是 1000 或 100004 | pid 是對的；**uid、gid 一律顯示 65534** |

讀法：

- 往下看沒問題（daemon 看得到自己起的子帳號 proc），往上與平行都不通。所以分帳號的 proc 拿到 `AOS_ROOT=/proc/<PID>/cwd` 等於沒拿到。
- 最後一列是新的邊緣：換了子帳號的收件人，從 socket 看外面的人，帳號全是 65534（它的 namespace 裡只對了自己一個號碼）。在這種 proc 裡想靠連線對方的帳號認寄件人，認不出來，只剩 pid 可用。

<details><summary>最小重現（純標準庫，17 行；只碰目前所在的夾）</summary>

```python
import os, subprocess, sys
r1, w1 = os.pipe(); r2, w2 = os.pipe()
pid = os.fork()
if pid == 0:        # 子：自己開 user ns → 等父對好號碼 → 換成 100004 → exec
    os.unshare(os.CLONE_NEWUSER); os.write(w1, b"1"); os.read(r2, 1)
    os.setgroups([]); os.setresgid(100004, 100004, 100004); os.setresuid(100004, 100004, 100004)
    code = ("import os\nfor p in ('/proc/%d/cwd', %r):\n"
            "    try: print('uid', os.getuid(), p, '->', sorted(os.listdir(p)))\n"
            "    except OSError as e: print('uid', os.getuid(), p, '->', e.strerror)\n") % (os.getppid(), os.getcwd())
    os.execv(sys.executable, [sys.executable, "-c", code])
os.read(r1, 1)
subprocess.check_call(["newuidmap", str(pid), "100004", "100004", "1"])
subprocess.check_call(["newgidmap", str(pid), "100004", "100004", "1"])
os.write(w2, b"1"); os.waitpid(pid, 0)
me = "/proc/%d/cwd" % os.getpid()
print("uid", os.getuid(), me, "->", sorted(os.listdir(me)))
```

實際輸出：

```
uid 100004 /proc/2399125/cwd -> Permission denied
uid 100004 /home/guanyu/.aos/scratch/aos-proc-arch-1125/17/mini -> ['mini.py']
uid 1000 /proc/2399125/cwd -> ['mini.py']
```

完整那支（三隻 proc、socket、對照組）在 `~/.aos/scratch/aos-proc-arch-1125/17/subuid_cwd.py`，跑完自己清暫存夾。

</details>

## 8. 邊緣狀況

1. **進度檔自己落後六處**（跟新模型無關；我是對 commit 與筆記推的，沒問當事的位子）：
   - `eca-lab-1118`：條目寫 13、14、17、19 沒檔、要重派；但 19 份都在 repo（fbce69eae），交接檔自己寫「本線已無待辦」（`proto8/thinking/2026-11/18/交接-各線/eca-lab-1118.md:5`）。
   - `eca-tool-mcp-idea`：條目寫 core 兩件排隊中；兩件已交、已裝、知識庫已跟（2a1a259e7、a551bba03、2a9161dd0、46e0f0e1a；筆記 416～420、427 行）。
   - `eca-main-obs-1124`：條目寫 core 三件要查做了沒；三件 11-24 已交（筆記 393 行）。
   - `org-template-1123`：next 還用未來式寫切換；11-24 16:14 已切完（e3edcb02d；筆記 462～464 行）。
   - `agent-fsm-py-folder`：what 還寫「跟設定檔平放」；三分之後格程式已不在定義夾。
   - `eca-bg-mail-1124`：next 寫派 core 查原因；原因已查出，`-p` 那半已交（6f8fd99a6）。
2. **eca 有兩個活的東西。** loop 與 Claude Code 的畫面是兩棵行程，停樹只停 loop，畫面還在回話（筆記 469 行）。`/proc/<PID>` 只能指 loop；loop 死了、那條路斷了，別人會判它死，但畫面那邊還在動同一份對話。細節歸報告 04。
3. **socket 上的「對方是誰」在子帳號的 proc 裡認不出帳號**（第 7 節最後一列）。同帳號時大家的帳號本來就一樣，也只剩 pid 可認。所以「連線認身分」這個好處（`plan9-ns-1124` 聊過）在現有兩種情況下都只有 pid 這一樣可用（推論）。pid 怎麼對回是哪一隻，報告 15 結論 4 測過：往上找祖先對得到 daemon 表上的那一列。
4. **「status」這個字已經有四個主人**：Linux 的 `/proc/<PID>/status`、新模型的 status 檔、`aos-agent ctl status`（state 的別名）、agent-fsm 今天剛加的 `/status` 斜線指令（templates d64aec3c0）。9p-proc 只提了前兩個。
5. **短路徑的 socket 今天就有一種做法，也有它的坑。** 畫面用的 socket 放在 `/run/user/<uid>/` 底下、名字是小格真實路徑的雜湊，為的就是 108 bytes（報告 04 結論 8）。11-24 搬 stack 時撞過：路徑一換，雜湊跟著換，新的 loop 認不得舊畫面（筆記 469、476 行）。身體會換位置的新模型下，凡是拿路徑算名字的東西都有這個坑。
6. **`arcagi` 的解凍條件。** 條目只寫「等 aos 大修完」，當時指的是 11 月上旬那次。新模型又是一次大改，這條會無限期往後。小事，下次整理進度時問一句就好。
7. **順手看到的兩句舊話（不在進度檔；報告 16 結論 2 的 D 也列了這一處）。** 使用者 11-02 晚自己提過「讓daemon底下的stack變成捷徑」，兩條路裡選了記在名單上：「那就記錄在名單上。我是希望盡量不要用捷徑啦。」（`proto8/thinking/2026-11/03/procs/01-使用者原文-11-02-晚起-逐字-依先.md:17`、`21`）新模型的 `procs/<名>` 是連結（他這次說「或許可以是類似symlink」），比較像當時沒選的那條（推論）；FUSE 時不需要連結檔。同一份第 5 行還有一句對撞名的態度：「可是我又擔心和linux的proc撞名...不過好像撞名也沒差。」可以拿來看第 4 點的四個 status。

## 9. 要問使用者的

**第 1 題：換成子帳號（或關進沙箱）的 proc，怎麼進樹？**
- a. 入口就以同帳號為前提；分帳號那條線（`subuid-1119` 後面三刀、看信夾擁有者認寄件人）先凍結，等真的要做隔離再回頭。
- b. 兩邊都留：名字那條路（`procs/<名>`）才是介面，`/proc/<PID>/cwd` 只是本機、同帳號時的捷徑；另外給一條不經 `/proc` 的固定路徑，分帳號的 proc 走那條。
- c. 入口整個不走 `/proc/<PID>`，改走固定路徑。
- **推薦 b。** 他兩次把擋得住的那道牆指到 Linux 帳號（第 3 節第二件），那條路已經做了一半；9p-proc 攤的邊緣本來就要一個固定名字的連結讓外面的殼找根、也說跨機器認的是名字那條路，可以共用同一條。要注意的一點：給分帳號用的那條得指到真實的資料夾，不能再繞回 `/proc`（繞回去照樣進不去）。

**第 2 題：`idle-polling` 做到哪？**
- a. 做到第 3 刀、量完數字就停；第 4～6 刀等「socket 上講什麼」定了再排。
- b. 照原刀序一路做到第 5 刀。
- c. 第 2 刀交了就停，不掛範本。
- **推薦 a。** 前四刀只要落檔的實作還在跑就省得到，數字要第 3 刀才掉；第 5 刀最貴，它省的那種等待在新模型下會不存在。

**第 3 題：早上那句「最根本的錨點就是離自己最近的頭上的那個daemon的stack」，stack 改義之後指哪個？**
- a. daemon 活的目錄（從 `AOS_ROOT` 走名字到的那個）。
- b. daemon 留在硬碟的那份（它的 persist）。
- c. 兩個都是錨點、各有名字：找活的東西用前者，寫進會留下的檔用後者。
- **推薦 c。** 活的路徑每次起都換，寫進 persist 的東西要有不變的基準；找人、下 ctl 又不該繞去硬碟。

**第 4 題：寫 ctl 或 socket「回來＝收到」，收到的是誰？**
- a. 常駐的那支收下就算；腦什麼時候看到，從 status 看（例如多一行：還沒給腦看的訊息幾則、最久等了多久）。
- b. 要等腦真的讀到才回。
- c. 各實作自己定，寫在 settings。
- **推薦 a。** 跟〔收到〕那條（做完沒有另外看 status）同一個切法；11-24 那次是行程活著、信兩小時沒進到腦，該讓 status 看得出來，不是讓寫的人卡著等。

**第 5 題：等他答的幾題舊題，要不要改成新模型定了再問？**（`arena-feedback-1124` ③ 的資源鎖五題、`aos-kres` 的兩個尾巴、`waiting-1121` 的第 4、5 題）
- a. 是：從「等使用者」收起來，改掛「等新模型」。
- b. 照舊題現在答。
- **推薦 a。** 這幾題的選項都寫著信怎麼寄、位址怎麼給、誰等誰，新模型定了選項會變；現在答等於答兩次。

## 10. 沒查到／沒把握的

- 同批的報告我只讀了已交的十二份的結論（01～06、12～16、18），沒對過內文，而且它們交出後還在改（我看的時候 01、02 的檔案大小又變過）。07～11、19、20 與原型沒看到；指到這幾份的地方（例如閒置歸報告 11）是照共同說明的題目一覽寫的。
- 第 8 節第 1 點說看起來已做完的六處，是對 commit 與 eca-aos 筆記推的，沒問 core、kb、templates 或家機的 main。
- 第 7 節是模擬，不是真的 aos-daemon 起的 `sub:N` proc（那一格報告 02 測了）。家機沒驗。FUSE 掛載點跨帳號能不能進（`allow_other`）沒碰，歸報告 09、15。`SO_PEERCRED` 顯示 65534，只測了 namespace 裡只對一個號碼這一種對法。
- 第 9 節第 1 題的 b 只是方向，沒做原型；身體放在 FUSE 或只在記憶體裡的時候，不經 `/proc` 的那條固定路徑要怎麼給，沒想清楚。
- `idle-polling` 的核數全是規劃的估計。已量到的只有第 0、1 刀之後閒置總核數沒降（4.70 到 4.86，進度檔 next）。第 5 刀「最可能白做」是我的推論：前提是腦的回信以後會主動叫醒等的人，這點新模型還沒定。
- 進度檔每條的 see 連結沒有全跟。跟了的：idle-polling 規劃夾、subuid-1119、aos-kres 已答、aos-init-kernel 已答、aos-htop 的 README、kernel 攔截 daemon 存取的 README、驗寄件人已答、資源鎖發想、frontend 備妥、eca-lab 交接、sol-4 盤點、bgmail 報告的標題、N-13／N-14／N-16／N-17／N-54／N-69 的相關段。沒跟的：aos-compile 那二十多個連結、aos-hook-iface 那一串、org、pages。這幾條我判不相干，是照條目本文與它們動到的層判的。
- 條文裡「待定」以外的兩處沒逐條對：CONCEPTS 附錄 2 第 4 節「概念之間還沒接起來的」那 16 條（只是觀察，不是待定）、CONVENTION 第十一節（都已裁定）。
- 第 2.5 節 `pages-trial-1116` 的「六行」是對 `docs/` 底下的 html 搜 `AOS_STACK`、`.stack`、`ctl.json`、`state.json`、`state_flux` 得到的；用中文講 stack 的句子搜不到，可能有漏。
