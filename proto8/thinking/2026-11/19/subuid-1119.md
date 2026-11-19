線 subuid-1119（11-19）紀錄：aos-daemon 開始認 `limits.user: "sub:N"`，免 root 把一支 proc 換成使用者名下的 subuid（linux-as-hw 05 的乙案、kernel-limits-plan 段 3 的最小一刀）；公司 WSL 缺 newuidmap，真換身分等使用者裝好後補驗；同日上午補驗撞到 `procs` 與 user ns 的順序坑，線 subuid-fix-1119 修好、真機測試全過（見「真機補驗」）。

← [11-19 日索引](README.md)｜分檔夾 [subuid-1119/](subuid-1119/01-現況核對與施工計劃.md)

使用者 11-19 早：「子帳號：linux-as-hw 剩的那一段 <- 派線去繼續吧」。目的照 [linux-as-hw 06](../18/linux-as-hw-1118/06-使用者裁定.md)：先做防呆，單人使用、模型可信。

## 先講結論

1. **daemon 那一哩接上了（程式）**：proc 的 `limits` 寫 `"user": "sub:5"`，daemon 起它時讓它自己開一個 user namespace、由 daemon 跑 `newuidmap`／`newgidmap` 對號碼，再換成真的 100004（群組＝這台 daemon 的 `group`，預設 60001＝真 160000）；起之前把它的 stack 改成 700＋ACL（它和使用者都進得去、同台別隻進不去），換身分前清環境、關多餘的 fd，換完檢查路走不走得到。kernel 站本來就會照 `users` 表填 `sub:N`，不用改。
2. **驗到哪**：設定驗證、`group`、helper 找不到、helper 失敗、小格 ACL、父子握手與 helper 收到的號碼都在這台實測過；aos-daemon 全部 13 支測試照過。**真的換成 100004 沒驗到**——這台沒有 newuidmap（要 `sudo apt install uidmap`）。真機那兩條測試已寫好，裝了就會自己跑（[02](subuid-1119/02-測試結果與補驗步驟.md)）。
3. **裝好之後還會卡一個地方**：這台家目錄是 750，換了身分的 proc 走不進 `/home/guanyu`，daemon 會報 `cannot reach /home/guanyu` 讓那支起不來。怎麼開這扇門會動到使用者的家目錄設定，**要使用者拍板（Q1）**。
4. **這一刀能跑的是「不用寄信」的 proc**：換了身分的 agent 寫不進 daemon、kernel 的信箱（照 K16 要用 `aos-share` 開），也還沒有「用信夾擁有者認寄件人」（丙）。

## 真機補驗（11-19 上午，線 subuid-fix-1119）

使用者 11-19 上午裝了 `uidmap`、家目錄改成 751（等於 Q1 選 a 的「穿過去」那一半）。兩條真機測試第一次真的跑：`test_real_cpu_hit`（`sub:6`）過；`test_real_switch`（`sub:5`＋`procs: 5`）穩定失敗，job 起來 0.02 秒就 stopped：

```
failed to start: exited within 3s of wake/start (code 1): aos-exec: error: LaunchFailed cannot start: …/subuid-real/who.sh (Resource temporarily unavailable)
```

**坑：`procs` 不能在開 user ns 之前設。** 換身分本身沒問題（setgroups、setresgid、setresuid 都過了，走得到檢查也過了），是 aos-exec 最後 execve 身體時被核心以 `EAGAIN` 擋下。原因是 Linux 5.14 起 `RLIMIT_NPROC` 改由 ucounts 記帳：開 user ns（`unshare(CLONE_NEWUSER)`）那一刻，核心把**當下**的 `RLIMIT_NPROC` 記成這個 ns 在外層的天花板，外層數的是**開 ns 的人**（uid 1000，使用者本人）的全部行程與執行緒；換 uid 時（setresuid）只要任何一層超過就立旗、下一次 execve 回 `EAGAIN`。原本的順序是「setrlimit（procs: 5）→ unshare → setresuid」，所以 5 被拿去比使用者自己的幾十個行程，必超。`cpu_s` 那條沒寫 `procs`，天花板是繼承來的 62961，所以過。

證據（`~/.aos/scratch/subuid-fix-1119/exp/nproc.c`，同 daemon 的做法：fork→unshare→父跑 newuidmap／newgidmap→setgroups/setresgid/setresuid(5)→execve /bin/true）：

| 寫法 | 上限 | 結果 |
|---|---|---|
| 先 setrlimit 再 unshare（原本） | 5、10、30、50、80 | execve `Resource temporarily unavailable` |
| 同上 | 100、150、…、60000 | 過（這時使用者自己約 70～90 個行程／執行緒，門檻跟著它走、不是跟著 subuid） |
| unshare 之後、setresuid 之前才 setrlimit | 5、60000 | 過 |
| 同上，上限 3，ns 裡再 fork 4 個 | 3 | 前 2 個成功、第 3 個 `EAGAIN`（自己＋2＝3：數的是 ns 裡這個 subuid） |
| 同上，兩支同時跑、都換成同一個 100004 | 3 | 各自都 fork 得出 2 個：**不同 ns 各數各的** |

**修法（程式）**：`procs`（`RLIMIT_NPROC`）在 `sub:N` 時延後到開了 ns、對好號碼之後，換 uid 之前才設；其他 rlimit 順序不變。`limits.cpp` 拆出 `apply_sub_nproc`，`subuid.cpp` 的 `enter_sub` 拆成 `open_sub_ns`（開 ns、握手）與 `become_sub`（換身分以後），`child.cpp` 的 `run_child` 照「open_sub_ns → apply_sub_nproc → become_sub」叫。語意照 docs 09 原文「`procs` 只數這個 uid 自己的行程」與 [kernel-limits-plan 07](../13/kernel-limits-plan/07-cgroup可選.md)「換了 subuid 才是這隻自己的」——不是新方向；文件補寫清楚「同一個 `sub:N` 的兩支各數各的、整個帳號在外層仍受 daemon 自己的上限」。

**測試**：`reachable()` 原本對「不是 cannot reach 的起不來」用 `assertIn` 失敗，訊息看不出是什麼錯；改成直接 `fail` 並印 reason（不 skip）。新加兩條真機：`test_real_procs_counts_the_subuid`（`procs: 3` 比使用者自己的行程數小也起得來；身體 fork 到第 3 個 `EAGAIN`；這支 session 裡 uid 100006 剛好 3 個；`rm` 後全收）、`test_real_cannot_reach`（fixture 裡自己做一層 700 當 ws 的祖先，daemon 點名那一層）。

**[02 第三節](subuid-1119/02-測試結果與補驗步驟.md#三沒驗到的要真的-newuidmap)五項這次各自驗到沒有**：

1. setgroups、setresgid、setresuid 在真對照表下過，`/proc/<pid>/status` 的 Uid 四欄都是 100004——**驗到**（修好後的 `test_real_switch`；修之前已經走到 execve，代表這三步那時就過了）。
2. agent 寫的檔是 `100004:160000`、使用者照改得動——**驗到**（同條，斷言擁有者並由使用者 append）。
3. 環境白名單：`HOME=/nonexistent`、`SUBUID_PROBE` 不見、`GIT_CONFIG_VALUE_0` 是 ws——**驗到**（同條）。
4. 「走得到」點名 `/home/guanyu`——**照原樣沒驗到**：家目錄已改 751，subuid 穿得過去，不會停在那裡。改驗同一段程式：新測試在 fixture 裡做一層 700，原文 `LimitBad user sub:8: cannot reach /home/guanyu/.aos/scratch/subuid-fix-1119/run-092836/subuid-real-reach/locked: Permission denied`——**驗到點名第一層走不進去的祖先**。
5. `rm` 後行程不在、`cpu_s` 命中、`procs: 5` 起得來——`rm` 與 `cpu_s`（`signal 24, code 152, limit_hit cpu_s`）**驗到**；`procs: 5` **修之前失敗（就是這個坑）、修之後驗到**，另加 `procs: 3` 真的只數這隻自己的。

02 第四節第 4 步（自己起一台看 `ps`）沒做，是選做。

**跑法與結果**：`git archive 480b1dac1` 抄到 `~/.aos/scratch/subuid-fix-1119/src/`、`install.py`、疊上改動 `make -C cpp aos-daemon`（無 warning）後把 `cpp/build/bin/aos-daemon` 換進複本的 `bin/`；測試經 `~/.aos/scratch/subuid-fix-1119/tools/run-tests.sh`（先 unset 全部 `AOS_*`）。改前同一份複本 `test_real_switch` FAIL（重現）；改後 `test_subuid` 9 條全過、連跑三次都過；aos-daemon 全部 13 支（`run-093136`，`regress.log`）rc=0：bad_letter 3、cgroup 0（skipped 1，這台沒 systemd user）、ctl 19、lifecycle 40、limits 12、poke 10、ref_hash 1、stack_make 5、stale_stop 1、state_path 4、stop_cause 11、subuid 9、two_machines 9。

順手看到、沒改：沒開 cgroup 時 `rm` 只 SIGTERM 主行程，主行程先退、後代沒跟著走就會留成孤兒（docs 09 本來就這麼寫，跟換不換身分無關）；新測試的身體自己收子行程。

## 要你拍板

**Q1：換了身分的 agent 怎麼走進你的家目錄？**（`/home/guanyu` 是 750：別人連「穿過去」都不行。aos、暫存樹、工作區都在家目錄底下。）

| 選項 | 做法（你親手跑） | 後果 |
|---|---|---|
| **b（推薦）** 只給 aos 的群組「穿過去」 | `sudo apt install acl` 後 `setfacl -m g:160000:x ~` | 只有 aos 換了身分的 proc（主群組 160000＝預設 `group` 60001）能穿過家目錄、列不出裡面有什麼；其他帳號照舊進不來。daemon 換了 `group` 就要多加一行 |
| a 給所有人「穿過去」 | `chmod o+x ~` | 最簡單、不用裝 acl；這台其他帳號也能穿過去，讀得到家目錄裡本來就開放讀的東西（例 `~/repo` 是 755）。單人 WSL 其實只有 aos 的 subuid 是「其他人」 |
| c 把 aos 搬出家目錄 | 例 `sudo mkdir /srv/aos && sudo chown guanyu: /srv/aos`，樹與 repo 放那裡 | 家目錄不動；但重建步驟單、兩台機器的路徑都要改，代價最大 |
| d daemon 起 proc 前自動替每層祖先加 ACL | （程式改） | 不用你動手；但 daemon 會默默改你家目錄的權限，跟「權限是使用者的事」（C-64）相反，不推薦 |

推薦 b：防呆夠用、只開最小的門；a 也可以，差別只在這台有沒有別的帳號。

沒有其他要拍板的；規劃沒講到的細節我自己定了，列在 [01 第三節](subuid-1119/01-現況核對與施工計劃.md)（D1～D9）。

## 做了什麼

| 檔 | 改了什麼 |
|---|---|
| `cpp/aos-daemon/src/child/subuid.{hpp,cpp}`（新） | 認 `sub:N`、查 `/etc/subuid`／`subgid` 與 PATH 上的 helper、環境白名單、小格 ACL（直接寫 xattr）、socketpair 握手、子行程 `unshare`→`setgroups({})`→`setresgid`→`setresuid`→換環境→`close_range`→走得到檢查 |
| `child/limits.{hpp,cpp}` | `sub:N` 寫法驗證、改走 `prep_sub`；`/etc` 讀檔共用 `etc_rows` |
| `child/child.cpp` | `launch` 在 fork 前備好、fork 後替子行程對號碼；`run_child` 在 setrlimit 之後換身分 |
| `daemon/daemon.cpp`、`daemon/table.cpp` | daemon.json `group`（60001～65536）；`state.json` 多 `group` |
| `tests/test_subuid.py`（新） | 7 條，2 條要真 newuidmap |
| daemon `docs/09`、`docs/01`、`docs/06`、`docs/07`、N-28（NORMS 09）、知識庫 `aos/cli/daemon.json` 的 `subuid`、kernel 站 README | 新節「換成 subuid」、`group` 鍵、錯誤表兩列、測試清單、條文一條、給 agent 看的英文說明、拿掉「daemon 認之前不要填 sub:N」 |

程式、測試與文件在 commit `368719e7a`。持久格式：daemon 的 `state.json` 多一欄 `group`，不用重建任何東西。

## 沒做與為什麼

- **真機換身分的實測**：缺 newuidmap，agent 不能 sudo。
- **K18 後半**（子 daemon 沒寫 `group` 沿用父的）：要讀父 daemon 的表，跟最小一刀無關；今天子 daemon 沒寫就是 60001。
- **信上的 `groups`**（K15 進階附屬群組）：仍不認；普通用途用不到。
- **信箱與共用夾的權限**：K16 定成用 `aos-share`，不歸 daemon 自動做；所以換了身分的 agent 還寄不出信。
- **K9 用信夾擁有者認寄件人**、**K10 收緊活樹權限**、**清道夫讀不到 environ**（04 第 24 條）、**`rm` 時用同一個 subuid 清垃圾**：都在乙之後，下一刀。
- **eca 本體換身分**：K7 已裁先留 1000。

## 留下的東西

- 暫存：`~/.aos/scratch/subuid-1119/`（`src/` 乾淨複本＋已建好的執行檔、`tools/` 測試腳本、`run-*` 測試現場、`regress.log`）。另有兩個我手誤留下的空檔／暫存：`~/.aos/scratch/subuid-1119-setup.sh`（0 位元組）、`/tmp/kd-before.json`；照規矩不刪，留給使用者。
- 沒起常駐行程；測試起的 daemon 都由測試自己 SIGTERM 收掉。
