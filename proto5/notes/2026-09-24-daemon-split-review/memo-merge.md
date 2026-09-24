← [daemon 分開的理由審查](README.md)

# 合併／縮減派：拿掉 root 之後，兩支撐不住（2026-09-24，Opus）

## 結論

1. **「daemon 要 root 才能切使用者」站不住（重）。** 真要不同 uid，不用 root 也做得到（[實驗 3](exp/README.md)）；隔離我們已經用 bwrap 牢在做（[agent-access](../2026-09-24-agent-access/README.md)）；daemon 從來沒切過使用者（[aos_daemon.py](../../lib/aos_daemon.py)），proto5 決定兩支時也沒寫這條（[09-22 總結第 4 節](../2026-09-22-daemon-kernel-summary.md)）。
2. **拿掉之後，分開剩下的理由都是輕到中**，加起來撐得住「現在先別動」，撐不住「以後也該兩支」。
3. **建議「縮」而不是「全合」**：proto5-2 重寫 kernel 時，把 daemon 和 kernel 的**家與開機**合成一個，kernel 每一格**仍是單獨開一次的程式**。一個家、一條開機指令，崩潰隔離照舊。
4. 權限：**預設只走 bwrap 牢，daemon 永遠不 root**，寫進規範。

## 第 1 題（簡答）：切使用者要 root 嗎

換成真的另一個使用者要 root 或 sudo 白名單（實驗 1）。bwrap `--uid` 只是換名牌（實驗 2）。副 uid（subuid）不用 root 就有真隔離，但人從外面 `cat`／`rm` 不到孩子的家（實驗 3e／3f），傷 `ls`／`cat` 範式。

**root daemon 本身是更大的洞（重）**：daemon 誰往 `D/requests/` 丟檔就拉誰。它若是 root，任何能寫那資料夾的人（包括沒關牢的工具）就等於拿到「用 root 跑任意程式」。daemon 會從最單純變最敏感。

## 第 2 題：分開還剩哪些理由

| 理由 | 份量 | 我的看法 |
|---|---|---|
| root 切使用者 | **站不住** | 見上 |
| kernel 崩了有人拉 | 輕 | [kernel](../../spec/kernel/README.md) 本來就不是長命行程，「崩了只丟一格」靠**每格單獨開一次**，不靠兩支程式；縮版照樣每格開一次。 |
| daemon 極簡、少改 | 中 | 真有價值：長命那支要少改。但縮版只多「到時間就開一格 tick」約 30～50 行，排程程式仍在 tick 裡，改了下一格就是新版。 |
| 一個 daemon 管多個 kernel 家（K2） | 輕 | K2 是管理分區、自己的池（[cli-agents](../2026-09-24-cli-agents/README.md)），一個家一支爸爸就好。 |
| 26 條崩潰測試已過 | 中 | 是改的代價，不是設計理由；縮版只重寫開機／交接那批。 |
| 以後多機：一台一個 daemon | **中（對方最強）** | 到時本來就要改跨機講話，現在為它多背一個家不划算。 |
| 已拍板「daemon 不認識 kernel」 | 重（是代價） | 縮版一定要動這條，見下。 |

**兩支的代價**：兩個家、兩個環境變數、兩種死法、開機兩步；[`aos_kernel_boot.py`](../../lib/aos_kernel_boot.py) 有一段在交接舊 kernel cpu；r5 的順序陷阱（[甲反駁](../../../proto5-2/notes/2026-09-24-one-program/rebuttal-a.md)）。

## 「縮」之後長什麼樣

- **一支長命行程**（沿用現在 daemon 的迴圈）、**一個家**：`info`／`state`／`requests`／`responses` 照 cpu 範式，孩子表和 kernel 帳本放同一個家（帳本照 I 隊 ③ 可以是 sqlite）。
- 它照舊當所有 cpu 的爸爸（spawn、`restart:true`、停機階梯不變）。
- **多做一件**：前一格 tick 結束（或 `K/requests/` 有新檔）就開下一格 `aos-kernel tick` 當孩子，**不等它**，繼續收屍、收件。tick 仍是另一個行程、仍用檔案跟爸爸講話，所以不會「自己等自己」（I 隊 ② 的陷阱）。
- **kernel cpu 拿掉**：tick 鏈、開機交接都不用了；有新件就能馬上開下一格，縮小延遲（[idle-wait](../../../proto5-2/notes/2026-09-24-idle-wait/README.md) 也受益）。
- **誰拉這支爸爸**：選配 systemd 使用者服務（`Restart=on-failure`；它按整組收，也解掉 I 隊乙說的「爸爸被 KILL，孩子變孤兒」，見[乙反駁](../../../proto5-2/notes/2026-09-24-one-program/rebuttal-b.md)）。沒 systemd 就手動 `aos up`。
- **不做的**：不叫 systemd 當上千顆 cpu 的爸爸（上千單元太重、不是每台都有）。這點我退讓：**自製 daemon 當 cpu 的爸爸是對的**，錯的是它自己一個家、跟 kernel 分兩步開。

**要動的已拍板前提**：daemon §8「只管生死、不認識 kernel」要改成「只管生死＋定時開 kernel 一格」；kernel「跑在 kernel cpu 上的 tick 鏈」改成「爸爸開的一格」；cpu 範式不動。
**代價粗估**：daemon 加 30～50 行；kernel 開機 119 行大半刪；tick 自己排下一格那段刪；開機／交接的崩潰測試重寫。proto5-2 本來就要重寫 kernel，順路做不多花一次。

## 第 3 題：對 I 隊結論的影響

**「現在不動」不變；③（分開＋帳本 sqlite）改成「③＋縮」**：帳本換 sqlite 的同時把家與開機合一。I 隊的「合一」都是排程搬進長命行程（②④），沒考慮「家合一、tick 照舊單獨跑」這格。

## 第 4 題：權限怎麼走

**預設：只用 bwrap 牢＋`envs clear`，不切使用者。** 牢擋得住是因為「沒掛」，對同一個人照樣有效；astra 說的「同 UID 能讀 daemon 帳本找 K2」，牢裡不掛 D／K 就擋住了。
切使用者只在以後「連 agent 本身都不可信」時才考慮，要做也走副 uid、由爸爸開一次 namespace（每顆多零點幾毫秒），**不走 root**。

## 第 5 題：要使用者拍的

1. **「daemon 永遠不用 root，隔離走 bwrap」寫進規範？** 預設：寫。
2. **proto5-2 重寫 kernel 時要不要「縮」（一個家、一條開機，tick 仍每格單獨跑）？** 預設：要，跟換 sqlite 同一次做；不做就至少包 `aos up`／`aos down`。
3. **為「以後多機」保留兩個家？** 預設：不保留，到多機時再拆。
4. **systemd 使用者服務當那支爸爸的爸爸？** 預設：選配，不強制。
