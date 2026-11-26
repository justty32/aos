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
7. **主 kernel 選怎麼讀寫 daemon 的目錄，用設定鍵 `daemon_access`**（第 80 段，照現在）：`mount`（預設，天空裡的 `/aos`、零權限）或 `ptrace`（留 CAP_SYS_PTRACE、走 `/proc/1/cwd`）。使用者說這塊不太懂，先這樣，用起來有問題再說。
8. **只有主 kernel 拿得到 daemon 目錄的環境變數，名字叫 `AOS_DAEMON`。**（第 81、82 段）其他 proc 不給，設定寫了也拿掉；每隻都給 `AOS_NAME`。原本叫 `AOS_ROOT`，改名跟 proto8 的 `AOS_DAEMON`（daemon 的資料夾）同一個意思，也免得看成天空的根。只動 aos-daemon2，舊 aos-daemon、aos-procfs、aos-exec 照舊。
9. **`status` 多一行 `main_kernel_access`**（第 83 段）：`mount /aos` 或 `ptrace /proc/1/cwd`，只是資訊、給除錯看。
10. **aos-procfs 的 `remove_tree` 不拿 ctl 與信箱**（第 84 段，照現在）：本身或底下有就整個不動、回失敗。現在 `procs/<名字>/` 沒有這兩種；以後 proc 的夾要放自己的 ctl 時，再做「先收好（停做事的線、等著的人回錯）再拿掉」。
11. **`ctl` 做下去才失敗一律回 `EIO`**（第 85 段）：原因在 `status` 的 `aos_ctl_error`；寫錯的照舊 `EINVAL`。不依原因挑不同號碼。
12. **主 kernel 在天空裡一定要是 uid 0，設定寫了別的 daemon 起動就拒**（第 86 段）：退出碼 2，跟 `/aos` 撞名一樣。uid 0＝外面的使用者本人、跟 daemon 同帳號；`ctl` 只有擁有者能寫、daemon 的目錄只放同帳號進來，其他 proc 用 subuid 的帳號，光這條就進不去。
13. **`start` 吃的設定檔照 aos-daemon2 現在的寫法，但 `ns` 每條改成一個 JSON 物件**（第 87、88 段）：一隻 proc 一個 JSON（`name`、`argv`、`env`、`cwd`、`ns`、`uid`、`locks`、`stdout`／`stderr`，不認得的鍵拒）；`ns` 照順序做，每條像 `{"type": "bind", "src": "/usr", "dst": "/usr"}`、`"rw": true` 才可寫，另有 `tmpfs`、`proc`、`dev`、`symlink`（`target`）。第 87 段先說字串照現在，第 88 段改口物件。
14. **天空表的資訊 `ns` 與 `ns.json` 共存**（第 88、89 段）：`ns` 照舊一個掛載一行文字（`種類 來源 位置 ro|rw [locked]`）；`ns.json` 是同一張表的 JSON 陣列、一個掛載一行，鍵跟設定檔一樣（`rw` 一定寫、被迫帶進來的多 `"locked": true`）。兩個檔一起量、一起更新；`ns_check` 照舊文字。
15. **`start` 的路徑只收外面（起 daemon 那一層）看到的絕對路徑**（第 90～92 段）：主 kernel 自己 bind 一個外面的夾、換成外面的路徑。相對路徑寫入當場 `EINVAL`：daemon 不知道「相對於哪裡」——外面寫的人的 PID 它看到 0、小世界裡也沒有 `/proc`。相對路徑交給**以後的外層程式**（第 6 條說的可執行檔）用呼叫者的身分與 CWD 換成絕對路徑再寫 `ctl`；手動就寫 `$PWD/…`。
16. **設定檔沒寫 `stdout`／`stderr` 就去 `/dev/null`**（第 93 段）：不再跟 daemon 的 stderr；主 kernel 也一樣。要留輸出就在設定檔寫路徑（daemon 不收 log）。stdin 照舊 `/dev/null`、每隻 `setsid`。
17. **daemon 結束怎麼收、起動那一層死了 daemon 走不走，都做成起動參數**（第 94 段）：預設照現在（結束時直接 SIGKILL、不給寬限；起動那一層死了 daemon 跟著走）；參數可以改成先 SIGTERM、等 N 秒再 SIGKILL，或起動那一層死了 daemon 留著。參數名字是 eca-aos 擬的。
    - 收尾的做法（第 95 段）：daemon 收到 SIGTERM，**先只對主 kernel 送 SIGTERM**，等設定的秒數（主 kernel 先結束就不等了；這段時間它死了不重起），再對所有 proc 送 SIGKILL。其他 proc 要不要好好收，由主 kernel 在這段時間自己處理。預設秒數 0，跟現在一樣。
18. **`forget` 時 cgroup 裡還有行程照舊拒，但可以選先清再刪**（第 95 段）：預設要先寫 `cgroup.kill`；`forget -k <名字>` 就是 daemon 先寫 `cgroup.kill` 再拿掉。做成指令上的選項，每次由主 kernel 決定。
19. **daemon 吃設定檔**（第 96、97 段）：`aos-daemon2 daemon.json`，鍵 `kernel`（路徑或整份主 kernel 設定；相對路徑以 daemon.json 所在夾為準——這個檔是起 daemon 的人給的，「相對於哪裡」清楚）、`on_kernel_exit`、`restart_limit`、`restart_window`、`exit_grace`、`on_parent_death`、`cgroup`、`subuid`；只有 `kernel` 必寫，其餘預設照現在；原本的起動參數照留、寫了蓋過檔；不認得的鍵拒；`status` 多一行 `config`。
20. **Linux 沒有 Landlock 時，主 kernel 以外的 proc 一律起不來**（第 98 段）：`start` 回 EIO。規則現在只擋建區塊裝置，用意是讓每隻進自己的 domain，新版 Linux 能擋訊號時程式自動加。
21. **退出碼照現在**（第 99 段）：0 收訊號、`exit` 時用主 kernel 的（被訊號殺 128＋N）、1 到重起上限、2 起不來。
22. **daemon 跟主 kernel 綁死的地方盡量都做成可選，預設照現在**（第 99、100 段，使用者：「感覺跟kernel耦合的有點緊...希望能多些設定」「希望可以比較多都可選的」）：可以沒有主 kernel（只從外面操作）；主 kernel 死太多次 daemon 可以留著；主 kernel 天空裡放 daemon 目錄的位置可以改；主 kernel 可以另外上鎖；daemon 的退出碼可以不跟主 kernel。鍵名 eca-aos 擬。
    - 第 101 段照擬的：`daemon.json` 的 `kernel` 可不寫、`on_restart_limit exit|stay`、`exit_code kernel|own`；主 kernel 設定的 `daemon_path`（預設 `/aos`，cgroup 夾跟著放同一層的 `cgroup`）、`locks.landlock`（預設不進）。主 kernel 的 uid 照舊要 0。
23. **天空裡的 uid 最多到 65535**（第 102 段）：0＝使用者本人，N＝subuid 範圍第 N 個；範圍小就照實際，超過 `start` 失敗。
24. **「主 kernel」正式叫 `init`**（第 103、104 段；先說 core，看到改名範圍後改 init）：角色像 Linux 的 1 號——daemon 起來第一個起它、其他 proc 都由它下 `start`。程式與文件凡是「主 kernel」都換：`daemon.json` 的 `init`、`--init`、`on_init_exit`、status 的 `init`／`init_access`／`init_restarts`／`init_last_exit`…、`exit_code` 的值 `init`。它在 `procs/` 底下的名字照它設定的 `name`。這份紀錄前面寫的「主 kernel」不改（當時的紀錄）。
25. **舊的 proto9 aos-daemon 收掉，aos-daemon2 改名回 aos-daemon**（第 105、106 段）：舊夾刪掉，最後一版在 `068bfb2fb`；proto8 那支不動。
26. **網路：設定檔加 `net`，預設 `none`**（第 107 段）：`none`＝自己一個空的 network namespace、只有 loopback，外面連不到；`host`＝共用外面的網路（要上網的寫這個）。init 也一樣照設定。能連外網但看不到本機服務的那種要 pasta 之類，以後再說。
27. **seccomp：預設套 daemon 內建的常見危險清單**（第 108 段）：像 Docker 預設那種（擋掛載、核心模組、開 namespace、ptrace、改系統時間等）；`"seccomp": "off"` 不套；`"seccomp": "/路徑/清單.json"` 用自己寫的。內建清單要自己維護；需要被擋功能的程式（例如在裡面開瀏覽器沙盒）就寫 `off` 或給自己的清單。
28. **daemon.json 那批子 agent 定的細節**（第 109～113 段，都照現在）：收尾時間中再收到 SIGTERM／SIGINT 不理（Ctrl-C 會收到兩份），要馬上收就 `kill -9` daemon；`on_parent_death: stay` 只擋起動那一層被 `kill -9`，關終端機的 SIGHUP 照常收尾（長期背景跑交給 systemd／nohup）；收尾時間中 `ctl` 照常（含 `start`）；`forget -k` 固定最多等 5 秒；init 設定寫在 daemon.json 裡時 `config` 寫 `路徑#/init`；status 多 `exit_grace`、`on_parent_death`。其餘屬程式內部，不問。
29. **天空裡的 proc 預設准自己再開 user namespace**（第 114、115 段；先選甲不准，改口准：「我一開始就打算讓他可以層層疊疊嵌套」；sky-1125 發現 4、四題的第 2 題）：內建 seccomp 清單**不擋**開 namespace（user、mount、PID 等），其他危險的照擋；proc 裡可以再跑 daemon、疊新的天空。開了也只能把自己的世界縮小或蓋住，天空原本的掛載卸不掉、翻不開。
30. **天空表每一筆記下是怎麼來的、什麼時候**（第 118 段；daemon當容器第八輪第 8 條）：`ns.json` 每筆多 `by`（`start` 起動時照設定、`mount` 跑的時候 ctl 掛的、`daemon` daemon 自己加的如 `/aos`、`locked` 被迫帶進來的）與 `at`（UTC）；文字 `ns` 不加。分不出是誰寫的 ctl（外面寫的人 PID 看到 0），能寫的本來也只有 init 與外面的使用者。
31. **合併目錄：A＋B，C 也做**（第 119 段；daemon當容器第八輪第 7 條）：A 不合併、各放各的資料夾用 `PATH` 串；B 起動前留一個空的 `tmpfs`，跑的時候用 ctl 的 `mount` 把單一個檔掛進去；C overlay 做成 `ns` 的 `{"type": "overlay", …}`（起動時疊，起動後不能加層）。D FUSE 合併目錄不在 daemon，歸某個 kernel 提供——使用者第 121 段補「D也是可以啦，就當以後有人想提供這個介面」。
32. **init 那批子 agent 定的細節都照現在**（第 121～123 段）：沒有 init 要用 daemon.json（最短 `{}`），只用參數又沒 `--init` 就拒；status 的 `init_state`（`alive`／`dead`／`starting`／`none`／`gone`）與 `on_restart_limit`、`exit_code` 兩行，沒 init 時 `init`、`init_access` 寫 `-`；`stay` 時死的 init 留在表上可 forget；`exit_code own` 用 3；`daemon_path`＋ptrace 起動就拒；`daemon_path` 要乾淨；init 上 Landlock 後看不進別人的天空、沒 Landlock 時設 true 就拒。
33. **ctl 加 `restart-init`**（第 122、123 段）：只在 init 不在時能用（死了、`gone`、還沒起過；活著就 `EINVAL`），照 daemon.json 的 init 設定起一隻真正的 init（有 `daemon_path` 掛的目錄與 `AOS_DAEMON`），表上舊的那筆先拿掉、重起次數歸零；設定裡沒有 init 就失敗。
34. **daemon 的資訊與工具用 aoslua 描：先擺介面宣告**（第 124 段）：daemon 目錄擺 `__meta/__interfaces/aos/daemon`（有 `status`、`ctl`、`procs/`）、`__meta/__interfaces/aos/jsonpath`（底下可用 `#`，例 `procs/w/ns.json#/0/src`），每隻 `procs/<名字>/` 擺 `__meta/__interfaces/aos/proc`，都是靜態空檔。第二步以後再做：`procs/` 的 `__newindex`＝`start`、`__gc`＝`forget`，是可執行檔、背後寫 `ctl`，就是第 6 條的外層程式。
    - 同一段：**`aos/utilpath` 改名 `aos/jsonpath`**（「也就是可以用#去存取json的東西」），記在 [aospl循址與元介面-1126](aospl循址與元介面-1126.md) 第 45 條。
    - 改（11-26 傍晚，[kernel-1126](kernel-1126.md) 第 2 條、第 130 段）：`aos/daemon` 不做，daemon 目錄改宣告共同介面 **`aos/ctl`**——`__meta/__interfaces/aos/ctl/` 夾底下 `kind`（`file`）、`path`（`ctl`）、`commands`。`aos/jsonpath`、`aos/proc` 照舊。
35. **daemon 只收外面送來的停止訊號**（fable 審查第 1 條，第 131 段）：signalfd 讀到的寄件人 PID 是 0（daemon 的 PID namespace 外面送的）且 `ssi_code` 是 `SI_USER`／`SI_KERNEL`，或寄件人是 init，才收尾；天空裡其他 proc 送的不理。uid 0 的 proc 還是殺得掉 init（60 秒 6 次 daemon 照上限結束）與兄弟：**先接受**，寫進 README 與 `locks` 檔。使用者問「哪個proc會是uid 0？如果是init kernel有這個權限，那我覺得OK」——預設 uid 是 0，所以沒寫 `uid` 的 proc 都是；要不要改預設另題。
36. **擋普通 proc 寫 init 的 ctl 其實只靠 Landlock**（fable 審查第 2 條，第 131 段「先試試看」）：init 也是 uid 0、caps 0，同 uid 的 proc 照帳號規則走得進 `/proc/<init>/root/aos/`，擋下的是它自己的 Landlock domain。加測試驗它讀 `status`、寫 `ctl` 都失敗；第 2、12、20 條的理由照這個讀（原文不改）。
37. **bind 來源卡住時不再無限等**（fable 審查第 6 條，第 131 段）：組天空、跑的時候掛卸的幫手逾時送 SIGKILL 後直接回失敗，不用會一直等的 `waitpid`；那個 PID 留給主循環平常的收屍收。
38. **proc 預設用 subuid，不是 uid 0**（第 132 段，選乙；使用者打「以」，照字音當成「乙」）：設定沒寫 `uid` 的 proc，daemon 自動配一個沒人用的 subuid，每隻不同；~~要改使用者檔案的才明寫 `"uid": 0`~~→ 使用者第 133、134 段改：**除了指定的 init，禁止明寫 0**（設定寫 `"uid": 0` 的 `start` 要拒）。init 照舊一定 uid 0。起因是使用者問「哪個proc會是uid 0？如果是init kernel有這個權限，那我覺得OK」。代價：除了 init，沒有 proc 能用使用者本人的帳號寫檔；要改使用者的 repo：**先用外面的 `setfacl` 給那隻的 subuid 寫的權限**，daemon 不用改（第 135 段，選甲）；經 init 開檔或交 fd 也是可以的路（「以後可能會有人想自製另一種init kernel」），先不管；subuid 的 proc 建的檔，外面看是大 uid。
39. **疊 daemon 等新版 Linux**（fable 審查第 3 條，第 136 段，選乙：「等新版linux。反正就是強制大家升linux」）：不為了疊 daemon 放寬 Landlock。等 Linux 6.12 以上（Landlock ABI 6）改成只管訊號、abstract socket 範圍、不管檔案權限的 domain，大家照進 Landlock 也能 mount。公司這台 6.6 疊不了，照實記在 README 與測試（`nest` 組）。第 29 條「准開 user namespace」照舊。
40. **舊版 Linux 照跑，風險講明**（第 137 段：「就跟大家說，你linux版本如果是舊的，那你就可能要承擔X風險」）：daemon 在 6.6（Landlock ABI 小於 6）上照樣能跑；README 寫明正式要求 6.12 以上，並列出舊版要承擔的風險（天空裡 uid 相同的能互送訊號、abstract socket 擋不住、不能疊 daemon）；舊版時 `status` 多一行英文警告。
41. **不用 bwrap，起 proc 是自己寫的**（fable 審查第 4 條，第 137 段）：第六輪定的「直接用 bwrap」改掉，原因是這些 bwrap 做不到——同一個 user namespace 裡換成 subuid、進 Landlock、exec 前停下來量天空表、跑的時候掛進去、從 daemon 握著的那一層取來源。代價是 /dev、終端機、seccomp 清單自己維護：另列「bwrap／runc 有、我們還沒有」的待辦（`/dev/pts` 與終端機、tmpfs 大小上限…），seccomp 清單在註解記下對照的現成清單。
42. **「只能往下傳自己有的」歸 init，daemon 給兩樣機制**（fable 審查第 5 條，第 137 段）：bind 加可選的 `beneath`（從那個夾往下開，`RESOLVE_BENEATH`，出界或跟 symlink 出去就失敗）；`ns.json` 每筆多 `real`（daemon 實際開到的真實位置）。
43. **init 重起前先把舊 init 的 cgroup 殺乾淨**（fable 審查「值得想」第 3 條，第 138 段）：等於自動做一次 `forget -k`，舊 init 留下的孩子不再漏在表外；沒開 cgroup 時做不到，README 寫明。
44. **daemon 握著的外面跟著外面的掛卸走**（「值得想」第 4 條，第 138 段）：原本那一層從 private 改成 slave（收外面的掛、卸，不往外傳），複製進天空的那份照舊 private、不在背後變；要實測，做不好就照現在、寫進已知限制。
45. **`daemon_access: ptrace` 收掉**（「值得想」第 9 條，第 138 段）：只留 mount 做法（第 7 條改成只剩一種）。
46. **天空：看得到什麼是路由，行程之間是牆**（fable 審查「值得想」第 8 條，第 139 段：「啊...沒想到會自然而然發展成這樣。好，那就改成這樣吧」）：取代 [daemon當容器-1125](../25/daemon當容器-1125.md) 第九輪的「天空是共用的路由、不是牆」。
    - 看得到什麼：由起它的那一方決定，kernel 提供的名字大家共用——路由。
    - 行程之間：預設互相碰不到（送訊號、看彼此的天空與環境變數），daemon 與 init 一定擋住——牆。
    - 網路預設不給，讓流量只走指定的 kernel（例 llm proxy）。
    - 每隻自己一個 PID namespace（「值得想」第 2 條）先不做：帳號各自不同後只多擋「看得到別人的命令列」；README 提醒祕密別放命令列參數。
47. **`start`／`mount` 的路徑照寫的人的天空解**（fable 審查「值得想」第 5 條，第 140 段）：寫 `ctl` 的是外面的人（PID 0）照外面解；寫的是 init，照 init 自己的天空解（來源從它的 mount namespace 取）。「只能往下傳自己有的」對 init 自動成立；代價是 daemon.json 裡 init 的天空要列較多東西（例：使用者的 repo）。第 15 條「只收絕對路徑」照舊。要在 ctl 格式定死前做。
48. **daemon 目錄加 `events`**（「值得想」第 6 條，第 140 段；daemon當容器第七輪已定要做「事件」）：讀的時候會等，有事才吐一行（時間、名字、欄、舊值 -> 新值），`cat events` 能一直看著。
49. **FUSE kernel 的路先列待辦**（「值得想」第 7 條，第 140 段）：要由 daemon 開 FUSE 連線、把掛載點擺進指定的天空、把連線交給那隻 kernel；等第一隻要用 FUSE 的 kernel 出現再設計。
50. **審查「小事」**（第 141 段）：
    - `kill <名字>` 送給它整個 cgroup；沒開 cgroup 時送給它的行程組。
    - `tmpfs` 條目與天空的根加可選 `size`，預設不限。
    - daemon 在 `$XDG_RUNTIME_DIR/aos-daemon/<名字>` 放固定位置的連結、結束時拿掉；README 教人寫 `ctl` 前先對 `status` 的 PID。
    - 其餘 11 條照審查報告（`~/.aos/scratch/proto9-daemon-review-1126/report.md`）「小事」的建議直接修（kill 改 pidfd、`on_main` 逾時標取消、擋 `daemon_path` 上層的 umount／mount、`/tmp` 不在也能起、文件補正等）。
51. **資訊與開關可由 init 指定分出去**（決策審查第 2 題，第 144 段，選乙；報告 `~/.aos/scratch/proto9-decisions-review-1126/report.md`）：可選的 kernel（重起、排程、登記表）都是 subuid，原本讀不到 daemon 目錄（FUSE 只准掛載者的帳號）、寫不了 cgroup 檔（主人是使用者本人）。daemon 多給兩樣機制，**給誰由 init 用 ctl 指定**，daemon 只照做：
    - 把某隻 proc 的 cgroup 夾交給指定的那隻 kernel（讓它能寫 `cpu.max`、`cgroup.freeze` 等）；
    - 讓指定的 proc 唯讀地看 `procs/`（之後的 `events` 同）。
    - 第 4 條「只開給一個 kernel」改讀成：**ctl 只開給 init；資訊與開關可由 init 指定分出去。**下面「我的讀法」那條有了機制。
    - 不選甲（init 全部轉手）：init 會多出資訊轉送、事件分發、開關轉送三套介面，外加一張「誰能碰誰」的表，等於把准不准的 kernel 搬回 init；而且 init 卡住時排程 kernel 連凍結都做不了。

## 我的讀法（使用者沒反對，照這樣記）

- 第四輪寫「把開關發給 kernel，發給哪個由 daemon 定」。照第 4 條改成：**daemon 只把開關交給那一個 kernel；要不要再分給排程、准不准等其他 kernel，由它決定。**

## 還沒定的

