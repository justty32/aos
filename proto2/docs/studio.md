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

每個孩子家裡的 `team` 都是指向 owner 共用區的 symlink，所以全員一律用 `team/projects/...`。owner 與 chief 用自己的鐘。sales、pm、dev-a、dev-b、qa 掛在 owner 的鐘。設了 `AOS_DAEMON_DIR` 時，`team new` 會登記兩個自己的鐘；`team stop` 收掉它們，檔案與帳保留。

## 預算

總額先留 10% 給 owner 救急，90% 給 PM。owner 與 PM 可用 `team_grant` 從自己的未用額度分給成員。超額不寫帳。個人額度用完就不再叫 LLM，改報主管；整隊額度用完就全隊停，sales 向甲方問要不要追加。`llm.json` 的 agent 硬上限與 team 額度同時存在時，先撞到哪個就先停。

`team status` 的 token 來自 LLM 每日 requester 帳，ticks 是 agent 的 step，磁碟是資料夾大小，hours 是開隊後的牆上時間。記憶體目前量不到，固定顯示未知，只有軟上限。

## 已知坑

- 共用檔沒有鎖。兩人同時改同一檔，後寫的可能蓋掉前面。
- `team status` 每次掃七人的狀態、信箱、帳和資料夾。小工作室很快；信件與專案很多時會變慢。
- 開隊做到一半失敗會留下已建檔案，不會自動回滾。修好原因後，要換一個新目錄重建。
- shared 成員沒有自己的 daemon clock。owner 停，它們一起停；chief 仍可能繼續走。
- money 只加總各人 cost ledger 已能配到工具回合的金額。純文字回覆沒有工具時，可能低估。
- 這版不做檔案隔離、送達保證、自動換人、自動合併或精準記憶體限制。
