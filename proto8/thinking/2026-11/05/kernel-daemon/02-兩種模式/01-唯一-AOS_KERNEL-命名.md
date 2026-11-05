← [回入口 02-兩種模式.md](../02-兩種模式.md)｜段落：§ 3「唯一能下 ctl」怎麼保證、§ 4 `AOS_KERNEL` 指什麼、§ 5 誰算 kernel｜上一份：—｜下一份：—

## 3 「唯一能下 ctl」怎麼保證（[05 衝突 2](../05-衝突與方向題.md)）

aos 從頭到尾不驗寄件人身分（kernel 已知限制、N-54 末、C-64「用檔案是為了借 Linux 權限」）。「唯一」只有三級，**推薦前兩級、不做第三級**：

1. **約定**（同一帳號裡能做到的全部）：daemon 的 ctl 信箱還是會被 `procs_state.json` 回報、aos-daemon-ctl 還是找得到——擋不住，只能文件寫「這台 daemon 走 0 號，掛東西寄 `$AOS_KERNEL`」。藏法（可選）：daemon.json `procs_ctl_mailbox` 指到 0 號的 stack 底下（例 `procs/procs-kernel/base/`）、`procs_ctl` 寫 `null`——只是藏，不是擋。
2. **Linux 權限**（真的擋）：daemon 與 0 號 kernel 同一帳號 A，其他 proc 另一帳號 B（沙箱 `s6-setuidgid aos-run` 現成，[10-24 sandbox](../../../../2026-10/24/sandbox/README.md)）；daemon 的 ctl 信箱 `new/`、`tmp/` 755＝B 寫不進（aos-post `send` 當場 `MailboxBad`，edge-basics 實測 #24）；0 號的 `requests/` 給 B 可寫（`setup.sh --mailbox` 那套）。這就是 C-64 的本意，不加程式。
3. **daemon 認寄件人白名單**（不做）：要讀信封 `sender`、要定「誰算誰」、違 C-52／C-56、跟「寄信的人是誰不驗」先例相反。

## 4 `AOS_KERNEL` 在兩種模式下指什麼（使用者 11-05：留給「通用於所有 proc 的 kernel」）

- **定義**：`AOS_KERNEL`＝**「要掛 proc 往哪寄」的 hub**（N-63 三件：資料夾、沒設＝…、繼承）：值是一個**收 `procs_*` 信的信箱資料夾**，信的 body 形狀跟 daemon 的 ctl 信箱一模一樣——所以 daemon 的 ctl 信箱本身就是最基礎的那個 `AOS_KERNEL`（模式 0）。
- **沒設**＝kernel 就是 daemon：要掛 proc 的程式（llm kernel、以後的 aos-daemon-ctl）寄到 `$AOS_DAEMON/procs_state.json` 回報的 `procs_ctl_mailbox`。這不是 N-63 ②「猜位置」——那條路是 N-64 ④ 明定的「子項靠 `AOS_DAEMON` 找 daemon 的信箱」，而且 daemon 本來就是 kernel。所以 `AOS_KERNEL` 沒設**不報 `KernelMissing`**（代定、可翻案；跟 `AOS_LLM_KERNEL` 沒設＝`LlmKernelMissing` 不同——問腦沒有 daemon 可退）。
- **模式 1**：`AOS_KERNEL`＝daemon 的 `requests/`（判官讀的那個）。**模式 2**：`AOS_KERNEL`＝0 號 proc 的 `requests/`。都由人設或寫進 daemon 的 `.env` 用指示詞帶給子項（portable-flow 題 5 的同一招：`{"$env": "AOS_STACK", "$path": "procs/procs-kernel/requests"}`），人不設就是模式 0。
- **`AOS_LLM_KERNEL`**＝llm kernel 的信箱（問腦寄到哪），**人設、不自動傳**（使用者 11-05）；跟 `AOS_KERNEL` 各管一事：一個管「掛不掛 proc」、一個管「問腦」。
- **aos-daemon-ctl／aos-agent add**：第一版不改（照舊寄 daemon 的 ctl 信箱）；之後要讓它們也走 0 號＝有 `AOS_KERNEL` 就寄那裡，一行改動，列在 [06 步 6](../06-實作步驟草稿.md)、不急。

## 5 誰算 kernel、名字帶不帶 kernel（照使用者第 6 句）

| 角色 | 算不算 | 名字 |
|---|---|---|
| daemon | 算（最基礎） | `aos-daemon`，不改 |
| 模式 1 的判官身體 | 算（它決定掛不掛） | `judge/`（資料夾程式；是 daemon 的身體、不是獨立程式，不帶 kernel） |
| 模式 2 的 0 號 proc | 算（轉交型） | `procs-kernel`（主題在前，C-54；「kernel」只給真的在判「掛不掛」的） |
| llm kernel（改掛後） | 算 | `aos-llm-kernel`，不改 |
| aos-daemon-ctl、aos-agent | 不算 | 不改 |
