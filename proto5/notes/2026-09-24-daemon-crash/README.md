# daemon 崩潰窗口測試 C-2／C-3（2026-09-24）

← [proto5 README](../../README.md)｜規範：[daemon.md](../../spec/daemon.md) §2、§6.1｜題目出處：[impl-review-report.md](../2026-09-23-rearch/impl-review-report.md) C 節｜上一輪：[impl-fix-round1.md](../2026-09-23-rearch/impl-fix-round1.md)（跳過 C-2／3）

**結論：兩個窗口 daemon 都照規範收斂，產品程式一行沒改。** 新測試 [test_daemon_crash.py](../../lib/test/test_daemon_crash.py) 共 11 條，
單獨連跑 20 次 20 次全過，四份平行（加壓）再跑 20 次也全過；全套 1016 → **1027 條全綠**；跑完沒有殘留行程。

## 怎麼卡、怎麼 KILL

- **HUB（測試專用 subreaper）**：所有 daemon 都由它拉起。daemon 被 KILL 後，孤兒孩子歸它收屍。它先用 `waitid(WNOWAIT)` 偷看死因、寫進 `reaped.jsonl`，**寫完才真的收屍**——所以殭屍消失之前死因一定已經記好。
  收尾時只砍它自己還沒收屍的直接孩子（pid 不可能被別人重用），連「測試還沒記到 pid 就失敗」的孤兒也會被收掉。
- **GATED（閘門 daemon）**：跑的是真的 `aos_daemon.run()`，閘門靠在測試 driver 裡換掉幾個函式（像既有的 CLOCK_DRIVER），**產品程式沒有任何測試掛鉤**。
  環境變數 `AOS_TEST_GATES` 點名的那一步寫 `<點>.reached` 後就停住，測試再送真的 `SIGKILL`。沒點名的步驟照常走。
  另外記三樣證據：每次 fork 的孩子（查「有沒有多拉一顆」）、每次寫回音（查「回音只寫一次」）、**第一次寫自己 state 那一刻對上一任每個孩子 `kill(pid,0)` 的結果**（查「舊孩子死透才公布新表」，當場探、沒有競態）。
- 孩子兩種：真的 `aos-cpu`（有 info.json 的 cpu 家，用來看「沒收到 go 就一個檔都沒碰」），和 `_daemon_util.CHILD` 的 `kill` 模式（不理 TERM、不讀 stdin，EOF 叫不停，逼新任走到最後一階 KILL）。
- 時間參數：`poll_ms` 5、`stop_wait_ms`／`kill_wait_ms` 各 80。

## C-2：daemon 握手中段被 KILL

第一任卡在 spawn 的某一步 → SIGKILL → 第二任起來接手。

| 閘門（卡在哪） | 孩子 | 預期（規範） | 實際 |
|---|---|---|---|
| `spawned`：已 fork、孩子表還沒寫 | 真 cpu | §2：孩子讀到 EOF、沒 go 就退，家不碰；新任不知道它、也不用找；原單對帳成 `Interrupted` | 孩子退 0、cpu 家只剩 info／inst；第二任表空、`Interrupted` 一份、原單刪掉 ✔ |
| `before_go`：表已寫、go 還沒送 | 真 cpu | 同上；表裡有它，新任照 §6.1 等它消失 | 同上；第二任公布時它已不在 ✔ |
| `go_sent`：go 已送、回音還沒寫 | kill 模式 | §6.1：新任 TERM → 等兩段 → KILL 整組，死透才對帳、才公布新表 | 孩子被 SIGKILL（hub 記 signal 9）、公布那一刻 `kill(pid,0)` 已不在；`Interrupted` 一份 ✔ |
| `go_sent` | 真 cpu | cpu 讀到 EOF 溫和停；客戶重送 spawn | cpu 退 0、current 清空；重送 spawn 拉**新的一顆**（新 pid），fork 總數 2 ✔（見歧義） |
| `responded`：回音已寫、原單還沒刪 | kill 模式 | §6.2 對帳：回音在＝只刪原單、不改回音 | 原單刪、回音 bytes 不變且只寫過一次；但回音裡那個 pid 已被新任砍掉（見歧義） ✔ |

## C-3：接手中的 daemon 再被 KILL

第一任卡在 `go_sent`（孩子 kill 模式、current 有一則 spawn）→ KILL；第二任卡在接手某一步 → KILL；第三任（或第四任）接手。

| 閘門 | 被 KILL 時的狀況 | 預期 | 實際 |
|---|---|---|---|
| `prev_term`：已 TERM 舊孩子 | 孩子還活著（TERM 被忽略） | state.json 還是第一任的原樣；第三任重新 TERM → KILL，死透才公布 | 中間 state 與第一任完全相同；第三任公布時孩子已被 SIGKILL ✔ |
| `prev_term` × 2 | 第二、三任都死在這 | 第四任照樣收斂 | ✔ |
| `prev_kill`：已 KILL 整組 | 孩子隨即死 | 第三任看到不在、直接對帳 | ✔ |
| `prev_done`：舊孩子死透、還沒對帳 | 原單在、回音不在 | 第三任對帳成 `Interrupted` | ✔ |
| `reconcile_interrupted`：`Interrupted` 已寫、原單還沒刪 | 兩個都在 | 第三任只刪原單、不重寫回音 | 回音 bytes 不變、全程只寫一次 ✔ |
| `reconciled`：對帳完、新 state 還沒寫 | 原單已刪 | 第三任對帳什麼都不做、公布空表 | ✔ |

每一條都另外驗：中間那任死後 state.json 跟第一任一模一樣（沒提前清表）、全程只 fork 一次、最後 `stop` 退 0、`pid` 0、表空。

## 修了什麼

- **daemon 程式：沒改。** `run()` 的順序本來就是「等舊孩子死透 → 對帳 → 才寫新 state」，而且新 state 在接手完成前不落地，所以接手途中再死，下一任讀到的一定是舊表。
- 為了確認測試真的抓得到錯，我暫時把程式改壞五種再跑（跑完還原）：先寫 state 再接手、永不 KILL、先對帳再接手、先送 go 再寫表、對帳不看回音就重寫——**五種都有測試變紅**（2～9 條不等）。
- 測試本身照 astra 審查（[review-report.md](review-report.md)）改了四處：公布順序改成在 daemon 內當場探 `kill(pid,0)`（原本「看到 state 再讀收屍名單」有競態）；加回音寫入次數、fork 次數；`responded` 那條先等孩子 ready 再接手（否則 TERM 可能搶在忽略訊號之前）；hub 收尾改成砍自己所有未收屍的孩子。第一版跑的時候就真的漏過一顆孤兒（測試在記 pid 前失敗），已手動清掉、改法就是這條。

## 20 次結果

```sh
cd proto5/lib
for i in $(seq 20); do PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p test_daemon_crash.py -v || echo FAIL $i; done
```

- 單跑 20 次：20 OK（每次約 3.4 秒、11 條）。
- 四份平行 × 5 輪（加壓）：20 OK。
- 全套 `python3 -m unittest discover -s test`：1027 條 OK（約 47 秒）。
- 殘留檢查：`pgrep` 只看到另一個 session 的試玩 daemon（`scratchpad/play4-*`），不是這條線的。

注意：任務書寫的 `python3 -m unittest test.test_daemon_crash` 這種寫法在 `proto5/lib` 下跑不起來（`test/` 沒有 `__init__.py`，`_daemon_util` import 不到；既有的 `test.test_daemon` 也一樣），所以改用 `discover -p`。

## 歧義（照最保守的解讀做，規範正文沒動）

1. **§2 的「冪等」跨不跨 daemon 重啟**：§2 說「崩在寫表之後、回音之前……客戶收不到回音會重送 `spawn`，同名同目標 → 回它的 pid（冪等）」；
   但 §6.1 說新任先把上一任的孩子弄死、表從空開始、不收養，而 §3 末說原單照範式對帳（會拿到 `Interrupted`）。兩句接不起來。
   我照 §6.1 讀（程式本來就這樣）：**冪等只在同一任 daemon 還活著時成立**；daemon 被 KILL 後客戶拿到 `Interrupted`，重送 spawn 會拉新的一顆。
   已在 daemon.md 檔尾〈實作補記〉補一句。astra 的讀法相同。
2. **`responded` 窗口的回音會「說謊」**：回音已寫 `{"pid": X}`、原單還沒刪就崩，新任照規範把 X 砍掉、只刪原單不改回音——客戶會拿到一個已經死掉的 pid。
   這符合「daemon 重啟後 kernel 要重新 boot」（§5），但規範沒明說回音裡的 pid 可能已失效。沒改，攤給你看。

## 順手看到、不在這條線範圍的

- `_previous_children` 碰到 `kill(pid,0)` 回 PermissionError（pid 被別的使用者的行程重用）時當成活著，接著送 TERM 會丟 PermissionError、daemon 啟動失敗退 1，舊表保留——不會卡死，但也不會自己好。規範已把 pid 重用列為「機率可忽略」。
- `go_sent` 閘門精確說是 `_send()` 回來之後；控制 pipe 塞住時 go 可能還在 `pending` 裡沒真的寫出去。測試用的孩子都在讀，不影響結論。

## 檔案

- 測試：[lib/test/test_daemon_crash.py](../../lib/test/test_daemon_crash.py)（HUB、GATED 兩段 driver 都在檔頭）
- 審查任務書／回報：[review-task.md](review-task.md)、[review-report.md](review-report.md)（codex gpt-6-astra，唯讀；回報的四條測試漏洞已照改）
- 文件同步：[lib README](../../lib/README.md) 測試表加一列、總數；[proto5 README](../../README.md) 總數；[daemon.md](../../spec/daemon.md) 檔尾〈實作補記〉一句
