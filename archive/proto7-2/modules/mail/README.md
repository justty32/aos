# mail 信箱包

一個放在資料夾裡的小郵局：誰都可以寄一句話給別人，對方看完、辦完就回你一封「完成」，最後一個指令查還有沒有沒辦完的事。

← [modules](../README.md)｜進階（其他狀態、團隊、程式 API、內部設計）→ [ADVANCED.md](ADVANCED.md)

## 四個概念（就這些）

1. **郵局資料夾**：用 `export AOS_MAIL_ROOT=<資料夾>` 指定一次（或每個指令加 `--root <資料夾>`）。每個名字第一次收信時，裡面自動長出他的信箱，不用先建。
2. **請求與完成**：send 寄出的一律是「請求」（檔名帶 REQUEST）；對方辦完，系統自動回一封「完成」（帶 DONE）給你。日常只有這一對。
3. **序號**：read 在每封信前面編號 1、2、3…，done 用這個號碼指定要辦哪封。
4. **辦完＝歸檔**：看過不等於辦完。done 把信收進已辦（歸檔）；是請求就順便回「完成」。

## 第一次跑

整段貼上（第一行先切到 repo 根目錄；`$(mktemp -d)` 開一個臨時郵局）：

```sh
cd "$(git rev-parse --show-toplevel)"
M=$PWD/proto7-2/modules/mail/aos7-mail
export AOS_MAIL_ROOT=$(mktemp -d)
"$M" send alice bob '請 bob 檢查範例'
"$M" read bob
"$M" done bob 1 '檢查完了，沒問題'
"$M" read alice
"$M" done alice 1
"$M" read alice
```

會看到（路徑、時間、id 每次不同）：

```text
aos7-mail: 注意：bob 是新信箱（第一次收信）。確認名字沒打錯；沒錯就不用管
{"sent": "/tmp/tmp.XsBHbYyg6A/bob/inbox/20261009T1617-alice-REQUEST.md", "id": "alice-20261009T161753-d64ac66c2b4e"}
1  20261009T1617-alice-REQUEST.md  請 bob 檢查範例
已辦結 20261009T1617-alice-REQUEST.md，已回 DONE 給 alice
1  20261009T1617-bob-DONE.md  檢查完了，沒問題
已歸檔 20261009T1617-bob-DONE.md
（沒有新信）
```

意思是：alice 寄請求給 bob → bob 看到第 1 封 → bob 辦完並自動回 DONE → alice 看到回信、歸檔 → alice 的信箱清空（沒有新信），整件事結束。
第一行「新信箱」是提醒你確認收件人名字沒打錯，不是錯誤。

## 三個指令

| 指令 | 做什麼 |
|---|---|
| `send <我> <對象> '<一句話>'` | 寄一個請求給對象。印一行 JSON（信檔位置與信 id）。 |
| `read <我>` | 列出我還沒辦的信：`<序號>  <檔名>  <一句話>`；沒信印 `（沒有新信）`。 |
| `done <我> <序號> ['<一句話>']` | 辦完第幾封。若是請求，**一定要給一句結論**，會回 DONE 給寄件人；若只是回信，不用給，直接歸檔。 |

- `<我>` 是你自己的名字，`<對象>` 是收件人名字；只能用英文字母、數字、`.`、`_`、`-`。
- `export` 只在目前這個終端機有效；開新終端機要再 export 一次（或改用 `--root`）。
- **done 前先 read**：done 的號碼＝你最近一次 read 畫面上的號碼。中間又來新信也不會改號，所以不會辦到你沒看過的信。沒 read 過會提示「請先 read」。
- 忘了用法：`aos7-mail --help`、`aos7-mail <指令> --help`（不用先設郵局資料夾）。
- 出錯時 stderr 一行白話說明怎麼辦。

## 想做更多

日常用不到；需要時看 [ADVANCED.md](ADVANCED.md)，裡面有：

- **其他狀態**：回「進度／卡住／要使用者決定／失敗」，而不只是完成。
- **團隊與上游**：一群人共讀的團隊信箱、`--up` 自動寄給上司。
- **查帳**：一個指令查整個郵局還有沒有寄出卻沒人辦完的請求。
- **給程式用**：`--json`／`--quiet` 輸出、Python 函式、信檔格式、當機後怎麼自動補完。

範例腳本 [examples/two_nodes.sh](examples/two_nodes.sh)（自己檢查後印 OK）；測試在 `tests/`，跑法見 ADVANCED.md〈驗證〉。
