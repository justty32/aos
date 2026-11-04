← [入口](README.md)｜涵蓋：規劃（fable，照原則定的細節，可翻案） › 方案 C：daemon 自己也讀「控制口」，把對外的那部分切出 stack（使用者第四句）｜上一份 [03-方案-B-一個名字-使用者第二句-只要投](03-方案-B-一個名字-使用者第二句-只要投.md)｜下一份 [05-方案-A-B-C-怎麼選-fable-的](05-方案-A-B-C-怎麼選-fable-的.md)

### 方案 C：daemon 自己也讀「控制口」，把對外的那部分切出 stack（使用者第四句）

使用者接受「daemon 執行時的東西都放 stack」；新想法是：daemon 起來時讀同一個變數（暫名「控制口」），**給外人碰的那幾樣**放到它指的資料夾，stack 只留內部的，權限好切（外人只能寫信箱、讀 state，碰不到 stack 裡面）。

**1. 哪些算「對外」、哪些留 stack**（判準：這個檔是不是**設計上就要讓 daemon 以外的人讀或寫**；依據 N-13「窗＝程式願意分享給大家的」、N-16 信箱＝給人投的、C-64 權限歸 Linux 檔案層）：

| 放控制口（對外） | 誰碰、怎麼碰 | 留 stack（內部） | 理由 |
|---|---|---|---|
| `loops_mailbox/`（`tmp/`、`new/`、`cur/`） | 外人**寫**（aos-post send 先寫 `tmp/` 再 rename 進 `new/`），daemon 讀、搬 `cur/` | `loops/<名字>/`（子項小格：`loop.json`、`stderr.txt`、子項自己的窗與小格） | 小格是**子項的 stack**（C-70 子程式的 stack 由父訂），不是 daemon 對外的東西；外人要跟某個子項講話走子項自己的窗（aos-say 的 `--stack`） |
| `loops_state.json`（＋分頁 `loops_state_loops/`） | 外人**讀**（ls、eca-hub 的心跳檢查） | `eca_archive/`（eca-hub 的歸檔） | eca-hub 自己的東西，放 daemon 的 stack 是 10-30 的決定，跟對外無關 |
| `state.json`（loop 面的窗） | 外人讀 | daemon 自己的 `trace`、暫存、以後的鎖 | 內部 |
| `ctl.json`（停）；非信箱模式時的 `loops_ctl.json` | 外人**寫**——但只有「管理者」該寫得了 | | 權限上把 ctl 跟信箱分開：信箱群組可寫、ctl 只有擁有者可寫，正好是「誰能投、誰能停」兩種人 |

**2. 沒給變數時放哪**：**照舊全在 stack**（N-28 現行；使用者說「我覺得 OK」）。不猜別的位置（N-63 ②）。

**3. 怎麼落地——先看現有機制夠不夠**（11-01 使用者「明明現有的機制組合一下就能搞定」）：**今天不改 aos-daemon 一行就能切**。daemon.json 的 `ctl`、`state`、`loops_ctl`、`loops_state`、`loops_mailbox` 五個 key 都吃指示詞（`config.cpp resolve_keys`、`daemon.cpp` 對 `loops_*` 的 `aos::resolve`），絕對路徑照寫（impls README `loops_mailbox` 那列）。所以 `daemons/main/daemon.json` 寫

```json
"loops_mailbox": {"$env": "控制口", "$path": "loops_mailbox"},
"loops_state":   {"$env": "控制口", "$path": "loops_state.json"},
"ctl":           {"$env": "控制口", "$path": "ctl.json"},
"state":         {"$env": "控制口", "$path": "state.json"}
```

就是「daemon 吃這個變數、把對外的切到那邊」；不寫＝照舊在 stack。這有三個好處：(a) **不是 aos-daemon 偷讀一個固定名字的環境變數**——是 daemon 定義的作者在 daemon.json 裡明寫要讀哪個變數、放哪幾個檔，跟 `{"$env": "AOS_WS"}` 一樣的寫法（N-45、P-39「要往下傳就拿它的值明給」）；(b) 不給變數時 `$env` 解不開＝指示詞錯、退 1，不會默默退回 stack（N-63 ②、KISS「寫什麼就做什麼」）；(c) 控制口資料夾誰建、權限怎麼設，全在 daemon 外面由起它的人決定（C-67 放哪是呼叫方的自由、C-64 權限歸 Linux）。**要補的只有**：impls README 一段「把對外的窗切出 stack」的範例、demo 一份 daemon.json 示範——條文不用加新機制。

要不要再進一步讓 aos-daemon **內建**讀這個變數（沒寫路徑就自動放控制口）？不建議：那是把一個環境變數當 aos-daemon 的設定旋鈕（11-01 第 3 題裁「這就是濫用」——旋鈕走 argv 或設定檔）；而且 daemon.json 本來就是它的設定檔，再多一條「環境變數也能定位置」就是兩個地方管同一件事。

**4. 外部工具怎麼找到它**：aos-daemon-ctl、aos-eca-hub 讀同一個變數（控制口）→ 在那個資料夾裡用**預設檔名**找 `loops_mailbox/`、`loops_state.json`（跟今天找 `$AOS_DAEMON` 底下一樣，只是資料夾從 stack 換成控制口）。沒切的 daemon，使用者就把控制口設成 stack——**方案 B 是方案 C 的特例**（控制口＝stack）。所以程式面兩個方案改的是同一行：`daemon_dir()` 讀控制口變數。
   - 一個洞：aos-daemon-ctl `add --ws` 會把 `<WS>/.stack` 捷徑指到小格 `<stack>/loops/<名字>/`、eca-hub 要搬小格去歸檔——這兩件要知道 **stack** 在哪，控制口≠stack 時就找不到。補法（照「別多一個變數」）：daemon 把每個子項的小格路徑寫進 `loops_state.json` 那一列（多一欄 `stack`），工具從狀態窗讀、不用知道 daemon 的 stack。C++ 一行＋ctl／eca-hub 改讀那欄；這也是「stack 反查」唯一真的要加的一欄（上面方案 A 第 5 點說不加的，是 daemon 自己的定義／ws，不是這個）。

**5. 跟沙箱身分層的關係**（[10-24 sandbox](../../../2026-10/24/sandbox/README.md) S14、S17、`setup.sh --mailbox`）：那套已經是「信箱擁有者＝跑 kernel 的人、群組 `aos-run`、2770＋預設 ACL，沙箱裡只綁信箱、`AOS_KERNEL` 指它」。控制口資料夾就是 daemon 版的同一招：擁有者＝跑 daemon 的人；`loops_mailbox/`（含 `tmp/`、`new/`、`cur/`）2770＋同一組 ACL 讓 `aos-run` 投得進；`loops_state.json`、`state.json` 照 umask 644 誰都讀得到；`ctl.json`、`loops_ctl.json` 600 只有擁有者能停；**stack 整個 700**，沙箱裡不綁它。`setup.sh --mailbox` 現在只處理一個 kernel 信箱，要擴成「`--daemon-ctl 控制口`」把這四種權限一次設好（腳本層，不是 aos 程式）。注意 daemon 寫 `loops_state.json` 走原子 rename（N-05），控制口資料夾本身要讓 daemon 可寫、外人只要 r-x。這是方案 C 真正的收益：**沒切的話，信箱在 stack 裡，要讓外人投信就得把 stack 開給他走**，順手看到小格裡的一切。

**6. 跟 11-01「環境變數只在必要時用」的關係**：方案 C 用的變數仍只有一個（控制口），個數跟 B 一樣；它是 hub 型（一個位置、兩層以上要讀：外面的工具與 daemon.json 都讀，中間的 shell 不必懂）——11-01 第 1 題裁「hub 型不用改」。daemon 那邊靠 daemon.json 的 `$env` 明讀、不是程式偷讀，沒踩「環境變數當設定」那條。

**方案 C 的名字**：變數指的不再是 stack，`AOS_DAEMON_STACK` 就不對了；候選要照「外人跟 daemon 來往的那個資料夾」重想（命名使用者說再想，這裡只列）：`AOS_DAEMON_CTL`（使用者暫用；問題同上表——`ctl` 已是 `ctl.json` 那一個檔的名字，一詞兩義）、`AOS_DAEMON_WINDOW`（問題同上——信箱不是窗，而信箱正是最常碰的）、`AOS_DAEMON_BOX`／`AOS_DAEMON_FRONT`（新詞，要進縮寫表／名詞表）、`AOS_DAEMON_PUBLIC`（意思最準：「daemon 公開給外人的那一夾」，但 aos 沒用過 public 這個詞）。**fable 不在這裡推薦**，等使用者想；只提醒 C-54 一詞一義：別跟 `ctl.json`、`loops_mailbox`、「窗」這三個已有具體意思的詞撞。
