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
