做完減法之後 daemon 的職責：daemon 只提供資訊與工具，判斷與使用全交給 kernel；資訊與工具用 Unix 路徑 `/proc/<daemon PID>/cwd/xxx` 存取，daemon 自己住進只有資訊與工具的小世界；只開給一個地位像 Linux kernel 的 kernel，其他 proc 用 Landlock 擋，擋不住訊號的部分之後要求較新的 Linux。

# daemon 的職責（11-26 午後，公司）

← [2026-11-26](README.md)｜前情：[daemon當容器-1125](../25/daemon當容器-1125.md)（做減法、五樣）、[aospl循址與元介面-1126](aospl循址與元介面-1126.md)、[sky-1125 小實驗](../../../../proto9/experiments/sky-1125/README.md)

使用者原話逐字在 [9p-proc-1125](../25/9p-proc-1125.md) 第 64 段起。這份只留整理後的原意、定了的、還沒定的。

## 前提（11-25 晚第四輪已定）

daemon 只管碰 Linux 權力的五樣：起收行程（自己 PID namespace 的 1 號）、組天空（每隻 proc 一個 mount namespace）、給身分（uid）、起動前上鎖（Landlock、seccomp、cgroup 上限）、把開關發出去（cgroup 檔等）。其餘都歸 kernel。

## 定了的

1. **daemon 只提供資訊與工具，實際判斷與使用交給 kernel。**（第 65 段）
   - 資訊＝發生了什麼：起了哪些行程、名字、活著或死了、結束碼、登記了哪些 kernel、每個天空掛了什麼。
   - daemon 不判「接下來該怎樣」：死了要不要重起、卡住了沒，都由 kernel 讀資訊後決定，再用 daemon 的工具去做。
   - 照這條，現在 C++ aos-daemon 的「讀 proc 的 `status` 判卡住」、`aos_obey`、自動重起的判斷、替 proc 記信箱與 persists，都不該在 daemon 裡。
2. **資訊與工具用 Unix 路徑存取：`/proc/<daemon PID>/xxx`。**（第 65 段）
   - `/proc/<PID>/` 底下是 Linux 生的，塞不進檔；實際走 `/proc/<PID>/cwd/xxx`（daemon 站進自己擺出來的目錄）。現在的 aos-daemon 已經這樣做（印 `export AOS_ROOT=/proc/<PID>/cwd`）。
   - 天空裡 daemon 是 1 號，所以天空裡寫 `/proc/1/cwd/xxx`，不用知道 PID。
3. **daemon 自己住進只有「資訊＋工具」的小世界。**（第 66 段，選 A）
   - 起因：sky 實驗量到同帳號的 proc 讀 `/proc/1/root` 就看到整台機器，當時用 non-dumpable 擋，但那也會鎖住 `/proc/1/cwd`。
   - daemon 換根成只有資訊與工具的目錄；組天空要用的外面檔案，換根前先打開握著。這樣 `cwd`、`root` 看進去都不會露出整台機器，不用 non-dumpable。
4. **資訊與工具只開給一個 kernel，地位像 Linux kernel。**（第 66 段）其他 proc 與其他 kernel 不直接碰 daemon。
5. **擋其他 proc 用 Landlock。**（第 67 段，選甲）除了那個 kernel，其他 proc 起動前各進一個自己的 Landlock domain。
   - Linux 6.6（公司 WSL，ABI 3）只擋得住讀 `/proc/1/...`，擋不住送訊號；同帳號的 proc 還能對 daemon 送 SIGTERM（daemon 一收，底下整片收掉）。
   - 使用者：之後就要求較新的 Linux 版本（訊號、abstract socket 的擋法要 6.12 以上）。
6. **工具先做可寫的檔。**（第 68 段，選 A）daemon 擺一個檔，寫一行進去 daemon 就照做（像現在的 `procs_ctl`）。照 exec／before／after 那套的可執行檔以後當外層包上去，內部就是去寫這個檔（可執行檔用呼叫者的身分跑，本身沒有 daemon 的權力）。
7. **資訊與工具的清單照草稿。**（第 69 段）
   - 資訊（每隻 proc 一份）：名字、PID（講明哪一層）、活著或死了、結束碼或訊號、起動時間、天空表（像 Plan 9 的 `ns`）、uid、上了哪些鎖。
   - 工具（同一個可寫檔，一行一個指令）：`start <設定檔路徑>`（名字、程式與參數、天空、uid、鎖都寫在設定檔）；`kill <名字> <訊號>`（沒有「好好停」，要好好收由 kernel 先 SIGTERM、等一陣子再 SIGKILL，等多久它定）；`mount`／`umount <名字> …`（跑的時候改天空）；`forget <名字>`（把死掉的從表上拿掉）。
   - 開關：每隻 proc 的 cgroup 資料夾（`cpu.max`、`memory.max`、`cgroup.freeze`）直接擺進資訊，不另做工具。
   - 不在 daemon：自動重起、判卡住、准不准；kernel 登記表（哪些 kernel 提供哪些名字）改歸那一個 kernel，daemon 只照 `start` 給的天空掛。
8. **主 kernel 怎麼來**（第 70 段；名字先叫「主 kernel」）：daemon 起動參數指定是哪支程式，daemon 起來第一件事就起它；它是唯一不進 Landlock 的 proc，其他 proc 都由它對 daemon 下 `start` 起出來。使用者在外面跟 daemon 同帳號，也讀寫得到 `/proc/<daemon PID>/cwd`，留著方便除錯。
   - 它死了怎麼辦（第 71 段）：daemon 照起動參數預先寫好的規則做，判斷還是在起 daemon 的那一層（像 systemd 的 `Restart=`）。預設 `restart`：重起，但有上限（60 秒內死超過 5 次就不再起，daemon 結束、底下整片收掉）；另一個選項 `exit`：不重起，daemon 直接結束。主 kernel 重起後讀 daemon 的資訊接回去；它自己記憶體裡的東西（kernel 登記表、做到一半的判斷）要留就自己寫 persists。

## 實作時定的（[aos-daemon2](../../../../proto9/cpp/aos-daemon2/README.md) 第一版之後）

1. **`ctl` 做完才回。**（第 72 段，選 B）做下去才出錯的（設定檔讀不到、程式起不來、掛載失敗）也要讓寫入失敗；aos-procfs 多一種「做完才回」的模式。`start` 的做完＝程式 exec 起來了。
2. **主 kernel 從自己天空裡的固定位置讀寫 daemon 的目錄，不給任何權限。**（第 73 段，選 B）實測：讀別人的 `/proc/<PID>/cwd` 要同帳號且自己的權限包含對方的；daemon 有一整套權限，主 kernel 沒有就讀不到。原本給 CAP_SYS_PTRACE（代價是能 ptrace daemon），改成把目錄掛進主 kernel 的天空。`/proc/<PID>/cwd` 留給外面的使用者。**A 也保留**（第 74 段）：預設走天空裡的固定位置，設定裡可以選給主 kernel CAP_SYS_PTRACE、改走 `/proc/1/cwd`。其他 proc 也沒有權限，光這條規則就讀不到 daemon 的目錄；Landlock 要擋的只剩訊號（6.6 擋不住，之後要求較新的 Linux）。
3. **小世界裡留著 `cgroup/`。**（第 75 段）每隻 proc 資訊裡的 cgroup 連結指向它；`/proc/<PID>/root` 只有外面的使用者讀得到。
4. **`procs/<名字>/` 是真的資料夾，`forget` 了就消失。**（第 76 段，選 B）aos-procfs 要能拿掉資料夾（連同底下的檔），不再用 `slots/<號碼>/` 加連結。合 aoslua：`procs/` 是一張 table，列出來的就是還在的名字。

5. **主 kernel 天空裡 `/aos`、`/cgroup` 兩個名字保留。**（第 77 段，照現在）`/aos` 是 daemon 的目錄（底下 `status`、`ctl`、`procs/<名字>/`）；`/cgroup` 是 cgroup 夾，跟小世界擺法一樣，`procs/<名字>/cgroup` 的相對連結在兩邊都通。主 kernel 的天空設定不能用這兩個地方。`procs/<名字>/` 裡草稿外多的 `config`（設定檔路徑）、`ns_check`（實際掛載對不對得上天空表）留著（第 78 段「可以」）。
6. **天空表叫 `ns`。**（第 78、79 段）資訊檔 `procs/<名字>/ns`、對照檔 `ns_check`、設定檔的鍵 `"ns"`，三個一起改（原本叫 `sky`）。是 Plan 9 的意思；跟 Linux 的 `/proc/<PID>/ns/`（namespace 連結的資料夾）同名不同東西，路徑不撞。中文照舊叫「天空」。

## 我的讀法（使用者沒反對，照這樣記）

- 第四輪寫「把開關發給 kernel，發給哪個由 daemon 定」。照第 4 條改成：**daemon 只把開關交給那一個 kernel；要不要再分給排程、准不准等其他 kernel，由它決定。**

## 還沒定的

- 資訊與工具用 aoslua 的講法怎麼描（table、`__meta`、介面宣告）。
- 主 kernel 的正式名字。
