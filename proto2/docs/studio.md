# 小型工作室

`studio` preset 一次建七個 agent。甲方只找 `sales`。專案放在 owner 世界的 `team/projects/`。

## 開隊、下單、看回覆

```sh
aos-user team new work/studio --preset studio --engine deepseek-flash \
  --budget '{"tokens":200000,"hours":8,"ticks":500,"disk_mb":2048,"mem_mb":1024,"money_usd":8}'
aos-user order work/studio "做一支 todo.py" --budget '{"tokens":30000,"hours":1}' \
  --accept "加、列、刪都能用" --accept "測試全過"
aos-user listen work/studio
aos-user team status work/studio
aos-user team budget work/studio                       # 看總額、每人 tokens 上限／已用／被擋原因
aos-user team budget work/studio --add '{"tokens":100000}'   # 甲方追加（sales 問你要不要追加時就跑這句）
aos-user team stop work/studio
```

`say`、`listen`、`talk` 對工作室根使用時，會自動走唯一甲方窗口 `sales`。明講 `--home` 才會找指定成員。

## 資料夾

```text
studio/                         owner 世界，也是 owner home
  kids/{sales,pm,chief,dev-a,dev-b,qa}/
  team/team.json                現況名冊
  team/budget.json              總額、每人額度、分帳紀錄
  team/progress.md              共用短進度
  team/projects/                全員共用成果
```

每個孩子家裡的 `team` 都是指向 owner 共用區的 symlink，所以全員一律用 `team/projects/...`。成員的回話**不會**像普通小孩那樣自動轉成 owner 的信（那會讓 owner 光讀信就燒光額度、占住共用引擎）；回報一律自己 `mail_send` 給 `reports_to` 的主管。owner 與 chief 用自己的鐘。sales、pm、dev-a、dev-b、qa 掛在 owner 的鐘。設了 `AOS_DAEMON_DIR` 時，`team new` 會登記兩個自己的鐘；`team stop` 收掉它們，檔案與帳保留。

## 預算

總額先留 10% 給 owner 救急、5% 給 sales 接單與回甲方，85% 給 PM。owner 與 PM 可用 `team_grant` 從自己的未用額度分給成員。超額不寫帳。

**額度是硬閘門，每格都守**（agent 每走一格、做任何事之前先看帳）：

- **個人 tokens**：`0 就是 0`——沒拿到 `team_grant` 的成員一格都不動（連信都不讀、step 不加）。沒事做（沒信、也不在題目中間）就安靜凍著；有人派活給他才向主管寄一封「額度用完、有工作在等」（沒主管就對外回一句），只寄一次。主管 `team_grant` 之後下一格自動解凍，接著處理原本那封信。所以 PM 派工前一定要先分 tokens，一次至少 20000（一輪對話就要幾千）。個人的 ticks／money 分帳只是紀錄，不擋。
- **整隊 tokens／hours／ticks／money**：任一項用完，**全隊凍住**（每個人都在原地不動、不叫 LLM、不跑工具），只有 sales 對甲方回一句「整隊額度用完了，要追加請跑 `aos-user team budget <世界> --add ...`」。甲方追加後（總額加上去、同一份給 leader，`--to` 可指定給誰，記一筆 `kind: top_up`），下一格全隊自動解凍。
- 在途的那一筆 LLM 請求收不回來，所以個人 tokens 最多超過「一筆」的量；`max_concurrent` 是幾就是幾筆。
- `llm.json` 的 agent 硬上限與 team 額度同時存在時，先撞到哪個就先停。

`team status` 的 token 來自 LLM 每日 requester 帳；**ticks 只算 busy 格**（真的做了事的那格：問模型、跑工具、收信），idle 空轉與凍住的格不算，不然閘門會被空轉穿透；磁碟是資料夾大小，hours 是開隊後的牆上時間。記憶體目前量不到，固定顯示未知，只有軟上限。`INFLIGHT` 欄是 `主線+旁線` 在途筆數（主線＝正在等模型回的那一筆，旁線＝think／branch／jobs 這類還沒回來的），`BLOCKED` 欄是被擋原因（`own:tokens`／`team:hours`…）。

## 模型協定壞掉時

小模型常把工具呼叫寫成文字（`<tool_call>{...}</tool_call>`、或整段就是 `{"name": ..., "arguments": ...}`）。agent 撿到主線結果時：認得的工具名就救成正式 `tool_calls` 照跑（id 是 `salvaged_N`）；救不回來就當協定錯誤，壞文字不進記憶、同題重送一次；第二次還是壞的就照普通回覆處理。已通知但一直沒讀的信，agent 閒滿 30 格會再提醒一次（見 [mailbox](mailbox.md)）。

## 已知坑

- 共用檔沒有鎖。兩人同時改同一檔，後寫的可能蓋掉前面。
- `team status` 每次掃七人的狀態、信箱、帳和資料夾。小工作室很快；信件與專案很多時會變慢。閘門用的是不量資料夾的輕量版，每格一次。
- 七個人共用兩三路本機引擎時一發要等一兩分鐘是常態：agent 只要請求還在 LLM 世界排隊或執行中就一直等（上限 1800 格），這段等待不算每題動作格。
- 開隊做到一半失敗會留下已建檔案，不會自動回滾。修好原因後，要換一個新目錄重建。
- shared 成員沒有自己的 daemon clock。owner 停，它們一起停；chief 仍可能繼續走。
- 「全隊凍住」是每個 agent 自己在原地不動，鐘還在轉（空轉很便宜）；沒有去 daemon 停鐘，所以追加後不用重開。
- money 只加總各人 cost ledger 已能配到工具回合的金額。純文字回覆沒有工具時，可能低估。
- 這版不做檔案隔離、送達保證、自動換人、自動合併或精準記憶體限制。
