# author 意圖卡

← [intents](README.md)｜[包 README](../../packs/author/README.md)｜[三關](../../packs/author/checkers/README.md)

**①解決什麼**：學徒（AI）交來的候選先過三關，過了才變成一個可跑的任務或一條可合併的分支。

**②必要的副作用**：寫 `<node>/author/req/<rid>/…`、`<node>/jobs/<job>/`；`publish` 把自己那一項合進 `.aos/tasks.json`（發布＝掛任務）；`--llm` 經 llmcall（花錢）；三關檢查器 `check` 起 bwrap 沙盒（斷網、唯暫存可寫）跑學徒的測試；三關 `publish` 只新建 `apprentice/<rid>_<sha8>` 分支，不碰 HEAD／工作樹。

**③不做**：不幫學徒改碼、不自動合進 main、不跳關。

**④多出來的（現狀）**
- 三關 `--reviewer` 預設 `astra`：第一次跑就呼叫 codex 花錢 → **改成可選**：預設 `rules`（離線），`astra` 明示才用。
- 三關 `publish` 預設把分支建在檢查器所在的真 repo → **改成可選**：`--repo` 必填，沒給印「會建在哪」不建（U 隊也點名沒標風險）。
- `propose --llm` 預設預留 100 萬 token → **保留**（軟預算）但 README 標明。
- `propose` 換候選時 rmtree 舊未發布 job → **保留**（自己的檔）。
