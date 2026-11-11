# do_task — 派一次小任務，收回短結論並保存子帳（11-11 由 thought 改名）。

子 agent 回答後，不論 `keep`，都先把公開宣告的帳抄到工具小格的 `observed/<子名>/`，才停止或移除子 agent。失敗與舊失敗子的清理也先保存帳。

抄帳只認子 stack 下各層 `interfaces.json` 的 `aos-observed.file`，保存帳的相對路徑與觀測介面宣告；沒有宣告的不猜。子再生的孫抄本一併保留。這次抄本的位置交給呼叫端寫入 `tool.child`，不混進結論。
