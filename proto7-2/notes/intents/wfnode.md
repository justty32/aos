# wfnode 意圖卡

← [intents](README.md)｜[包 README](../../modules/wfnode/README.md)

**①解決什麼**：替 node 裝一本工作簿（`wf/`），每次收工記一句「停在哪」，開工前先體檢。

**②必要的副作用**：`init` 跑外部 `~/repo/workflows` 的 wf-init.sh 建 `wf/**`、`AGENTS.md`、`CLAUDE.md`、`.claude/`，填已知事實、改寫 4 份導入判斷段（只在首次且原文相同）；`state` 追加 `wf/handoffs/<日期>/STATE.md`、改 `NEXT-SESSION.md` 一行；`init`／`check` 起 wf-lint 子程序。不連網、不花錢、不碰 `.aos/`。

**③不做**：不猜未定事實；不改 workflows 本身；不起 daemon。

**④多出來的（現狀）**
- 先建空的 `wf/routines.json`、`wf/schedule.json`（routines 的表）→ **保留**：模板連結指到它們，不建 wf-lint 就壞；格式要與 routines 包同步（寫進兩邊 README 各一句）。
- `init` 每次重掃所有含 `{{` 的 md 覆寫 → **保留**（只動未填的）。
- 其餘零多出來。
