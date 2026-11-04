# CHANGELOG — v0.5 的 multi-agent 包

[docs](README.md)｜[v0.5 完整條列](CHANGELOG-v0.5.md)

由 [CHANGELOG-v0.5](CHANGELOG-v0.5.md) 拆出（母檔抵 8 KB 上限）：v0.5 這一輪 multi-agent flavor 包的變動。沒有導入 multi-agent 的專案跳過本檔。

- multi-agent 包 `workflows/dispatch.md` → 資料夾 `workflows/dispatch/`：`README.md`（原內容＋六條最容易錯的、兩層派線、多信任但收線對證據、休眠前自檢；含活狀態表，project-owned）、新增 `driving-cli-agents.md`（互動式 tmux／非互動 exec 啟動、監看三訊號、通訊、清理、收線七步）與 `lessons.md`（派線四條坑）→ 兩新檔 kernel-owned 直接加；既有專案把指向 `workflows/dispatch.md` 的連結改成 `workflows/dispatch/README.md`。
- 新增 multi-agent `tools/inbox_mail.sh`（`mail/<對象>/`、`topics/<主題>/` 投遞）、`inbox_poll.sh`（輪詢個人信箱＋訂閱主題＋自己的 `orders/<我>.md`，`--once`／`--watch`）、`notify_watch.sh`（長駐輪詢 `new/`，無事件靜默）→ kernel-owned，隨 `tools/` 複製；root 由 `WF_INBOX_ROOT`／`<script>/../inbox` 推導，STATUS 白名單同 `inbox_send.sh`。未升級的專案用不到。
- multi-agent `workflows/inbox/PROTOCOL.md` 通道升級路徑擴充（四通道「可否取代」欄、`orders/` append-only 與 `from:` 段標題、調度者指示優先於交接書、輪詢義務、`done/` 按日期合併成 `messages.md`＋`messages.json`）→ kernel-owned 整檔覆蓋；`inbox/README.md`、`ROSTER.md`（＋訂閱主題欄、已收線格封存）、`resources.md`（headful 瀏覽器也取桌面鎖、鎖目錄被刪檢查恆真）→ project-owned 手動套；`TEMPLATE.handoff.md`（暫存不 `rm`、整檔改寫用 Update、送出前對背景與工作矛盾）→ kernel-owned 覆蓋。
- 新增 multi-agent `workflows/team-model.md` ＋ `workflows/team-model/{context,speed,plans}.md`：角色三層（頂層／領導＝計畫制定者／工人）、聰明度分級表、token 消耗速度表、六項選人判準、context 管理五條、執行速度三因素、逐模型指揮心得表。入口、分頁 kernel-owned 直接加；上述三表與 `plans.md` project-owned，專案填模型、實測。既有專案複製四檔，WORKFLOWS.md／AGENTS.md／workflows/dispatch/README.md 補 team-model 指向。
- inbox 五通道（＋`teams/<團隊>/`）：`inbox_mail.sh` 加 `--up`（依 `teams/*/members` 自動投領導，工人不必知道上游名）、`--team`（僅成員、頂層可投）；`inbox_poll.sh` 自動發現團隊信箱，加 `--wait [--timeout N]` 醒鐘（有信 exit 0、逾時 exit 3 靜默）；dispatcher 多掃 new/。新增 `tools/inbox_team.sh`（create／add／close；收線搬至 `done/<日期>/teams/`）、`tools/test_inbox.sh`（14 條）。`workflows/inbox/PROTOCOL.md` 改五通道佈局，拆 `wake-policy.md`（各層醒鐘策略、`--wait`、領導轉發三規矩）→ kernel-owned 覆蓋。`inbox_send.sh` 路徑定址簽名不變，未升級專案不受影響。
- `workflows/inbox/ROSTER.md` 加「團隊」欄；上游改「有團隊就是 `members` 第一行」；註明團隊信箱自動發現、不列訂閱主題。`TEMPLATE.handoff.md` 回報並列「基本佈局 `inbox_send.sh <上游 inbox 路徑>`／升級後佈局 `inbox_mail.sh <我> --up`」，加「本線團隊」欄 → ROSTER project-owned 手動套、handoff 範本 kernel-owned 覆蓋。
