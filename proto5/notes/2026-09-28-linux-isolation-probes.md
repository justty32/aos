# Linux 隔離：無特權 canary 實測

← [筆記索引](README.md)｜[重跑腳本](2026-09-28-linux-probes/README.md)｜[員工方向](2026-09-28-employee-identity.md)

## 問題與方法

確認目前執行環境能否用 Landlock 限制自有檔案讀寫，以及限制是否由子程序繼承。這是支援 root daemon 架構討論的局部證據，不是 root daemon 驗收。

2026-09-28，以 UID 1000 的普通使用者執行獨立 C 程序。它在新 scratch 裡只允許 `allowed/`，對同樣由我們建立的 `denied/` canary 嘗試讀寫。施加限制之前先設置 NNP；限制只套在該 C 程序及其後代，沒有套在主 agent shell 或 Python runner。沒有 sudo、帳號更動、系統設定更動或現有 daemon 啟動，也沒有存取 `/tmp/haha` 或他人的私密檔案。

## 環境觀測

本次 shell 回報 Linux `6.18.49-1-MANJARO`、x86_64，UID 1000、GID 1001。`/proc/1/comm` 為 `systemd`，`/proc/self/uid_map` 與 `gid_map` 都為 `0 0 4294967295`；可觀測到的 user/mount/net namespace 分別為 `4026531837`、`4026531832`、`4026531833`。這是執行環境的觀測，不以 namespace inode 或 PID 1 名称宣稱已證明不存在更外層容器。

`systemd-run`、`systemctl`、`busctl`、`bwrap`、`unshare`、`gcc`、`python3` 均位於 `/usr/bin/`。版本為 systemd `261.2-1-manjaro`、bubblewrap `0.12.0`。`unprivileged_userns_clone=1`、`max_user_namespaces=246988`。工具存在不代表已驗證 system bus 授權、root transient service 或 cgroup 配置。

## 實測結果

重跑指令：`python3 proto5/notes/2026-09-28-linux-probes/run.py`。本次 scratch 為 `/tmp/aos-landlock-probe-oowo3lo0`，返回 0，stderr 空白，gcc `-Wall -Wextra` 無警告。

```text
Landlock ABI=7
parent allowed read: PASS errno=0
parent allowed write: PASS errno=0
parent denied read: PASS errno=13
parent denied write: PASS errno=13
child allowed read: PASS errno=0
child allowed write: PASS errno=0
child denied read: PASS errno=13
child denied write: PASS errno=13
```

Python runner 在受限子程序結束後仍能讀取兩個 canary；`denied/canary` 內容未改變。這區分了真正的存取拒絕與檔案本身不存在、普通權限不允許等情況。

ruleset 處理 ABI 1 的檔案權利，並在 ABI 支援時加入 REFER 和 TRUNCATE。本次只實際測試已有檔案的 open/read/append-write 及 fork 繼承；沒有對上述每個權利逐項驗收，也沒有做 exec 繼承、網路、訊號、裝置、已開 FD 或跨 UID 驗收。新版 Landlock ABI 的額外權利沒有納入這個最小探針。

## 結論與設計邊界

在本次環境，無特權程序能自行設置 Landlock，對新開的檔案讀寫形成 kernel 強制限制，fork 子程序也受限。這讓「員工工具啟動時增加檔案限制」具有可實作證據；它不負責替程序取得另一個主機 Linux 身分。

Landlock 允許清單是限制既有權利，不授予 UID/GID 原本沒有的存取能力；讀寫限制也不等於把路徑名稱或整個檔案系統隱藏。產品仍需明確處理哪些權利必須存在、ABI 不足時如何拒絕啟動，以及繼承 FD 等邊界，不能把本探針當作完整 sandbox。

user namespace、subuid 映射與 namespace 內降權，由同輪[隔離方案調查](../../wf/workflows/investigations/proto5-linux-wall-feasibility.md)測試；本探針不重複執行，也不把別線的結論冒充為本腳本可重現的結果。

## API 來源

實驗前查讀 Linux kernel 的 [Landlock userspace API](https://docs.kernel.org/userspace-api/landlock.html)，依其 ruleset、path-beneath、NNP、restrict-self 與子程序繼承流程操作；常數與結構取自本機 `/usr/include/linux/landlock.h`，syscall 編號透過編譯器標頭解析。身分映射背景參考 [user_namespaces(7)](https://man7.org/linux/man-pages/man7/user_namespaces.7.html)。
