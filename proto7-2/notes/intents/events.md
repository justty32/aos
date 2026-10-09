# events 意圖卡

← [intents](README.md)｜[包 README](../../modules/events/README.md)

**①解決什麼**：每個 node 一個 `events/` 夾，固定檔數保存「發生過什麼」：核心觀測取樣＋別包逐件發布；必讀的要被確認。

**②必要的副作用**：只寫 `<node>/events/`（兩通道各 1 活檔＋≤4 封存、`state.json`＋鎖，總 ≤12 檔）；滿了刪最舊觀測、必讀只停收；取樣器當 keep 任務讀核心的 last-round／status／log（只讀）。

**③不做**：不改核心、不 fsync、不做集中收集（取樣器的 `--src` 可重複，只是把多個來源的最新檔取樣進**自己**的 events/，不是集中站）、不保證不丟取樣。

**④多出來的（現狀）**
- `read --ack` 在 state 不存在時仍建 `state.json.lock` → **移除**：沒 state 就回 unknown、不建檔。
- `pub` 在 events/ 不存在時新建整個夾（給 `--node` 就建）→ **改成可選**：預設只對已有 `events/` 的 node 發（mail／compact 皆照此），`--create` 才建；第一次跑由 `aos7-up` 決定要不要開夾。
- examples/longrun 起真 daemon → **保留**（只是範例，README 標明）。
