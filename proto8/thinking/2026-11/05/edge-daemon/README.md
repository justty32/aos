# 2026-11-05 daemon 一帶的邊緣實測（edge-daemon，B 線：aos-daemon、aos-daemon-ctl、aos-loop、install.sh、搬家）

← [2026-11-05](../README.md)｜同日 A 線：[edge-llm](../edge-llm/README.md)｜依據：[portable-flow 實作結果](../portable-flow/README.md#實作結果11-05-隊長)、[kernel-daemon 08](../kernel-daemon/08-實作結果.md)｜昨天測過的不重測：[four-elements 09](../../04/four-elements/09-邊緣狀況實測-11-04-夜.md)、[edge-basics](../../04/edge-basics/README.md)

使用者 11-05：「你先自己多測試測試各種邊緣狀況，有問題就修。當然，我會時不時回來看一下，有事可以問我。」同日另一句：「我發現我們做出來的程式，輸出的各種東西，裡面都有中文...全都用英文吧」——這輪新寫或改到的輸出都用英文。

做法：WSL `/tmp/edgeB-*` 自建測試場（daemon 定義＋幾個小 loop，`sh -c` 當身體，沒開模型），以現行程式為準。試了 **14 類**（下表），**修了 6 處**（3 個 commit），**2 題**要你看（推薦放第一）。

處理欄：**已修**＝附 commit；**列題**＝見下；**天然**＝照設計；**文件**＝寫一句、不改程式（風險自擔）。

## 結果表

| # | 類 | 情境 | 結果 | 處理 |
|---|---|---|---|---|
| 1 | DaemonRunning | 同一個 stack 一次起 3 個 daemon | 修前：兩個都過關（都還沒寫 state.json），一個死在 `state.json.tmp` 互搶，活下來的那個的 state.json 卻記著死掉那個的 pid，再起第三個也擋不住；修後：對 stack 資料夾 `flock`，5 輪每輪只活 1 個 | 已修 `6506deb7` |
| 2 | DaemonRunning | state.json 的 pid＋ticks 剛好對上一支活著的別人；pid 改成 1；kill -9 後重開 | 修前：前者會被誤擋；修後：都照起、kill -9 的子項照 adopt 回同 pid | 已修 `6506deb7` |
| 3 | 搬家 | `ws/.stack` 是捷徑（指到別處） | 修前：小格的 `$AOS_DAEMON/../../defs/…` 被 OS 照實體走 `..`，**一 add 就 EntryMissing 下表**（ws 在捷徑資料夾底下同理）；修後：daemon 的基準點取 stack 的真實路徑，ctl 讀表時也解開 | 已修 `6506deb7` |
| 4 | 搬家 | 空白＋中文路徑、240 字長路徑 rsync -a；定義是捷徑；git 來回放兩份範本 | 都在新位置醒、子項的 `AOS_STACK`／`AOS_WS`／`AOS_DAEMON` 都是新位置、舊位置沒被碰；git 沒帶進 stderr／tmp／.flock | 天然 |
| 5 | 起法 | `aos-exec 定義 --enable-logs` | 參數接在設定檔後面＝`ArgumentsBad`，訊息還叫人「寫在 -- 後面」（那是給身體的）；改成說「旗標要寫在設定檔前面，用 aos-exec 起的寫進 `_entry`」 | 已修 `6506deb7`／英文 `9e4f1ee0` |
| 6 | phase 組合 | sleep→sleep、sleeping 時 stop／start、stop 後馬上 start、pause→sleep→wake→resume、paused 時 stop、同一圈 sleep＋wake 兩封信 | ctl 照表擋（`PhaseBad` 提示下一步）；醒來照舊暫停、resume 接著跑（約 1 秒內）；paused 的 stop 照停；同圈兩封＝照順序套、最後 running | 天然 |
| 7 | daemon 不在時 | add、rm、stop、wake | 信照寄、開門照套；stop／wake 讀表會說「daemon 沒在跑」，**add／rm 一聲不吭**；補一句 note | 已修 `81a44bf5` |
| 8 | 3 秒判定 | 醒來後 2.5 秒才失敗、3.5 秒才失敗、醒來 1 秒內正常跑完（code 0） | 2.5 秒＝留 `stopped`＋reason；**3.5 秒＝直接下表、原因沒留**；正常跑完＝下表（done） | **列題 2** |
| 9 | ctl 信箱 | 壞信 8 種、信資料夾是空的／`letter.json` 是資料夾、一次 500 封 add | 壞信都進 `mailbox_warning`、不卡；未知 key、不在表上的名字照「當沒看到」；500 封 1.6 秒收完、2.2 秒全跑完，daemon 照活；500 個做完的小格留在磁碟（stack 不清，照設計） | 天然 |
| 10 | Ctrl-C | 子項不理 TERM 時按一下、按兩下（第二下在收工途中）；剛起來就 Ctrl-C | 都 2 秒內收好（單子 grace 到了整群 KILL）、列留 `sleeping`、沒殘留；剛起就按＝列先 `stopping` 再 `sleeping`，再起照醒 | 天然 |
| 11 | 巢狀 | ctl add 一個子 daemon、往子 daemon 掛 tick、cwd 在 stack 裡找 `./.stack`、父 sleep 子、父 Ctrl-C 再起；子 daemon 寫進父的 `daemon.json` | 子 daemon 判成 exec 型：**父不能 sleep 它（`CtlMissing`）、父收工就拔、父再開不回來**，它底下的 tick 一直 `sleeping` 沒人叫；寫進父的 `daemon.json` 的每次都會起、子項跟著醒；cwd 在 stack 裡＝`DaemonMissing`（不往上找，照設計）；子 daemon 的子項 `AOS_DAEMON`＝子 stack | 文件（下「代定」4） |
| 12 | 判官模式 1 | 放行、拒、daemon 不在時寄請求再起、`judge.json` 改壞 | 放行／拒照舊；不在時的請求開門照判；**`judge.json` 壞＝身體失敗＝整台 daemon 收工** | **列題 1** |
| 13 | install.sh | 重跑、同名一般檔、斷連結、唯讀、相對、空白、目的地是檔案、PATH 上別支排前面、移除 | 修前：目的地是檔案卻報「裝 20 支」退 0；PATH 上排前面的同名指令不提醒；沒有移除。修後：`DestBad`、`warning: X on PATH resolves to … first`、`--uninstall`（只拿指進這份 repo 的連結） | 已修 `9e4f1ee0` |
| 14 | aos-exec | 函數正常結束、它丟到背景的孫行程（A 線轉來） | 留著繼續跑、沒人收；逾時／訊號才整群收 | 文件（代定 5） |

## 修了什麼

- `6506deb7`：aos-daemon 的 `check_running` 改 `flock` 鎖 stack 資料夾（O_CLOEXEC，鎖到行程結束；不多建檔）；`AOS_DAEMON`／表的基準點取 stack 真實路徑，aos-daemon-ctl 讀表時 `realpath(D)`；aos-loop／aos-daemon 設定檔後接旗標的提示。
- `9e4f1ee0`：install.sh `DestBad`、`LinkFailed`、PATH 衝突 warning、`--uninstall`；上面兩句輸出改英文。
- `81a44bf5`：aos-daemon-ctl add／rm 在 daemon 沒在跑時印 note。
- 連帶重建：aos-loop、aos-daemon、aos-fsm、aos-json、aos-llm-kernel、aos-llm（都把 aos-loop 的 lib 編進去；只差錯誤訊息）。aos-exec、aos-post 沒改。

## 代定（可翻案）

1. DaemonRunning 用 `flock` 鎖 stack 資料夾本身（不建 `.lock` 檔）；NFS 這種 flock 不可靠的地方自擔。訊息的 pid 只在對得上活著的行程時印。
2. 基準點取真實路徑、目標照字面：ws 在捷徑資料夾底下時，表上會出現 `../../..` 繞到真實位置的路徑——就地跑一定對；整份搬走時，捷徑本身沒一起搬就自擔（`ws/.stack` 是捷徑時，`cp -a` 只帶走捷徑、兩份共用同一個實體 stack）。
3. install.sh 的 PATH 衝突只印 warning、照裝；`--uninstall` 只拿指進這份 repo 的連結。
4. 子 daemon 用 `ctl add` 掛＝exec 型（只有跑和拔），要它跟著父起落就寫進父的 `daemon.json` 的 `procs`。沒改程式。
5. aos-exec 正常結束不收背景孫行程（Unix 慣例；要不留尾巴就在單子裡 `wait`），寫進 [aos-exec docs/03](../../../../impls/aos-exec/docs/03-環境變數.md)。
6. 3.5 秒才失敗的醒來者照舊下表（見題 2）；daemon 身體失敗照舊整台收工（見題 1），都寫進文件。

## 要你看的題

### 題 1（已裁：記一行、下一圈再跑）：daemon 的身體一次失敗，要不要整台停

**白話**：daemon 是一個開了窗的 aos-loop，所以照 aos-loop 的規矩「身體那次退非 0＝整個 loop 結束」。daemon 的身體（判官、llm kernel）只要失敗一次——`judge.json` 打錯一個字、身體的執行檔剛好在重建（A 線遇到的 `LaunchFailed`）——整台 daemon 就收工，底下全部 proc 睡下。資料不壞，再起就醒，但「硬體」因為一支程式的一次失敗就關機，有點反直覺。

**選項**：
1. **（推薦）daemon 的身體失敗＝記一行、下一圈再跑**：只改 aos-daemon（aos-loop 照舊）；stderr 一行「body failed (code N), retry next round」，state.json 記最後一次的碼。後果：身體一直壞時 daemon 一直跑、一直印（每圈一行；可只在碼變了時印）；要整台停改用 ctl `stop`。
2. **只有起不來（LaunchFailed）才重試，退非 0 照舊停**：後果：`judge.json` 壞照樣整台停。
3. **不改**：身體自己吞錯退 0（寫在 [aos-daemon docs/06](../../../../impls/aos-daemon/docs/06-結束碼等.md)）。

### 題 2（已裁：一起改成留表）：醒來之後過了 3 秒才失敗的，要不要也留在表上

**白話**：你定了「定義沒搬、醒不來的留 `stopped` 並寫原因」。現在的做法是看時間：wake／start 之後 3 秒內就退＝留 `stopped`＋原因；超過 3 秒才退＝當成正常結束、從表上拿掉，原因也沒了。實測醒來 3.5 秒才失敗的（例：身體要先連網路才發現壞了），表上就不見了，`ls` 看不到它曾經存在。

**選項**：
1. **（推薦）維持 3 秒、寫進文件**：大部分「定義沒搬」都是一啟動就失敗；後果：慢失敗的會消失，要看 log（`--enable-logs`）。
2. **醒來後第一次跑完之前退非 0 都留**：不看時間，看「醒來後有沒有成功跑完一次」。後果：daemon 要知道子 loop 跑了幾次＝要讀子項的 state.json，跟「daemon 不讀子項狀態」（C-52）打架。
3. **loop 型凡是退非 0 都留 `stopped`＋原因**（不只醒來的）：後果：改掉 11-02「自己結束就下表」；問腦的 `llm_<id>` 失敗也會留著，A 線 kernel「stopped 但沒跑完＝等」那條會一直等，要跟著改。

## 沒測到的

- 判官模式 2（procs-kernel）的收工與開門；`adopt: false`；procs_state 切檔壞掉；真跨帳號（只用另一個路徑模擬家目錄）。

## 使用者裁定（11-05，頂層轉達，選項原文）

- 題 1 →「記一行、下一圈再跑 (Recommended)」
- 題 2 →「一起改成留表 (Recommended)」：不分 3 秒內外，出錯結束一律留表標 stopped＋原因；3 秒只用來區分「起不來」與「跑一半掛了」的原因字樣。

上面「代定 6」被這兩題推翻。

## 裁定落實（11-05 晚，隊長）

- 題 1：`34f17425` aos-daemon 在建構子把 Loop 的身體收過來、自己在每拍最後跑：身體退 10 以外的非 0 或起不來＝stderr 一行 `aos-daemon: body … failed (code N), retrying next round`（碼或錯變了才印，好了印 `ok again`）、`state.json` 記 `body_code`、下一拍再跑；退 10 照舊收工。aos-loop 沒改（P-20 照舊，CONVENTION P-20 加 11-05 註）。
- 題 2：`c946aa72` loop 型退非 0 一律留 `stopped`＋reason；3 秒內＝`failed to start: exited within 3s of wake/start (code N)`，之後＝`failed while running: exited with code N: <stderr 最後一行>`。`d1ed1abe` aos-llm-kernel：列有 reason＝當收尾（看碼、該重掛先 procs_removed、記 remount、列拔了才再掛）。NORMS N-28「11-05 晚補 ⑤⑥」。
- 實測（/tmp/edgeD1-*）：身體 0→3→5→0 各一行、底下 proc 照顧著；llm daemon 的 kernel.json 改壞 1.5 秒照跑、修好 ask 照答；問腦 loop kill -9 一次＝重掛答對、兩次＝`EndpointFailed`，表上不留列、不卡死。
- 落實時代定見 [edge-agent 落實時代定](../edge-agent/README.md#落實時代定可翻案)（同一批）；另：身體起不來時 `body_code` 記 1；身體退 10 時 state 的 phase＝`stopped`（原本 `done`）。
