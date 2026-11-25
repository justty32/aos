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
