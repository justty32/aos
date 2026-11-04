# 試玩 one-boot（Opus，2026-09-24）

← [play README](README.md)｜前一輪 [r5 Opus](2026-09-24-r5-opus.md)

one-boot（`aos up`／`aos down` 一條開關機、kernel cpu 拿掉、帳本換 sqlite）之後。分數 5/4/4/4/4。

我只看了 `proto5/README.md`、教程 01、02、06，還有它們直接連到的 [aos up／down 規範](../../spec/daemon/up.md)。沒看 notes/、lib/、測試。
工作目錄照教程用 `$HOME/aos-try`。模型走 LiteLLM `http://localhost:4000/v1` 的 `deepseek-chat`，沒碰 LM Studio、1234、ollama。
教程本來就寫這個端點，**一個字都不用改**。玩完 `aos down`，我這組的行程全收掉了（見文末「清場」）。repo 除了這份報告和索引那一列，什麼都沒改。

## 總結

**照抄就一次過，一個真的卡住的地方都沒有。** 教程寫的每一行輸出，跟我看到的幾乎一字不差。

- **01 開機**：`init` → `check --probe`（只有 `warn daemon`，教程說不用管）→ `aos up` 1.2 秒印出 `up … （新開） 2 個池、3 顆 cpu` 和 `health ok`。`aos-kernel ls` 跟教程的範例一樣。
  開著再打一次 `aos up`，印「本來就在」，`seq` 從 2 重算，教程說會重開一次，對得上。`aos down` 3.1 秒，印兩行 `stopped`。第 7 步再 `aos up`、再 `init` 被 `AlreadyExists` 拒絕，也都照教程。
- **02 kernel 跑工作**：once 等回音 0.35 秒；不等的版本印單名，`cat`、`ack` 都行；反覆的 `count` 跑 3 次就 `done`；`boom` 20 秒內跑到 `bad 10 10`，表下還多一行叫我去看 `boom.err`。`rm` 各印一次名字。故意寫不存在的程式，回音 `code 127`、指令照樣退 0，跟教程講的一樣。
- **agent 一圈**：README 的「五分鐘」用 `init` 建 bob，`say --wait` 12 秒回報時。教程 06 手寫四份檔建 amy，`check` 全 ok，投 `input.json` 約 5 秒有回話，`say --wait` 8.5 秒。
- **06 多開一個 kernel（K4）共用同一個 daemon**：照寫 `dpool: k4-default`，`aos up --target $W/K4` 印「本來就在」、`health ok`，丟一張 once 單也會回。我另外故意不寫 `dpool`（K5），`aos up` 就跟教程說的一樣退 1、印 `NameTaken（池 default 已是 …/K 的）`。`aos down --target K5` 收得掉，而且原本的 K 完全沒受影響。K4 收工那行「daemon 沒停：還有別的 kernel」也照教程印。

## 五條標準

- **容易上手：5**。01、02、06 加 README 五分鐘全部照貼就過，沒有一步要自己想辦法。開機從以前的好幾條變成一條 `aos up`，每天重開機也只要這一條，這是最大的進步。
- **容易理解：4**。`health` 第一行加括號裡的指令，一看就知道下一步要做什麼。扣分在幾個小字眼：
  `ls --pool default` 的 `gen 1` 教程沒解釋；`proc 1 個 … （其餘 1 個沒事的沒列）`，上面一個都沒列，還寫「其餘」，讀起來怪；
  `aos-agent status` 的 `batch -`、`input -` 新手不知道在講什麼；`check` 寫「五支 CLI 都找得到」，可是 README 說有十一支。
- **複雜的東西藏好了：4**。daemon 被 kill -9 之後，一條 `aos up` 就救回來，agent 登記、停車狀態都還在，話照樣回。扣分：daemon 死了以後 `ls` 還印舊數字（見卡點 3）；daemon 在工作中被殺，舊的 cpu 會留一下直到把手上那件做完（見卡點 4）。
- **外層控制結構簡單但全面：4**。`up`／`down` 兩條就管住開關機，底下四條 debug 用的也還在，而且規範講清楚「只是包起來」。扣分：`aos down` 打兩次都印 `stopped stopped`，分不出第二次其實什麼都沒做；`aos up` 撞名退 1，可是那個 kernel 已經開了一半，要記得自己 `aos down`（教程有講，但很容易漏）。
- **要背的東西少：4**。日常只剩 `aos up`／`aos down`／`aos-kernel ls`。還是要記得每開一個新終端要 `. env.sh`，還有兩個 kernel 共用 daemon 時要寫 `dpool`（`check` 不會預先提醒，見卡點 2）。

## 卡住的地方

真的卡住的一個都沒有。下面是「愣了一下」和刻意弄壞時看到的怪事。

1. **教程 02 第 3 步，`ack`。** 我打 `aos-kernel ack cli-…json`，什麼都沒印、退 0；馬上 `ls K/responses/`，檔還在。我以為 ack 沒成功。過 2 秒再看就不見了（要等下一格才真的刪）。教程沒說 ack 印什麼、多久生效；印一行 `acked …` 就不會愣。
2. **教程 06 第 4 節，故意不寫 `dpool`（K5）。** 我先打 `aos-kernel check --target $W/K5`，全部 `ok`，還寫「daemon 目前有：default」。我以為沒事，就 `aos up --target $W/K5`，結果第二行 `health 池 default：NameTaken`、退 1。教程有預告這個錯，照它 `aos down --target $W/K5` 就收掉了。可惜 `check` 明明已經看到 daemon 那邊有個 `default`，卻沒先說「這池是別的 kernel 的，要寫 `dpool`」。
3. **自己加的：kill -9 daemon 後馬上 `aos-kernel ls`。** 第一行 `health daemon 沒在跑…（aos up…）`，這句很好。可是同一張表裡 kernel 寫 `running`，池那行寫 `daemon default: running 2 pending 0 …   daemon 沒在跑`，同一行前面說有 2 顆在跑、後面說 daemon 沒在跑。我一時以為 cpu 還活著，`pgrep` 一看全死了。照 health 打 `aos up`（0.17 秒）就好了，agent 回話正常。
4. **自己加的：llm 池 cpu 正在問模型時 kill -9 daemon。** 殺完 1 秒，舊的 `aos-cpu` 和它底下的 `aos-llm call` 還活著（變成沒爸爸的行程）；我接著 `aos up`，新 daemon 又拉了 3 顆新的。有一小段時間，llm 池那顆 cpu 的家好像有新、舊兩個主人。後來舊的做完手上那件就自己退了，`listen --wait` 9 秒拿到完整回話，沒壞東西。我不知道這是不是設計好的；如果是，教程或規範提一句「舊 cpu 會把手上那件做完才退」，看到的人就不會緊張。
5. **自己加的：`aos down` 打第二次。** 還是印兩行 `stopped`、退 0。我以為它又停了一次什麼，其實本來就停了。`aos up` 會分「新開／本來就在」，`down` 沒有。
6. **daemon.log 是空的。** 開機、kill -9、再開機三次後，`D/daemon.log` 還是 0 位元組。教程說 `DaemonFailed` 時「看 daemon.log 最後幾行」，但正常時一行都沒有，被殺過也沒留痕跡。至少印一行「daemon 開機 pid …」，日後翻 log 才知道它重開過幾次。
7. **清場用 `pgrep -f aos` 驗證永遠不會是空的。** 這台機器上有別的 session 在跑另一個 daemon，而且 repo 路徑本身就有 `simple_tools/aos`，所以連我自己的 shell 也會被抓到。我改用自己的路徑 `pgrep -af "aos-try|<我的 worktree>/proto5"` 去篩，那個才是空的。教程 01 第 6 步可以提一句「確認全停：`aos-daemon ls` 印 `daemon not running`」，比 pgrep 可靠。

另外，派我來的任務書把教程 02、06 寫成「agent 一圈」「多池」，實際上 02 是 kernel 跑工作、06 是手寫家（第 4 節才是多一個 kernel 共用 daemon）。
agent 一圈我用 README 的「五分鐘」和 06 的 amy 補上；03、05 沒看。這是任務書對錯了篇號，不是教程的問題。

## `aos up` 之後印的東西看不看得懂、`aos down` 之後乾不乾淨、kill -9 之後

- **`aos-kernel ls`**：看得懂。第一行 `health ok` 最要緊，教程也這樣說。`seq`、`tick 由 daemon 開：上一格 0 秒前`、每池的 `want／sent／busy／idle／draining`，教程第 5 步逐欄解釋過，對照一次就懂。看不懂的只有 `--pool` 版的 `gen 1`。
- **`aos-agent status`**：大致看得懂。`health`、`state idle errors 0`、`error （無）` 很清楚；`kernel agent-amy queued（停車：等回音或輸入，最晚 park_ms 自己醒）` 看得出「它在睡、有話會醒」。`batch -`、`input -`、`runs 8` 沒解釋（這三個在教程 03，我沒讀）。停機後 status 會寫 `kernel 停機中（aos up …）` 和 `沒登記（aos-agent start …）`，兩句都直接告訴我下一步。
- **`aos down` 之後 `pgrep`**：用我自己的路徑篩是空的；`aos-daemon ls` 印 `daemon not running`。只用 `pgrep -f aos` 不會是空的，原因見卡點 7（別人的 daemon，不是我的殘留）。
- **kill -9 daemon 再 `aos up`**：兩次都一條指令救回。閒著時殺：cpu 跟著全死，沒有孤兒；`aos up` 0.17 秒 `health ok`，bob 的登記和停車都在，接著 `say --wait` 11.5 秒回話。忙著時殺：舊 llm cpu 留到做完那件才退（卡點 4），回話沒掉。怪事只有卡點 3 的舊數字和卡點 6 的空 log。

## 改了會更順的清單（按痛度排）

1. `aos-kernel ls`：daemon 死了時，池那行不要印舊的 `running 2`，直接寫「daemon 沒在跑」就好；kernel 那行也別寫 `running`。
2. `aos-kernel check`：kernel 的池名（或 `dpool`）在 daemon 那邊已經屬於別的 kernel 時給 `bad`，並提示寫 `dpool`。
3. daemon 被殺時舊 cpu 的去留：如果是設計好的，教程「底下在幹嘛」補一句；如果不是，看要不要讓新 daemon 等舊主人退出再接手。
4. `aos down` 本來就停著時印「本來就停了」，跟 `aos up` 的「本來就在」對稱。
5. `daemon.log` 至少記開機和收到停機的時間。
6. `aos-kernel ack` 印一行 `acked <單名>`。
7. 教程 01 第 6 步加「確認全停：`aos-daemon ls`」；`ls --pool` 的 `gen` 在第 5 步補一句解釋。
8. `ls` 的「其餘 N 個沒事的沒列」在上面一個都沒列時改說「N 個都沒事」；`check` 的「五支 CLI」改成實際數字或直接寫「CLI 都找得到」。

## 你會不會想用它

會。以前開機要記 daemon、kernel 兩條，還有先後順序；現在一條 `aos up`，被 kill -9 也只要再一條 `aos up`。
開一個 kernel 跑自己的小工作、再開一個 agent 聊天，整個流程十分鐘內走完，沒有一步要猜。上面的小地方修好就更放心了。

## 清場

`aos-agent stop` bob、amy（amy 在 06 第 3 步就停了），K4、K5 各自 `aos down --target`，最後 `aos down`。
`pgrep -af "aos-try|agent-a4af3b9721fffd9cf/proto5"` 是空的；`pgrep -f 'aos-daemon|aos-kernel|aos-agent'` 只剩別的 session 的 `wf-try` daemon（`agent-a390649…` worktree），不是我開的，沒動它。
