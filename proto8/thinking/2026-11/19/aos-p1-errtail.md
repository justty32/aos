線 aos-p1-errtail-1119（11-19）紀錄：體檢 P1 修好——aos-daemon 在 proc 失敗時只讀 stderr.txt 的最後 64 KB 取原因，不再整份讀進記憶體；1 GB／8 GB 的記錄檔下 daemon 峰值記憶體約 3 MB、不倒。

← [11-19 日索引](README.md)｜問題出處 [基底體檢 P1](aos-base-audit-1119/02-問題清單.md)

使用者 11-19：「錯誤記錄那條小修可以直接派」。照體檢 P1 方向 (a)「只讀檔尾幾 KB 取最後一行」，只修這一條：沒加輪替、沒限記錄檔大小、沒動 P3（daemon 身體同步）。

## 改了哪

- `cpp/aos-daemon/src/daemon/failure.cpp`：`fail_reason` 原本用 `aos::read_file` 把整份 `stderr.txt` 讀進來，只為了取最後一個非空行（最多 300 位元組）。改成檔內的小函式 `read_tail`：`fstat` 拿長度，用 `pread` 只讀最後 `ERR_TAIL` 個位元組（檔在讀時還在長，只讀到 fstat 那一刻）。原本的規矩照留：只看這一支起來之後寫的（`err_off` 之後）、檔比 `err_off` 短＝被截短過從頭算、起點切在行中間就從下一行開始、控制字元換空白、300 位元組不切在 UTF-8 字中間。新加的一種情況：`err_off` 在讀進來那段之前（檔尾切掉了前面），那段開頭當成切在行中間處理。
- `cpp/aos-daemon/tests/test_err_tail.py`（新）：兩支測試，見下。

## 上限定 64 KB，理由

那段文字只拿來取「最後一個非空行，截到 300 位元組」。64 KB 裝得下最後一行加上它後面一大串空白行，綽綽有餘；記憶體用量跟檔多大無關，固定在 64 KB 上下。代價：最後一行本身比 64 KB 還長時，原因取到的是那一行的後段（原本是那一行的開頭 300 位元組）——一行 64 KB 的錯誤訊息少見，沒另外處理。

## 修前修後（體檢的重現腳本 `repro/f-struct/e1_big_stderr.py`，抄到暫存跑，原夾沒動）

| 跑法 | 修前（HEAD 乾淨複本） | 修後 |
|---|---|---|
| `1024 0`（1 GB 稀疏檔、不限記憶體） | daemon 峰值 VmHWM 2,100,256 kB；job 19.0 秒才變 stopped | VmHWM 3,276 kB；4.1 秒 stopped（身體本來就睡 4 秒） |
| `1024 600`（位址空間限 600 MB） | daemon `Internal std::bad_alloc` 退 1，旁邊的 `ok` 一起不見 | daemon 活著，VmHWM 3,276 kB，原因 `failed while running: exited with code 3: boom` |
| `8192 600`（8 GB 稀疏檔，只修後跑） | — | daemon 活著，VmHWM 3,272 kB |

## 測試

- 新測試 `test_err_tail.py` 兩支：(1) proc 起來後把自己的 stderr.txt 撐到 512 MB（稀疏，不佔磁碟）再印一行退 3——daemon 活著、峰值記憶體增加 < 32 MB、旁邊 `ok` 還 running、ping 有回、原因結尾是檔尾那行；(2) 上一輩子留下 512 MB 的記錄、這一輩子什麼都沒印就退——原因不帶上一輩子的字，其他同 (1)。
- 修前的 build 跑這兩支：兩支都 FAIL（記憶體分別多了 2,097,088 kB、1,048,464 kB），修後兩支過。
- aos-daemon 全部測試（含新的兩支）126 支：過，skip 1（`test_cgroup`，這台沒有 systemd user）。
- 都在 `git archive HEAD` 抄出的乾淨複本上疊兩個檔、複本裡 `install.py` 後跑；repo 的 proto8 沒跑 install.py，活樹要等下一次 install.py 才換成新的 daemon。

## 順帶看到的（沒處理）

- 施工中途（13:51 前後）整個 `~/.aos/scratch/` 被別人清掉重開，連本線先建的修前複本與修前量測檔都沒了（修前數字照當時輸出抄進上表）；本線重建後做完。是哪條線清的沒查。
