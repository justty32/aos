# screen_linger：eca 停下後由畫面自己的 tmux 計時關閉，起來撤單。

由 after_start／after_stop hook 呼叫，stdin 的事件 stack 是 agent stack；不是 handler 的 AOS_STACK（handler 的是 `<stack>/hookeds/<名>/`）。claude、codex、pi 三種小格都處理。tmux 需要支援 run-shell -d（3.2 以上）。

定義 cli.json 的 screen_close_after_s 是非負整數秒，預設 600，0 寫單後當場 reap；設定在停下時讀一次。讀不了設定就 warning 並用 600。stack 的 hookeds.json 把 screen_linger_start／screen_linger_stop 都設 null 可完全停用自動關畫面。退 1（輸入壞、讀寫失敗）經 `aos-hook fire --stop-on-nonzero` 交給 aos-loop＝loop 停，跟其他 loop 點的 hook 一樣。

到期單在 `<stack>/<kind>/screen_close.json`，包含 token、loop 與畫面身分、期限與重試次數。reap 不讀 daemon 表；只核本機 state.json 與 /proc。另一支 loop 已起來、token 換了或畫面重開就不關；pid 活著卻缺身分資料則留單警告。小格鎖忙時 30 秒後再試，最多 10 次。有人接著看也照關。

第一批沒有 sweeper 後援：SIGKILL／OOM 未跑 after_stop、或 agent 停著才開畫面，都不自動排關。到期期間搬樹可能使已排的絕對入口失效；改設定不改已排的期限。沒有到期單需要遷移；舊狀態可重建。
