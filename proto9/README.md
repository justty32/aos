proto9＝aos 第九版原型的起點：以「aos proc 介面」（一個 proc 的目錄長什麼樣、每個檔的格式）為中心從頭做；目前有介面草稿、一個 FUSE 小實驗（玩具）、C++ 小庫 aos-procfs 與一台最小的 daemon（aos-daemon）；還沒有信箱、沒有 agent。

# proto9

← [AGENTS.md](../AGENTS.md)｜上一版：[proto8](../proto8/README.md)（現在住的活樹還是 proto8）

## 為什麼開這一版

使用者 11-24、11-25 口述了 aos 下一步的形狀：一個 aos proc 就是一個活著的行程加上它擺出來的一個目錄，別人靠讀寫那個目錄裡的檔跟它往來（Plan 9／9P 的想法）。談了兩輪之後他說（逐字）：

- 「落檔...不算，我們直接起proto9」（11-25 下午；「落檔」指 ctl、status 是硬碟上的普通檔、proc 每隔一拍自己去讀的做法，proto8 的 aos-loop 就是）
- 問他範圍是不是「proto8 的 aos-loop、daemon 不改造成新介面，新介面在 proto9/ 從頭做」：「1.對。」
- 第一步用哪種做法（每隻 proc 用 FUSE 把自己的目錄掛出來）：「2.好，先用a.。」

原話全文、每一輪定了什麼：[9P proc 談話紀錄](../proto8/thinking/2026-11/25/9p-proc-1125.md)。事前查的十六份現況與對照報告：[架構規劃入口](../proto8/thinking/2026-11/25/aos-proc介面架構規劃-1125/README.md)。

## 現在有什麼

| 東西 | 狀態 |
|---|---|
| [docs/01-aos-proc介面草稿.md](docs/01-aos-proc介面草稿.md) | 草稿第 1 版：兩輪談話定下來的寫成一頁，沒定的標出來；含小實驗查到的 |
| [docs/02-可以抄的現成做法.md](docs/02-可以抄的現成做法.md) | 介面每一塊可以抄哪個現成做法（Plan 9、Maildir、cgroup、varlink、s6、systemd、FUSE 實務）；原始報告在 `docs/refs/` |
| [cpp/aos-procfs/](cpp/aos-procfs/README.md) | 第一塊正式程式：C++20 小庫（不靠 FUSE 的函式庫），讓一支行程把自己的目錄掛出來、照介面回答（`status`、`ctl` 的鎖與回饋、symlink、目錄裡的 unix socket）；附範例 proc 與 35 條測試 |
| [cpp/aos-daemon/](cpp/aos-daemon/README.md) | 第二塊：一台最小的 daemon（建在 aos-procfs 上）。自己是一隻 proc，另外擺出 `procs/`、`procs_ctl`（add／rm／stop／start／kill／register）、`procs_status`；收屍、清死掉的掛載、定期查卡住；底下的 proc 卡住時拖不住它（碰底下的事都交給帶期限的小行程）；可以嵌套。57 條測試。還沒有自動重起、sleep／wake、信箱 |
| [experiments/fuse-proc-1125/](experiments/fuse-proc-1125/README.md) | FUSE 小實驗（玩具 proc 與玩具 daemon，Python 標準庫）：這台不靠函式庫掛得起來、鎖做得出來；坑在死掉的掛載要有人卸、proc 卡住會拖住讀它的人 |

## 跟 proto8 的關係

- proto8 照常跑、照常修；不為新介面改造它（使用者 11-25）。
- 基礎先用 C++ 做（使用者 11-25），放 `cpp/<專案>/`，各夾自己的 Makefile；怎麼裝、agent 的身體放哪還沒談。
