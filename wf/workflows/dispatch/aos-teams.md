# aos 的隊形（2026-08-28 改制，2026-09-30 現況）

← [dispatch](README.md)｜選人判準 [team-model](../team-model.md)

本專案實際怎麼開隊。派線的通用規則在 [dispatch](README.md)，這裡只記 aos 專屬的隊形、指令與硬規則；改制時改這裡並標日期。任務書送出前要對一次的坑在 [lessons](lessons.md)。

## 誰做什麼

<!-- wf-nav -->
- **我（Fable，頂層）只當調度者**，不親自做內容，只親手做最難的那件。使用者 2026-08-30 說「頂層不要做太多事」，**09-24 再講更嚴**「你不要自己做事，盡量交給 agent」。頂層在主 repo 親手做的**只剩 `git merge --ff-only`＋`git push`**；重跑驗證、解 rebase 衝突、改 SESSION-LOG／WAIT_USER、清 backlog、報告存檔全派出去。收線＝讀隊長附的證據逐條對，不重跑；真要獨立驗證就派一條便宜的線去跑。想「順手」做小事時先問：能不能一句話交給別人？這條不看頂層跑哪顆模型，頂層是 Opus 也一樣。
- **碰程式碼一律派 Opus**（09-30：派 Sonnet 去把 proto5 aos-exec 複製進 proto6 時，他說「不要 sonnet」「就 opus」）——就算只是複製＋小改也一樣。**Sonnet 只做純文字小事**（記 notes、改文件、補日誌）。
- 一個團隊＝一個 **Opus 隊長**，隊長可以自己再派 Opus／Sonnet 下去；人數沒有上限（09-05 起）。隊長寫任務書、審 diff、跑測試、commit。
- **codex 只剩 `gpt-6-astra` 能用**：09-24 實測 gpt-sol／terra／luna 都回「不支援此模型」；09-30 他點名 `gpt-sol-6.1` 也回「not supported when using Codex with a ChatGPT account」。他點名別的型號時先試一下，不行就說明並問要不要改 astra。codex **不 commit**，常用來當唯讀審查（隊長自己跑 astra 唯讀審）。
- 開隊前**先把打算怎麼做講給他聽**，等他回應或糾正再派；他可能在手機上、回得慢，問題與選項照發、附預設建議。

## 指令與沙箱

- 開隊長：`Agent(subagent_type="general-purpose", model="opus")`，prompt 裡明講團隊規則、硬規則（不 push、不碰別隊的資料夾、只 `git add` 明確路徑）、回報格式。
- **同一 working tree 只能有一隊在 commit**；純規劃隊只寫自己的項目夾且不 commit，由我收。worktree 隊的**ff-merge 進 main 那步要我在主 repo 做**，清 worktree／分支也歸我〔使用者方向 2026-09-30 晚〕，見 [dev-env](../dev-env.md)「git 佈局」。
- **審查／報告類產出一定要求寫進 repo 內的路徑**，不要只留在 scratchpad 或靠最後一則訊息——agent 的回報只有最後一輪會回到我手上，主篇曾因此遺失一次。
- 別用 `TaskOutput` 讀 agent 任務（會倒整份 transcript 進 context）；等通知即可。
- 實作層級的裁決我可以代裁並寫進交接書（多隊共用的契約由我先定，才能真並行）；**方向性的留給使用者**（鐵律 5），記 [WAIT_USER](../../WAIT_USER.md)。

### codex 呼叫與沙箱

`codex exec -m gpt-6-astra -C <路徑> -o <out.md> - < <task.md>`（任務書從 stdin 餵、要自給自足；`-o` 收最後一則回報）。背景跑時也要餵 stdin（見 [driving-cli-agents](driving-cli-agents.md)）。

純審查用 `-s read-only`。唯讀沙箱沒有可寫暫存目錄，**測試跑不起來**，必修的驗證由派它的 agent 在主 repo 補跑。
要寫檔到 scratchpad（例如試玩）：`-s read-only` 寫不了、`-s workspace-write` 沒網路連不到 LiteLLM，只能用 `~/.codex/config.toml` 的 `danger-full-access`，`-C` 指 scratchpad、不進 repo。
要兩份獨立 codex 意見時，第二份只能是 astra 調高推理另開對話，綜合時要打折（兩份同源）。

公司那台（WSL）的 `~/.codex/config.toml` 沒設 `danger-full-access`，預設模型還寫著已不能用的 gpt-sol：所以**一律帶 `-m gpt-6-astra`**，要寫檔／開子進程時改用單次旗標 `--dangerously-bypass-approvals-and-sandbox`（2026-09-22 在那台驗過，codex-cli 0.155）。背景跑用 Bash `run_in_background`，log 導到 scratchpad。

**任務書開頭一定寫「可以開自己的 subagent 平行做事」**，不管派哪種 codex（使用者 2026-09-22：「不管開哪種 codex，都要允許他開自己的 subagent」）。codex 的 `multi_agent` 已開、每個 session 最多 8 條。要限人數就在同一句寫上限，別不寫——[driving-cli-agents](driving-cli-agents.md) 說過不寫它會自己開一堆。

**Claude API 不穩時改派 astra**：2026-09-22 Opus 連續四次被 500／529（伺服器過載）打斷，使用者說「claude api 目前狀況不好，改派 codex astra」。這時的分工是 astra 做調查、我做精簡總結、決策、寫規範——他接受這樣切。

## 每段做完派人試玩（2026-09-13 起）

使用者：「每次做完一個段落都可以讓他們去玩玩看，給建議，然後我們改進。」設計者自己看不出哪裡難懂，要靠沒讀過設計筆記的人去撞。
做法：段落 commit 後開一個**只拿 README 入口**的 agent（Opus 與 codex 各一更好），照 README 架起來、寫小程式、故意弄壞幾樣，照五條標準各打分＋舉例——**容易上手、容易理解、複雜的藏起來、外層控制結構簡單但全面、要背的少**。回報存該原型自己的 `notes/play/`（README 表一輪一列），我整理成「要改的清單」給他挑。

## 交接

- 派線流程、領地表、收線 → [dispatch](README.md)；外部 CLI 線的啟動與監看 → [driving-cli-agents](driving-cli-agents.md)；任務書 checklist → [lessons](lessons.md)。
- 各層派哪級模型 → [team-model](../team-model.md)；隊伍會撞的資源 → [resources](../resources.md)；模型端點 → [dev-env](../dev-env.md)。
