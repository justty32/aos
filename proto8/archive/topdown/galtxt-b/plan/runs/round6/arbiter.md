# round6 示範：優化器一步提 2 條 → 判斷器挑 → apply → 4 題驗證（真腦，10-25）

← [round6 §4、§7 第 6 項](../../round6.md)｜留檔 [arbiter/](arbiter/)｜程式 [train/optimize](../../../train/optimize/_entry)、[train/arbiter](../../../train/arbiter/ask.py)、[train/apply](../../../train/apply/_entry)（freeze_order、patch_act）、[train/record](../../../train/record/_entry)（量測、judgments）｜測試 `test_topdown_galtxt_b_round6.ArbiterOptimize`

## 怎麼跑的

訓練場在 scratchpad（不在 repo）。`train/init` → **第 1 輪不重跑**：把量測組 [trim_after](measure/trim_after/) 四題各第 1 次的 answer／score／measure 搬進 `runs/1/`（現在的樹就是那一組）→ score → record（量到 writer 每次 16579 token、3 次問腦；根 20175）。候選用隊長給的兩條（`proposals/1.json`，根據是 [measure.md](measure.md) 的數字）：

| | 動作 | optimize 推的預期梯度（每次） |
|---|---|---|
| a | `freeze_order:trim`：交稿前由 act 一律叫 trim、腦看不到 trim、system.txt 刪第 8 條 | 根 token −802（量測兩組的差）、writer 問腦 −1 次、違規不變 |
| b | `patch_act:default_args:lint`：腦叫 lint 漏 `brief_path` 時 act 補 `cur/{name}.json#/brief` | 根 token −691（漏參率 1/8 × 每次問腦 5527）、`counter_argbad` 1→0、違規不變 |

判斷器（真腦 1 次，3,192 token）選 **b**，理由（原文）：「a 多省約 111 token，但這不是台詞分數，且 a 會移除 trim 工具」「a 拿掉 trim 後可能讓 lint 漏參回來，已有 3/6 次觀測到此情況」。`weights_used`：counter_argbad 0.55、counter_violations 0.2、llm_tokens 0.15、llm_calls 0.1。→ apply 寫 writer 的 `act_rules.json`（不問腦）→ 第 2 輪四題各 1 次（真腦）→ score → record 算實測梯度、寫 judgments。

## 數字（[rounds_summary.json](arbiter/rounds_summary.json)）

| 輪 | 總分 | lint 違規 | 根 token／次 | writer token／次 | 問腦／次 | 漏 brief_path | act 補參 |
|---|---|---|---|---|---|---|---|
| 1（搬來的 trim_after） | 5、5、5、5 | 0 | 20,175 | 16,579 | 4 | 沒有 history（量測時 0/6） | — |
| 2（b 套用後） | 5、5、5、5 | 0 | **23,570** | 20,001 | 4.5 | **0/4** | **0 次** |

- 第 2 輪腦四次都自己帶了 `brief_path`，**補參一次都沒觸發**——b 這一步在這 4 次裡等於沒做事。
- token 反而 +3,396／次：四次裡兩次（她先那兩題）lint 自檢叫了兩回（writer 22.9k、23.5k，另兩次 16.7k、16.9k）。這是腦自檢次數的雜訊，跟 b 無關（b 只在漏參時動作，這輪沒動作）。
- 實測梯度（[changes_1.json](arbiter/changes_1.json) 的 `gradient`）：根 `rollup.measured.llm_tokens` +3395.5、`ratings.傲嬌.反差` 0.8→0.75、`承接` 0.875→0.85（都在雜訊內）；`gain` 0（沒有好變化）。
- **judgments**（[judgments.json](arbiter/judgments.json)）：只實測了被選的那條 → `verdict: partial`、`expectation_held` 0.2（預期 5 條有 delta 的 key，只有「違規不變」同號；token 預期降、實際升）；`accuracy` null（沒有兩條都實測的那一對）；`human_agreement` null（這輪沒人評）。**只核了一邊**：另一條 a 也跑 4 題約要 8 萬，份額不夠。

## 花費

判斷器 3,192＋第 2 輪四題 94,280＋漂移（critic_v0 4 次，見 [drift.md](drift.md)）14,478＝**111,950 token**（份額 14 萬內）。

## 看到的事

1. **預期梯度靠的是「過去的漏參率」，但這個量很稀**（現在的樹 1/8）。4 次驗證裡剛好 0 次漏參，這條改動就量不到效果；要量出 b 的效果，得在常漏參的條件下測（例如先做 a、或 `GALTXT_FAKE_LINT=nopath` 那種壓力），或把驗證次數拉高到漏參期望值 ≥ 2 次（約 16 次）。
2. **判斷器抓到了兩條之間的交互作用**（拿掉 trim 可能讓漏參回來），這是預期梯度表上沒有、只在「根據」那行文字裡的資訊。規則表固化後（≥ 8 次）這種判斷會丟掉——規則表只看 key 的加權，不讀根據。
3. **token 的單次雜訊（±3,000）比兩條候選的預期差（111）大 30 倍**：用 4 題×1 驗「省幾百 token」的改動，事後核對一定判不出誰對。accuracy 要有意義，驗證要嘛拉高次數、要嘛用確定性的量（例如 act 補參次數、工具呼叫次數）當主要指標。
4. 這一步的改動本身無害（補參只在缺參時動作、預設不觸發），所以留在訓練場的 tree/；沒有回寫 repo 的樹。

## 代定

- 「實測誰較好」（record 的 `measured_better`）：總分差 ≥ 0.5 高的贏，否則根 token 少 ≥ 5% 的贏，否則平手（不算進 accuracy）。只測了被選那條時記 `partial`＋`expectation_held`（預期 delta 的方向對了幾成；總分掉 ≥ 0.5 直接 0）。
- 另一條的實測放 `$AOS_WS/side/<輪>-<label>/changes/<輪>.json`（同一個改前、套另一條後跑出來的 gradient），record 有就拿來比；這輪沒有。
- 固化：≥ 8 筆 judgments → `weights_used` 平均（缺的算 0）正規化 → `priority_rules.json`（附 polarity、tie 0.05）、arbiter `stage: script`；之後兩條的規則分差 > tie 才不問腦（假腦測過，真腦這輪只有 1 筆，沒固化）。
- freeze_order 的工具要在 tool.json 宣告 `returns: "text"`（回的 text 能直接當稿）；提案器第一次在假腦上把 lint（回意見、不回稿）也提成 freeze_order，因此加了這條。trim 的 tool.json 已加。
