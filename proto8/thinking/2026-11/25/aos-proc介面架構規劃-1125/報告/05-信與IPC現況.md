盤點今天 aos 的信與各種 IPC（信的格式與投遞、queue 與 mailbox、寄件人、daemon／llm kernel／畫面 socket／時鐘／鎖、延遲與成本、對方沒在跑時會怎樣、信箱怎麼查）；結論是「掛了走寄信」那條路的零件今天全有，「活著走 unix socket」那條今天沒有任何 aos proc 在聽，只有幾樣可借的零件。

# 05 信與 IPC 現況（11-25）

← [架構規劃入口](../README.md)

第 05 隻子 agent 寫。只寫現況事實；新設計歸第 20 份（`20-送訊息兩條路的細節.md`），這裡不做。

- 路徑從 repo 根的 `proto8/` 算（例 `cpp/aos-post/src/send/send.cpp:150`）；`wf/…` 開頭的從 repo 根算。活樹＝`~/aos-home/.stack`，只讀。
- 三種話：**使用者說的**引原話；**查到的**附 `檔:行` 或實際輸出；我推的標「推論」。
- 實驗只在 `~/.aos/scratch/aos-proc-arch-1125/05/` 跑，先 unset 全部 `AOS_*`。量的時候機器 load 約 11（8 核），數字看大小、不看個位數。
- 三個詞：**拍**＝aos-loop 跑一次身體（現在每 300 ms）；**身體**＝loop 每拍起的那支程式；**小格**＝stack 裡某個工具或 hook 自己的資料夾。

## 1. 結論

1. 今天 aos proc 之間的交流全部是**落檔**：同一種信箱資料夾（`tmp/ new/ cur/`）用在六個地方，活樹上有 151 個。
2. **沒有任何 aos proc 開 unix socket 等人連。** 唯一用到 unix socket 的，是往開著的 Claude Code 畫面送字；那條 socket 是 Claude Code 自己的（退路是 tmux 的），而且是收件那隻自己的身體去寫，不是寄件人直連。
3. aos 自己的程式裡，常駐的只有 `aos-loop`、`aos-daemon` 兩支 C++。agent 的身體、llm kernel 的身體都是每拍一支新行程。「活著走 socket」第一個要定的就是誰來聽。
4. 投信本身便宜（`aos-post send` 約 10 ms，其中約 8 ms 是 fsync）。慢在起行程與等下一拍：agent 寄一封約 150 ms（幾乎全是起 Python）；queue 的信到開始問腦中位數約 1.3 秒；mailbox 的信要等每分鐘一次的通知；問腦一次來回的機制成本約 1.3 秒。
5. 最大的延遲不是輪詢，是 **agent 只在兩輪之間收信**。活樹上有一隻 21 封排了近三小時。
6. 寄件人是自己報的一條路徑，沒有任何檢查；手建一個資料夾搬進 `new/` 就是一封信（實測）。
7. **信不會叫醒任何人。** 寄給睡著、停掉的 agent，信收得下、一直留著；`aos-agent say` 會告訴寄的人「對方沒在跑」，`mailbox_send` 不會。
8. 查「某隻的信箱在哪」＝讀 daemon 留在硬碟的表，**不需要任何行程活著**。
9. 活樹上已經看得到「位址是路徑」的後果：一個信箱 38 封舊信裡 12 封的回信位址現在指到不存在的地方；9 份畫面 socket 的紀錄裡 4 份已經失效。

## 2. 查到的事實

### 2.1 一封信長什麼樣（aos-post）

信箱＝一個資料夾，像收發室：寄件人在後面桌上把信封好才放進待收籃，收件人拿到自己桌上就算簽收（`cpp/aos-post/README.md:9`、條文 `docs/NORMS/05-基礎設施-窗/05-N-16.md`）。

| 格 | 放什麼 | 誰動它 |
|---|---|---|
| `tmp/` | 寄件人正在寫的、正在撤回或丟掉的 | 寄件人；收的人永遠不看 |
| `new/` | 寫好了、排隊中 | 寄件人 rename 進來，收的人 rename 出去 |
| `cur/` | 被認領、處理中 | 收的人 |
| `archive/` | 選用：處理完要留的 | 收的人（`done --keep`）；aos-post 自己從不讀 |

一封信＝一個資料夾，裡面必有 `letter.json`（`cpp/aos-post/docs/01-用法與元素.md:31-38`、`src/send/send.cpp:175-187`）：

| 欄位 | 內容 | 必有 |
|---|---|---|
| `sender` | 寄件人身分＝一條絕對路徑，自己報的（見 2.4） | 是 |
| `sent_at` | UTC 到毫秒 | 是 |
| `sent_at_cycles` | 寄出時樹時鐘的格數；有 `AOS_CLOCK` 才寫 | 否 |
| `reply_to` | 回信要投的信箱；存成「相對這封信所在信箱的根」的路徑 | 否 |
| `in_reply_to` | 這封是回哪一封（原信的名字） | 否 |
| `body` | 內容，任何 JSON；形狀由收信的程式定 | 是 |

名字（`cpp/aos-util/src/proc.cpp:131-136`、`cpp/aos-post/src/mailbox/mailbox.cpp:115-136`）：

- 無序：`<UTC 奈秒 20 位>.<pid>.<行程啟動的 ticks>`，例 `01795579749994647426.2237844.1509640`。
- 有序（`send --ordered`）：前面多 12 位序號，例 `000000000001.01795579750020636421.2237851.1509643`。序號記在信箱的 `order.json`，取號時握 `order.lock/`（aos-lock）。
- 處理順序：有序的全部在前，各自照名字排。無序的名字開頭是寄出時間，所以照名字排＝照寄出先後。

怎麼保證不重不漏：

| 要保證的 | 怎麼做到 | 出處／實測 |
|---|---|---|
| 收的人不會看到半封 | 先在 `tmp/<名>/` 寫好 `letter.json`，再把整個資料夾 rename 進 `new/`（同一個檔案系統內 rename 是原子的） | `send.cpp:150、188、198` |
| 不撞名 | `mkdir tmp/<名>` 只有一個人建得成；預設名撞到就換一個再試；自己給的名字撞到＝`LetterExists` | `send.cpp:144-160` |
| 一封只被一個人認領 | 認領＝rename `new/<名>` → `cur/<名>`，只有一個人會成功 | `src/take/take.cpp:26-33`；實測 6 支同時搶 300 封：各拿到 199／44／50／7／0／0，合計 300、沒重複、沒漏 |
| 收的人當掉不漏信 | 認領了沒做完的留在 `cur/`，下次先做 `cur/` | `cpp/aos-daemon/src/daemon/mailbox.cpp:43-46`、`py/aos/apps/agent_fsm/idle.py:176`、`py/aos/apps/mailbox/__init__.py:285-287` |
| 有序信不重號 | 先寫 `order.json` 再 rename；死在中間只會缺一個號 | `send.cpp:11-16、79-97` |
| 落到磁碟 | `letter.json` 的暫存檔改名前 fsync；**資料夾不 fsync**；`--ordered` 多一次（`order.json`） | `cpp/aos-util/src/files.cpp:122、261-264` |

不保證的：

- 寄件人死在半路：殘骸留在 `tmp/`，沒有程式會清（`cpp/aos-post/docs/02-錯誤代號等.md:35`）。活樹 151 個信箱的 `tmp/` 現在都是空的。
- 斷電：資料夾的 rename 沒有 fsync，剛投的信可能不見（推論，照 fsync 的範圍）。
- 無序信的先後靠牆上時鐘，時鐘往回跳（WSL 睡醒校時）後寄的可能排前面（`cpp/aos-post/docs/01-用法與元素.md:27`）。
- 壞信（`letter.json` 讀不懂）直接丟，不通知寄件人（`take.cpp:7-9`）。
- 「剛好一次」：agent-fsm 是先接進對話紀錄再收信，中間當掉會重收一次（推論，照 `idle.py:218-228` 的順序，沒實跑）。eca 相反，交給 CLI 那一刻就收信，中途掛掉不重答（`py/aos/apps/eca/main_turn.py:36-41`）。

### 2.2 同一種信箱用在六個地方

活樹現在有 151 個這種資料夾（走一遍 `~/aos-home/.stack` 數的）：

| 用途 | 位置 | 誰寄 | 誰收、多久看一次 | body | 個數 |
|---|---|---|---|---|---|
| queue（直接進對話的話） | `<stack>/queue/` | `aos-agent say`、新信通知、開場白（有序）；時鐘信（無序） | 那隻的身體，每拍；agent-fsm 只在 idle 格收 | `{"role":"user","content", "name"?}` | 53 |
| mailbox（agent 之間的信） | `<stack>/mailbox/` | `aos-mailbox send`、工具 `mailbox_send`、使用者專區的回信 | 腦自己叫 `mailbox_peek`／`mailbox_read` 才看 | 八欄：from、to、status、title、what、outputs、not_done、decide | 36 |
| daemon 的收件口 | `<daemon stack>/procs_requests/` | `aos-agent ctl`、`aos-daemon-ctl`、kernel 站、llm kernel | daemon 每圈（活樹 200 ms） | `procs_added` 等六種名單、`ping`、`procs_state_path` | 10 |
| 回信箱 | `<stack>/daemon_reply/`、`<stack>/think/reply/`、收件口底下的 `reply/` | daemon、llm kernel | 等的人自己輪詢 | `{"applied":…}`、`{"message":…}` 或 `{"error":…}` | 51 |
| llm kernel 的收件口 | `$AOS_LLM_KERNEL/requests/` | `aos-llm send`／`ask` | kernel 每輪（300 ms） | `{"endpoint", "request", "priority"?}` | 1 |
| kernel 站（權限站）的收件口 | `<站的 stack>/requests/`＝`$AOS_KERNEL` | `aos-agent ctl` | 站每輪 | 同 daemon 的 | 0（活樹沒開） |

### 2.3 queue 與 mailbox 的差別、新信通知、信怎麼變成一輪

兩種收件口是使用者分的。11-10（逐字，`thinking/2026-11/10/mailbox/README.md` 原話 1）：「就是說，aos-say/listen目前是接近於直接存取history，這對於agent來說是底層工具，並且我希望這是偏向於獨屬於使用者的。如果要讓agent使用的話，我會希望只讓他能夠對子agent做。至於真正的agent間交流，我打算去看看a2a協議，或是用aos-post實現wf/inbox協議」

| | queue | mailbox |
|---|---|---|
| 是什麼 | 直接進對話的話 | agent 之間的信 |
| 誰該用 | 使用者；父對子 agent | 任何 agent；使用者專區 |
| 進不進對話紀錄 | 身體收到就接成一則 user | 不進；腦自己決定看不看 |
| 會不會變成一輪 | 會 | 不會；靠通知間接變 |
| 順序 | 有序（取號） | 無序（照寄出時間） |
| 收完 | 接進對話紀錄就刪 | 讀完預設刪；專區的信留 `archive/` |
| 怎麼回 | 不回信：回答寫在對方自己的 `history.jsonl`，問的人去讀（`aos-agent listen` 每 0.2 秒看一次） | 另寄一封到 `reply_to`，帶 `in_reply_to` |
| 寄件人怎麼顯示 | 別隻 agent 寄的，本文前加 `[say from 名字]` | body 的 `from` |

**新信通知（new_mail）**

- 使用者 11-11（逐字，`py/tools/agent/mail_notify/_entry:3-4`）：「我們可以透過hook，當有新信來的時候執行一次aos-say "[aos] new_mail: you got a new mail from xxx"這樣。當然，具體這是可調整的，agent自身也可以調整hook，類似免打擾」
- 怎麼產生：範本預設掛一個叫 `mail_notify` 的 hook，每 60 秒一次（`templates/agents/agent-fsm/hookeds.json`）。它跑 `aos-mailbox peek -j`，有還沒通知過的信，就往自己的 queue 寄一則 `[aos] new_mail: 2 new letters from bob, amy. …`。只帶封數與寄件人，不帶內文。通知過的信名記在 `<stack>/hookeds/mail_notify/notified.json`（`mail_notify/_entry:105-127`）。
- 誰看：那隻 agent 自己。通知跟 queue 裡其他的話一樣排隊。
- 這個 hook 不是獨立行程，是身體每拍開頭順手看一下時鐘、到了才跑（`py/aos/agentlib/hook_clock.py:135-191`）。所以**身體沒在起拍的時候不會通知**：
  - 睡著、停掉：不跑。
  - eca 一輪進行中：不跑。一輪＝一支 `aos-eca-turn` 從頭等到尾，只在開頭看一次時鐘（`py/aos/apps/eca/turn.py:24`）。
  - agent-fsm 一輪進行中：照跑（每格開頭都看），但通知進了 queue 要等回到 idle 格才收。

**信怎麼變成一輪：agent-fsm**（`templates/agents/agent-fsm/fsm.json`、`loop.json`）

1. aos-loop 每 300 ms 起一次 `aos-fsm`，跑現在那一格。
2. idle 格（`idle.py:175-254`）：`new/` 有信就全部認領，逐封讀、接成對話紀錄的一則 user、收掉；有收到就進 think 格。
3. think 組請求 → wait 寄給 llm kernel、逐拍看回信 → act 跑工具 → 回 think……直到腦不再叫工具才回 idle。
4. **一輪中間不看 queue。** 使用者 11-04「等答完回 idle 再收」（`py/aos/apps/agent_fsm/wait.py:23`）。唯一例外是 `/compact`（`brain.py:138-141`；這時會把 `new/` 的信全搬進 `cur/` 等著）。

**信怎麼變成一輪：eca**（`main_turn.py:21-41`）

1. aos-loop 每 300 ms 起一次 `aos-eca-turn`。
2. 整批認領 → 交給 CLI（畫面沒開＝`claude -p --resume`；開著＝往 CLI 的收件 socket 投，見 2.5）→ 交出去那一刻就接進對話紀錄、收信。
3. 一輪中間來的 queue 信：畫面開著＝馬上投（使用者 11-13「馬上送，eca他會自己處理」，`py/aos/apps/eca/midturn.py`）；沒開＝留在 `new/` 等下一輪（讓 `claude -p` 邊跑邊收信的 `live_mail` 預設關，`py/aos/agentlib/cli_session.py:37-38`）。

mailbox 的信要變成行動，至少多兩步：通知那一則先花腦一次（看到通知、叫 `mailbox_read`），讀到內文才開始做（推論，照流程，沒另外量）。

### 2.4 寄件人怎麼標、能不能假冒

| 欄位 | 誰填 | 值 | 有沒有人驗 |
|---|---|---|---|
| 信封 `sender` | aos-post | `$AOS_WS` ＞ `$AOS_STACK` ＞ `$AOS_CF` ＞ 現在的資料夾，轉成絕對路徑（`cpp/aos-util/src/proc.cpp:80-102`）。`aos-mailbox` 與 `aos-llm` 改成寄件人的 stack（`apps/mailbox/__init__.py:150-156`、`cpp/aos-llm/src/send/send.cpp:116`） | 沒有 |
| body `from` | `aos-mailbox --from`；工具 `mailbox_send` 填「我在 daemon 表上的名字」（`py/tools/agent/mailbox_send/_entry:43-44`） | 名字 | 沒有 |
| `[say from 名字]`、body `name` | `aos-agent say`：看自己的 `$AOS_STACK` 落在表上哪一隻（`py/aos/apps/agent/sender.py:28-65`） | 名字 | 沒有 |
| `reply_to` | 寄件人 | 路徑 | 只驗那裡是不是可寫的信箱 |

知識庫自己寫明（`knowledge/aos/kernel.md:15、18`）：`identity (the envelope sender, a path the sender reports and nobody checks)`；權限站 `is a rule for procs that keep the rules, not a wall`。

實測（`exp1.sh`）：改一個環境變數就換了身分；完全不用 aos-post、手建資料夾搬進 `new/` 也被當成信收下。

```
$ echo '{"from":"boss","to":"owner","status":"REQUEST",…}' | AOS_STACK=/home/nobody/not-a-real-agent aos-post send owner/mailbox
$ mkdir owner/mailbox/tmp/handmade
$ printf '{"sender":"/home/guanyu/.aos/user","sent_at":"…","body":{"from":"user","status":"DONE",…}}' > owner/mailbox/tmp/handmade/letter.json
$ mv owner/mailbox/tmp/handmade owner/mailbox/new/handmade
$ aos-mailbox -s owner read --all -j        # 腳本只挑四欄印，節錄兩封
{'letter': '01795579750188781698.2237904.1509660', 'sender': '/home/nobody/not-a-real-agent', 'from': 'boss', 'status': 'REQUEST'}
{'letter': 'handmade', 'sender': '/home/guanyu/.aos/user', 'from': 'user', 'status': 'DONE'}
```

寫得到那個資料夾的人就能寄，也讀得到裡面別人的信與回信（`py/tools/aos/kernel_llm/docs/04-已知限制.md:17-19`）。今天全部同一個 Linux 帳號，所以誰都寫得到。

**寄件人這條路徑今天還被拿來當三樣東西的鍵**（都照字面比路徑）：

- llm kernel 每個寄件人的額度帳（`budget.senders`、`used.json`；同檔 19-20 行）。帳本一列的樣子：`"sender": "/home/guanyu/aos-home/.stack/procs/mine_mecha/procs/main"`。
- 提示快取的鍵 `session_key`＝寄件人 stack 路徑的 sha256 前 32 字（`py/tools/aos/kernel_llm/docs/01-用法.md:22`）。
- kernel 站「照寄件人給份額」的 `limits.by_sender`（`py/tools/aos/kernel/README.md:89`）。

**`$AOS_KERNEL`（權限站）轉送那條**（`knowledge/aos/kernel.md`、`py/tools/aos/kernel/forwarding.py:149-190`）

- 預設關，活樹沒開。設了之後，`aos-agent ctl` 的起、停、睡、醒先寄到站的 `requests/`，不直接寄 daemon（`py/aos/daemon_ctl/post.py:28-42`）。
- 站每輪認領、照規則判（白名單、數量上限、hook；或交給 agent 自己逐封點頭，叫 `kernel_gate`）。
- 放行＝**把 body 重寄一封**到下一站。信名沿用原信的名字（有序信去掉前面的序號），用來認「這封寄過了沒」；`reply_to` 照留，所以下一站直接回給原寄件人。
- 重寄時信封是新的，所以下一站看到的 `sender` 是這一站，不是原寄件人。
- 拒絕＝回 `{"applied": false, "error": {"code", "msg"}}`。
- 查表也經過它：`{"procs_state_path": true}` 這封信一路轉到 daemon，daemon 回表檔的絕對路徑。3 秒沒回＝`KernelFailed`，不會退回去自己讀 `$AOS_DAEMON`（`kernel.md:33-34`）。
- 站在忙或睡著時（`kernel_gate` 的站就是 agent 自己，在一輪中或睡著時不跑），底下所有 agent 的讀信、寄信、設鬧鐘都 3 秒後失敗（`kernel.md:42-44`，寫明是刻意留的限制）。
- 繞得過：不設 `AOS_KERNEL`、直接寄 daemon 就行。`only separate Linux accounts are a wall`。

**使用者專區的驗證**（`frontend/aos-user/zone.py:639-726`、`knowledge/aos/user_zone.md:56-58`）

- 專區＝`~/.aos/user/`，是使用者自己的 stack，`mailbox/` 是普通信箱。使用者永遠不是「活著的 proc」，所以對使用者一律走寄信。
- 使用者回信時，專區把原信搬進 `done/<月>/<信名>/`、旁邊留一份 `reply.json`，並在 `log.jsonl` 記一行（帶隨機的 `reply_id`）。
- 收信方跑 `aos-user verify <回信資料夾>`（或工具 `user_verify`）：比「回信的 body 與專區留的那份一字不差」「`sender` 是專區」「log 有那個 `reply_id`」。專區的信讀完預設留在 `mailbox/archive/`，事後還能驗。
- 程式自己把它標成 level 1：擋得住轉述與丟進信箱的假回信，擋不住會開 shell、連專區留底一起造假的 agent（同帳號）。
- aos 自己會核對「密語」的地方，這次只看到專區網頁一處：只聽 127.0.0.1，POST 要帶一個存在檔裡的 token（`frontend/aos-user/web.py:1-2`）。proc 之間的信沒有這種東西。

### 2.5 其他 IPC

底下這些大多照同一條原則，是使用者 11-05 定的（逐字，`thinking/2026-11/05/no-pid/02-轉接設計.md:21`）：「寄信收信是我們aos的非同步呼叫的底層機制，寄信不回，等同於呼叫失敗……有可能他在忙，有可能你的要求他不認得，也可能他掛了。」

| 名稱 | 做什麼 | 用什麼載 | 怎麼知道對方收到／做完 | 出處 |
|---|---|---|---|---|
| procs_requests | 請 daemon 加、刪、停、起、睡、醒一列 | 信 | 帶 `reply_to` 就回 `{"applied": true}`。`aos-agent ctl` 寄之前先核 daemon 活著沒（它 `state.json` 的 pid＋啟動時刻＋開機 id 對 `/proc`），確定不在就不寄、當場報 `DaemonMissing`；寄了之後每 0.1 秒看回信與表，上限預設 30 秒，逾時把還沒被認領的信撤回 | `cpp/aos-daemon/docs/05-信箱.md:17-35`、`py/aos/apps/agent/ctl/shared.py:73-169` |
| ping、查表 | 問 daemon 在不在、表在哪 | 信 | 回信；等回信預設上限 3 秒、每 50 ms 看一次；不回就當這次呼叫失敗 | 同上 21-27 行、`py/aos/daemon_ctl/post.py:136-157` |
| poke（門鈴） | 叫 daemon 不等下一圈、立刻看檔 | 即時訊號 `SIGRTMIN+1～3`，用 pidfd 送；送之前核對 pid＋啟動時刻＋開機 id | 沒有回應。「鈴不帶內容，檔才是真相；鈴丟了也只是等回下一圈」 | `cpp/aos-daemon/docs/04-兩個手把-兩扇狀態窗.md:70-91`、`py/aos/daemon_ctl/poke.py:70-99` |
| ctl／state 窗 | 對一支 loop 或 daemon 下暫停、繼續、停 | 寫 `ctl.json`（帶 `seq`），讀 `state.json`、`state_flux.json` | `state_flux` 的 `ctl_seq` 跟上 | 細節歸第 01 份 |
| 問腦 | agent 問 llm kernel | 信，來回各一封；中間 kernel 再寄一封請 daemon 起一支短命行程去打端點 | agent 每拍看一次回信箱 | 下面「問腦怎麼走」 |
| 畫面 socket（live_a2a） | 往開著的 Claude Code 畫面投訊息 | unix socket（Claude Code 自己的） | socket 不回話；靠 CLI 的 hook 寫回條檔 | 下面「畫面那條 socket」 |
| 貼字 | 上一條的退路 | tmux 貼上再按 Enter | CLI 的 hook 寫 `turns.jsonl` | `py/aos/agentlib/cli_ask.py:102-133` |
| pi 的收件夾 | 往開著的 pi 畫面投 | 一封一個 `.json` 檔，外掛每 0.5 秒收 | 同一份回條檔 | `py/aos/agentlib/cli_a2a.py:16-18、173-187` |
| 時鐘信 | 每 N 格、某時刻、cron，往某個信箱寄一封固定的話 | `_clock` 每秒起一支 `aos-clock`：鐘加一，照登記表 `aos-post send` | 寄不到只印一行 warning，不重試 | `py/aos/apps/clock/main.py:15-18`、`py/aos/clock_register.py:1-11、193-202` |
| aos-lock | 鎖一個檔或資料夾 | `mkdir <目標>.lock/`＋名牌 `holder.json` | 拿不到退 10；`--wait-ms` 每 20 ms 再試 | `cpp/aos-lock/README.md` |
| flock 判活 | 不看 pid 就知道另一支行程還在不在 | `sender.flock`、`holder.flock` | 試鎖成功＝人不在了（行程一死核心自動放鎖，沙箱裡也行） | `kernel_llm/docs/01-用法.md:47`、`cpp/aos-lock/README.md` |
| 布告欄 | 貼「我在忙什麼、能不能打擾、在等誰」 | `<stack>/board.json` | 別人來讀；表上睡著或停掉的算 `away` | `py/aos/apps/comm/README.md` |
| 回報信箱 | 子 agent 問腦失敗時通知上層 | 信（BLOCKED）寄到 `$AOS_NOTIFY_BOX` | — | `knowledge/aos/brain.md:24-26` |
| 讀對方的檔 | `listen` 等回答、`ctl ls` 數 queue | 直接讀對方 stack 裡的 `history.jsonl`、`letters.json`、`cooldown.json`、`think/brain_wait.json` | 每 0.2 秒看一次 | `py/aos/apps/agent/listen.py`、`hints.py` |
| 專區網頁 | 使用者在瀏覽器回信 | HTTP，只聽 127.0.0.1 | — | `frontend/aos-user/web.py`（沒細看） |

**問腦怎麼走**（`cpp/aos-llm/docs/01-用法等.md`、`py/tools/aos/kernel_llm/docs/01-用法.md`、`wait.py:1-62`）

1. agent 的 wait 格：`aos-llm send --reply-to <stack>/think/reply` 把請求寄進 `$AOS_LLM_KERNEL/requests/new/`。信名記在 `think/pending.txt`；「信名＋kernel 的路徑」另寫進 `think/brain_wait.json`，給別人查「它在等哪個 kernel」。寄之前看一眼 kernel 的 `state.json`，不像在跑就印一行 warning，照寄照等。
2. llm kernel **不是常駐行程**：它是一台 daemon，每 300 ms 起一支 `kernel_llm` 跑一輪就退（`knowledge/aos/cli/parts/llm_kernel.md:3`）。
3. 那一輪做的事：驗信；排先後（優先級加等久升級 → 期限 → 同後端黏著 → 能力包的快慢 → 先來）；看格數。格數（slots）＝整台同時幾封在問；`reserved.high` 留幾格給高優先；每個能力包、每個後端另有自己的格數。活樹現在整台 8 格、保留 1 格。
4. 放行的那封：kernel 寄一封 `procs_added` 給 daemon，請它起一支叫 `llm_<信名>` 的短命行程。這支行程就在 `requests/cur/<信名>/` 這封信的資料夾裡跑端點函數（打 HTTP），結果寫成 `reply.json`（`py/tools/aos/kernel/runner.py:111-123`）。
5. 後面某一輪 kernel 看到它跑完：照 `reply_to` 寄回信、在 `ledger.jsonl` 記一列帳、整封刪掉。
6. agent 的 wait 格每拍 `aos-llm recv`：沒到就下一拍再看，到了接進對話紀錄。信不見了（kernel 那邊找不到、回信也沒到）就重寄（`wait.py:18-20`）。

- 能力包（endpoints）：agent 只給代號（像 `smart-high`），模型與參數綁在 kernel 的包上；`aos-llm ls` 讀 kernel 寫的 `endpoints.json`、`slots.json`。
- kernel 沒在跑時 agent 不失敗、一直等（`llm_kernel.md:11`）；等滿 10 分鐘印一行提醒。

**畫面那條 socket**（`py/aos/agentlib/cli_a2a.py`、`cli_ask.py:37-85`）——今天唯一走 unix socket 的

- socket 是 Claude Code 自己開的，每個 session 一條，例 `/run/user/1000/cc-socks/1584129.sock`。CLI 開場的 hook 把路徑抄進小格的 `a2a.json`。
- 寫的人是**收件那隻自己的身體**：`aos-eca-turn` 從自己的 queue 拿到信之後才寫。所以信還是先落檔、先等一拍。
- 連上、寫一行 JSON，對方**不回任何字**。「收到沒」靠 CLI 的 hook 往 `a2a_acks.jsonl` 寫一行回條；aos 每 0.2 秒看一次。
- 連不上＝這次改貼字。投了、CLI 閒著滿 30 秒都沒回條＝判定這版不吃這個格式，這個畫面之後都貼字。
- 路徑記在檔裡，畫面關了檔還在。活樹現在 9 份 `a2a.json`，其中 4 份指的 socket 已經不存在。程式每次先 `stat` 看那裡是不是 socket，不是就當沒有（`cli_a2a.py:118-134`）。
- 畫面本身的 tmux socket 另外放在 `${XDG_RUNTIME_DIR:-/tmp}/aos-tty-<uid>/<小格真實路徑的雜湊 16 字>.sock`。原因：`/mnt/c` 上建不了 unix socket，路徑又有 108 bytes 上限（`py/aos/agentlib/cli_session.py:17`、`cli_cell.py:20-81`）。

**誰在聽**：搜過 `proto8/` 的原始碼（`py/`、`cpp/`、`frontend/`、`templates/`，含沒有副檔名的入口；找 `AF_UNIX`、`socket.socket(`、`SOCK_STREAM`、`HTTPServer`、`inotify`、`mkfifo`、`shm_open`）。測試與往外打 HTTP 的客戶端不算，結果只有三處用到 socket：`cli_a2a.py` 當客戶端去連；daemon 起子行程時父子之間的 `socketpair`（`cpp/aos-daemon/src/child/child.cpp:148`）；兩支只聽 127.0.0.1 的網頁伺服器。沒有 inotify、沒有具名管線、沒有共享記憶體。

### 2.6 延遲與成本從哪裡來

| 動作 | 量到多少 | 錢花在哪 | 來源 |
|---|---|---|---|
| `aos-post send` 一封 | ext4 中位數 9.5～19 ms；tmpfs 1.9～7.6 ms | 一次 fsync 約 8 ms；其餘是起一支 C++ 行程（1～5 ms） | `wf/ws/eca-aos/temp/bench-tmpfs-1125.md`；這次重量 9.5 ms（n=150） |
| `aos-post send --ordered` | 19.6 ms（n=150） | 兩次 fsync（`order.json`、`letter.json`）加取號鎖 | 這次量（`exp3.py`） |
| `aos-post done` | 3.2 ms（n=100） | 起行程、rename、刪 | 這次量（`exp2.py`） |
| `aos-mailbox send`（agent 走的那層） | ext4 148～158 ms；tmpfs 113～118 ms | 幾乎全是起 Python | bench |
| 工具 `mailbox_send` 整支 | 沒量；推論 0.3～0.5 秒 | 三支 Python 接力（工具 → `aos-agent ctl who` → `aos-mailbox`）再加 aos-post | `py/aos/agentlib/mailbox_call.py:16-32` |
| 起一支行程 | `/bin/true` 0.6～5 ms（看負載）；`python3 -c pass` 25～41 ms；`idle.py` 61～146 ms；`aos-eca-turn` 123～200 ms（CPU） | — | `thinking/2026-11/24/閒置輪詢C++重寫-1124/06-這次補量的數字.md`、`wf/ws/eca-aos/eca-aos-core/report-1124.md` 第 3 節 |
| 閒著的一拍 | eca 170～200 ms CPU、fsm 120～140 ms；每隻佔 0.2～0.3 核；整棵樹閒置輪詢約 4.3 核（8 核的一半多） | 每 300 ms 起一支 Python，只為了看信箱空不空 | report-1124 第 3 節 |
| queue 的信 → 開始問腦（agent-fsm） | 對方閒著時（372 封）中位數約 1.3 秒、p90 2.2 秒；全部 455 封 p90 15.9 秒、最久 249 秒 | 等下一拍，加上 idle、think、wait 三格各起一支 Python，再加 `aos-post`、`aos-tools`、`aos-llm` | 這次從活樹 37 隻 fsm 的信名算的（`queue_latency.py`；信名帶寄出時刻） |
| mailbox 的信 → 通知進 queue | 0～60 秒；活例 63 秒 | 通知每 60 秒才看一次 | `hookeds.json`；活例見下 |
| 問腦一次來回的機制成本 | 約 1.3 秒＝寄出到 kernel 看到 246 ms＋掛出去到看到做完 0.72 秒（不打模型的假端點，n=5）＋ kernel 做完到 agent 拿到 282 ms（都是中位數，粗加） | kernel 每 300 ms 一輪、每輪起 Python；daemon 每 200 ms 一圈；端點函數是另一支 Python；agent 每 300 ms 才看一次 | 活樹 `ledger.jsonl` 4923 列，對上各 agent 的 `observed.jsonl` 4833 列（`ledger_stats.py`） |
| 問腦排隊等格子 | 中位數 13 ms；p90 28.7 秒；最久 207 秒 | 整台 8 格 | 同上 |
| 真模型一次 | 中位數 6.7 秒；p90 17 秒 | 模型 | 同上 |
| `aos-agent ctl` 的一封信 | 最多等 daemon 一圈（200 ms）才被認領；等結果的上限預設 30 秒（查表類 3 秒） | daemon 輪詢 | `ctl/shared.py:9`、`post.py:147` |
| 往畫面 socket 投 | 閒著時 20 ms 內有回條 | — | `cli_a2a.py:31` 的註解 |

- **等待一律是輪詢**：20 ms（`aos-llm ask`、等鎖）、50 ms（等 daemon 回信）、200 ms（`listen`、畫面回條、daemon 圈）、300 ms（loop 的拍、kernel 的輪）、500 ms（pi 外掛）、1 秒（時鐘）、60 秒（新信通知）。
- **最大的延遲不是輪詢**，是 agent 只在兩輪之間收信。活例：`mine_mecha/main`（agent-fsm）的 `queue/cur/` 現在排了 21 封，最早一封 09:12 寄的，12:02 它還在同一輪的 act 格，已經等了 2 小時 50 分。
- 新信通知的活例：`eca-aos-core` 的一封信 11:03:19 寄到，`notified.json` 在 11:04:22 寫下，隔 63 秒；一小時後那封還在 `mailbox/new/`（通知過了，讀不讀是腦自己決定）。
- 這些數字支持 eca-aos 11-24 記在進度檔的那句：「慢的是輪詢與起行程，不是 IPC 本身」。
- 注意：活樹的數字是機器很忙的時候、事後從信名與帳本算的。「queue → 問腦」的配法是「信寄出後的第一筆問腦」，對方正在一輪中時會配錯，所以只看中位數。
- 正在施工的閒置閘（工作樹裡還沒交的 `cpp/aos-idle/`，沒裝進活樹）會改掉「閒著的一拍」那一列，歸第 11 份。

### 2.7 寄給沒在跑的 agent 會怎樣

「沒在跑」分四種（`knowledge/aos/status.md:9-25`）：

- **睡著**（sleeping）：daemon 對它送 SIGTERM，列留在表上、stack 留著；`ctl wake` 或 daemon 重起才回來。
- **停掉**（stopped）：人停的，或它出錯結束（列上有 `reason`）；要人 `ctl start`。
- **暫停**（paused）：行程在、表上還是 running，只是不跑下一步。
- **當掉**：身體卡住（表上 running），或 daemon 自己也死了、表沒人更新。

| 寄法 | 對方睡著或停掉 | 對方不在表上（rm 過、stack 還在） | 寄的人知道嗎 |
|---|---|---|---|
| `aos-agent say`（進 queue） | 照投進 `queue/new/`，退 0 | 寄不出去：`InstanceMissing` | **知道**：stderr 一行 `queued in …; nothing is running NAME now; it is asleep … wake it: aos-agent ctl wake …`（`py/aos/apps/agent/say.py:57-64`、`hints.py:194-204`） |
| `aos-agent ask`／`listen` | 同上，然後等 | 同上 | **知道**：等的時候每秒看表與狀態檔，會說「沒在跑」「暫停中」「它的 llm kernel 沒在跑」「停在哪個錯」 |
| 工具 `mailbox_send`、`aos-mailbox send --to 名字` | 照投進 `mailbox/new/`（信箱沒有就替它建），退 0 | `InstanceMissing` | **不知道**：只回信名。程式只看表上有沒有這一列、stack 在不在，不看它在不在跑（`apps/mailbox/__init__.py:338-349`） |
| `aos-mailbox send --box 路徑` | 照投 | 資料夾在就照投；不在＝`MailboxMissing` | **不知道**。實測：投給一個沒有任何行程在收的信箱，退 0、stderr 空 |
| 時鐘信 | 照投，到一次疊一封 | 信箱資料夾不在了才把那一格拿掉（每 100 格檢查一次） | 沒有人知道 |
| 問腦（對方是 llm kernel） | 照寄、一直等 | — | 知道一半：寄的時候印一行 warning，只在 log 裡 |

**信會不會把它叫醒：不會。** `A letter in your mailbox does not wake you by itself`（`knowledge/aos/mailbox.md:43`）。agent 自己 `/exit` 之後也一樣：「來信不會叫醒，ctl start 再起」（`idle.py:31`）。沒有任何程式看到信就去起行程。

醒來之後：

- queue：第一拍把 `cur/` 與 `new/` 全收（`idle.py:175-184`）。睡著期間疊的時鐘信會一次全到（`knowledge/aos/clock.md:37`）。
- mailbox：通知的 hook 醒來第一次跑，把睡著期間新到的信通知一次（`mail_notify/_entry:109-112`）。

當掉：

- 身體出錯結束：daemon 把那一列標成 `stopped` 加 `reason`（或照設定自動重起），之後同上表「停掉」。
- daemon 自己不乾淨地死了：表檔還寫著 running，要等 daemon 再起來才改成 `stopped`（`cpp/aos-daemon/docs/08-當機復原與已知限制.md:9`）。這段期間：
  - `aos-agent ctl` 的起、停、睡、醒會發現：寄之前先核 daemon 的 pid，確定不在就報 `DaemonMissing … nothing was sent`（`ctl/shared.py:73-85`）。在沙箱自己的 pid 命名空間裡看不到 daemon 的 pid，就不核、照寄。
  - `say` 與 `mailbox_send` 不會發現：它們只讀表上的 phase（`py/aos/apps/agent/common.py:202-211`），信照投（推論，沒實跑）。
- 身體卡在很長的一輪：表上 running，信照收照排。滿 10 分鐘沒動靜，stack 裡會多一個 `quiet.json`，只是記號。

**以前定過的，不是新題**：使用者 11-14 對布告欄那一輪答「都按照推薦」，其中 U3「預設不叫醒；收件人布告欄 `wake_on_urgent: true` 才允許」、U7「第一版不自動叫醒，只告訴寄件人『睡了、可請它上層叫』」（`thinking/2026-11/14/board-1114/03-計劃.md:65-77`）。`wake_on_urgent` 這一欄今天在布告欄格式裡，沒有程式照它做事。同一份查到：`ctl wake` 走的是**寄件人自己的** kernel，叫別隊的 agent 多半被拒（同檔 25 行）。

### 2.8 「某隻 agent 的信箱在哪」怎麼查

規則只有一條：信箱＝`<它的 stack>/mailbox/`，queue＝`<它的 stack>/queue/`，名字固定。所以問題等於「它的 stack 在哪」。

| 查法 | 做什麼 | 要誰活著 |
|---|---|---|
| 讀表 | daemon 的 `procs_state.json` 每列有 `stack`，存成相對 daemon 自己的 stack（活樹例 `"stack": "procs/eca-aos-kb"`），讀的人拼回絕對路徑（`py/aos/daemon_ctl/table.py:64-73、124-130`） | 誰都不用，檔在就行 |
| `aos-agent ctl where 名字` | 印那一列的 stack；`--ws` 印工作區（`py/aos/apps/agent/ctl/where.py:26-40`） | 同上。設了 `AOS_KERNEL` 時要站與 daemon 都活著（先寄信問表在哪，等 3 秒） |
| `aos-agent ctl who` | 反過來：給一條 stack 路徑，回它是表上哪一隻；`--json` 多給工作區、定義、daemon、上層、回報信箱（`ctl/who.py:31-51`） | 同上 |
| 用名字寄 | `aos-mailbox send --to 名字 [-d DAEMON]`：自己查表，信箱沒有就建 | 同上 |
| 用路徑寄 | `aos-mailbox send --box 路徑`：那裡要已經是信箱（三格都在），不替人建 | 誰都不用 |
| 回信 | 信封的 `reply_to` 拼回來 | 誰都不用 |

- **名字只在一張表裡有效。** 寄給別台 daemon 底下的 agent，要另外給那台 daemon 的 stack 路徑。活例：`mine_mecha/main` 的 `stderr.txt` 有一行 `mailbox_send: error: InstanceMissing eca_main is not on the daemon table`（`eca_main` 掛在根 daemon，它自己在子 daemon）。
- 找 daemon：`-d` ＞ `$AOS_DAEMON`（`table.py:18-30`）；daemon 起子項時把 `AOS_DAEMON` 設成自己的 stack。
- 信箱是「第一次用到才建」。活樹有三隻（`guanyu/smr`、`mine_skyrim/main`、`mod_tome4/main`）還沒有 `mailbox/`；這時用路徑寄會 `MailboxMissing`，用名字寄才會替它建。
- 位置固定的例外：llm kernel 的收件口固定在 `$AOS_LLM_KERNEL/requests/`；使用者專區在 `~/.aos/user/mailbox`；上層的回報信箱寫在啟動設定的 `AOS_NOTIFY_BOX`（活樹 `eca-aos-kb/exec.json` 寫成 `{"$env": "AOS_DAEMON", "$path": "procs/eca-aos/mailbox"}`）。

### 2.9 對到使用者定的兩條路：今天有哪些零件

使用者 11-25（逐字，`9p-proc-1125.md` 第 5 段）：「如果proc活著，那我們就直接走unix socket了，然後如果proc掛掉，那有需求者就沒辦法透過unix socket直接傳送訊息，他就只能退而求其次，去問他的daemon或特定kernel，某個proc的信箱在哪，然後走寄信這條路，寄信，就是持續性的...除非是在tmpfs，這個就後續再看了。」

**掛了＝問信箱在哪、改走寄信：零件今天全有**

| 需要的 | 今天的零件 | 能不能直接用 |
|---|---|---|
| 落檔、持續的信 | aos-post（函式庫加命令列），條文 N-16 | 能。ext4、tmpfs 都行，只要 rename 是原子的 |
| 問 daemon 信箱在哪 | 表上的 `stack` 欄；`ctl where`；`aos-mailbox send --to` 查表加投信一步做完 | 能 |
| 問某個 kernel | `{"procs_state_path": true}` 這封查詢信，站會一路轉到 daemon | 能。但回的是「表在哪」，不是「信箱在哪」，問的人還要自己讀表 |
| 對方不在時信留得住 | `new/` 不會過期；`cur/` 當掉後重做 | 能 |
| 醒來先清信箱 | 身體第一拍收 `cur/` 與 `new/`；通知 hook 醒來補通知一次 | 能。eca-aos 攤的「兩條路的順序」那題，今天的行為就是先清 |
| 回信 | `reply_to` 加 `in_reply_to` | 能；但 `reply_to` 是路徑（邊緣 4） |
| 寄的人知道對方沒在跑 | `say`／`listen` 讀表與狀態檔；布告欄的 `asleep` | 一半：`mailbox_send` 不講 |
| 叫醒（可選） | `ctl wake`（寄 `procs_woken` 給 daemon）；布告欄的 `wake_on_urgent` 欄 | 手動的有；自動的沒有（11-14 定過第一版不自動） |

**活著＝直接走 unix socket：今天沒有，下面是可借的**

| 需要的 | 今天最接近的 | 差什麼 |
|---|---|---|
| 有人開 socket 聽 | 沒有。常駐的只有 `aos-loop`、`aos-daemon`；身體每拍是新行程 | 要嘛 aos-loop／daemon 來聽，要嘛身體改成常駐 |
| 「先試 socket、不通就退回」 | 畫面 socket：記路徑 → `stat` 確認 → 連、寫 → 等回條 → 沒回條退回貼字 | 流程可以抄；但它是收件方自己投、對方 socket 不回話 |
| 叫活著的行程「現在看一下」 | daemon 的 poke（pidfd 加身分核對） | 只有 daemon 接。同樣的訊號送給 aos-loop 會把它打死（`cpp/aos-daemon/docs/04-兩個手把-兩扇狀態窗.md:89`） |
| 寄之前先看對方活不活 | `aos-agent ctl` 核 daemon 的 pid＋啟動時刻＋開機 id；`aos-llm` 寄之前看 kernel 的 `state.json` | 有，但靠 pid 與落檔的狀態，沙箱裡看不到 pid 就失效 |
| 不靠 pid 判斷活著 | `sender.flock`、`holder.flock` | 能直接用 |
| 一輪中間把話送進對話 | eca 有（畫面 socket；`claude -p` 的 stdin，預設關；pi 的 steer） | agent-fsm 沒有：使用者 11-04 定「等答完回 idle 再收」 |
| socket 放哪 | 畫面的 tmux socket 那套規則（放 `XDG_RUNTIME_DIR`、短雜湊、0700 資料夾） | 新做法是 `/proc/<PID>/cwd/…`，歸第 08 份 |
| 回應分幾級 | 今天三級：投進去了（send 退 0）／被認領了（信離開 `new/`）／做了或答了（回信，或對話紀錄裡的回答） | 新介面的「寫回來＝收到」對到第二級 |

## 3. 對新介面的含意

對著 `9p-proc-1125.md`「定了的」講；只講從上面事實推得出的。標「推論」的是我的，沒有使用者的話。

- **送訊息兩條路**
  - 「掛了」那條不用新做：persist 裡照今天的格式放一個信箱就是。
  - 「活著」那條第一個要定的是誰來聽（2.9 第二張表第一列）。
  - 畫面 socket 給了一個教訓：socket 不回話時，「收到沒」得另外做回條，還要定「多久沒回條就退回」（今天 30 秒）。新介面定了「寫回來＝收到」，回條這段就省了；但「連上了、對方卡住不回」仍要有逾時，今天查表類用 3 秒、起停類用 30 秒。（推論）
- **stack 的意思換了、要留的放 persist**
  - 今天別人會去碰一隻 agent 的 stack 裡這些東西：`mailbox/`、`queue/`（投信）；`history.jsonl`、`letters.json`、`cooldown.json`、`think/brain_wait.json`（`listen` 讀）；`board.json`、`state.json`。
  - 前兩樣一定要在 persist：對方不在也要投得進去。
  - 今天所有 `reply_to` 都指進寄件人的 stack（`<stack>/mailbox`、`<stack>/think/reply`、`<stack>/daemon_reply`）。新模型下這些位址要嘛改指 persist，要嘛改成 socket 上當場回。（推論）
- **入口 `AOS_ROOT=/proc/<PID>/cwd`**
  - 今天寄件人身分＝stack 的絕對路徑字串，額度帳、提示快取鍵、權限站的份額都拿它當鍵（2.4）。
  - stack 若變成 `/proc/<PID>/cwd/…`，同一隻 agent 每次重起這條路徑就變，三樣都會斷（額度歸零、快取不中）。得有一個重起不變的身分。（推論；身分怎麼驗歸第 15 份，名字怎麼取歸第 06 份）
- **daemon＝橋，多一個 procs 夾**
  - 「daemon 是橋」不是新的：11-05 no-pid 那一輪的設計就寫「daemon 是 Linux 行程跟 aos 之間唯一的橋：pid、`/proc`、訊號只有它碰，它把看到的寫成檔案給大家讀」（`thinking/2026-11/05/no-pid/02-轉接設計.md:7`）。今天別人碰 pid 的地方是寫明的例外（poke、清道夫、`aos-agent ctl` 核 daemon 活著沒）。那一輪的題目叫「不靠 pid 找東西」，新模型的入口是根 daemon 的 PID，兩者怎麼對歸第 16 份。
  - 今天「問信箱在哪」是讀一個檔。daemon 死了也查得到，信也投得進去。
  - 如果以後 `procs/<名>` 是活的 daemon 當場回答，daemon 一死就沒人可問。要保住「寄信不需要任何人活著」，「名字 → persist 位置」得在硬碟留一份。（推論；跟 eca-aos 攤的「`procs/arena/persist` 在 arena 死掉時走不到」是同一件事）
- **kernel＝普通的 aos proc**
  - 今天 llm kernel 的身體不是常駐行程，是它那台 daemon 每 300 ms 起一支跑一輪。「kernel 活著就走 socket」不能直接套：聽的會是那台 daemon，或 kernel 得改常駐。
  - 問腦很長（中位數 6.7 秒）還會排隊（p90 等 28 秒），走 socket 也不會是「一問一答等到底」那麼單純。（推論）
- **token 用量各自報**：今天已經是這樣。agent 自己的在 `<stack>/observed.jsonl`，kernel 的在它自己 stack 的 `ledger.jsonl`、`used.json`，daemon 不管帳；兩邊用同一個信名對得起來（2.6 的問腦數字就是這樣算的）。
- **`ctl` 寫回來＝收到**
  - 今天對 daemon 下指令是寄信，再輪詢等回信、或看信離開 `new/` 沒有（`aos-daemon-ctl` 等認領上限 3 秒，`aos-agent ctl` 等結果上限 30 秒）。有回應的寫可以取代這種等法。
  - 但信有一個今天在用的性質：daemon 暫停或正在收工的那幾圈不認領信，信留在 `new/`，恢復後照套（`cpp/aos-daemon/docs/05-信箱.md:17`）。socket 上的寫沒有這個「先放著」。（推論）
- **`status` 一行一個「名稱: 值」**：今天別人想知道「它現在怎樣」要讀五六個檔（在不在跑、暫停沒、queue 幾封、冷卻到幾點、在等哪個 kernel、多久沒動靜、布告欄）。這些都是 `status` 的候選行（歸第 18 份）。
- **問信箱時要不要順手叫醒**：使用者 11-25「我傾向於這是daemon自身的可選設定」。跟 11-14 的 U3、U7（預設不叫醒、只告訴寄件人）方向一致。今天 `ctl wake` 走寄件人自己的 kernel、叫別隊多半被拒這件事，也說明放在「被叫那隻的 daemon」比較順。（推論）
- **部分用 json**：今天信封與所有 body 都是 JSON。信的格式列在「還沒談到的」，這份只提供現況：一個信封六個欄位，body 有六種形狀（2.2 的表）。

## 4. 邊緣狀況

1. **過期的通知**：通知寄出後就不管了。它在 queue 排著時，agent 可能已經把信讀掉，之後才看到「有 2 封新信」而信箱是空的（`wf/ws/eca-aos/eca-aos-core/report-1124-bgmail.md` 第 4 節）。兩條路並存時是同一類問題：socket 先到的訊息，與信箱裡比較舊的信，誰先。
2. **活著不等於現在會看**：agent-fsm 一輪中間不收 queue（活例 21 封、近三小時）；eca 一輪中間連新信通知都不產生。
3. **`claude -p` 會等背景 Bash 結束才退出**，那一輪卡住、鎖一直被佔、新信全排著（同上報告第 7 節，實測過）。
4. **回信位址是路徑**：`reply_to` 存相對路徑，兩邊一起搬沒事，只搬一邊就指到不存在的地方。活例：`eca-aos` 的 `mailbox/archive/` 38 封裡，別棵樹寄來的 12 封，`reply_to` 現在拼出來是 `/home/guanyu/aos-home/aos-home/.stack/…`（推論：11-24 搬樹時只有收件這邊換了位置）。同一個信箱裡同樹寄來的舊信，`sender` 還寫著搬家前的 `/home/guanyu/repo/aos/.stack/procs/…`，那個資料夾已經不在。
5. **socket 路徑記在檔裡會過期**（活例 9 份裡 4 份）。socket 檔還在但沒人聽時，連線是 `Connection refused`（`9p-proc-1125.md` 實測表）。
6. **socket 放不了的地方**：`/mnt/c` 上建不了；路徑上限 108 bytes；daemon 與人的殼 `XDG_RUNTIME_DIR` 不一樣時會算出兩個位置（`cli_cell.py:63-81`）。
7. **名字只在一張表內有效**；跨 daemon 要給路徑。
8. **信箱第一次用到才建**；用路徑寄給還沒有信箱的 agent 會失敗。
9. **時鐘信對睡著的 agent 一直疊**，醒來一次全到。
10. **壞信直接丟、不通知寄件人**；信讀完預設就刪，寄件人那邊也不留底（除非給 `keep`）。
11. **daemon 不乾淨地死掉時，表還寫 running**（2.7）。
12. **權限站忙＝底下全部 agent 讀信、寄信、設鬧鐘都 3 秒後失敗**（`kernel.md:42-44`）。
13. **一個信箱兩個人收**：不會重複認領，但 `cur/` 裡的殘骸分不出是誰的（`cpp/aos-post/docs/02-錯誤代號等.md:34`）。
14. **無序信的先後靠牆上時鐘**。要保證先後得用 `--ordered`，而取號鎖只在同一個信箱內有效。
15. **同帳號下，寫得到信箱的人也讀得到別人的信與回信。**
16. **權限站轉寄後原寄件人就看不到了**：下一站看到的 `sender` 是站自己（2.4）。
17. **沙箱裡看不到別人的 pid**：今天已經有兩處因為這件事特地讓步——`aos-agent ctl` 在沙箱的 pid 命名空間裡不核 daemon 活不活（`ctl/shared.py:65-78`），`aos-llm` 的「kernel 沒在跑」提醒在那裡會誤報（`cpp/aos-llm/docs/01-用法等.md:14`）。以 `/proc/<PID>/cwd` 當入口，在這種沙箱裡同樣走不進去（推論；歸第 08、15 份）。
18. **逾時撤信**：`aos-agent ctl` 等不到結果時，會把還在 `new/` 的信撤回，並說清楚是「撤回了、不會套用」還是「撤不回、可能還是會套用」（`ctl/shared.py:164-169`）。socket 上寫出去的東西沒有「撤回」這一步。

## 5. 要問使用者的

只列從現況看得出「不先定、兩條路就寫不下去」的四題；協議細節的題歸第 20 份。

1. **socket 上的一則訊息，算「進對話的話」（今天的 queue）還是「信」（今天的 mailbox）？**
   今天有兩種收件口，是使用者 11-10 分的：queue「偏向於獨屬於使用者」與父對子，直接進對話；mailbox 是 agent 之間的信，不自動進對話，agent 自己決定看不看。
   - a. 兩種都留，socket 只是送法：訊息自己帶一欄說是哪一種；對方不在時各自落到 `queue/` 或 `mailbox/`。
   - b. socket 只送「進對話的話」；信一律落檔進 mailbox，對方活著時多按一下門鈴叫它看。
   - c. 合成一種收件口。
   - 推薦 a。理由：換的是送法，「誰可以直接插進對話」這條他定的界線不用跟著動。
2. **daemon 自己也掛了的時候，還要不要查得到信箱、投得進信？**
   今天查信箱是讀 daemon 留在硬碟的表，誰都不用活著。
   - a. 要：「名字 → persist 位置」這張表繼續落檔，daemon 死了照樣查得到、投得進。
   - b. 不用：一定要問活著的 daemon；它不在就是寄不出去，當場報錯。
   - c. 先 b，之後再看。
   - 推薦 a。理由：寄信這條路的價值就在「不需要任何人活著」，整棵樹重起後信也都還在。
3. **寄件人的身分以後綁什麼？**
   今天是 stack 的絕對路徑（自己報的），額度帳與提示快取都拿它當鍵；stack 變成 `/proc/<PID>/…` 之後每次重起都會變。
   - a. 綁名字那條路（從根算的 `procs/repo-aos/procs/eca-aos` 這種）。
   - b. 綁 persist 的位置。
   - c. 照舊，寄件人寫什麼就是什麼，要用它的人自己擔。
   - 推薦 a。理由：名字重起不變、搬家也不變；persist 位置是 proc 自己挑的，會變。（要不要驗身分是第 15 份的題，這題只問「鍵用什麼」。）
4. **問腦要不要也照兩條路？**
   今天問腦是寄信給 llm kernel，機制成本每次約 1.3 秒（模型本身中位數 6.7 秒）；kernel 的身體不是常駐行程。
   - a. 先照舊走信，等有常駐的 kernel 再說。
   - b. 現在就規劃成：kernel 活著走 socket、不在才落檔。
   - c. 問腦永遠走信（本來就要排隊、要留得住）。
   - 推薦 a。理由：那 1.3 秒大半是「每輪起 Python、每 300 ms 才看一次」，閒置輪詢那條線正在處理；做完再量，才知道 socket 還能省多少。

## 6. 沒查到／沒把握的

- 沒起真的 agent 量端到端。2.6 的活樹數字是事後從信名與帳本算的，機器當時很忙，配法也粗，只能看中位數。
- 不打模型的假端點只有 5 筆，「掛出去到做完 0.72 秒」的樣本很小。
- 這台沒有 strace，「一次 send 幾次 fsync」是讀程式得的，沒有逐個系統呼叫去數。
- 「daemon 不乾淨地死掉時 `say` 不提醒」「agent-fsm 收信到一半當掉會重收一次」是照程式推的，沒實跑。
- pi、codex 兩種身體只看了註解，沒細讀。專區與全景頁的網頁（HTTP）沒細看。
- 互動畫面開著背景 Bash 時到底收不收得到信，核心程式位子的報告也還沒驗完。
- 家機沒看；`/run/user/<uid>` 這類位置兩台可能不同。
- 信件分級（急件）與頻道還沒做，今天只有布告欄，所以沒有「急件」可查。
- 表很大（上千列）時讀表查信箱要多久，沒量。

## 附：重跑用的腳本與原始輸出

腳本都在 `~/.aos/scratch/aos-proc-arch-1125/05/`，只碰自己的暫存夾；後兩支只讀活樹的信名、帳本與 `observed.jsonl`，不讀請求或信的內文。

| 檔 | 做什麼 |
|---|---|
| `exp1.sh` | 名字與信封長相、假冒寄件人、寄給沒人收的信箱 |
| `exp2.py` | 6 支同時搶 300 封；`send`、`done` 計時 |
| `exp3.py` | 有序與無序 `send` 計時 |
| `ledger_stats.py <llm kernel 的 stack> <活樹根>` | 問腦各段的時間分佈 |
| `queue_latency.py <活樹根>` | queue 的信到之後第一筆問腦 |

```
# exp2.py
sent 300; takers claimed [199, 44, 50, 7, 0, 0]; total 300; distinct 300; missing 0; in cur/ 300; left in new/ 0
aos-post send (ext4)   n=300 median=10.0 p90=20.6 ms
aos-post done (ext4)   n=100 median=3.2 p90=8.2 ms
# exp3.py
plain   send: median=9.5 p90=18.5 ms
ordered send: median=19.6 p90=28.9 ms
# ledger_stats.py
ledger rows: 4923
send -> kernel first sees it       n=4923  min=-124     p10=61       median=246      p90=488       max=2166 (ms)
seen -> mounted (wait for slot)    n=4923  min=1        p10=5        median=13       p90=28673     max=206871 (ms)
mounted -> finished (all)          n=4923  min=713      p10=3887     median=6719     p90=17386     max=167293 (ms)
  endpoint fake                    n=5     min=713      p10=713      median=724      p90=740       max=740 (ms)
observed.jsonl files: 62  joined think rows: 4833
agent elapsed - kernel elapsed     n=4833  min=-341     p10=310      median=673      p90=27493     max=207840 (ms)
kernel finished -> agent got it    n=4833  min=-368     p10=90       median=282      p90=563       max=87842 (ms)
# queue_latency.py
fsm stacks with data: 37  queue letters matched: 455
all: min=43 p10=842 p25=1078 median=1453 p75=2405 p90=15870 max=248568 (ms)
under 5 s (agent was idle): n=372 of 455; min=43 p10=834 median=1298 p90=2203 (ms)
```

負的最小值：kernel 記「第一次看到」用的是那一輪開始的時刻，信在那一輪中途才寄到就會算出負數。
