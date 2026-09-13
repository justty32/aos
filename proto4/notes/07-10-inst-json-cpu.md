# proto4 想法筆記 §7–§10：inst.json 與 cpu
← [索引](2026-09-08-ideas.md)｜[README](../README.md)

## 7. 翻案：`.aos/inst` 不是可執行檔，是 `inst.json`；cpu／kernel／daemon 的分工

使用者原話（看過 proto4-1 Python 版之後）：

> .aos/inst這個檔案，不會是一個可執行檔，我覺得還是要回到最初idea所說的，他就是一個json檔案.aos/inst.json，並且是嚴格的單一json物件，一個純粹的posix呼叫，有argv, stdin/out/err, exit status, env, ...。並且xxx/.aos/inst.json不是一個固定的位置。回到aos的操作系統架構層面，執行inst.json就是一個指令，然後一個持續以特定interval和條件中止...等設定去多次執行inst.json的程序，就是一個cpu正在執行。然後正如其他操作系統一樣，一開始一定是那個最初的cpu開始執行特定的proc，在這裡，我們叫他aos-kernel，他是與底層(linux)交互的介面，目前的基礎功能就是管理其他cpu，也就是每次指令都會去資料夾找request，然後將其掛到aos-daemon上讓他跑起來。我目前還在想，aos-daemon管理所有aos的通用cpu還有通用儲存空間，通用cpu指的就是持續執行inst.json的各linux process，通用儲存空間就是各linux process的佔用資源等。然後aos-kernel則是擁有最高權限的，與aos-daemon緊密結合的（對，預想中aos-daemon啟用之後，aos-kernel會一起被啟用，在使用上兩者是分不開的），aos-daemon提供基礎，aos-kernel做管理。

我的理解：

### 7.1 `inst.json`：一份「怎麼叫一次 POSIX 程式」的說明書

- **第 6 節的 6.2 被推翻**：不再是「直接執行 `.aos/inst`」，也不是「讀進來 system()」。inst 是**資料**，不是程式。
- 檔名 `inst.json`，內容**只能是一個 JSON 物件**（不是陣列、不是多個物件串起來）。
- 物件描述的就是一次 POSIX 呼叫要的東西：`argv`（跑什麼、帶什麼參數）、`stdin`／`stdout`／`stderr`（接哪裡）、`env`（環境變數）、`exit status`（怎麼看結果）……。也就是 `core/exec` 那一層本來就在做的「批次執行器」，一格只叫一次。
- 這樣 6.2 表格裡「直接執行」的好處大部分留住（選語言自由、argv 傳參數、symlink 共用 runner 可以改成 argv 指到同一支），而 6.2 的兩個麻煩不見了：不用管執行位、不用猜要不要退回 sh。
- 6.2 最後那個「inst 跑到一半改寫自己」的問題也變簡單：讀 JSON 是一瞬間讀完的，之後跑的是 argv 指到的程式，inst.json 本身沒在執行。
- **`xxx/.aos/inst.json` 不是寫死的位置**：路徑可以設定，對應第 1 節的 `:inst-path` 和 proto4-1 的 `config.json`。哪裡能設、預設值是什麼，還沒定。

### 7.2 三個名詞：指令、cpu、proc

拿真的作業系統比喻：

| aos 裡的名詞 | 是什麼 | 對應到 Linux |
|---|---|---|
| **指令** | 把某個 `inst.json` 執行一次 | 跑一次程式 |
| **cpu** | 一個一直在「照 interval 反覆執行同一份 inst.json」的東西，附帶什麼條件停下來等設定 | 一個 Linux process（跑著 loop） |
| **proc** | 被 cpu 跑的那個目標（資料夾／inst.json） | 程式本體 |

所以 proto4 kernel 裡的「登記一個資料夾＋interval」，用新名詞講就是「開一顆 cpu 去跑那個 proc」。

### 7.3 aos-kernel 與 aos-daemon 的分工（還在想，先記下來）

- **aos-daemon＝提供基礎**。管兩樣東西：
  - **通用 cpu**：所有正在反覆執行 inst.json 的 Linux process。
  - **通用儲存空間**：這些 process 佔用的資源。
- **aos-kernel＝做管理**。它是跟底層（Linux）打交道的介面，權限最高。開機順序跟一般作業系統一樣：一開始一定有一顆最初的 cpu，跑的就是 aos-kernel 這個 proc。
  - 目前的基本功能只有一件：**管其他 cpu**。它自己每格做的事＝去資料夾找 request，找到就掛到 aos-daemon 上讓它跑起來。也就是說，kernel 本身也是一個照 interval 反覆執行的 proc，**沒有例外**。
- **兩者綁死**：aos-daemon 起來的時候 aos-kernel 一起起來，使用上分不開。daemon 沒有 kernel 就只是一堆沒人管的 process；kernel 沒有 daemon 就沒地方掛 cpu。

跟 proto4／proto4-1 現況的差別：

- 現在是「一個進程裡一個 kernel，kernel 自己的 loop 每格輪流 cd 進每個資料夾跑一次」——所有資料夾**共用一個時鐘、同一個進程**。
- 新講法是「每個 proc 一顆 cpu、一顆 cpu 一個 Linux process、各自有自己的 interval 與停止條件」——比較像 proto2 的「一個世界一個 `aos-loop` 進程」，但把「找 request、掛上去」這件事本身也做成一個 proc（aos-kernel）來跑。
- 「掛到 daemon 上」具體是 daemon fork 一個 process 跑 loop，還是 daemon 只登記、由誰去 fork，使用者說還在想。

還沒定、之後會撞到的：`inst.json` 的欄位清單與預設值（stdin 沒寫接哪裡？exit status 非 0 算什麼？）；「條件中止」有哪些條件（跑幾次、exit code、時間到、檔案出現）；cpu 掛掉要不要自動重開（proto2 有 restarts，proto4 沒有）；kernel 找 request 的資料夾在哪、request 長什麼樣（第 6.1 節已定 JSON）；「通用儲存空間」除了 process 佔的資源還包不包含資料夾裡的檔案。

## 8. 補定義：proc 的本體＝cwd、外在世界、手腳；`.aos/` 是 proc 碰不到的「法則」

使用者原話（proto4-2 做完之後）：

> 我這邊補些定義：一個持續在跑inst.json的proc，他的cwd，就是他的本體，也是他的唯一標示（對，在這個系統下，一個資料夾只能允許一個cpu在跑），而他這個proc能碰到的cwd外的其他資料夾或檔案，則是他的外在世界，而他的env/PATH，則是他的手腳（或是說可以做的行動）。在這種情況下，inst.json待在哪裡都可以，只是慣用來說，通常會待在cwd的.aos/inst.json，並且.aos會是這個proc無法存取的，畢竟這是他不該碰的所謂法則，規則之類的，那是時間，是類似空氣一般的存在

我的理解：

### 8.1 一個 proc 的四個部分

| 部分 | 是什麼 | 對應到 proto4-2 |
|---|---|---|
| **本體** | 它的 cwd，那個資料夾。也是它的**唯一標示**：一個資料夾最多一顆 cpu 在跑 | 現在 cpu 是用 `name` 認的，資料夾可以重複開；要改成用 cwd 的絕對路徑當 key |
| **外在世界** | cwd 以外、它碰得到的所有資料夾與檔案 | 沒特別限制，跑起來就是一般 Linux process 看到的整個檔案系統 |
| **手腳** | 它的 env／PATH，也就是它能做的行動 | `inst.json` 的 `env` 欄；PATH 裡有什麼程式，它就會什麼動作 |
| **法則** | `.aos/`——inst.json 住的地方。proc **自己碰不到**，像時間、像空氣：規則在那裡、決定它怎麼動，但它看不見也改不了 | 現在 `.aos/` 是普通資料夾，proc 想讀想改都行；`last.json`／`runs.jsonl`／`cpu.json` 也都寫在裡面 |

### 8.2 幾個直接推得出來的事

- **「一個資料夾一顆 cpu」是硬規則**，所以 cpu 的識別就是 cwd，不用另外取名字。register 同一個資料夾第二次＝拒絕（或視為同一顆）。`name` 這個欄位可以拿掉，`ls` 直接列路徑。
- **inst.json 在哪裡是慣例，不是規則**：慣例是 `<cwd>/.aos/inst.json`，但它可以在別處。第 7.1 節「位置可設」的意思在這裡定清楚了：是「這顆 cpu 拿哪一份 inst.json 來反覆跑」，跟 proc 本體（cwd）是兩件事。
- **`.aos/` 對 proc 是不可見的**。這句話的意思不只是「別去碰」，而是「它的世界裡沒有這個東西」。所以 proto4-2 把 `last.json`／`runs.jsonl`／`cpu.json` 寫在 `.aos/` 是對的（那是 cpu／daemon 的紀錄，不是 proc 的），但 proc 現在還是看得到，這點還沒做到。
- 「時間、空氣」的比喻：`.aos/` 裡放的是「它每隔多久被跑一次、被跑的時候 argv／env 是什麼」，這對 proc 來說就是它所處的物理法則。proc 不需要知道自己是被誰、以什麼節奏跑的。

### 8.3 要讓 proc 真的碰不到 `.aos/`，有幾條路（還沒選）

1. **只靠規矩**：README 寫「別碰」，程式不擋。最簡，proto4-2 現況。
2. **檔案權限**：`.aos/` 用另一個 user 擁有、mode 700，proc 用普通 user 跑（proto4-1 有過 `user` 欄）。要 root 或至少兩個帳號。
3. **mount namespace**：cpu 開 proc 之前 `unshare` 一層，把 `.aos/` 蓋掉（bind mount 一個空目錄或 tmpfs 上去）。不用 root（user namespace），但 Linux 專屬、細節多。
4. **FUSE**（第 5 節提過）：整個 cwd 由 aos 掛出來，`.aos/` 根本不在裡面。最徹底，也最重。

還沒定、之後會撞到的：cpu 的識別改成 cwd 之後，daemon 的 `state.json`／`cpus.json` 的 key 要換成絕對路徑，symlink／`..` 這種同一資料夾兩種寫法要先 `realpath`；inst.json 放在 cwd 以外的時候，`.aos/` 還算不算「法則」的位置（cpu 的紀錄檔寫哪）；proc 的「外在世界」要不要也有邊界（現在是整個檔案系統）；`.aos/` 不可見要選上面哪一條。

## 9. 補定義：daemon 由使用者手動管、壞了等於硬體壞了；daemon 起來順手開 kernel＝上電跑 boot 進 root

使用者原話：

> 然後daemon預期是由使用者自己手動管理的，包括他的生命週期。daemon這東西壞掉就等於是硬體壞掉，aos不管這事。.aos/的存取權限後續再處理。daemon啟動後，會順手啟動一個kernel，這就是類似上電後，會先跑boot那類，然後直接進入root

我的理解：

- **daemon＝硬體**。開機、關機、壞掉都是使用者自己的事：他手動 `start`、手動 `stop`，daemon 掛了就是「機器壞了」，aos 系統本身不負責救、不做自動重開、不做健康檢查。所以 proto4-2 隊長列的「daemon 被 SIGKILL 後 cpu 變孤兒」「重開不接回」這兩條，**不是 aos 要解的問題**，是硬體壞了，使用者自己處理（要的話用 systemd 之類外面的東西包）。
- **daemon 起來順手開 kernel＝上電跑 boot、然後直接進 root**。對應：上電＝`start` daemon；boot＝daemon 開第一顆 cpu、把 kernel 的 inst.json 掛上去；進 root＝kernel 開始每格跑，從此以後所有事都從 kernel 這裡進來。使用者不會另外去「開 kernel」，那是開機流程的一部分。proto4-2 現況就是這樣做的，方向對。
- **`.aos/` 的存取權限先擱著**（第 8.3 節那四條路不用現在選）。先照規矩，proc 別去碰。

對 proto4-2 的影響：不用改。隊長那份「之後會撞到」裡跟 daemon 生死有關的都可以劃掉；剩下值得改的還是第 8 節那條「一資料夾一顆 cpu、用路徑當 key」。

## 10. inst.json 格式沿用凍結分支 `core/inst` 那套；cpu 加「整體時限」

使用者原話（2026-09-09）：

> 1. inst.json的格式，我記得在src/就已經有很完善的處理了，你應該直接去拿來用。2.加上時間到，也就是整體時限。 3.cli後面再說。 4.等等。

### 10.1 inst.json 的格式＝凍結分支 `roadmap-run` 的 `core/inst`（SPEC §C-3～§C-6）

那套已經被 ctest 和攻擊腳本打過（見 [wf/salvage/01](../../wf/salvage/01-已驗證的規格結論.md)），直接搬進 proto4-2 的 Python cpu，不重新發明。原文在 `git show frozen/roadmap-run-2026-08:docs/SPEC.md`（§C-3 欄位表、§C-4 指示詞、§C-5 未知 key、§C-6 拒絕表）與 `core/inst/docs/format.md`、`exec.md`、`resolve.md`。

搬過來之後 inst.json 長這樣（一個物件，八個欄位，只有 `argv` 必填）：

| 欄位 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `argv` | 字串陣列 | 必填 | 跑什麼；`argv[0]` 走 PATH（用疊加後的 env 裡的 PATH 找） |
| `stdin` | 路徑 | 空＝沒有輸入 | **檔案**當標準輸入（不再是塞字串） |
| `stdout` | 路徑 | 空＝cpu 收進 last.json | 標準輸出寫到這個檔（建立並清空） |
| `stderr` | 路徑或 `{"$opt":"merge"}` | 空＝cpu 收進 last.json | 寫到檔；`merge`＝跟 stdout 走同一條 |
| `exit` | 路徑 | 空＝不寫 | 跑完把結束碼（十進位＋換行）寫進這個檔，fsync 檔案與目錄 |
| `cwd` | 路徑 | 空＝資料夾本身 | 工作目錄，相對於資料夾 |
| `env` | 物件 | `{}` | 疊在繼承環境上，只加不減；key 不能空、不能含 `=` |
| `timeout_ms` | 整數 | 0＝不限 | 這一次執行的上限 |

相對路徑一律從**資料夾**（proc 的 cwd＝本體）起算。跟凍結版差在兩處，理由都是「一顆 cpu 只跑一份、一次一個」：

- 拿掉 `parallel`（那是「一批多筆」才有的東西，proto4 一份 inst.json 只描述一次呼叫）、拿掉 `id`。
- `stdout`／`stderr` 沒寫時**不是繼承**，而是 cpu 抓回 `last.json`（proto4-2 現況）。有寫才導到檔案，此時 `last.json` 對應欄位記 `null`。

指示詞照搬：`argv` 的每個元素、五個路徑欄位、`env` 的值都可以寫 `{"$env":"NAME"}`（從 cpu 自己的環境取；變數不存在＝錯誤、存在但空＝空字串）或 `{"$ref":"file.json#/json/pointer"}`（相對於資料夾讀檔、RFC 6901 pointer、取回來的值當成本來就寫在那裡所以可以再巢狀、同一條鏈撞到同一個「絕對路徑＋pointer」＝循環＝錯誤）。`stderr` 多一個 `{"$opt":"merge"}`。指示詞物件剛好一個 key、值一定是字串。

**未知的 key 一律拒絕**，不是忽略（凍結版的理由：舊執行檔碰到新欄位寧可硬失敗，也別默默少一個限制）。§C-6 那張拒絕表每一條都要有對應的錯誤字串，寫進 `last.json` 的 `error`，這次不跑、cpu 照活。

逾時砍法也照凍結版：先對整個 process group 送 SIGTERM，給 2 秒，直接子行程還在就 SIGKILL。`last.json` 多一個 `timed_out: true`，`signal` 記實際砍中的那個（15 或 9）。找不到程式＝exit 127、沒執行權＝exit 126，都算「跑完了一次」，不是 `error`。

### 10.2 cpu 的第二個停止條件：整體時限

cpu 從起跑那一刻算，過了 `time_limit`（秒，0＝不限）就停：

- 正在睡（兩次執行之間）→ 醒來直接退。
- 正在跑 → 把那次執行當逾時砍掉（同上 SIGTERM→2 秒→SIGKILL），那次的 `last.json` 記 `timed_out: true`，然後退。**硬時限**，不等它跑完。
- 退之前把 `cpu.json` 補上 `stopped: "time_limit"`（另外兩種是 `"max_runs"`、`"sigterm"`）與 `ended_at`。

時限是 cpu 的設定，跟 interval 一樣走登記：`{"op":"register","dir":…,"interval":…,"time_limit":…}`，kernel 原樣翻成 spawn，daemon 傳給 cpu 的 `--time-limit`。CLI 先只加一個第三個位置參數 `register DIR [INTERVAL] [TIME_LIMIT]`，其他 CLI 的事使用者說後面再說。

跟著要改的一件事：**cpu 自己跑完退出（時限到、max_runs 跑滿、SIGTERM）之後，daemon 要把它從登記表拿掉**，不然那個資料夾就永遠「已經在跑」、再也 register 不進去。daemon 本來就會 reap 子行程，reap 到就從 `cpus.json` 與 `state.json` 移除、在 `daemon.log` 記一行。「cpu 掛掉不自動重開」不變。

還沒定、之後會撞到的：`$env` 該讀 cpu 的環境還是 daemon 的（現在兩者一樣）；`$ref` 能不能指到資料夾外（凍結版說能，範圍＝行程權限）；時限到時正在跑的那次要不要給更長的寬限；`exit` 檔算不算 proc 該看得到的東西（它寫在 proc 指定的路徑，不在 `.aos/`）。

