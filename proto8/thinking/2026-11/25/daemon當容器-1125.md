使用者 11-25 晚（家機）提出做減法：procs/<名>/ 底下不規定要有什麼，ctl、sock 那些歸之後的 agent 界面；daemon 可不可以是沙箱或 container，讓底下的程式看到它指定的天空；kernel 是攔特定系統調用的 proc（例：跑 /usr/bin/draw turtle 時被某隻 proc 接走）。家機 main 實測「把名字交給 kernel」這種做法可行，並攤出三種「攔」、做減法之後剩什麼、順手解掉的、代價與三題。只是討論，沒開工。

# daemon 當容器、kernel 接住名字（11-25 晚，家機）

← [2026-11-25](README.md)｜前情：[9p-proc-1125](9p-proc-1125.md)（第 30 段是這次的原話）、[proto9 介面草稿](../../../../proto9/docs/01-aos-proc介面草稿.md)、[aos 的目標（11-24）](../24/aos的目標-1124/README.md)

這份由家機 `main` 寫。方向是使用者的；下面「我的讀法」「建議」「傾向」都還沒有他的話。

## 使用者原話（逐字）

30. 「調好了，是這樣的，我決定做減法。首先是我覺得，其實不必特別規定procs/xxx/底下一定要有啥，那些ctl,sock之類，應該是後續agent界面的東西。然後是我在想，所謂daemon，是否可以是一個沙箱？一個container？用於攔截所有其管轄下的子程序的系統調用，並且讓他看到的是虛假的天空，也就是/usr, /lib那些全都是容器內指定的。而kernel，則是用於攔截特定系統調用的proc，比如當某個普通程序他想要跑/usr/bin/draw turtle時，由於daemon的設定，他這個呼叫會被某個proc攔截。可以這樣嗎？」

## 一句話回答

可以。而且這比今天做的「每隻 proc 掛出自己的目錄」更接近 Plan 9 真正的核心：每個行程有自己的名字空間（namespace），裡面每個名字由誰提供，都是一筆一筆組起來的。

有一個說法要改：container 並不攔所有系統調用。它做的是把名字重排好（/usr 指哪、/lib 指哪），之後 Linux 照這張對照自己去找檔，不需要攔。kernel 要接住 `/usr/bin/draw`，最便宜的做法是讓 daemon 把這個名字交給它。

## 實測（家機，Linux 6.18，不用 root）

| 看的地方 | 結果 |
|---|---|
| 外面（真的系統）的 `/usr/bin/draw` | 沒有這個檔 |
| 天空裡的 `/usr/bin/draw` | 有，是 daemon 疊上去的小程式 |
| 天空裡跑 `draw turtle` | 小程式連到外面一隻扮 kernel 的行程。kernel 拿到呼叫者的 stdout，直接寫進去：`[kernel pid 972391] drew a turtle for caller pid 972429 uid 1000`，退出碼 0 |
| kernel 知不知道是誰叫的 | 知道。socket 上有系統填的 PID 與 uid，呼叫者改不了 |
| 從外面看天空 | 走 `/proc/<天空裡某支行程的 PID>/root/usr/bin/draw` 看得到（同帳號才行） |

用到的機制：

- **user namespace**：在天空裡自己就是 root，不用真的 root。
- **mount namespace**：天空裡做的掛載只有這個天空看得到。
- **overlay**：把一個小夾疊在 `/usr/bin` 上。
- **unix socket 傳 fd**：kernel 拿到呼叫者的 stdout 直接寫。

這台 `bwrap`、`unshare`、`nsenter` 都有，LSM 有 landlock。

<details><summary>重跑用的腳本（只碰自己的暫存夾；S 改成任一個空夾）</summary>

```sh
S=/path/to/empty/dir; mkdir -p "$S/up"
cat > "$S/kernel.py" <<'EOF'
import os, socket, struct, json, sys
s = socket.socket(socket.AF_UNIX); s.bind(sys.argv[1]); s.listen(4)
c, _ = s.accept()
pid, uid, gid = struct.unpack("3i", c.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
msg, fds, _, _ = socket.recv_fds(c, 4096, 1)
argv = json.loads(msg)
with os.fdopen(fds[0], "w") as out:   # write straight into the caller's stdout
    out.write(f"[kernel pid {os.getpid()}] drew a {' '.join(argv[1:])} for caller pid {pid} uid {uid}\n")
c.sendall(b"0\n"); c.close()
EOF
cat > "$S/up/draw" <<'EOF'
#!/usr/bin/python3
import socket, sys, json
c = socket.socket(socket.AF_UNIX); c.connect("/srv/aos/turtle.sock")
socket.send_fds(c, [json.dumps(sys.argv).encode()], [1])
sys.exit(int(c.recv(16)))
EOF
chmod +x "$S/up/draw"
python3 "$S/kernel.py" "$S/turtle.sock" &
sleep 0.3
unshare -Urm --fork sh -c "
  mount -t tmpfs none /srv && mkdir /srv/aos && mount --bind '$S' /srv/aos &&
  mount -t overlay overlay -o lowerdir='$S/up':/usr/bin /usr/bin &&
  draw turtle; echo draw exit \$?"
```

</details>

## 「攔」有三種做法

| 做法 | 怎麼做 | 好處 | 代價 |
|---|---|---|---|
| 一、把名字交給 kernel | daemon 在天空裡那個路徑擺一個東西接到 kernel：一支小程式、一個 FUSE 檔，或一個 socket | 只有碰到這個名字的呼叫才多花；什麼語言、靜態連結的程式都一樣；看得見（看掛載表就知道每個名字誰提供）；嵌套自然（裡面那台拿外面給它的天空再組一次） | 只接得住「用名字找得到」的東西 |
| 二、在系統調用層攔特定幾種 | seccomp 的 user notification（Linux 5.0 起）：指定的系統調用一進來就停住，去問一隻監看的 proc 怎麼辦 | 接得住名字表達不了的（例：某種 `connect`） | 每次多一來一回；監看的 proc 讀呼叫者的記憶體會有時間差，man page 明說「放行」不能拿來做安全判斷；它沒辦法替呼叫者做 `execve`，只能放行、拒絕，或整個代答；兩層 daemon 都要攔同一種時怎麼疊，我沒把握，也沒實測 |
| 三、全部攔 | ptrace（PRoot 那種），或自己寫一個使用者空間的 kernel（gVisor 那種） | 什麼都看得到 | 慢；ptrace 一支行程只能被一個人追，裡面就不能用 gdb、strace；gVisor 等於用 Go 重寫整層 Linux 系統調用，我們不會去寫 |

建議：先用第一種。第二種留著，等真的碰到名字接不住的再用。第三種不做。

## 做減法之後剩什麼（我的讀法）

- aos proc 的規定只剩 daemon 那一側：
  - **天空**：照一份設定，組出底下的程式看到的世界。
  - **管底下的**：want／phase、死因、強制手段。今天定的這些照留。
- `procs/<名>/` 底下不做規定。vim、一支 python 腳本，一行都不用寫就是 aos proc。
- ctl、status、attrs、sock、mailbox、ctl 的鎖、`aos_ctl_*` 都搬去 agent 界面（之後規劃）。今天寫的 aos-procfs 變成寫 agent 和 kernel 時用的庫，不是每隻都得用。
- kernel 不是一種程式，是 daemon 設定裡的一個角色：「這個名字歸那隻 proc」。任何一隻 proc 都可以被指派成某台 daemon 的 kernel。這跟 11-25 定的「kernel＝普通的 aos proc」一致。
- 每個 kernel 守什麼規矩，由它接的名字決定：接 `/usr/bin/draw` 的就要表現得像一支程式；接 `/srv/llm` 的講什麼話它自己定。這跟 Plan 9 每個檔案伺服器自己定義自己的檔是同一回事。

## 順手解掉的（今天草稿與報告裡沒解的）

- **絕對路徑與搬家**：天空裡的絕對路徑是名字，不是硬碟位置，就像 Plan 9 的 `/bin` 永遠是 `/bin`。真實位置只寫在 daemon 的設定裡，搬家時只改那裡，而且那裡可以寫成相對 daemon 自己的路徑。「`add` 只收絕對路徑會害搬家」和 progress `relative-paths-1124` 的顧慮，大半就消失了。
- **`AOS_ROOT` 與根的 PID 會過期**：天空裡可以給一個固定路徑。要手動 export 的只剩樹外的殼。
- **socket 路徑 108 bytes 的上限**：天空裡的路徑可以很短。
- **沙箱、換帳號**：天空本來就是關著的。user namespace 可以讓裡面用別的 uid；要多個 uid 就得用 subuid，等於接回 subuid-1119 那條。
- **persists**：就是天空裡接到真實硬碟的那幾塊（可寫的掛載），其餘可以全放記憶體。「`cp AOS_ROOT` 搬走一切」＝抄 daemon 的設定，再加那幾塊真實資料夾，跟 container 搬家（映像加 volume）一樣。
- **token**：天空不給直接上網，只給 llm kernel 的 socket（Claude Code 認 `ANTHROPIC_BASE_URL` 和 proxy）。這樣 token 是 kernel 在唯一的出口量到的，不靠 proc 自己報。昨晚講過「量到的」比「宣稱的」可信，`_metainfo` 客觀的那一半也就有了來源。

## 代價與要定的

1. **PID namespace 開不開**：開了的話，daemon（天空裡的 1 號）一死，Linux 會把那個天空裡的行程全部殺掉（pid_namespaces(7)），這跟今天定的「daemon 掛了，底下還活著的自行承擔」相反。不開的話，行為跟今天一樣，但天空裡看得到外面所有行程。我傾向先不開。
2. **天空要鎖住**：底下的程式在天空裡如果有權限改掛載，把疊上去的東西卸掉就看到真的天空了。要像 bwrap 那樣，組好之後先丟掉權限，再起底下的程式。
3. **嵌套上限**：user namespace 最多疊 32 層。
4. **人從外面看**：要看 agent 看到的東西，得走 `/proc/<PID>/root` 或 nsenter，所以要一支「進某台 daemon 的天空」的小工具。另外 tmux 的 socket 如果在私有的 `/tmp` 裡，外面 attach 不到，要替它開口子。
5. **Claude Code 住進天空**：要給它 `~/.claude`、node、repo、git，以及上網（走 proxy）。它自己的 bwrap 沙箱會疊在我們的天空裡面，這要實測。
6. **卡住的問題搬了家**：一個 kernel 卡住，所有碰到它那個名字的都會跟著卡住。今天定的「回答只用自己記憶裡的東西」和 FUSE 的 abort 開關，改成 kernel 與 daemon 的規矩，照樣用得上。
7. **天空的設定長什麼樣**：可以抄 Plan 9 的 namespace 檔（純文字，一行一個 bind 或 mount），或 OCI 的 `config.json`（裡面的 mounts 陣列）。照 11-25 說的「以 struct 為主、衍生 json、再衍生純文字」，兩種都出得來。

## 等使用者的三題

1. 我的讀法對不對：aos proc 的規定只剩 daemon 那一側（天空，加上管底下的），其餘全歸 agent 界面？
2. PID namespace 是先不開（底下照今天的規矩），還是開（daemon 一死整片收掉，不留孤兒）？
3. 要不要先做一個小實驗，再改草稿？內容是：寫一份天空設定，由最小的 daemon 組出來；一隻 kernel 接 `/usr/bin/draw`，一隻 llm proxy 當唯一的出口來量 token。另外誰來做：家機派 opus 子 agent，還是留給公司的 eca-aos？

## 第二輪（11-25 晚，第 31 段）

原話在 [9p-proc-1125 第 31 段](9p-proc-1125.md)。

### 這段定了的

- 攔截用第一種，也就是把名字交給 kernel。他原本想過用權限加切換使用者身分，但那樣更麻煩。
- **界面＝檔案布局＋檔案格式內容正確＋在指定條件下存取得到**（條件是權限，以及一定時間內有回應）。做得到這些，你就是那個東西。
- 不提供界面，daemon 一樣管得了，只是手段比較粗。
- agent 界面之後再規劃。
- 想當 kernel，就去跟 daemon 登記，例如「以後 drawer 身分的 proc，它的 `/usr/bin/draw` 連到我的 draw 程式」。kernel 可以疊 kernel：kernel 自己也是普通的 proc，它的天空也可能是假的，所以天空可以一層疊一層。
- 一隻 proc 的天空，由起它的 proc 決定。例如 leader 說「起一隻 drawer，套用 draw-kernel、perm-kernel」。

### 家機 main 的回答（還沒有他的話）

**「界面」這個定義帶來三件事**

1. **界面是量出來的，不是自己說的。** 寫一支檢查工具，照界面的定義走一遍布局、讀格式、計時。這就是 `_metainfo` 客觀那一半的來源：誰在什麼時候量到了什麼。
2. **界面會變。** 卡住的那段時間，它就暫時不算 agent，daemon 自動退回粗的手段。早上另外定義的「卡住」可以收進這一條。結果也看是誰在看：權限不同、天空不同，量到的就可能不同。
3. **daemon 的手段分兩級：**

   | | 任何程式都有 | 提供界面的才有 |
   |---|---|---|
   | 停 | SIGTERM、SIGKILL | 寫 ctl 的 stop（把手上這一步做完再停） |
   | 暫停 | cgroup 的 freeze（比 SIGSTOP 乾淨） | 寫 ctl 的 pause |
   | 狀態 | 活著沒有、結束碼、cgroup 量到的 CPU 與記憶體 | 它自己在 status 報的 |
   | 卡住 | 分不出是卡住還是在忙 | 限時內讀不到，就不再符合界面 |

   cgroup 那兩格的前提是 systemd 把一塊 cgroup 交給 daemon 管。公司的 WSL 有沒有 systemd 要查。

**天空由起它的 proc 決定，建議加三條規矩**

1. **提供和選用分開。** kernel 登記的意思是「我能提供 `/usr/bin/draw`」，像 Plan 9 的 `/srv`：伺服器把自己貼上公告欄，要用的人自己 mount。要不要用、掛在哪裡，由起它的 proc 明寫。「drawer」這類身分可以當成一份有名字的配方，起的人寫「照 drawer 配方」就好。
   - 不建議讓 kernel 自己宣告「以後所有 drawer 都套我」。那樣誰登記誰就能改別人的天空，「某隻 proc 的天空長什麼樣」也會變得很難回答。
   - 前例：Kubernetes 以前有 PodPreset，照標籤自動往 pod 裡塞東西，1.20 拿掉了。
2. **只能往下傳自己有的。** 新 proc 的天空＝起它的 proc 自己的天空，加上起的人寫的修改。起的人自己看不到的東西，給不出去。這樣天空往下只會變窄或被改道，沒有人能靠起一隻新的 proc 拿到更多。
3. **起來那一刻就定好，記成一張表。** daemon 起 proc 時解析一次，記下「每個路徑由誰提供」，這是「要的」那份；Linux 的 `/proc/<PID>/mountinfo` 是「實際的」那份，兩份可以互相對照。
   - 這張表也是重起時照著再組一次的依據，搬家時要一起帶走。
   - 想看某隻 proc 的天空，把這張表印出來就行（Plan 9 的 `ns` 指令就是印一隻行程的名字空間）。
   - 之後 kernel 來來去去，不會偷偷改到已經在跑的 proc；要改就明確下一道指令。

**kernel 疊 kernel 的坑**

- **跟早上的規矩衝突。** perm-kernel 要回答 drawer，就得去問底下的 draw-kernel，所以早上定的「回答的線上不去讀寫別的 proc」，kernel 做不到。
  - 改成：kernel 只能往下問，不能繞圈（誰問誰畫成圖不能有環），每問一手都帶期限。
  - daemon 起 proc 的時候就看得出會不會成環，成環就拒絕。
- **疊越多層越慢。** 每疊一層就多轉一手。像 `exec draw` 這種偶爾一次的沒差；讀檔這種一秒幾千次的，疊兩三層就感覺得到。
- **有些 kernel 不需要每次都攔。** 像 perm-kernel，可以只在起動時交出一份「它能碰什麼」的規則，由 daemon 用 Linux 自己的機制鎖好：不給看的就不掛上去，再用 Landlock 限制能讀寫的地方。這樣執行時零成本，也不會卡。

**對到 Linux 上的分工**（我的打算，沒實測）

- **daemon 負責掛，kernel 負責答。** 掛載都由 daemon 做（它有權限）。kernel 只要提供一個 socket 或一條 FUSE 連線，不需要任何權限。fusermount 本來就是這樣，把掛好的連線交給沒權限的程式。
- **一台 daemon 一個 user namespace，底下每隻 proc 各一個 mount namespace。** 只有 daemon 疊 daemon 時才多一層 user namespace，碰不到 32 層的上限。

### 等使用者的四題

1. 提供和選用分開（推薦），還是 kernel 照身分自動套用？
2. 只能往下傳自己有的（推薦）？
3. 天空在起來時定好、要改就明確下指令（推薦），還是做成活的、kernel 來去就跟著變？
4. kernel 之間只能往下問、不能繞圈，由 daemon 起 proc 時檢查（推薦）？

另外，perm-kernel 是「起動時給規則」那種，還是「每次呼叫都要它點頭」那種？上一輪還開著兩題：PID namespace 開不開；要不要先做小實驗、由誰做。

## 第三輪（11-25 晚，第 32、33 段）

原話在 [9p-proc-1125 第 32、33 段](9p-proc-1125.md)。

### 這兩段定了的

- **PID namespace 開。** daemon 的死活由使用者保證，風險也由使用者承擔。後果是 daemon 一死，Linux 就把它底下整片收掉。這條取代 11-25 下午那條「daemon 掛了，底下還活著的不管」：一樣是自己承擔，只是結果從「留著沒人管」變成「一起收掉」。
- **他還在想的：** daemon 可以層層疊疊；資源管理和排程大多可以交給 kernel，daemon 也許只管權限與使用者帳號的切換。

### 實測（家機）

| 看什麼 | 結果 |
|---|---|
| PID namespace：daemon 當 1 號，底下起兩支 `sleep` | 從裡面看，自己是 1，孩子是 2、3 |
| 從外面對那個 1 號下 `kill -9` | 孩子馬上不見，是 Linux 收的 |
| subuid | `lorkhan` 有從 100000 起的 65536 個 uid，`newuidmap` 也在。所以不用 root，就能在天空裡讓每隻 proc 各用一個帳號 |
| cgroup | `user@1000.service` 那塊已經交給使用者（可寫，有 cpu、memory、pids 三種）。daemon 可以替每隻 proc 開一塊 cgroup，再把開關交給 kernel |

### 家機 main 的回答（還沒有他的話）

方向同意，換個說法：**daemon 是唯一碰 Linux 權力的那一個，kernel 負責所有的決定。**

daemon 手上的，都是只有它做得到的事：

1. **起、收行程。** 它是天空裡的 1 號，負責收屍和 kill。
2. **組天空。** 用 mount namespace。
3. **給身分。** 也就是 uid。subuid 範圍內不用 root；真的要換成主機上的別的帳號，就要 root。
4. **起動前上鎖。** Landlock、seccomp、cgroup 上限，起來之後就拿不掉。
5. **把開關發出去。** 每隻 proc 的 cgroup 檔（`cpu.max`、`memory.max`、`cgroup.freeze`）和 `procs_ctl` 的字，交給哪個 kernel 用，由它決定。

kernel 做的全是決定：排程（誰醒、誰凍住）、額度（token、CPU）、准不准（perm-kernel）、名字給誰（draw-kernel）。

- 這就是作業系統的老分法「機制與政策分開」。微核心只給機制，政策放到外面的伺服器去做。在 aos 裡名字剛好反過來：daemon 是給機制的那層，aos 的 kernel 才是放政策的伺服器。
- 第二輪問過 perm-kernel 是哪一種。照這個分法，它就是 daemon 在起 proc、發開關之前，去問「准不准」的那一隻，不需要每次呼叫都攔。daemon 是在做事的線上去問它，而且帶期限（照早上的規矩）。
- **daemon 什麼時候才疊：只有跨過一道權力的邊界才疊。**
  - 換帳號：真的換成主機上的另一個帳號。
  - 把一塊權力交出去：例如讓 leader 自己起、收它隊上的 proc，但碰不到別隊。做法是給它一台自己的 daemon，用的 cgroup 和 subuid 範圍是上面分給它的一塊。
  - 一群要一起死的：PID namespace 開了之後，一台 daemon 就是一起死的單位。

  其他像換天空、換 kernel、排程，都在同一台 daemon 底下用 kernel 解決，不必再疊 daemon。
- **開了 PID namespace 之後要改的：**
  - **PID 只在自己那層有意義。** 同一支行程在外面是 1227529，在裡面是 3。介面裡寫 PID 的地方（`procs_status` 的 pid、`register`、`AOS_NAME_PID`）都要講明是哪一層的號碼。Linux 的 `/proc/<PID>/status` 有一行 `NSpid`，列出這支行程在各層的號碼。方向照舊：指別人用名字，不用 PID。
  - **daemon 自己當 1 號。** Linux 不會把 1 號沒處理的訊號送給它；收屍也是它的事，這點今天的 aos-daemon 已經在做。
  - **`register` 外來的行程。** 外來的行程不在這個 PID namespace 裡，daemon 一死它不會跟著死。要講明它算不算這一片。

### 等使用者的

第二輪的四題照舊。第一輪的 PID namespace 那題定了；「先做小實驗、由誰做」還開著。另外多一題：daemon 的職責是不是就定成上面這五樣（推薦），其餘都歸 kernel？

## 第四輪（11-25 晚，第 34 段）

原話在 [9p-proc-1125 第 34 段](9p-proc-1125.md)。

### 定了的

- **kernel 回答時繞圈：不限制，風險自行承擔。** 這取代第二輪我提的硬規矩「kernel 只能往下問、不能繞圈」。
- **PID：推薦盡量不用 PID，用名字。**
- **以下照推薦：**
  - 提供與選用分開。
  - 只能往下傳自己有的。
  - 天空在起來時定好；要改，就明確下一道指令。
  - daemon 只管碰 Linux 權力的五樣：起收行程、組天空、給身分、起動前上鎖、發開關。其餘都歸 kernel。
- **kernel 之間的依賴：軟性檢查。**
  - kernel 跟 daemon 登記時，說出自己會用到哪些 kernel，daemon 就知道整條依賴鏈。
  - 要起 proc 的那一方，可以先問 daemon 這條依賴鏈，再自己決定起不起；daemon 不硬擋。
  - daemon 另外提供一個選項：不准有成圈的依賴，有的話就拒絕登記。
- **小實驗：可以做，隨意做。**

### 他問的：天空能不能在跑的時候改（家機實測）

可以。daemon 從外面進到那隻 proc 的 namespace 去掛載，那隻 proc 正在跑，下一次看就看到了：

| 時間 | 天空裡的 proc 看 `/srv` |
|---|---|
| t=1～3 | 空的 |
| 約 t=1.2，外面用 `nsenter` 進它的 namespace，`mount --bind` 一個夾到 `/srv/new` | — |
| t=4～6 | 看得到 `new` |

改的做法有三種：

1. **進去掛。** setns 進它的 namespace 再 mount，就是上面實測的這種。
2. **掛載會傳播。** daemon 先把 `/srv` 設成會傳播的掛載點（shared subtree）；之後它在自己那邊掛上一個新的 kernel，每隻 proc 的 `/srv` 都會跟著出現。
3. **FUSE 目錄。** 內容本來就能隨時變，掛載完全不用動。

要注意的地方：

- 已經開著的檔、站在裡面的 cwd，會繼續用舊的那個。
- 有人正在用、卸不掉的時候，要用 lazy 卸載。
- **誰能改：** 只有握著那個 namespace 權限的一方，也就是 daemon；proc 自己不行。實測裡，天空裡的 sh 自己 `umount` 卻成功了，原因是這個小測試沒有丟掉權限。這正是第一輪第 2 點「天空要鎖住」講的事，小實驗會做。

### 小實驗（派出）

放在 `proto9/experiments/sky-1125/`。家機 main 派一隻 opus 子 agent 去做；它不 commit，做完由 main 重跑、查有沒有殘留，再交件。要驗的東西：

1. **天空設定。** 一份純文字的天空設定，daemon 照著組出來，記下「要的」那張表，再跟 `mountinfo` 量到的對照。
2. **把名字交給 kernel。** draw-kernel 登記「我能提供 `/usr/bin/draw`」，leader 起 drawer 時選用它，drawer 跑 `draw turtle` 時由 kernel 回答。
3. **只能往下傳自己有的。** 起的那一方看不到的東西，指定了會被拒。
4. **依賴鏈。** kernel 登記時寫出依賴，起的一方可以去問；daemon 的「不准成圈」選項關著時，成圈也收，開著時就拒。
5. **llm proxy 當唯一出口。** 天空裡沒有網路，只有接到 proxy 的 socket。proxy 轉給一個假的上游，由它自己數 token。不打真的 API。
6. **跑的時候改。** daemon 明確下指令，替一隻跑著的 proc 加一個掛載，並且更新那張表。
7. **天空鎖住。** 天空裡的 proc 卸不掉、也掛不了。
8. **PID namespace。** daemon 是 1 號，它一死，底下的全部被收掉。
9. 加做（做得到才做）：用 subuid 讓兩隻 proc 各用一個帳號，互相讀不到對方的檔。
10. 加做（做得到才做）：用 cgroup 凍住、解凍一隻沒提供界面的 proc，示範「粗的手段」。

**結果**（11-25 23:0x 回來，十項全過；main 自己重跑一次也是 10 PASS，跑完沒留下行程、掛載、cgroup、systemd unit）。做法、量到的數字、撞到的坑都在 [sky-1125 README](../../../../proto9/experiments/sky-1125/README.md)。跟前後幾輪接得上的發現：

- daemon 是 1 號，同 uid 的 proc 讀 `/proc/1/root` 就看到整台機器；daemon 自己設 non-dumpable，一行就擋掉。兄弟之間的那幾條（`/proc/<PID>/root`、environ、送訊號、abstract socket，第八輪量到的）每隻 proc 進一個自己的 Landlock domain 就全擋，不用 root。第九輪定了天空不是牆，所以加不加是選項。
- 「只能往下傳自己有的」要拿真實的檔來判，不能只比路徑：起的一方放一個 symlink，就能把 daemon 帶出去（實測把整個 home 交出去過）。身分、網路、/proc、/dev 也要判。
- 根要從零組（pivot_root），表才答得出天空裡「沒有什麼」。這樣的天空要在跑的時候改，得用 open_tree＋move_mount；第四輪試過的 `nsenter + mount --bind` 對它不管用（EINVAL）。
- daemon 當 1 號要自己裝 SIGTERM 的處理，不然只有 SIGKILL 停得掉它。

README 最後列了四題等使用者：每隻 proc 預設進 Landlock 嗎；准不准天空裡的 proc 自己再開 user namespace；選用 kernel 要不要起的一方自己先有；天空裡預設用 uid 0，還是每隻各用一個 subuid。

## 第五輪（11-25 晚，第 35 段）：跟現有的 container 比

原話在 [9p-proc-1125 第 35 段](9p-proc-1125.md)。以下由家機 main 憑記憶比較，沒有上網查證；要查證可以請上網幫手。家機上有 docker、runc、bwrap 0.13、systemd-nspawn，systemd 使用者 session 有在跑；沒有 podman、crun、pasta、slirp4netns、criu。

### 一句話

container 做的是「隔離＋打包」：把一個凍好的世界帶著走，自己關起來跑。我們這套做的是「組合＋往下授權」：每隻 proc 的世界，由起它的 proc 用一個個有名字的服務（kernel）組出來，一層一層往下。所以最像我們的不是 Docker，是 Plan 9、Hurd、Genode、Fuchsia 這幾個作業系統。我們缺的，大多是 container 圈磨了十年的底層雜事，外加幾個概念。

### 對照

| | 我們 | container（Docker、Podman、Kubernetes） | 最像我們的 |
|---|---|---|---|
| 一個單位 | 一隻 proc 加它的天空；一台 daemon 是一起死的一群 | 一個 container（映像＋設定）；k8s 的 Pod 是一起排程的一群 | Plan 9：行程＋名字空間 |
| 世界長什麼樣誰定 | 起它的 proc，一層層往下，只能給自己有的 | 寫 run 指令或 spec 的人，只有一層 | Genode、Fuchsia：parent 替 child 接線 |
| 服務怎麼接進來 | 一個名字交給一個 kernel | volume、port、sidecar（共用網路） | Hurd 的 translator（掛在一個檔名上的程式）、Plan 9 的檔案伺服器 |
| 跑的時候改 | 可以，要明確下指令 | Docker、k8s 不行（要重建）；LXD 可以熱插 | Plan 9 隨時可以 bind |
| 嵌套 | 本來就支援 | 勉強（Docker-in-Docker） | Genode、Plan 9 本來就支援 |
| 策略放哪 | kernel，是可以換的 proc | 內建在 runtime 或 orchestrator 裡（k8s 有 webhook、scheduler plugin，可以外掛一部分） | Genode：parent；Fuchsia：component manager |
| 資源 | cgroup，再加 token（kernel 在出口量） | cgroup（CPU、記憶體、IO、pids） | Genode：parent 把自己的記憶體額度讓一塊給 child |
| 健不健康 | 符不符合界面（布局＋格式＋限時回應） | 健康檢查（跑一個指令或打一個 HTTP） | — |
| 帶走 | 設定＋persists；/usr 用機器自己的 | 映像（分層、內容定址、放 registry） | — |

### 我們有、他們沒有的

1. **服務按名字組合，由起的人挑**：container 沒有「你這個路徑由那隻程式回答，而且是起你的人挑的」這種一等公民。
2. **遞迴授權**：每隻 proc 都能起一隻更窄的 child；container 基本是平的，由一個中央的 daemon 或 orchestrator 管。
3. **界面是結構型別，而且量得出來**：container 只有標籤和健康檢查；我們是「做得到就是那個東西」，量到的結果記進 `_metainfo`。
4. **策略是可以換的 proc**：排程、額度、准不准，都是 kernel。
5. **跑的時候可以改天空。**
6. **token 是一種資源。**

### 他們有、我們缺的

**底層雜事：一定要補，照抄就好**

- **/dev、/proc、/sys 的最小擺法**：/dev 只給 null、zero、random、urandom、tty、pts；/proc 要配合 PID namespace 重掛，並遮掉幾個敏感的檔；/sys 唯讀。
- **終端機**：天空裡要有自己的 pts。tmux 的 socket 如果放在私有的 /tmp 裡，你從外面 attach 不到。
- **stdout、stderr 要收下來、要輪替**：proto9 的 daemon 也還沒做「把底下的 stderr 收進 reason」。
- **預設的防護**：Docker 的預設 seccomp 表擋掉四十多個少用又危險的系統調用；還有一份預設要丟掉的權限清單，以及 `no_new_privs`。
- **這些 bwrap、runc 都做好了，家機兩個都有。** 建議 daemon 起 proc 的那一步直接叫 bwrap（或照 OCI 的 config.json 叫 runc／crun）。我們自己的程式只寫上面那層：kernel 的登記表、天空表、依賴鏈、跑的時候改、發開關。

**概念：值得補**

- **就緒和活著分開**：起了不等於能用（k8s 的 readiness、systemd 的 sd_notify）。報告 10 提過，草稿裡還沒有。
- **事件**：狀態一變就通知，不必一直去讀（cgroup 的 `cgroup.events`、inotify、FUSE 的 poll）。這跟 proto8「閒置輪詢吃 CPU」那條是同一件事。
- **按需起 kernel**：天空裡先擺好 socket，第一次有人連才把 kernel 起起來（systemd 的 socket activation、inetd 都是這樣）。kernel 一多，閒置成本就靠這招壓下來。
- **進到某個天空的工具**：像 `docker exec`、`machinectl shell`，讓人能站在 agent 的位置看。

**看需求再說**

- **可重現的 /usr**：現在天空的 /usr 是機器自己的，搬到別台機器，/usr 不一樣就可能壞。container 用映像解決，Nix 用內容定址的 store 解決。要不要管，取決於「cp AOS_ROOT 搬走一切」搬去的是不是同一種機器。
- **網路**：現在只有「沒網路＋proxy」一種。要讓 agent 自己上網，就得有不用 root 的網路（pasta、slirp4netns，家機都沒裝），或做一個通用的 proxy kernel。
- **跨機器**：你有兩台。Plan 9 的做法是把 9P 跑在網路上（import／exportfs），把一台的名字掛進另一台的天空裡。
- **把跑著的整片凍起來帶走**：CRIU 的 checkpoint／restore。

**不用**：registry、跨多台機器的排程、GPU。

### container 圈踩過、我們也會踩的坑

- **帳號和共用的 repo**：用 subuid 給每隻 proc 一個帳號，它在 repo 裡寫的檔，從外面看是 100xxx 擁有的，你自己的帳號改不了也刪不掉。Podman 用 `keep-id`（把你自己對應到天空裡的同一個 uid）解決；idmapped mount 則要 root。所以會寫 repo 的 agent 先用你自己的 uid，需要隔開的才給 subuid。
- **掛載傳播**：預設要設成不往外傳（private 或 slave），否則天空裡掛的東西會漏回外面，或在兄弟 proc 之間互漏。真的要傳播的（例如第四輪說的 /srv），再明確設定。
- **公司那台**：WSL 有沒有開 systemd（沒有就拿不到 cgroup 委派）、不用 root 開 user namespace 行不行，都要在公司實測一次。
- **Claude Code 自己的沙箱**：它的 bwrap 會疊在我們的天空裡面，要實測。

### 等使用者的三題

1. daemon 起 proc 那一步直接用 bwrap（或 runc／crun），我們只寫上面那層？（推薦）
2. 「概念：值得補」那四樣（就緒、事件、按需起 kernel、進天空的工具）排進下一批？
3. /usr 要不要管：先只搬到同一種機器、不管它（推薦先這樣），還是要做到可重現（映像或 Nix）？

## 第六輪（11-25 晚，第 36 段）

原話在 [9p-proc-1125 第 36 段](9p-proc-1125.md)。

### 定了的

- **daemon 起 proc 那一步直接用 bwrap（或 runc／crun）**，我們只寫上面那層。（第五輪第 1 題：「好主意，就這個！」）
- **可重現的 /usr 是很遠以後的目標**；現在 /usr 先不管，用機器自己的。
- **網路之後要討論。**
- **就緒、事件、按需起 kernel、進天空的工具**：這四樣要討論。他說「感覺都是技術問題」。

### 家機 main 的提案（四樣，等他看）

**1. 就緒**

- 定義：符合界面的那一刻起，就算就緒。
  - kernel：它提供的名字開始回答，就是就緒（socket 接得起來、FUSE 讀得到）。
  - 沒提供界面的 proc：只有「活著」，沒有「就緒」。起它的人可以另外指定一個條件，例如某個檔出現、某個 socket 接得起來。
- 兩種來源都收：
  - proc 自己說：daemon 給它一個 fd，就緒時寫一個換行。s6 和 systemd 的 sd_notify 都是這樣做。這是宣稱的。
  - daemon 自己量：照界面去試。這是量到的。
- `procs_status` 多一欄 `ready`。
- 有了按需起 kernel（第 3 點），多數「等它就緒才起下一個」的順序問題就不存在了。

**2. 事件**

- daemon 擺一個 `events` 檔。讀它時會一直等，有事才吐一行（`時間 名字 欄 舊值 -> 新值`），所以 `cat events` 就能一直看著。前例是 Plan 9 的 `/proc/n/wait`，讀它會等到有 child 結束。
- 程式要用的話：對 `status` 這類檔做 poll，值變了才會醒。FUSE 支援 poll。
- daemon 自己看底下的 proc：用 cgroup 的 `cgroup.events` 加 inotify，值一變 Linux 就主動通知，不必每隔一拍去讀。這正是 proto8「閒置吃 CPU」的解法。
- 要注意：FUSE 伺服器那邊自己變的，inotify 看不到；FUSE 的檔要用 poll，或讀 `events`。

**3. 按需起 kernel**

- kernel 登記時可以說「我是按需的，閒置 N 秒就自己結束」，同時給出怎麼起它。它的天空照登記的人寫的組。
- daemon 先替它開好 socket、擺進各個天空。第一次有人連進來，daemon 才起它，並把那個 socket 交給它（照 systemd 的 `LISTEN_FDS` 慣例）。它起來之前的連線會在 socket 裡排隊，不會掉。
- 好處：
  - 閒著不花錢。
  - 不用管起動順序。
  - kernel 掛了，下一次有人連就會再起。
- 代價：
  - 第一次呼叫要等它起來。
  - kernel 閒置結束前，要把要留的東西存進 persists。
  - FUSE 提供的名字不好做成按需，所以先只做 socket 和小程式這兩種。

**4. 進天空的工具**

- `aos-enter <名字>`：請 daemon 在那隻 proc 的天空裡替你起一個 shell，跟 `docker exec` 是請 dockerd 代起一樣。由 daemon 代起，是因為碰 Linux 權力的只有 daemon。
- 兩種看法：
  - 跟它一模一樣：同樣的天空、同樣的帳號、同樣的鎖，看得到它能做什麼、不能做什麼。
  - 管理者看：同樣的天空，但不上鎖。
- 另配一支 `aos-ns <名字>`，印出那張天空表（要的）和 mountinfo（量到的）。
- 誰准進去：由 daemon 去問 perm-kernel。

### 等使用者的

這四樣照提案排進小實驗的下一批嗎？還是有哪一樣想先細談？網路另外再談。

## 第七輪（11-25 晚，第 37 段）

原話在 [9p-proc-1125 第 37 段](9p-proc-1125.md)。

### 定了的

- 第六輪那四樣（就緒、事件、按需起 kernel、進天空的工具）照提案做，排進小實驗的下一批。

### 他問：kernel 如果是被動、靜態的（只提供一些檔案讓人存取），還要按需起嗎？消耗多少？

**家機 main 的回答**

- **不需要按需起，因為它根本不需要一支行程。** 登記時寫成「這個名字 → 這個夾（唯讀）」，daemon 把夾綁進天空，之後所有的讀檔都由 Linux 自己處理，沒有任何程式在等。沒有行程，就沒有「起不起」的問題，也不會卡住。
- **前提要更正一下**：按需起並不是因為 kernel 要攔東西。閒著等連線的伺服器本來就不吃 CPU，它停在 accept 或 read 上睡著。按需起主要省的是記憶體和行程數，順便解掉起動順序和掛掉重起的問題。
- **什麼時候才需要自己的行程**：要握住呼叫者不該拿到的東西時，例如 API key、網路、額度的計數、別人的資料。要攔，就得站在呼叫者碰不到的地方，所以只能是另一支行程。單純提供東西的不需要。

**四種提供者**

| 種類 | 例子 | 要不要自己的行程 | 消耗 |
|---|---|---|---|
| 靜態的夾或檔（綁進天空） | 文件、設定、某套工具 | 不用 | 幾乎零，讀檔是 Linux 原生的速度 |
| 一支可執行檔（在呼叫者身上跑） | draw 本身就是一支會畫圖的程式 | 不用 | 只在被叫時才花；CPU 和記憶體都算在呼叫者的 cgroup 上，帳也就記在他身上 |
| 會現算的檔（FUSE） | `status`、內容會變的目錄 | 要 | 閒著約 0 CPU；一支約 4 MB；讀一次約 0.04 ms（公司 aos-procfs 量的） |
| 要攔、要握權力的（socket 伺服器） | perm、llm proxy（握著 API key 和網路）、額度 | 要 | 同上；按需起可以省掉閒置時的記憶體 |

**實測（家機，綁的是一個裝了 4 KiB 檔案的夾）**

| 看什麼 | 結果 |
|---|---|
| 在一個天空裡做 1000 個唯讀綁定 | 0.42 秒，大多花在每次起 `mount` 指令本身；直接呼叫系統調用會快得多 |
| 那個天空的掛載數 | 1027 筆（每個天空預設上限十萬筆） |
| 讀 4 KiB：經過綁定 vs 直接讀 | 0.0020 ms vs 0.0021 ms，一樣快 |
| 從天空裡寫 | 被擋：`Read-only file system` |

**要注意的**

- 頁快取是共用的：一百隻 proc 讀同一個檔，記憶體裡只有一份。
- 提供者在原夾裡改檔，所有天空會馬上看到，因為是同一份檔。如果要大家一起換版本、不想讓人看到改到一半的內容，就先放一個新的夾，再請 daemon 換掛（第四輪說的明確指令）。
- 提供者把整個夾刪掉或換掉時，已經掛著的天空還會指著舊的那個，要重掛才會更新。
- 檔案的 Linux 權限照樣生效：拿 subuid 帳號的 proc 讀不到只有你能讀的檔（第五輪提過的坑）。

### 等使用者的

靜態的夾也算 kernel 嗎？我推薦算：照「kernel 是 daemon 表上的角色」的說法，登記表裡標一欄種類（`dir`、`exec`、`fuse`、`socket`）就好。

## 第八輪（11-25 晚，第 38 段）：還有沒想到的

原話在 [9p-proc-1125 第 38 段](9p-proc-1125.md)。

### 定了的

- **靜態的夾也算 kernel**（「很好，就是這樣」）。登記表上標一欄種類：`dir`、`exec`、`fuse`、`socket`。

### 會咬人的（建議先想）

**1. 兄弟之間其實沒隔開**（家機實測）

| 試什麼 | 結果 |
|---|---|
| 同一個帳號，讀兄弟的環境變數 | 讀得到（`SECRET=hunter2`） |
| 同一個帳號，走兄弟的 `/proc/<PID>/root` | 走得進去，也就是進了它的天空 |
| 兄弟設成 non-dumpable（`prctl(PR_SET_DUMPABLE, 0)`） | 讀不到了：`permission denied` |
| 換了天空（新的 mount namespace）去連 abstract socket（不在檔案系統上的那種） | 連得上，天空擋不住 |
| 再加一個新的 network namespace | 連不上：`Connection refused` |
| 自己一個 PID namespace | 只看得到 3 支行程（外面看得到 462 支） |

- 天空本身只管「名字怎麼找」，它不是一道牆。同一台 daemon 底下、用同一個帳號的兄弟，可以讀到對方的環境變數（API key 常常放這裡），也能走進對方的天空。abstract socket 完全不看天空；X11、部分 D-Bus 用的就是這種。
- 要先講好一句承諾：天空是「合作用的路由」，還是「安全的牆」。
- 如果要當牆，有三件便宜的事可做：
  - 每隻 proc 各給一個 PID namespace，就看不到兄弟。
  - 握有秘密的 kernel 設成 non-dumpable，或改用別的帳號跑。
  - 需要隔開的，給它自己的 network namespace，abstract socket 就斷了。
- 附帶要注意：每隻 proc 都當自己 namespace 裡的 1 號時，Linux 會吞掉它沒處理的訊號（例如 SIGTERM），所以裡面要放一支小的 1 號，負責收屍、轉送訊號（tini 就是在做這件事；bwrap 怎麼處理要實測）。

**2. kernel 怎麼知道是誰在呼叫它**

- socket 上拿得到對方的 PID，但開了 PID namespace 之後，每一層看到的號碼都不同，而且我們本來就推薦不用 PID。
- 建議：daemon 替每個呼叫者各開一條自己的 socket 接到 kernel。kernel 從哪一條收到請求，就知道是誰；通道本身就是身分，冒充不了。Genode、Fuchsia 都是每個 client 一條通道。
- 要按 agent 記 token、按 agent 判 perm，都得靠這一條。

**3. 替別人做事花掉的資源，要算在誰頭上**

- 例如 draw-kernel 替一百隻 proc 畫圖，CPU 全記在 draw-kernel 自己的 cgroup 上，額度就沒辦法按人計。
- 可以參考的做法：
  - Genode：client 開連線時，把自己的一塊額度讓給 server。
  - 可執行檔那種提供者，本來就在呼叫者身上跑，自然記在呼叫者頭上。
  - token 在 proxy 那邊按通道記。

**4. 整片一起重起會是常態**

PID namespace 開了之後，daemon 一重起，底下的全部跟著重起。所以：

- 每隻 proc 都要能隨時被收掉，重起後接著做（狀態全放在 persists）。設計 agent 的身體時要把這當成前提。
- 升級 daemon 不能靠重起，要用 re-exec：1 號原地換成新程式，PID 不變，底下的也不會死。systemd 的 daemon-reexec 就是這樣做的。
- kernel 的 socket 由 daemon 握著。kernel 重起或升級的時候，進來的連線會在 socket 裡排隊等，呼叫者感覺不到。

### 可能沒想到的好處

**5. 鐵律可以變成天空的設定**

今天「push 要使用者本人說」「wf/user 只讀」「別棵樹的 stack 不讀」，都是靠 agent 自己守。放進天空之後：

- push 用的 key 只放在一個 push kernel 手上，要有你的授權才推。
- wf/user 用唯讀掛進去。
- 別棵樹根本不出現在天空裡。

規矩就從「請你守」變成「你做不到」。

**6. 假的天空可以拿來測試**

給 agent 一個假的 llm kernel，讓它回固定的答案，整個組織就能一個 token 都不花地跑一遍。昨晚提的「上千個 agent 實測」，就可以用這個方法做。

### 技術題，之後再談

7. **合併目錄**：兩個提供者都要往同一個夾放東西時（例如 host 的 /usr/bin 加上 draw 再加上別的），要有誰蓋誰的規則。overlay 不能在跑的時候再加一層，所以跑的時候想往唯讀的夾加一個檔，要另想辦法：改用 FUSE 合併目錄，或是一開始就留一個可以加東西的夾。
8. **天空表的每一筆，都記下是誰要的、什麼時候要的**：之後有人問「它為什麼看得到這個」，才答得出來。
9. **界面本身怎麼寫下來、怎麼改版、誰來量**：跟 agent 界面一起談。
10. **上千隻 proc 時，掛載傳播的成本**：只讓 /srv 這類少數幾個掛載點傳播，或改用 FUSE 目錄當登記表，就不必動掛載。
11. **persists 誰來清**：rm 不會刪 persists，久了會越堆越多。

### 等使用者的

第 1 題最該先定：天空是合作用的路由，還是安全的牆？我的傾向：預設當牆，但只做那三件便宜的事（各自的 PID namespace、握秘密的 kernel 設 non-dumpable、需要隔開的給 network namespace）；分帳號（subuid）留給真正需要的情況。

## 第九輪（11-25 晚，第 39 段）

原話在 [9p-proc-1125 第 39 段](9p-proc-1125.md)。

### 定了的

- **天空是共用的路由，不是牆。** 要牆就去隔壁的 daemon。以後 daemon 也許可以多一個功能：把一個 uid 分給某隻 proc，再靠權限限制別人存取。
  - 11-26 傍晚改了：看得到什麼是路由、行程之間是牆，見 [daemon職責-1126](../26/daemon職責-1126.md) 第 46 條。
- **每個呼叫者一條 socket**：他覺得是好主意，但還沒完全掌握，之後再談。
- **替別人做事花的資源**：由各 kernel 自己處理。
- **之後要訂一份「aos proc 界面」，意思是能跟著 daemon 一起重起。** 不符合這個界面的程式也能掛到 daemon 底下當 proc，只是風險自己承擔。這跟今天下午草稿 01 的「aos proc 介面」（ctl、status 那些）不是同一件事：那些內容已經在第一輪搬去 agent 界面了，這個名字現在改指「重起得了」。
- 其餘（第八輪的 7～11 條）之後再談。

### 家機 main 補的兩點（還沒有他的話）

- **隔壁 daemon 要當牆，需要兩個條件**：它要有自己的 network namespace，否則 abstract socket 照樣通得過來（第八輪實測）；而且不能把外面的 `/proc` 掛進它的天空。PID namespace 和 mount namespace 本來就各自一份，不用另外處理。
- **「重起得了」可以量**：daemon 先 `kill -9` 它，再照記下的設定把它起回來，看它能不能回到就緒、名字是不是同一個、persists 有沒有原封不動。量得出來的話，就照第二輪說的，結果記進 `_metainfo` 客觀那一半。
