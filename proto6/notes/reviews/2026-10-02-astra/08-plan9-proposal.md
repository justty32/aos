# Plan 9 思想實驗提案 審查（astra，2026-10-02）

## 一段話結論

**構想可留，但目前不能直接當實作配方。** 檔位 1 最適合先試，這個判斷合理；但它能省掉的身分與權限機制被說得太多。FUSE 的部分成本反而被高估。最小實驗縮成「單帳號、固定路徑、假 LLM」後，一兩天可作探索預算；原文全部驗收，還不足以支持這個估時。

下文 `01`～`08` 指提案中同編號的檔案。

## 必修

1. **實驗 A 的範例目前跑不起來。**  
   [08:33](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/08-檔位與最小實驗.md:33) 使用不存在的 `--unshare-mount`。overlay 選項要 bwrap 0.11，本機套件候選版是 0.9；空根目錄也沒放 Python、aos 與函式庫。[官方用法](https://github.com/containers/bubblewrap/blob/main/README.md)、[版本紀錄](https://raw.githubusercontent.com/containers/bubblewrap/main/NEWS.md)。  
   [08:72](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/08-檔位與最小實驗.md:72) 也不能直接把 daemon 的 inst 改成 argv 陣列；[現行程式](../../../../proto6/src/py/lib/aos_daemon_run.py) 把 inst 當路徑交給 `aos-exec`。**改法：先拿掉 overlay、補執行環境，將 bwrap 命令寫進 inst 檔的 `argv`。**

2. **`unshare＋bind` 不等於「只看得到白名單」。**  
   [05:51](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/05-agent與kernel的namespace.md:51) 漏了另建根、切換根、移除舊根。單純 unshare 會保留原掛載表，原本的 `/srv/...` 仍可到達。[mount_namespaces 手冊](https://man7.org/linux/man-pages/man7/mount_namespaces.7.html)。  
   [02:61](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/02-Linux上的工具與代價.md:61) 的「掛不了 ext4／9p＝RFNOMNT」也不成立；它仍可掛 bind、tmpfs 等。Plan 9 同樣要區分複製 namespace 與禁止重新取得服務。[fork(2)](https://9p.io/magic/man2html/2/fork)。**改法：最小實驗明定用 bwrap 的空根組樹，刪掉兩者直接等價的說法。**

3. **固定 socket 路徑，不能消掉身分，也不會縮成單項權限。**  
   [08:30](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/08-檔位與最小實驗.md:30) 把共用控制 socket 掛成自己的名字，服務仍然接受其他 inst 名稱。`take／peek` 也仍需要 [AOS_DAEMON_INST](../../../../proto6/src/py/lib/aos_mq.py)。  
   **改法：檔位 1 只承諾路徑固定，保留身分變數，明確覆寫 socket 路徑。** namespace 不會自動清掉環境變數；bwrap 的清除／設定選項必須實際使用。[bwrap 原始碼](https://raw.githubusercontent.com/containers/bubblewrap/main/bubblewrap.c)。

4. **inst 原字串不能直接變成目錄路徑。**  
   [03:39](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/03-daemon變成檔案伺服器.md:39) 說含斜線「天然成立」。但[現行測試](../../../../proto6/src/py/tests/test_daemon_config.py) 把 `a`、`./a`、絕對路徑當不同項；檔案路徑會把前兩者合併。**改法：完整編碼 inst 字串，或另用識別碼作目錄名。**

5. **tick 現況有舊說法殘留。**  
   [04:12](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/04-tick與inst變成目錄.md:12) 說 `tasks-blocked` 只看存在；[現行程式](../../../../proto6/src/py/lib/aos_tick.py) 已讀 `kinds`，只跳過指定類別。**改成：`tick-blocked` 只看存在，`tasks-blocked` 還看內容。**  
   同篇第 22 行也應改成「頂層物件中的 `tasks` 是陣列」，與 [schema](../../../../proto6/spec/protocol/schemas/tick-tasks.schema.json) 一致。

6. **實驗 C 會改掉廣播語意。**  
   [08:76](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/08-檔位與最小實驗.md:76) 把信放在門下，取信就刪。現行是[每位訂戶各有一份](../../../../proto6/src/py/lib/aos_daemon_mq.py)；共用一份會被第一位收件人刪掉。**改成每項自己的 mail 目錄，保留各自取信的狀態。**  
   第 26 行也不能把「peek 不取走」列為新收益，現在已經有。

7. **namespace 化不會自動讓 root 端消失。**  
   [07:21](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/07-推到極限與代價.md:21) 說 root 開啟、setuid 後只開 namespace 即可。但[現行主程式永久降權](../../../../proto6/src/py/lib/aos_daemon_account.py)後，要啟動其他宿主帳號，仍交給 root 端。**改法：保留 helper；若要移除，明列替代方法或放棄哪項能力。**

8. **FUSE 的一次 write handler，不保證就是一封信。**  
   [03:80](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/03-daemon變成檔案伺服器.md:80) 直接在 handler 收完整訊息。但 Linux 即使用 direct I/O，也可能依 `max_write` 拆成多次請求。[Linux 6.6 實作](https://raw.githubusercontent.com/torvalds/linux/v6.6/fs/fuse/file.c)。  
   **改法：依開啟的檔案累積資料，用換行或明確提交指令判定完成。** `/llm/N/request` 也要定義何時收完 JSON；這是正常 I/O 語意。

9. **Plan 9 事實表有幾處需要直接改字。**

   | 提案證據 | 修正 |
   |---|---|
   | [01:40](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/01-Plan9逐條對照.md:40)「不要環境變數」 | 有 `/env`；rio 本身也用環境變數找服務。改成「把許多介面統一成檔案操作」。[env](https://9p.io/magic/man2html/3/env)、[rio](https://9p.io/magic/man2html/4/rio) |
   | [01:26](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/01-Plan9逐條對照.md:26)「沒有 PATH」 | rc 有 `$path`。改成「優先用 union `/bin`，少依賴搜尋路徑」。[rc](https://9p.io/magic/man2html/1/rc) |
   | [01:18](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/01-Plan9逐條對照.md:18)「全部只講 9P」 | 改成「9P 統一檔案服務介面」。本機核心操作與其他應用協議不能一併算成 9P。[原作者論文](https://9p.io/sys/doc/names.html) |
   | [04:27](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/04-tick與inst變成目錄.md:27)「args 一行一參數」 | 實際是有引號規則的字串列表。刪掉「Plan 9 的作法」即可。[proc](https://9p.io/magic/man2html/3/proc) |
   | [01:20](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/01-Plan9逐條對照.md:20)「listen 也是 read 等待」 | 它阻塞在 open。改稱「blocking I/O」。[ip](https://9p.io/magic/man2html/3/ip) |
   | [05:96](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/05-agent與kernel的namespace.md:96)「factotum 永遠不交密碼」 | `proto=pass` 是例外。改成「集中管理秘密與認證操作」。[factotum](https://9p.io/magic/man2html/4/factotum) |

10. **Linux 的代價表也有幾處過度概括。**

   | 提案證據 | 修正 |
   |---|---|
   | [02:36](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/02-Linux上的工具與代價.md:36)「daemon 死＝hang」 | 正常退出、FUSE 連線關閉後，操作回錯。活著但不回覆才可能一直等。掛載點殘留與呼叫卡住要分開。[Kernel FUSE](https://docs.kernel.org/filesystems/fuse/fuse.html) |
   | [07:46](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/07-推到極限與代價.md:46)「一個等待占一條執行緒」 | pyfuse3 可用非同步等待。成本是管理未完成請求與取消，不必一請求一執行緒；它也有 asyncio 相容層。[pyfuse3](https://github.com/libfuse/pyfuse3/blob/main/README.rst)、[asyncio 支援](https://pyfuse3.readthedocs.io/en/latest/asyncio.html) |
   | [02:42](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/02-Linux上的工具與代價.md:42)「QEMU 已換掉 9P」 | QEMU 仍支援 9p local；移除的是 proxy backend。改成「部分共享目錄場景改採 virtiofs」。[QEMU 官方說明](https://www.qemu.org/docs/master/about/removed-features.html) |
   | [02:45](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/02-Linux上的工具與代價.md:45)「Linux 掛 9P 得 root」 | 限縮成 kernel v9fs。同篇第 21 行已列 rootless `9pfuse`。直接 FUSE 可以比較省事，但不是唯一可行路。 |

## 建議

- **四檔不要只按「介面改多少」估價。** [08:58](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/08-檔位與最小實驗.md:58) 的排序大致合理，但應改成：

  | 檔位 | 審查判斷 |
  |---|---|
  | 0 | 格式修改不難；信件持久化是另一項功能，應分開估。 |
  | 1 | 最適合先試；收益先限定為路徑組裝與可見範圍。 |
  | 2 | 明顯較大；主要工作是把既有協議接成檔案語意。 |
  | 3 | 假 LLM 展示可以小；額度、帳號與真 HTTP 整合不能用玩具行數估。 |

- **把一兩天改成探索時間盒。** [08:74](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/08-檔位與最小實驗.md:74) 同時要求動態目錄、假回應、阻塞讀取、Ctrl-C、卸載及 agent 整合。建議先驗「兩個視野、一個假回應、shell 能呼叫」。150 行與一天都不要當完成保證。

- **行為格式仍以程式與測試為正本。** [07:73](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/07-推到極限與代價.md:73) 要求把 ctl/status 格式寫進 spec，應改成連到 parser、測試與格式定義，符合[現行 spec 原則](../../../../proto6/spec/README.md)。

- **來源要能對到具體主張。** [02:67](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/02-Linux上的工具與代價.md:67) 目前只是來源名稱。效能數字應附測量條件；WSL「2026 改 DMA pool」應補直接 PR。union／overlayfs 則宜寫「近似替代」，避免誤認語意完全相同。

## 疑問

- **實驗 B 要驗檔案介面，還是額度強制？**  
  [05:66](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/05-agent與kernel的namespace.md:66) 的 `/llm` 存在與否，只表示能不能使用；呼叫次數、token 額度仍靠第 95 行的新服務管理。**建議先驗介面，不把額度強制算成第一輪已證明的收益。**

- **clone 要跟 fd 一起回收，還是留下持久請求？**  
  [05:86](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/05-agent與kernel的namespace.md:86) 的 `cat` 讀完會關 fd；若照 webfs，所有相關 fd 關閉後，號碼即可回收。[webfs 手冊](https://9p.io/magic/man2html/4/webfs)。**建議最小實驗保留 clone fd，完成後才關。** 自製服務尚未定回收規則，所以這條不列必修。

## 看過的範圍

提案全部九份；AGENTS.md、使用者偏好、現行 spec 原則；Python tick、daemon、ctl、mq、account/root 相關程式、測試與 schema。

外部核對涵蓋 Plan 9 的 9P、namespace、bind/union、proc、clone、factotum、plumber、rio，以及 Linux FUSE、v9fs、user namespace、bwrap、overlayfs、inotify。針對 Linux 6.6，FUSE 服務內部變化不會自動成為一般 inotify 通知，提案這點方向正確。

全程唯讀。未改檔、未 commit、未跑測試或掛載實驗。