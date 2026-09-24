# kernel 崩潰窗口測試 C-7／C-8（2026-09-24）

← [notes 索引](../README.md)｜[proto5 README](../../README.md)｜規範：[kernel tick](../../spec/kernel/tick.md) 第 4～10 步、[帳本](../../spec/kernel/ledger.md)｜題目出處：[impl-review-report.md](../2026-09-23-rearch/impl-review-report.md) C 節｜上一輪：[impl-fix-round1.md](../2026-09-23-rearch/impl-fix-round1.md)（跳過 C-7／C-8）｜同手法：[daemon-crash](../2026-09-24-daemon-crash/README.md)

**結論：兩個窗口 kernel 都照規範收斂，產品程式一行沒改。** 沒有重派、沒有算兩次、沒有鬼回音、syscall 沒有重做。
唯一的「同名收到兩次」是 stop 箱：cpu 已經讀掉 stop、已經退出，下一格照規範重放，留下一份同名 stop（就是 B-10 那件事，見下）。
新測試 [test_kernel_crash.py](../../lib/test/test_kernel_crash.py) 共 15 條：單獨連跑 20 次，20 次全過；四份一起跑（加壓）× 5 輪也 20 次全過。
全套測試從 1100 條變成 **1115 條，全綠**。跑完 `pgrep` 查不到這條線留下的行程。

## 怎麼卡、怎麼 KILL

- **HUB**：借 `test_daemon_crash.HUB`，是測試專用的 subreaper（替死掉的父行程收孤兒）。真 daemon 由它拉起，daemon 底下的 cpu、tick 都是它的後代。kernel cpu 被砍時，另一個 process group 的 tick 會變成孤兒，由 HUB 收屍。
- **TICK（測試專用啟動器）**：boot 時把 `aos_kernel_boot.CLI` 換成它。帳本裡的 `cli` 因此就是它，之後鏈上每一格都經過它。
  它跑的是真的 `aos_kernel.main()`，只在測試程式裡替換幾個函式當閘門，**產品程式沒有任何測試掛鉤**。
  - 閘門是 `gates/<id>.json` 這個檔，寫著「哪一步、什麼條件」，只生效一次。命中後寫 `<id>.reached`（內容：pid、seq、細節），然後停住，等測試送真的 `SIGKILL`，或等測試放 `<id>.release` 讓它繼續。
  - 閘門點：`before_log`（append kernel.log 之前）、`before_post`／`after_post`（派工放檔的前後，分 cpu）、四箱各自的 `before_put`／`after_put`（ack、reply、stop、delete）、`start`（一格剛開始）。
  - 另外記 `trace.jsonl`：kernel 每次放檔、寫回音、刪原單，都記一筆「成功或 EEXIST」。拿來查同一個名字是不是只成功放過一次。
- **固定手法**：卡住第 N 格 → 先把第 N+1 格卡在開頭 → 再 KILL 第 N 格。第 N+1 格要等 kernel cpu 手上那格死了才會開始，所以不會有競態。
  接著讓接收者（cpu 或交件者）**先把該處理的處理完**，最後才放行第 N+1 格。
- 工作用真的 aos-cpu 跑一份 inst，每跑一次就往 `runs-<名>.txt` 加一行，用來查「副作用恰好發生一次」。

## C-7：已記結果、已送 ack，append kernel.log 之前被 KILL

| 測試 | 預期（規範） | 實際 |
|---|---|---|
| 反覆工作成功（`interval_ms` 設大，只跑一次） | 帳本已結清（runs 1、fails 0、cpu 閒、四箱空）；cpu 在下一格之前就把 ack 消化掉；之後不重算；log 缺那一格 | 全部照預期 ✔。kernel.log 沒有第 N 格，也沒有這件工作的 response 事件。被砍的那格由後面某一格記成 `tick_error`。cpu 沒被重拉 |
| 反覆工作失敗（退 3） | fails 只加一次 | runs 1、fails 1，之後不變 ✔ |
| `once`（交件者等回音） | 回音在第 10 步已經出貨；交件者讀到、ack 之後，不會再冒出來 | 回音只 link 成功一次，ack 之後就消失、不再出現；工作跑一次 ✔ |
| 同一窗口，改由 boot 接手（第 N+1 格卡著的時候重新 boot） | 新鏈接手，帳本照舊，不重跑 | runs 1、工作跑一次；舊鏈卡住的那格被收掉，就算還活著，放行後也在第 1 步自己結束，沒放任何檔 ✔ |

規範第 10 步已經承認「log 不保證涵蓋崩潰中途」。實測除了 log 缺一行之外，其他都對。
**astra 補充**：log 缺的不只工作結果。派工事件、舊 tick 的 `tick_error`，也可能在「已 ack、未寫 log」時丟掉。規範那句「不是完整的持久稽核紀錄」已經涵蓋，沒另外補句。

## C-8：出貨逐箱、逐顆，中途被 KILL

**派工**（第 8 步：先記帳再放檔，兩顆 cpu 在同一格各派一件）：

| 卡在哪 | 預期 | 實際 |
|---|---|---|
| cpu 0 已放；cpu 1 已記帳、還沒放 | 下一格第 6 步照帳本上的**原名**補放 cpu 1；cpu 0 不重放 | cpu 0 的檔全程只放一次；cpu 1 在第 N+1 格補放一次；兩件各跑一次、runs 1 ✔ |
| cpu 0 已放；cpu 1 還沒記帳 | 另一件留在 queue，下一格用新名字派 | 帳本 queue 還有它；之後在新的一格派一次；兩件各跑一次 ✔ |

**四張出貨箱**，每箱測兩種：「送出後、清帳前」和「記帳後、送出前」。

| 箱 | 送出後、清帳前（接收者先處理） | 記帳後、送出前 |
|---|---|---|
| acks | cpu 先把回音和 ack 都消化掉，下一格用新一格的 seq 再放一份不同名的 ack（規範 §1.3 允許）。回音已經不在，所以第二份無害；cpu 沒有多出回音、也沒被重拉 ✔ | 回音留著，下一格放 ack，放一次 ✔ |
| replies | 交件者讀到回音、放 ack；下一格重放時碰到 EEXIST，接著第 5 步刪回音。**沒有鬼回音**（第 4 步出貨一定在第 5 步收 ack 之前，這個順序是關鍵）✔ | 下一格放一次 ✔ |
| deletes | 原單已刪；下一格再刪是 ENOENT；syscall 沒重做（add 不給 name，重做的話會多出行程 "1"，實測沒有）✔ | 原單還在，但已記在 deletes；下一格第 4 步先刪、第 5 步看不到它；沒重做 ✔ |
| stops（cpu 0） | **cpu 0 讀掉 stop、退 0、從 daemon 表上消失；下一格重放，在它家留下一份同名 `stop-<chain>.json`**。下次 boot，新的 cpu 0 讀到就退 0，下一格第 7 步看它不活就再拉起來；之後工作照常跑 ✔（見歧義 1） | 下一格放，三顆都停 ✔ |
| stops（kernel cpu，最後一筆） | kernel cpu 讀掉 stop 就退，下一格不會再跑；帳上留 `stops:["k"]`，下次 boot 丟掉；沒有重放；新鏈照常跑 ✔ | — |

## 修了什麼

- **kernel 程式：沒改。** 規範本來的順序就守得住：派工先記後放、出貨先記後放並且逐筆清帳、第 6 步「兩個都不在才補放」、第 4 步出貨在第 5 步收 syscall／ack 之前、log 最後才寫。
- **故意弄壞五種**，確認測試抓得到（跑完已還原，`git status` 只剩新檔）：

| 改壞的地方 | 紅幾條 |
|---|---|
| B1 派工先放後記 | 2（兩條派工窗口：一件跑兩次） |
| B2 出貨先清帳再放 | 9（四箱全抓到：ack／回音丟失、stop 沒送到） |
| B3 派工不當場寫帳本（等格尾一起寫） | 2 |
| B4 kernel.log 在出貨之前寫 | 3（三條 C-7） |
| B5 收 syscall 移到出貨之前 | 1（鬼回音那條：交件者 ack 後回音又被 link 回來） |

## 歧義與待拍（照最保守的讀法做，規範正文沒動；已在 [kernel impl-notes](../../spec/kernel/impl-notes.md) 補一句）

1. **stop 箱的「EEXIST 當已放」不夠用。** stop 的接收者讀完會刪檔，所以重放時分不出「還沒送到」和「送到而且已經處理完」。
   結果是一份同名 stop 留在已經停掉的 cpu 家裡。它跟 B-10（跨代 stop）是同一件事：
   - 工作 cpu：下次 boot 會自己好（多退一次、再拉一次）。
   - kernel cpu：它排在最後一筆，這個窗口不會重放給它，所以不會卡住鏈。
   測試把這個現況釘住了（兩次都 `ok`、檔案留著、boot 後收斂）。要不要修，跟 [impl-fix-round1](../2026-09-23-rearch/impl-fix-round1.md)「要使用者拍的 1」一起決定。astra 認為這算重複投遞、應該列待修。我沒修：修法（例如 boot 清掉舊 chain 的 stop、或重放前先看孩子還活不活）會改到規範的行為，要你來拍。
2. **ack 重放換名字**：規範 §1.3 說 ack 名稱帶「放的那一格」的 seq，所以重放一定是新名字；同一則回音會收到兩份 ack。astra 的讀法相同：允許。

## astra 審查（[任務書](review-task.md)／[回報](review-report.md)）

astra 說閘門都落在宣稱的窗口，替換的函式也確實被產品路徑用到。下面照它的回報處理：

- **已照改的測試漏洞**：
  - 補「失敗工作」的 C-7，驗 fails 只加一次。
  - 「同名只成功一次」的檢查把 K 的回音也納入。
  - deletes 兩條改成不給 name 的 add，這樣重做不會被 AlreadyExists 遮住。
  - 讀 trace／log 時只收完整的行，避免讀到正在寫的半行。
  - 補 kernel cpu 的 stop 窗口。
- **沒改、列在這**：
  - settle 只看 `last_seq`（一格開頭就更新），所以只保證「又多跑了至少三格」，不是嚴格的完成屏障。夠用，20＋20 次都沒 flaky。
  - HUB 收尾沒另外斷言「後代全清」。每次都用 pgrep 人工確認過：這條線沒留行程。
- **真 bug，但不在這兩個窗口裡，沒修**：`_daemon_call` 拿到 spawn 回音、還沒把 ack 寫進帳本就崩潰的話，下一格要嘛孩子已經活著、直接跳過 spawn，要嘛用新名字重送。舊的那則回音永遠沒人 ack，會一直留在 `D/responses/`（`aos_kernel_engine.py` 的 `_daemon_call`）。
  後果只是 daemon 家多一個檔，不影響排程。修法是「先記要 ack 的名字、再送」，會改到 kernel 跟 daemon 對話那段（§5），留給你決定。
- `collect()` 在 `discard=true`、原單和回音都不在時會一直 `continue`、卡住那顆 cpu。astra 和我都沒找到正常情況下走得到的路徑（`rm` 在兩個檔都不在時直接把 slot 清掉）。

## 20 次結果

```sh
cd proto5/lib
for i in $(seq 20); do PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p test_kernel_crash.py || echo FAIL $i; done
```

- 單獨跑 20 次：20 次 OK（每次約 8～9 秒、15 條）。
- 四份一起跑 × 5 輪（加壓）：20 次 OK。
- 全套 `python3 -m unittest discover -s test`：**1115 條 OK**（約 60 秒）。
- 殘留檢查：`pgrep` 只看到主 repo 一顆 14:40 起的 `aos-daemon boot`（不在 tmp 測試家，不是這條線的），以及 fix-r5 那隊 worktree 的測試行程。
- README 裡的測試數字沒改，留給合併時處理。

## 檔案

- 測試：[lib/test/test_kernel_crash.py](../../lib/test/test_kernel_crash.py)（TICK、BOOT 兩段 driver 在檔頭，HUB 借 test_daemon_crash）
- 審查：[review-task.md](review-task.md)、[review-report.md](review-report.md)（codex gpt-6-astra，唯讀）
- 規範補記：[spec/kernel/impl-notes.md](../../spec/kernel/impl-notes.md) 最後一條
