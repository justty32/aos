← [notes 索引](../README.md)｜[proto5 README](../../README.md)

# daemon 跟 kernel 分開的理由：「daemon 要 sudo 才能切使用者」審查（2026-09-24）

**只是審查，沒改程式、沒改規範。** 使用者原話：「關於為何要把 daemon 和 kernel 分開這件事，我想起來了，是因為當時想說可以透過切換使用者的方式來做權限，所以 daemon 就要 sudo……這個理由好像不太站得住腳？麻煩再去審看看。」

誰寫的：保留派、合併派兩個 Opus 各寫 memo 再互相反駁；astra 獨立意見兩次（同一顆模型，打折算）；實驗在這台 Manjaro 上跑（沒 sudo、沒建使用者、沒改系統設定）。

## 先講結論

1. **這個理由站不住。** 四份意見都同意。原因有三：
   - 不用 root 也切得成真的不同 uid（實驗 3：系統原本就配給你的 subuid），bwrap 牢根本不用切 uid。
   - **daemon 如果真的用 root 跑，反而更危險**：誰能往 `D/requests/` 丟一個檔，誰就等於能叫 root 跑任何程式。
   - 現在的 daemon 從來沒切過使用者。09-22 決定兩支時的理由是「kernel 崩了要有人管」，**沒寫權限**（[09-22 總結 §4 第 3 題](../2026-09-22-daemon-kernel-summary.md)）。你記得的其實更早：[proto2 身份筆記](../../../proto2/notes/tools/identity-and-env.md)寫「切身份靠 `runuser`，kernel 得用 root 跑」，proto4-1 也有要 root 的 `user` 欄位（沒測過）；proto5 沒帶過來。
2. **分開還剩別的理由，但加起來只撐得住「兩個角色、兩種行程」**。撐不住「一定要兩支執行檔」，也撐不住「兩個家、兩步開機、中間還夾一顆 kernel cpu」這個現狀。
3. **現在不用動。** 兩派吵完收斂到同一個折衷，astra 的方向也相容：**等 proto5-2 重寫 kernel 時，順路改成「開機合一、家不合一」**（見 §3）。
4. **權限：預設只走 bwrap 牢，daemon 永遠不用 root。** 真要切使用者，等出現「牢外也互不信任」的需求再做；做的話走 subuid，照信任群體分 uid，不照 cpu 分。

## 1. 切使用者一定要 root 嗎？

不一定。實驗全文在 [exp/README.md](exp/README.md)。

| 做法 | 要 root 嗎 | 擋得住 | 擋不住／代價 | 對「一個家一個主人」 | 啟動成本 |
|---|---|---|---|---|---|
| daemon 用 root 跑，孩子再 `setpriv` 降權 | **要**（實驗 1：不是 root 就 `Operation not permitted`） | 不同 uid 互相讀不到檔 | daemon 變成全系統最敏感的一支 | 貼近現在的父子關係 | 很小（沒量） |
| sudoers 白名單（`NOPASSWD` 限定指令） | daemon 不用，但你要先改系統設定 | 同上 | 白名單只限到「aos-exec」，inst 照樣能跑任何東西；**不同 uid 的孩子 daemon 殺不掉**，停機也要經 sudo | 多一層包裝，pipe、收屍都要重接 | 每次一個 sudo，沒量 |
| 系統層 `systemd-run -p User=`（你自己的 `--user` 換不了人，實驗 1c） | systemd 替你切，你要有授權 | 同上，還能加資源上限 | 孩子的爸爸變成 systemd，現在的 pipe、收屍要改接；上千個單元太重 | 不友善 | 沒量 |
| bwrap／`unshare -U` 的 `--uid` | 不用 | **只是換名牌**（實驗 2a、2b：照樣讀到別的家） | 擋住東西靠的是「沒掛進去」（2d），不是 uid | 很友善（L 隊的 `aos-jail`） | 0.72～1.19 ms |
| subuid 多 uid namespace（像 rootless podman） | 不用；用系統已配好的 `/etc/subuid`＋`newuidmap` | **真的擋住**（3b：A 讀不到 B 的家；3c：切不回去） | 開 namespace 的爸爸是「假 root」，讀得到所有家；**你從外面 `cat`／`rm` 不到孩子的家**（3e、3f）；祖先資料夾（HOME 是 700）擋路（3p）；uid 要有人分配記帳 | 家各有主人，但 `ls`／`cat` 看檔的習慣受傷 | 1.43 ms（每次開新的一層） |
| setgid＋群組權限 | 在自己已有的群組裡不用 | 適合「分享」 | 擋不住同一個 uid 的程式；群組可寫的 `requests/` 不等於「只能投、不能刪別人的」 | 好接 | 幾乎 0 |

一句話：**傳統換使用者要 root 或改系統設定；不用 root 的有兩條：bwrap 靠「不掛」擋，subuid 靠真的不同 uid 擋。** 成本都在 2 ms 以下（起一支 Python 約 20 ms），但只是 `/bin/true` 跑 200 次的平均，**不是上千顆常駐 cpu 的壓測**。

## 2. 分開還剩哪些理由？

| 理由 | 保留派 | 合併派 | astra | 我的判斷 |
|---|---|---|---|---|
| **root 切使用者** | 站不住 | 站不住 | 推不出 | **劃掉**。硬要講，它只說明「握權力的那支要小」。這是權限分離，前提是真的要切使用者，現在沒有 |
| **kernel 一格崩了只丟一格、改了不用重開** | 中 | 輕 | 強 | **真的，但這個好處來自「每格單獨開一次」，不是來自兩支程式。** 只要 tick 照舊單獨跑，合不合一都保得住 |
| **kernel 崩了有人收屍、拉回** | 中 | 輕 | 強 | 中。排程和收屍不該在同一個迴圈裡（這就是 I 隊②④的坑）。但「爸爸開 tick 當孩子」也做得到 |
| **daemon 極簡、不常改** | 輕～中 | 中 | 中強 | 中。還沒被時間證明（09-20 起 daemon 改 4 次、kernel 13 次）；idle-wait 會讓 kernel 更複雜，更該擋在長命迴圈外 |
| **一個 daemon 管多個 kernel 家、K2** | 輕 | 輕 | 中／弱 | 輕。**K2 不是權限牆**：同一個 uid，牢外的程式照樣讀得到 daemon 帳本（[cli-agents 審查](../2026-09-24-cli-agents/review-astra.md)） |
| **將來 subuid 路線下，namespace 要一支長命的爸爸撐著** | 重（限這條路線） | 認 | 條件式 | 條件式。真走這條路，這支爸爸就是 daemon、要小；**②④出局** |

**夠不夠撐「兩支程式」？** 撐得住「生死管理」和「排程」是兩個角色、兩種行程（大家同意）。撐不住「兩支執行檔」（astra：同一個 `aos` 的兩個子命令也行）。也撐不住「兩步開機、中間夾一顆 kernel cpu 接 tick 鏈」：這代價天天在付（開機交接、r5 順序陷阱），保留派也認了。

## 3. 對 I 隊結論的影響

[I 隊](../../../proto5-2/notes/2026-09-24-one-program/README.md)的結論是「現在不動；要動選③（分開＋kernel 帳本改 sqlite）」。**結論不變，理由要改：**

- 它本來就沒靠權限這條。
- **補一格 I 隊沒想到的：「開機合一、家不合一」**。兩派反駁後都接受，是③的加強版：
  - 一條 `aos up` 開機。長命的爸爸照舊當所有 cpu 的爸爸（spawn、`restart:true`、停機階梯不變）。
  - 時間到或 `K/requests/` 有新檔，爸爸就開一格 `aos-kernel tick` 當孩子、不等它。**拿掉 kernel cpu、tick 鏈、開機交接。**
  - tick 照舊每格單獨開一次：崩潰隔離、改了下一格就生效都保得住，也不會「自己等自己」。
  - **`D/`、`K/` 仍是兩個家**（不然一個家有兩個寫的人，撞 cpu 範式）；同時只准一格 tick（用鎖）。
  - 爸爸只看檔在不在、不讀內容；不用 root。
  - 代價：改兩條已拍板前提（daemon「不認識 kernel」、kernel「在 kernel cpu 上一格接一格」）；爸爸多 80～150 行（同時只准一格、tick 卡住、連敗要不要停）；開機交接那批崩潰測試重寫。proto5-2 本來就要重寫 kernel，順路做。
- **補一條否決條件**：將來若切使用者，把排程搬進長命行程的②④直接出局。
- 延遲不是理由：[idle-wait](../../../proto5-2/notes/2026-09-24-idle-wait/README.md) 的停車＋喚醒就能解。

## 4. 權限這條線怎麼走

**預設：同一個 uid＋bwrap 牢，daemon 永遠不 root。** 信任 daemon、kernel、cpu 這些框架；不信任模型能控制的程式。

- 工具照 [L 隊提案](../2026-09-24-agent-access/README.md)進 `aos-jail`：只掛表裡的資料夾、清環境、預設沒網路、不掛 `D/`、`K/`、K2。
- **Claude Code／Codex 這種會自己跑 shell 的 CLI agent，要把整支連子孫都關進牢**，只包 aos 工具入口不夠（astra）。
- bwrap 擋得住多少，看參數給得多緊；只加 `--uid` 等於沒擋（實驗 2）。

**什麼時候兩者都要**：「牢外也互不信任」時（別人來投單、兩群 agent 連框架層都要互不相見），牢外再疊一層 subuid：

- 由 daemon 開一次 namespace，孩子降權；bwrap 照舊留著。
- **按信任群體分 uid，不要一顆 cpu 一個**：agent 會換 cpu，身份不該跟著座位走。
- 代價：你從外面看不到、刪不掉孩子的家，要多一支小工具進去看。

不選 root daemon、sudoers、系統層 systemd：都要改系統設定。

## 5. 要使用者拍的（附預設）

1. **「切使用者所以 daemon 要 sudo」這條理由撤掉，並在 daemon 規範寫一句「daemon 永遠不用 root，隔離走 bwrap」？** 預設：撤、寫；分開的理由改成「生死與排程崩了互不拖累」。
2. **現在要動 daemon／kernel 的分法嗎？** 預設：不動（同 I 隊、同 WAIT_USER C 段「規模先不動」）。
3. **proto5-2 重寫 kernel 時，要不要順路做「開機合一、家不合一」（一條 `aos up`、爸爸開 tick、拿掉 kernel cpu 與交接、`D/`／`K/` 仍兩個家）？** 預設：要，跟帳本換 sqlite 同一次；不做的話至少包一支 `aos up`／`aos down`。
4. **隔離範圍：工具＋整支 CLI agent 進牢，框架層（daemon／kernel／cpu）受信任？** 預設：是。沒 bwrap 就拒跑。
5. **現在就替 agent／cpu 配不同 uid 嗎？** 預設：不配。等出現「牢外互不信任」的需求再開題，到時走 subuid、按信任群體分。

## 附錄

| 檔 | 內容 |
|---|---|
| [task.md](task.md) | 給子隊和 astra 的任務書 |
| [exp/README.md](exp/README.md) | 實驗四組 |
| [memo-keep.md](memo-keep.md) | 保留派 |
| [memo-merge.md](memo-merge.md) | 合併派（「範式不動」「30～50 行」兩句已在反駁更正） |
| [rebuttals.md](rebuttals.md) | 互相反駁 |
| [codex-astra.md](codex-astra.md) | astra 兩份獨立意見 |

## 使用者裁決（2026-09-24）

1. 撤掉「daemon 要 sudo 切使用者所以跟 kernel 分開」這條理由；daemon 規範加一句「daemon 永遠不用 root，隔離走 bwrap 牢」（已寫進 [spec/daemon/README.md §8](../../spec/daemon/README.md)）。
2. daemon／kernel 分法現在不動；等 proto5-2 重寫 kernel（帳本換 sqlite）時，順路做「開機合一、家不合一」（§5 原第 2、3 題合併拍板）。
3. 隔離範圍：第一版只有工具進牢，Claude Code／Codex 這種 CLI agent 先不進牢。
4. 現在不替 agent／cpu 配不同 uid（subuid），有需求再開題。
