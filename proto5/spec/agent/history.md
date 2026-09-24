← [agent](README.md)｜[spec 總導航](../README.md)

# 沿革

原標題：`agent 資料夾規範（第 2 版，2026-09-24 定稿（astra 三輪審查＋第 4 輪補 3 條）；已實作）`

> 2026-09-23 草稿；2026-09-24 照 審查報告「定稿前必改」與使用者三件裁決改成第 2 輪；同日照 第 2 輪審查 E／D／B／C 改成第 3 輪；照 第 3 輪審查 D 節補 3 條（第 4 輪）後定稿。（審查與實作紀錄在 [rearch 筆記](../../notes/2026-09-23-rearch/README.md)）
> **已實作**（2026-09-24，T9）：`lib/aos_agent_info.py`／`aos_agent_home.py`（讀驗），實作發現見 agent-impl-findings。
> 調度者裁決移到檔尾（09-24 試玩 r2 搬），已拍板的前提在 §7。
> 2026-09-24 fix-r4：`AOS_K` 改名 `AOS_KERNEL_HOME`；家裡多兩個程式寫的檔 `.tick.lock`（tick 鎖）、`paused`（手動暫停）；問模型的指令改名 `aos-llm call`。
> 2026-09-24 fix-r5：家裡多一個程式寫的檔 `resumed`（`continue` 解了連敗暫停、還沒等到一次成功；§1）。
> 2026-09-24 access-impl（A1）：`tools` 元素可寫 `$opt` 選項物件（`as` 改名、`only` 挑幾支），`info.md` 的「沒有欄位吃 `$opt`」改成「只有 `tools` 的元素吃」；新 §3.4 [tools-opt.md](tools-opt.md)；§3.3 加 `_jail`（只收 bool）與 `_source`。
> 2026-09-24 access-impl（A2）：新 §3.5 [access.md](access.md)（`access.json` 格式、信任資料、`self` 只能 ro）；`info.json` 加 `access` 欄；`state.batch` 加 `access` 快照；家裡多一個人寫的 `access.json`；錯誤代號加 `AccessInvalid`／`AccessUnsafe`／`NoBwrap`。
> 2026-09-24 access-impl astra 修（A1）：家裡多一個管理指令用的 `.admin.lock`（§1）。
