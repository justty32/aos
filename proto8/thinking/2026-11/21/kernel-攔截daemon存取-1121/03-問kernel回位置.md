探索使用者說的那條路：「寄信給 kernel，kernel 回它要存取的 daemon 東西的位置」：今天已有的、每樣東西可以是哪種、跟舊紀錄的關係（只列事實與可能的樣子）。

← [README](README.md)｜上一份：[02](02-逐項地圖.md)｜下一份：[04-邊緣狀況](04-邊緣狀況.md)

## 今天已經長這樣的東西：查詢信

- **有，就是「表在哪」那封**。寄 `{"procs_state_path": true}` 給 `AOS_KERNEL`；最後的 daemon 回 `{"applied": true, "procs_state_path": "/abs/…/procs_state.json"}`（`null`＝它的表窗關著）。程式：問的那頭 `py/aos/daemon_ctl/state_path.py`，答的那頭 `cpp/aos-daemon/src/daemon/mailbox.cpp`。
- **回的是路徑，不是內容**。問的人拿到路徑後自己讀檔；表裡的相對路徑從**那個檔所在的資料夾**算（`state_at`）。
- **kernel 能回不同的位置**：知識庫 `aos/kernel.json#/write_your_own` 寫了三種：照轉、自己答一個路徑、不答。實測做了第四種：站開 `reply_via_me`，`before_reply` hook 把 daemon 的答案換成站自己 stack 裡的一份抄本（拿掉 llm 那列、相對路徑先轉成絕對）。結果 `agents_ctl ls` 看不到 llm、`where llm` 報 `InstanceMissing`；但 `mailbox_send` 給 llm 照樣寄得出去，因為 aos-mailbox 不問 kernel、直讀 `AOS_DAEMON` 的表（02 第 6 列）。
- 代價實測：開代回後 `self_state` 從 3.5 秒變 7.4 秒（10 封查詢都多繞一站）。

## 三種樣子的現有零件

- **甲 kernel 取一份放到問的人碰得到的地方**（抄本）
- **乙 kernel 回原本的位置，並暫時開權限**
- **丙 兩者都有**（例：表給抄本，那一隻的 stack 給原位置＋開權限）

| daemon 管的東西 | 今天怎麼拿到位置 | 甲 抄本 | 乙 原位置＋開權限 |
|---|---|---|---|
| 表 `procs_state.json` | 問 kernel（設了時） | **今天就做得到**（實測）。新鮮度＝問的那一刻；aos-agent 一次執行只問一次，eca 畫面看守每 5 秒重問。表本來就是唯讀，沒有寫回的問題 | 同 uid 下不用開。換 uid 後要讓 subuid 讀得到表檔，現成可用 `aos-share read`（ACL），但沒有「這一次給、之後收」 |
| 別隻的 stack 路徑（say、pause、改設定、讀 history 都靠它） | 表上那一列的 `stack` 欄 | 抄本可以不給那列（實測），或把 `stack` 指到別的夾（讀程式推論：pause 會照抄本寫那個夾的 ctl.json）。寫回原 stack 要有人搬，今天沒有 | daemon 只替換了 uid 的 proc 設自己 stack 的 0700＋ACL（11-19，daemon docs/09）；要讓另一隻進去，手動有 `aos-share stack --uid U`；沒有逐次開、到期收 |
| 時鐘 `clock`、登記表 | `$AOS_CLOCK`（根的 .env 給），不問 kernel | 讀鐘可給抄本；登記是寫，抄本沒用，得改成請 kernel 或鐘代寫 | 登記表在根的 stack，開權限＝ACL；沒有現成指令專門做 |
| daemon 的 ctl 信箱 | 表上 `procs_requests` 欄 | 抄本可以把它改指 kernel 自己的信箱（讀程式推論；只對讀表才寄信的程式有用，aos-daemon-ctl 不讀這份） | kernel 02 寫的硬擋就是反過來：ctl 信箱不給 B 寫、站的 `requests/` 給 B 寫 |
| daemon 的 `state.json`、`state_flux.json` | 直讀（只在沒走 kernel 時） | 可給抄本 | 同上 |

## 「暫時開權限」的零件做到哪

- `aos-share`（`py/aos/apps/share/`）：`team`、`read`、`key`、`work`、`drop`、`stack` 六種 ACL 設法，加 `check`、`reset`。是人或程式下的一次性指令；**沒有到期、沒有「誰給的、何時收」的帳**。
- `aos-asuser sub:N -- 程式`：免 root 換成 subuid 跑一支程式。
- daemon `limits.user: "sub:N"`：11-19 起認，起之前替那隻的 stack 設 0700＋ACL（daemon docs/09「換成 subuid」）。kernel 站的 `users` 表會照名字填它。**`limits.groups` daemon 還不認**。（`aos-share` README 第 52 行還寫「daemon 段 3 還沒做」，跟 daemon docs/09 對不上，兩份文件不一致。）
- 少的一塊：kernel 認不出真的寄件人。11-13 已裁 K9「uid 分開後 kernel 用信檔擁有者認寄件人」，站程式裡沒有看檔案擁有者的碼（`py/tools/aos/kernel/*.py` 沒有 `st_uid`）。

## 跟舊紀錄的關係

- [linux-as-hw-1118/05 丁「權限＝遞給你的夾」](../../18/linux-as-hw-1118/05-發想.md)：能碰什麼看「遞給它什麼」。甲（抄本）是丁的一種：kernel 遞給你的那份就是你看得到的世界。05 寫的代價是要 bwrap 布景；查詢信這條不用布景，但只管得到「問了才讀」的程式。
- 同檔 庚「權限也是資源，寄信給 kernel 要」：就是乙。05 當時寫「要有乙（每隻一個 subuid）或丁當底，同 uid 時 agent 根本不用申請就碰得到」，跟使用者今天的原則同一句話的兩面：走規矩的會申請，不守規矩的不用申請，硬防靠 Linux 權限。
- [kernel-limits-plan（11-13）](../../13/kernel-limits-plan.md)：已裁的 K6（一台 daemon 一個群組）、K9（信檔擁有者認寄件人）、K16（stack ACL 由 daemon 自動設、共用夾用 `aos-share`）、K17（子 daemon 的 agent 不帶上層群組，要分享就用 ACL 點名）。乙要的「開權限」零件大多在這份裡規劃過；「逐次給、到期收」沒有出現在 K1～K18。
- 知識庫 `aos/kernel.json#/write_your_own` 已寫「table questions: pass it on, answer it yourself, or leave it」，也就是 kernel 回自己的位置今天就是被允許的寫法。

## 這條路的邊緣狀況（另見 [04](04-邊緣狀況.md)）

1. **位置回了，kernel 就看不到之後的存取**：問一次表，可以讀十次、改五隻的 stack。要看得到，就得每一次動作都寄信，或者給的位置本身是 kernel 管的（抄本、代理夾）。
2. **回的位置什麼時候失效**：aos-agent 一次執行內一直用同一份（`_asked` 快取）；daemon 那頭表換檔名、stack 搬走，問的人不會知道，要等下一次執行重問。
3. **抄本過期**：抄本是問的那一刻的表，之後 phase 變了、列被拿掉，問的人照舊讀舊的。走 kernel 時多數起停只看回信、不讀表，但 `set-def` 拔下前會讀表等它真的停好（`ctl/phase.py` 給 `look=True`），讀的是同一個路徑；抄本不會自己更新的話，它會等到逾時（讀程式推論，沒實測）。
4. **同一個帳號下「暫時開權限」等於沒差**：大家本來就讀寫得到。照使用者的原則，這不算問題：走規矩的照 kernel 給的位置走，不守規矩的自己承擔；真的要擋才換 uid。
5. **抄本放哪也是存取**：放在站的 stack 裡，問的人要讀得到站的 stack；換 uid 之後就要替抄本夾開讀權限。
