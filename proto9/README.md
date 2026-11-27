proto9＝aos 第九版原型的起點：以「aos proc 介面」（一個 proc 的目錄長什麼樣、每個檔的格式）為中心從頭做；目前有介面草稿、一個 FUSE 小實驗（玩具）、C++ 小庫 aos-procfs（含活著收信的信箱）、一台最小的 daemon（aos-daemon）與瘦身過的 aos-exec；還沒有 agent。

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
| [cpp/aos-procfs/](cpp/aos-procfs/README.md) | 第一塊正式程式：C++20 小庫（不靠 FUSE 的函式庫），讓一支行程把自己的目錄掛出來、照介面回答（`status`、`ctl` 的鎖與回饋、symlink、目錄裡的 unix socket）；另有 Maildir 式的信箱 `mailbox/`（proto8 的 `aos-post send` 原樣寄得進來）；附範例 proc 與 154 條測試；ctl 可選「做完才回」（做下去失敗＝寫入回 EIO，11-26）；掛上後可用 `remove_tree` 拿掉整個資料夾；狀態類檔案的欄位各宣告一次（`include/aos/fields.hpp`），純文字與 json 都由它產生 |
| [cpp/aos-daemon/](cpp/aos-daemon/README.md) | daemon（原本叫 aos-daemon2，11-26，照 [daemon職責-1126](../proto8/thinking/2026-11/26/daemon職責-1126.md)）：不用 root 開 user／PID／mount namespace、自己當 1 號；資訊與工具擺在 `/proc/<PID>/cwd`、自己住進小世界；工具是一個可寫檔 `ctl`（`start`、`kill`、`forget`、`mount`、`umount`）；主 kernel 由參數指定、唯一不進 Landlock，死了照 `restart`（有上限）或 `exit`；cgroup 資料夾直接當開關；`ctl` 做完才回；主 kernel 從天空裡的 `/aos` 讀寫、零權限；`procs/<名字>/` 是真的夾；每隻 proc 預設套內建 seccomp 清單（擋 44 個呼叫、不擋開 namespace 與 mount）；daemon 裡疊 daemon 在預設鎖下起不來（原因與選項見 README）；停止訊號只認外面與 init 送的；bind 來源卡住最多等約 10 秒就回 `EIO`、不拖住 daemon；`ns.json` 每筆記 `by`／`at`；`ns` 可疊 overlay；ctl 加 `restart-init`；daemon 目錄與每隻 `procs/<名字>/` 有介面宣告（`aos/ctl`、`aos/jsonpath`、`aos/proc`）；舊版 Linux（Landlock ABI<6）照跑、`status` 多警告；bind 可選 `beneath`、`ns.json` 每筆有 `real`；init 重起前殺舊 init 的 cgroup；握著的外面改 slave；ptrace 做法收掉；`kill` 送整個 cgroup；tmpfs／根可設大小。648 條測試。【擬】的與等使用者選的列在 README |。舊的 aos-daemon（判卡住、自動重起、register，73 條測試）11-26 使用者說收掉，最後一版在 commit `068bfb2fb`
| [cpp/aos-exec/](cpp/aos-exec/README.md) | 從 proto8 的 aos-exec 抄進來瘦身的「執行一個資料夾程式」小工具：拿掉 `AOS_STACK` 與 inst 單子，其餘行為照舊，不連 proto8；75 條測試。README 有一張「還能砍的」表，等使用者挑。還沒接上 daemon 的 `add`。用到的 json 標頭在 `cpp/third_party/` |
| [experiments/fuse-proc-1125/](experiments/fuse-proc-1125/README.md) | FUSE 小實驗（玩具 proc 與玩具 daemon，Python 標準庫）：這台不靠函式庫掛得起來、鎖做得出來；坑在死掉的掛載要有人卸、proc 卡住會拖住讀它的人 |
| [experiments/sky-1125/](experiments/sky-1125/README.md) | 天空小實驗（玩具 daemon 當 PID namespace 的 1 號，Python 標準庫加 unshare／setpriv，不用 root）：照純文字設定替每隻 proc 從零組天空、表跟 mountinfo 一對一；名字交給 kernel、只能往下傳自己有的、依賴鏈、llm proxy 當唯一出口、跑的時候改、上鎖、一起死、subuid、cgroup 凍結，`python3 run.py` 十項全過；發現同 uid 的 proc 會走 /proc/<PID>/root 看進 daemon 與別人的天空（daemon 自己 non-dumpable 擋得住；兄弟之間要不要每隻加 Landlock，等使用者選） |
| [experiments/channels-1127/](experiments/channels-1127/README.md) | 封路小實驗（家機 6.18，C 探測程式＋`python3 run.py`，七種設定 × 191 條路）：量 aos-daemon 底下的 proc 除了檔案路徑還碰得到什麼——預設設定下 SysV IPC 與 POSIX mqueue 三個方向全通（沒開 IPC namespace）、`/proc/1/net` 看得到外面整台的 socket 表、照 PID 改得動兄弟與 daemon 的 nice／上限；訊號、ptrace、網路、危險系統呼叫都擋住了；封路建議五條等使用者挑 |
| [experiments/pi-sandbox-1127/](experiments/pi-sandbox-1127/README.md) | pi 住進沙箱的原型（家機，`python3 run.py`；`--fake` 不花錢）：pi coding agent 整隻跑在 aos-daemon 的一隻 proc（預設的鎖、`net none`），腦只能經天空裡的 `/llm`（unix socket＋介面宣告、proxy 數次數與擋模型），read／write／edit／bash 都通，連外網、讀工作夾外的檔、繞過 `/llm` 都做不到；天空要的只有 `/usr`、`/dev`、node、pi 套件、可寫 HOME、工作夾、`/llm`；要使用者定的三題在 README 最後 |

## 跟 proto8 的關係

- proto8 照常跑、照常修；不為新介面改造它（使用者 11-25）。
- 基礎先用 C++ 做（使用者 11-25），放 `cpp/<專案>/`，各夾自己的 Makefile；怎麼裝、agent 的身體放哪還沒談。
