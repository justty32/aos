← [入口](README.md)｜涵蓋：找 agent（`--target`／`AOS_AGENT`）、哪個 daemon（`--daemon`／`AOS_DAEMON`）、`using-aos-agent.sh`、chat 怎麼運作｜上一份 [01-子命令](01-子命令.md)｜下一份 [03-種類與契約](03-種類與契約.md)

> 11-04 晚改寫。原本這份是「兩條路：名字查表／當前資料夾的 `.aos/agent.json`」加佔資料夾的衝突表；使用者 11-04「先不做擴充」、稍晚定 `--to`／`AOS_AGENT`、晚上改 `--target`——標記、`occupy`／`release`、「名字還是話」整段作廢。

## 找 agent：只有一條路

使用者 11-04 晚：「--target……這東西沒給的話就是吃AOS_AGENT。」

1. `--target 名字` ＞ `$AOS_AGENT`；都沒有＝`TargetMissing`。
2. 名字查 daemon 表（`aos-daemon-ctl ls --json` 的 `procs`）：`running`／`stopping`／`stopped`／`sleeping` 都算在（跟 `where` 一樣，11-03「除此之外就是不存在於daemon了」）；沒有＝`InstanceMissing`，訊息：rm 過或自己結束下了表、stack 可能還在、要接著用同名再 `add`。
3. 對到那一列：stack＝列上的 `stack`、工作區＝列上的 `ws`（沒有＝daemon 的）。之後只碰這個 stack（[03](03-種類與契約.md)）。

**`add`／`rm` 不走這條**：`add` 的名字是 `--name`（沒給＝資料夾名）、`rm` 是位置參數 `rm 名字`（使用者 11-04 晚）；兩個都**不吃 `AOS_AGENT`**——插拔改的是 daemon 的名單、拔掉還刪 stack 不可逆（11-02 晚不封存），對象要明講，不讓環境變數默默代入（C-56 不藏暗規則）。`ls` 不收對象。

**不再比工作區**：aos-eca 會「表上 `ws` 跟 cwd 相同就算」，aos-agent 不做（第三條暗路；兩隻同工作區就猜不出來）。要「cd 進去就能說」＝在那個殼裡 `export AOS_AGENT=bob`（或 `source using-aos-agent.sh bob`，下節）；使用者 11-04 自己的話：「有點類似命名空間」。

**`--stack S` 例外**（`say`／`listen`／`chat`／`state`）：給了就直接用那個 stack、不查表、不要 daemon——給直接 `aos-exec` 跑的留的（[方向題 2](06-衝突與方向題/02-新題-11-04-晚.md#方向題-2直接-aos-exec-跑的要不要留---stack)）。這時沒有名字：`start`／`stop`／`rm`／`pause`／`resume`／`open` 不收 `--stack`（給了＝`ArgumentsBad`「這隻不在 daemon 上」）。

## 哪個 daemon

`--daemon D` ＞ `$AOS_DAEMON`；都沒有＝`DaemonMissing`（N-63 ②：不猜位置）。值＝那個 daemon 的 stack（窗用預設名：`procs_ctl_mailbox/`、`procs_state.json`）。跟 aos-daemon-ctl 同一套，名字從 `--daemon-stack`／`AOS_DAEMON_STACK` 改過來（使用者 11-04 晚「AOS_DAEMON_STACK實在太醜，還是直接簡化成AOS_DAEMON就好了」；影響範圍在 [05 步 0](05-實作步驟.md#步-0aos_daemon_stack-改名-aos_daemon)）。`AOS_DAEMON` 要絕對路徑（相對路徑 cd 之後對不上，11-02「3」維持只寫清楚）。daemon 沒在跑（`procs_state.json` 的 pid 對不上）：查表類（`ls`／`state`／`where`）照 aos-daemon-ctl 說一句注意、照表印；要動它的（`add`／`rm`／`start`／`stop`）＝`DaemonMissing`；`say` 照寄、提醒重開 daemon（`sleeping`＝「重開 daemon 它會自己醒」，aos_human 現成）。

## `using-aos-agent.sh`：像命名空間

使用者 11-04：「有需要的話就是讓人用source using-aos-agent.sh，然後我們就可以直接say --to bob "..."，有點類似命名空間。」放 `proto8/extras/agent/using-aos-agent.sh`，`source` 用（不是跑；10-15「少用 sh」是說 inst 的 argv 不拼 `sh -c`，給人 source 的殼檔不在內）。只做兩件事：

```sh
source proto8/extras/agent/using-aos-agent.sh bob   # 帶名字＝export AOS_AGENT=bob；不帶＝只定義函數
say 現在幾點 && listen                             # ＝aos-agent say 現在幾點 && aos-agent listen
say --target ann 你好                             # 旗標照常過（函數就是 aos-agent say "$@"）
chat                                              # 一直聊，Ctrl-C 退出
status
```

- 定義的函數只有 **`say`、`listen`、`chat`、`status`**：這四個名字跟系統指令不撞。**不定義** `rm`、`ls`、`open`、`watch`、`start`、`stop`、`state`——會蓋掉或撞到 shell 本來的指令（`rm` 尤其危險），這些照打 `aos-agent rm …`。
- 帶的名字不查表、不報錯（只是 export）；真的不在表上，下一句 `say` 自己報 `InstanceMissing`。
- 不設 `AOS_DAEMON`（那是另一個 hub 的事，各設各的，N-63 一個 hub 一個變數）；也不改 PATH（PATH 照 [dev-env](../../../../../wf/workflows/dev-env.md) 自己擺）。
- bash 與 zsh 都能 source（`$1` 兩邊都有）；函數名撞到使用者自己的別名由他自己承擔。

## chat 怎麼運作

使用者 11-04 晚：「幫我弄個aos-agent chat指令，ctrl-c退出。」它就是 `say`＋`listen` 的迴圈，程式共用同一段（aos_ws.put、aos-listen 的 `wait_latest`／`print_answer`），沒有自己的新機制、不碰 agent 的 stack 以外的東西：

1. 開場：對到那隻（`--target`／`AOS_AGENT`／`--stack`）；stderr 一行「跟 bob 聊（Ctrl-C 退出）」。不印舊對話（要看先 `listen --last N`）。
2. 提示符 `> ` 印在 **stderr**，讀 stdin 一行＝一句（空行跳過；一行就是一句，多行貼上就是多封）。**stdout 只有回答**（跟 say／listen 同一條規矩：提醒、錯都在 stderr），所以 `chat < 問題.txt > 答案.txt` 也能用。
3. 寄（同 `say`：有序信、印不印信件名稱？——**不印**，人聊天不要看到序號；要對帳用 `say`）→ 等（同 `listen` 不帶旗標：等最新那封；沒人在跑＝提醒一次、繼續等）→ 印回答 → 回到 2。
4. **Ctrl-C**：任何時候退 130。正在等答案時按：**那封信已經寄出、agent 照答**（say 只寄信、不叫醒誰、也收不回——信交出去就是它的，P-42／eca 20）；chat 退出前 stderr 一行「那句已寄出，回答之後用 `aos-agent listen` 看」。`listen` 不帶旗標本來就會「信還在就等、不見了就印最新回答」，所以不會漏。Ctrl-D（stdin 結束）＝正常收尾、退 0。
5. 錯跟 `listen` 一樣：`QuestionUnknown`／`AnswerMissing`（信不見了、沒回答、也沒人在跑）印一行後**不退出**、回到提示符——聊天途中 agent 掛了，人看到一行就知道，再按 Ctrl-C 走。
6. 不做：歷史回顧、斜線指令、多行輸入、逾時（11-03 封存的 aos-chat 有一堆，使用者「等之後進展到那塊再拉出來看」——這次只要一行一句）。
