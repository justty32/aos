aos proc 對 daemon 的存取哪些今天經 kernel、哪些改寄就攔得到、哪些是直接動檔，加上「kernel 回位置」那條路與兩套權限的現況（線 top-1121-kintercept，唯讀調查＋暫存樹實測，不標推薦）。

← [2026-11-21](../README.md)｜逐項表：[逐項表.json](逐項表.json)（20 列）｜切點那份在 [shell-指令的比喻/05-切點](../shell-指令的比喻-1121/05-切點.md)

## 先講結論

1. **kernel 今天只攔得到兩種信**：起停掛拆的信（整封 body 看得到，能放行、拒、改、排隊、留著等人、分流），和「表在哪」的查詢信。都要寄件人帶著 `AOS_KERNEL` 才寄（[01](01-今天kernel攔到什麼.md)）。
2. **早上那 14 處「認自己」的工具，設了 `AOS_KERNEL` 就已經有一個攔截點**：ctl who 改問 kernel 表在哪。攔到的只有「這個 sender 要看表」，看不到它拿表去做什麼；kernel 不回，這些工具 3 秒後全部 `KernelFailed`（實測）。
3. **最大的攔不到**：pause／resume（直接寫對方的 `ctl.json`）、塞別隻的 queue、改 stack 裡的設定、刪 stack、時鐘登記、讀別隻的 history。原因都一樣：它們是「先問表（經 kernel）→ 再直接動檔」，後一段沒有信。另外 `aos-mailbox --to`、guard 等六處查表不問 kernel、直讀 `AOS_DAEMON`（[02](02-逐項地圖.md)）。
4. **「寄信給 kernel、kernel 回位置」今天就有一個**：查詢信回的是路徑。實測讓站回一份拿掉 llm 的抄本，`agents_ctl` 就看不到 llm；但直讀表的 aos-mailbox 照樣寄得到（[03](03-問kernel回位置.md)）。
5. **信封的 sender 是寄件人的 `$AOS_WS`**（實測），同一個工作區的幾隻在 kernel 眼裡一樣。
6. 可能的樣子攤了七種，不標推薦（[05](05-可能的樣子.md)）。

## 兩套權限現在各有什麼、缺什麼（只限本地圖用到的）

| 零件 | 狀態 | 出處 |
|---|---|---|
| kernel 站放行／拒絕／改寫／hold／分流 | 有、能用；只對寄來的信 | 本夾 01 |
| 查詢信回位置（抄本） | 有、能用（站 hook 寫，實測） | 本夾 03 |
| `kernel_gate`（agent 自己當站） | 有、能用；忙或睡時不回 | 知識庫 `aos/kernel.json#/gate` |
| perm 權限站 | 有零件沒接上：出廠沒掛、ann 的 `.env` 那行是註解 | `start-api/README.md` |
| 信封 sender | 有，但自報（`$AOS_WS`），沒人驗 | linux-as-hw-1118/02 第 3 點；本夾實測 |
| 認真寄件人（看信檔擁有者） | 完全沒有（K9 已裁、站沒做） | kernel-limits-plan/05 K9 |
| guard | 有、能用；只擋 agent 自己的工具呼叫，讀表也直讀 | `py/tools/agent/guard/` |
| 沙箱 bwrap | 有、能用；範本沒有任何 `sandbox.json`，工作區包住整棵樹時碰得到 daemon | linux-as-hw-1118/02 第一節 |
| uid／subuid | 有、能用到 daemon：11-19 起 `limits.user: "sub:N"` 會換、kernel 站 `users` 會填；範本沒開 | daemon docs/09；linux-as-hw-1118/02 那句「daemon 不認」已過時 |
| stack 檔案權限（0700＋ACL） | 有：daemon 只替換了 subuid 的 proc 設；其他 proc 照同帳號 | daemon docs/09（`aos-share` README 還寫沒做，兩份不一致） |
| ACL 共用（`aos-share`） | 有指令；沒有逐次給、到期收 | kernel-limits-plan/08、K16 |
| 群組 | 有零件沒接上：daemon 不認 `limits.groups` | kernel 站 README「限制與身分」 |
| daemon ctl 信箱只給站寫 | 完全沒有現成設定（kernel 02 只寫了做法） | `templates/kernel/docs/02-kernel-modes.md` |
| rlimit／cgroup | 有、能用（cgroup 可選、預設關）；跟存取無關 | daemon docs/09 |
| 訊號（poke、kill）不同 uid | 換了 subuid 的才有 | linux-as-hw-1118/02 第三節 |

## 使用者原話（逐字）

11-21 下午，調查起因：

「然後是daemon，這個是比較麻煩的地方，我之所以要做這個調查，是因爲我要開始考慮有哪些東西可以讓aos kernel攔截，就是說，讓aos proc訪問daemon當然可以，只是說可能有些東西可以被kernel攔截」

頂層問「攔截是走規矩的才攔得到，還是繞不過去」，他答：

「我覺得原則是只防走規矩的存取，不守規矩的就是要自己承擔風險。真的要硬防，那就要多依賴linux的權限體系」

再補：

「不是說要讓kernel完全替代daemon的用途，只是說，我們來探索一下可能性。一個很值得走的道路是"寄一封信給kernel，kernel返回他想要存取的daemon的東西的位置"，這可能是kernel幫他取來，放在他能存取的地方，也可能是kernel暫時讓他具有權限，或是兩者皆有」

「老實說，這麼多的東西需要用到linux權限體系和aos權限體系，我很擔心目前aos在這方面不夠全面」

對照的舊話：11-18「權限管理這塊，其實都想要，但是先做防呆就好，先考慮單人使用，模型可信。」（[linux-as-hw-1118/06](../../18/linux-as-hw-1118/06-使用者裁定.md)）；11-21「agent不該和daemon耦合」（[aos-daemon-env-1121](../aos-daemon-env-1121.md)）；11-21「宣告這東西只是參考」（[kernel-宣告進interfaces/09](../kernel-宣告進interfaces-1121/09-使用者已答.md)）。

## 分檔

| 份 | 內容 |
|---|---|
| [01-今天kernel攔到什麼](01-今天kernel攔到什麼.md) | 誰寄給 kernel、站能做什麼、沒設時走哪、程式位置 |
| [02-逐項地圖](02-逐項地圖.md) | 20 列 a／b／c／d 與硬防靠什麼；乙類 14 處的攔截點 |
| [03-問kernel回位置](03-問kernel回位置.md) | 今天的查詢信、甲乙丙三種的零件、跟 1118 丁庚與 1113 的關係、這條路的邊緣狀況 |
| [04-邊緣狀況](04-邊緣狀況.md) | kernel 掛了、kernel 自己、人的殼、unset、巢狀 daemon 等十二條 |
| [05-可能的樣子](05-可能的樣子.md) | 七種，對照使用者五句話 |
| [06-實測紀錄](06-實測紀錄.md) | E1～E5 怎麼做、結果 |

## 替使用者做的選擇（逐條）

1. 用暫存樹的 perm 站加三個**測試用** hook 量測（記帳、換抄本、拒查詢），範本沒改。
2. 「攔了沒意義」那類（d）照我的判斷劃：daemon 給子行程的環境、站自己轉信、llm kernel 掛工作、路標顯示。
3. 七種樣子是我切的，名稱也是；不互斥。
4. 「問腦」列進 a 類但標明是另一條線，沒展開。

## 實測或讀程式

每列的依據寫在 逐項表.json 的 `evidence`。實測在 `~/.aos/scratch/top-1121-kintercept/`（HEAD `a04eb437c` 的複本，假腦），細節見 [06](06-實測紀錄.md)；夾留著沒刪。
