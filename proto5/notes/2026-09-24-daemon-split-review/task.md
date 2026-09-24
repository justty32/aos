← [daemon 分開的理由審查](README.md)

# 任務書（給兩個子隊與 codex，2026-09-24）

唯讀審查，只寫意見，不改程式、不改規範。回答用繁體中文、白話。

## 題目（使用者原話）

「關於為何要把 daemon 和 kernel 分開這件事，我想起來了，是因為當時想說可以透過切換使用者的方式來做權限，所以 daemon 就要 sudo……這個理由好像不太站得住腳？麻煩再去審看看。」

也就是：daemon／kernel 分成兩支程式的理由之一，是 **daemon 以 root 跑，替每個 kernel／cpu／agent 切成不同的 Linux 使用者，用作業系統的使用者權限當隔離**。審這個理由現在還站不站得住。

## 背景（repo 裡）

- 現在的 daemon：`proto5/spec/daemon/README.md`（只管 cpu 行程的生死：spawn、`restart:true`、停機階梯；pipe 只管生死；家照 cpu 範式、JSON-RPC）。程式 `proto5/lib/aos_daemon.py`（430 行）。現在**完全沒有**切使用者。
- kernel：`proto5/spec/kernel/README.md`（不是長命行程，一格一格 `aos-kernel tick`，跑在 daemon 拉起來的一顆 kernel cpu 上；帳本 `K/state.json`）。
- cpu 範式：`proto5/spec/cpu/README.md`（一個家一個主人行程）。
- 歷史：proto2 的 `proto2/notes/tools/identity-and-env.md`（當時就寫「切身份靠 runuser，kernel 得用 root 跑」，建議停在全部同一個 user）；proto4-1 的 `user` 欄位走 `runuser`、要 root，沒測過。proto5 決定維持兩支時的理由在 `proto5/notes/2026-09-22-daemon-kernel-summary.md` 第 4 節第 3 題：「daemon 管 Linux 進程、kernel 管排程；B 併成一支會『kernel 崩了 aos-run 全沒人管』」——**那份沒寫權限**。
- I 隊（合不合一、脫不脫檔）：`proto5-2/notes/2026-09-24-one-program/README.md`，建議「現在不動；要動選③分開＋kernel 帳本改 sqlite」。
- L 隊（agent 權限）：`proto5/notes/2026-09-24-agent-access/README.md`，access.json＋bwrap 牢 `aos-jail`、envs clear，牢不需要 root。
- cli-agents：`proto5/notes/2026-09-24-cli-agents/README.md`（Claude Code／Codex 當 cpu 池、「另一個 kernel 家」K2；astra 審查說「隱藏路徑不是權限；同 UID 可讀 daemon 帳本找 K2」）。
- idle-wait：`proto5-2/notes/2026-09-24-idle-wait/README.md`（kernel 停車＋喚醒，kernel 多 50～80 行）。

## 已跑的實驗（`proto5/notes/2026-09-24-daemon-split-review/exp/README.md`）

1. 不是 root：`setpriv --reuid`、`runuser`、`systemd-run --user -p User=／DynamicUser=` 全部換不了人。
2. `bwrap --unshare-user --uid 2001`、`unshare -U --map-user`：只換名牌，照樣讀到別的家；bwrap 擋得住是因為「沒掛」。
3. 用 `/etc/subuid`（lorkhan:100000:65536，系統原配）＋`unshare --map-auto` 開多 uid namespace，裡面 chown＋`setpriv` 降權：A 的孩子**讀不到** B 的家、切不回去；但祖先 700 資料夾擋路、外面的 lorkhan 反而 cat／rm 不到孩子的家；開 namespace 的爸爸在裡面是假 root，讀得到全部。
4. 啟動代價：直接 0.19 ms、`unshare -U` 0.34、bwrap 0.72～1.19、`map-auto`＋setpriv 1.43 ms。

## 要回答的

1. 切使用者做權限，需要 daemon 是 root 嗎？比較：root daemon 再 setpriv／setuid 降權；`sudo -u` 白名單（sudoers NOPASSWD 限定指令）；`systemd-run`（系統層）／每個使用者自己的 systemd user 服務；bwrap user namespace；subuid 多 uid namespace；setgid＋檔案群組權限。每種：要不要 root、擋得住／擋不住什麼、對「一個家一個主人」的 cpu 範式友不友善、上千顆 cpu 的啟動成本。
2. 這個理由站不站得住？若站不住，分開還剩哪些理由（kernel 死了 daemon 拉回來、daemon 極簡不常改、一個 daemon 管多個 kernel 家、K2 另一個家…）？各自份量？夠不夠撐「兩支程式」？
3. 對 I 隊結論的影響：變不變？怎麼變？
4. 權限這條線怎麼走：切使用者 vs bwrap 牢 vs 兩者都要？建議與預設。
5. 要使用者拍的（每題附預設）。

規矩：不跑 sudo、不建使用者、不改系統設定；不碰 LM Studio／ollama／`localhost:1234`。
