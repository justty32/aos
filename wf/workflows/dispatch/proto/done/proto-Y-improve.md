# 任務：改進四項不順手——少打指令、狀態可見、agent 看得到通訊錄、不燒 LLM 的信箱

> 交接書是唯一契約。發現在 [trial/findings-L1.csv](../../trial/findings-L1.csv)／[L2](../../trial/findings-L2.csv)（`awkward`／`spec-gap`／`cannot`），摘要與「缺的原語」在 [trial/README](../../trial/README.md)；判準 usability-target。使用者 2026-08-30 選了四項（下方）。修 bug 隊 X 同時在 main 上修 25 條 `bug`。

## 唯一目標

四項改進落地、最小可用：
1. **少打指令**：`aos chat [--engine …] "第一句話"`＝沒 `.aos` 就 init、背景起 `aos run`（或前景 loop 直到回覆）、say、listen 到回覆為止；`aos run --daemon`／`aos stop`（pid 檔在 `.aos/`）；**投遞即喚醒**（`run` 空回合時監看 `inbox/`／`say/` 有新檔就立即開下一回合，不等 interval）。
2. **狀態可見**：`aos state` 印真實處境——未讀幾封、思考中（含等槽 `waiting-llm`）、上回合結果（成功／LLM 失敗＋錯誤一行）、idle；`state.json.agents.<name>` 帶 `unread`、`last_error`；**LLM 失敗不吃掉訊息**（step 失敗時 `say/` 保留或退回）。
3. **agent 看得到通訊錄與投遞能力**：contacts（含 `~`）進 system prompt；預設工具加 `aos say --to`（回信地址＝自己的世界）；`aos contact status`＝跨通訊錄的隊層級彙總（每格：unread、status、turn）。
4. **不燒 LLM 的信箱**：`aos inbox ls`／`aos inbox read [id]`（列／讀 `say/` 與 `~/.aos/say/` 的未讀，標已讀不叫 LLM）；`aos listen` 空時印「無新訊息（未讀 N 封在 say/）」而不是空白。

## 團隊（你是 Opus 隊長）

codex ×4（同呼叫方式；任務書寫「最終回覆即成品，另寫到 -o」），一項一線；**先派 Fable 規劃者一輪**把四項的指令面與 `state.json` 新欄位寫成 `core/agent/docs/ux-round-1.md`（≤ 2 頁），你核過再派。隊長寫任務書、審 diff、跑 ctest、commit；不親自寫實作。**worktree；第一步 `git reset --hard main` 對齊。**

## 硬性限制

- 可改 `core/agent`、`core/loop`（只為喚醒與 daemon）、`core/tool`（contact status）、code-map、PROTOCOL（只加欄位、附「改動」段）。**禁區**：`core/exec`、`core/wire`、`core/llm`、`core/tick`、`app/`、`reference/`、`docs/`、其餘 `wf/`。
- `git add` 只加明確路徑；不 push；收線前 `git rebase main`（隊 X 會先落地，衝突自己解、解完 ctest＋X 的 repro 全綠才回報）；不 load／unload LM Studio；不開 GUI；不用 wf-lint；`aos run --daemon` 測完一定 `aos stop`，不留常駐。
- 邊緣跳過、小裁決記「隊長裁決」；方向性的（例如 chat 該前景還是背景）選最簡單的並記下。

## 驗收（就這 5 條）

1. rebase 後 build＋ctest 全綠，X 隊 25 支 repro 仍 PASS。
2. 空資料夾：`aos chat "你叫什麼名字"` 一個指令印出回覆（真 LM Studio）；`aos stop` 後無殘留行程。
3. 連說三句不跑回合 → `aos state` 顯示 `unread: 3`；LM Studio 關掉（或假端點失敗）跑一回合 → `aos state` 顯示 `last_error`，且 `say/` 訊息仍在、修好後下一回合被回答。
4. 兩個世界互加通訊錄，agent A 被要求「請 B 報時」→ A 的 step 投出 `aos say --to B`（log 可見），`aos contact status` 兩格都有 unread／status。
5. `aos inbox ls` 列出未讀、`aos inbox read` 印內容且不呼叫 LLM（用 `AOS_LLM_URL` 指向不存在端點證明）。

## 回報

最後一則訊息＝摘要（≤ 25 行）＋STATUS＋worktree 路徑與分支名。

## 隊長裁決

（隊長追加）
