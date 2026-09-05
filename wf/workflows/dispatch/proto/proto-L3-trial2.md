# 任務：試用 L3——X／Y 落地後重跑兩級劇本，記還剩什麼不順手

> 交接書是唯一契約。判準 usability-target；發現格式見 [trial/README](../trial/README.md)；上一輪發現 [findings-L1.csv](../trial/findings-L1.csv)／[findings-L2.csv](../trial/findings-L2.csv)、隊 X／Y 的修法在 [reports/X.md](reports/X.md)、[reports/Y.md](reports/Y.md)。**只找不修、不改 core/。**

## 唯一目標

隊 X（25 條 bug）與隊 Y（`aos chat`、`aos run --daemon`／`aos stop`、投遞即喚醒、`aos state` 的 unread／last_error、通訊錄進 prompt、`aos contact status`、`aos inbox ls/read`）落地後，**用使用者的方式再走一遍 L1（單人 coding agent）與 L2（指揮團隊）劇本**，回答三件事：
1. 上一輪 60 條裡哪些**還在**（同 id 引用，不重抄）、哪些已消失；
2. **新出現**的 bug／awkward／spec-gap／cannot（新 id `L3-NN`）；
3. 現在做「在 README 加一行」與「boss 派 w1／w2 做事並收回報」各要幾個指令、幾秒，跟 L1／L2 記的數字對照。

## 團隊（你是 Opus 隊長）

**第一步（必做）**：`git merge-base --is-ancestor HEAD main && git reset --hard main`，`git log -1` 必須是主 repo main 的 HEAD（worktree 可能建在很舊的 commit）。然後在你的 worktree 建置：`cmake --preset default && cmake --build --preset default`，用該 worktree 的 `build/bin/aos`（絕對路徑）。

codex ×3 當操作者（`codex exec -m gpt-5.6-sol -C <worktree> --dangerously-bypass-approvals-and-sandbox -o <out.md> - < <task.md>`；任務書寫「最終回覆即成品，另寫到 -o」）：一條走 L1（lmstudio ＋ pi 各一遍），一條走 L2，一條專打新指令（chat／daemon／stop／inbox／contact status／state）的邊角。**工作量押給 codex**，你出劇本、收斂、核對。

## 劇本

- L1／L2 照 [proto-L1](done/proto-L1-solo.md)、[proto-L2](done/proto-L2-team.md) 的劇本原樣走，素材在 `trial/sandbox/`（可重建）。
- 新指令線：空資料夾 `aos chat`；`--daemon` 起停、重複啟動、`aos stop` 後孤兒；`aos say` 三句不跑回合後 `state`／`inbox ls`；`inbox read` 後 step 不重讀；`contact status` 在 boss 看 w1／w2；LM Studio 沒開時各指令的錯誤指路；Ctrl-C。
- 每條發現附「用 pi／Claude Code 做同一件事的對照」一句。

## 硬性限制

- 只寫 `wf/workflows/dispatch/trial/{findings-L3.csv,repro/L3-*.sh,sandbox/}` 與 `trial/README.md` 追加一節（不改既有內容）；commit 到 worktree 分支；不 push、不 merge、不改 core/、不改 L1／L2 的 csv 與 repro。
- 不 load／unload LM Studio（現在裝的是 `qwen/qwen3.5-9b`，沒開就記「沒開時的行為」）、不開 GUI、不取鎖、不用 wf-lint；DeepSeek key 只從環境變數；測試用暫時 HOME／AOS_HOME，**不碰真 `~/.aos/`**；收工前 `aos stop` 所有 daemon、`pgrep -f "aos run"` 必須為空。
- **件數 gate**：新發現 ≤ 40 條；時間 gate：60 分鐘內收斂。

## 驗收（就這 3 條）

1. `findings-L3.csv` 存在、欄位齊（`id,lane,kind,severity,step,expected,actual,compare,repro`）；每條 `bug` 有 `repro/L3-NN.sh`（用 `$AOS` 環境變數指 aos，預設 `build/bin/aos`）。
2. `trial/README.md` 追加「L3 摘要」≤ 25 行：舊發現的存活表（id 列）、新發現的最痛五條、指令數／秒數對照表。
3. 回報只要：最痛五條＋存活數字＋STATUS＋worktree 路徑與分支名。
