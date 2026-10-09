# mail 信箱包

一個放在資料夾裡的小郵局：誰都可以寄一句話給別人，對方看完、辦完就回你一封「完成」，最後一個指令查還有沒有沒辦完的事。

← [modules](../README.md)｜進階（其他狀態、團隊、程式 API、內部設計）→ [ADVANCED.md](ADVANCED.md)

## 四個概念

- **郵局資料夾**：所有信箱都放在這裡。用 `export AOS_MAIL_ROOT=<資料夾>` 指定一次（或每個指令加 `--root <資料夾>`）。
- **請求（REQUEST）與完成（DONE）**：send 寄出的是請求；對方辦完，系統自動回一封 DONE 給你。日常只要懂這兩種。
- **序號**：read 會在每封信前面編號 1、2、3…，done 用這個號碼指定要辦哪封。
- **辦完（done）**：看過不等於辦完。done 把信收進已辦，是請求就順便回 DONE；audit 只看還沒 done 的請求。

## 第一次跑

在 **repo 根目錄**整段貼上（`$(mktemp -d)` 開一個臨時郵局）：

```sh
M=$PWD/proto7-2/modules/mail/aos7-mail
export AOS_MAIL_ROOT=$(mktemp -d)
"$M" send alice bob '請 bob 檢查範例'
"$M" read bob
"$M" done bob 1 '檢查完了，沒問題'
"$M" read alice
"$M" done alice 1
"$M" audit; echo $?
```

會看到（路徑、時間、id 每次不同）：

```text
注意：bob 是新信箱（第一次收信）
{"sent": "/tmp/tmp.qYffPObHzl/bob/inbox/20261009T1536-alice-REQUEST.md", "id": "alice-20261009T153659-385fa96d43e8"}
1  20261009T1536-alice-REQUEST.md  請 bob 檢查範例
已辦結 20261009T1536-alice-REQUEST.md，已回 DONE 給 alice
1  20261009T1536-bob-DONE.md  檢查完了，沒問題
已歸檔 20261009T1536-bob-DONE.md
0
```

意思是：alice 寄請求給 bob → bob 看到第 1 封 → bob 辦完並自動回 DONE → alice 看到回信、歸檔 → audit 印 0，表示沒有沒辦完的請求。
第一行「新信箱」是提醒你確認收件人名字沒打錯，不是錯誤。

## 四個指令

| 指令 | 做什麼 |
|---|---|
| `send <我> <對象> '<一句話>'` | 寄一個請求給對象。印一行 JSON（信檔位置與信 id）。 |
| `read <我>` | 列出我還沒辦的信：`<序號>  <檔名>  <一句話>`；沒信印 `（沒有新信）`。 |
| `done <我> <序號> ['<一句話>']` | 辦完第幾封。若是請求，**一定要給一句結論**，會回 DONE 給寄件人；若只是回信，不用給，直接歸檔。 |
| `audit` | 查整個郵局還有沒有沒辦完的請求：沒有就退出 0，有就列出並退出 1。 |

- 名字只能用英文字母、數字、`.`、`_`、`-`。
- **done 為什麼要先 read**：序號只認你最近一次 read 看到的清單。這樣就算中間又來了新信，`done bob 1` 也不會辦到你還沒看過的那封。沒 read 過會提示「請先 read」。
- 忘了用法：`aos7-mail --help`、`aos7-mail <指令> --help`（不用先設郵局資料夾）。
- 出錯時退出碼 2，stderr 一行白話說明怎麼改。

## 想做更多

要回「卡住／失敗」等其他狀態、報進度、開團隊、找上游、用 Python 呼叫、了解檔案格式與當機復原，看 [ADVANCED.md](ADVANCED.md)。日常用不到。

範例腳本 [examples/two_nodes.sh](examples/two_nodes.sh)（自己檢查後印 OK）；測試在 `tests/`，跑法見 ADVANCED.md〈驗證〉。
