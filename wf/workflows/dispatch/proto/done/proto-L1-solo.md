# 任務：試用 L1——在 shell 裡只用 `aos …` 當單人 coding agent，記所有不順手

> 交接書是唯一契約。判準 usability-target 第一級；發現格式見 [trial/README](../../trial/README.md)。**只找不修、不改 core/。**

## 唯一目標

以「使用者坐在終端機前」的方式，在一個真的程式碼資料夾裡完成「修改某個程式碼區塊」這類任務，全程只用 `aos …`，
**lmstudio 與 pi 各跑一遍**，每個摩擦點記一條發現＋對照（同一件事直接用 `pi` 做要幾步）。

## 團隊（你是 Opus 隊長）

codex ×4 當「使用者」（`codex exec -m gpt-5.6-sol -C <worktree> --dangerously-bypass-approvals-and-sandbox -o <out.md> - < <task.md>`；任務書寫死劇本、要求「最終回覆即成品，另寫到 -o」）。你出劇本、收斂、去重、排序。**codex 不可修 aos、不可改 core/**；它只操作與記錄。

## 劇本（每條 codex 一組，可自行加變化）

素材：在 worktree 內建 `trial/sandbox/<name>/`，放一個小 C++ 或 Python 專案（3–5 檔＋測試）。
1. **改一個函式**：`aos agent init`（lmstudio）→ 視窗 B `aos run --step 0`（用 `--step N` 模擬）→ `aos say "把 parse() 改成回傳 optional"` → `aos listen` → 追問「跑測試」→ 看 diff。同一劇本 `--engine pi` 再一遍。
2. **狀態可見性**：思考中／執行工具中／等 LLM 時，`aos state`／`state.json`／`listen` 能不能看出來；Ctrl-C 掉 `aos run` 再開、`.aos/` 殘留什麼。
3. **記憶**：停掉、換 shell 回來、`aos say "剛才改了什麼"`；pi session 與 lmstudio history 各自行為。
4. **錯誤路徑**：LM Studio 沒開／模型不存在／DEEPSEEK_API_KEY 沒設／工具不存在／`aos say` 在沒 `.aos` 的資料夾——錯誤訊息有沒有指路。
5. **多打的指令**：每個任務數「理想上一句話 vs 實際打了幾個指令、等了幾回合」。

## 硬性限制

- 只寫 `wf/workflows/dispatch/trial/{findings-L1.csv,repro/,sandbox/}`；commit 到你的 worktree 分支；不 push、不 merge、不改 core/。
- 不 load／unload LM Studio、不開 GUI、不取鎖、不用 wf-lint；DeepSeek key 只從環境變數。
- **件數 gate**：發現 ≤ 60 條、去重後 ≤ 40；超過就停下來收斂。

## 驗收（就這 3 條）

1. `findings-L1.csv` 存在、欄位齊、`kind` 四類都有分佈統計在 README 一段（你追加 `trial/README.md` 的 L1 摘要 ≤ 20 行，含「最痛的五條」）。
2. 每條 `bug` 類都有 `repro/<id>.sh` 可重跑。
3. lmstudio 與 pi 兩遍都跑完（沒跑完的寫 `cannot` 並附原因）。

## 回報

最後一則訊息＝最痛的五條＋分佈統計＋STATUS＋worktree 路徑與分支名。
