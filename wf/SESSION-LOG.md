# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> 完成的記日誌 [session_logs](session_logs/README.md)，寫法見 [user/02](workflows/common/user/02-交接與收工.md#日誌怎麼寫2026-10-26-定)。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **open｜整體瘦身（11-01 晚使用者定方向：「就是整體要瘦身」「這塊等明天再說」）**：明天由使用者定範圍再開工 → [02 § 整體要瘦身](../proto8/thinking/2026-11-01-playground-bob/02-環境變數要使用者裁的問題.md#整體要瘦身11-01-晚使用者定方向明天再說)；今晚先做的環境變數旋鈕 42 個改 argv／檔＋刪 aos-round 整支（→ [02 § 刪 aos-round](../proto8/thinking/2026-11-01-playground-bob/02-環境變數要使用者裁的問題.md#刪-aos-round11-01-晚使用者裁定)）由隊長在 worktree 分支 `worktree-agent-a279443ccbe53ca97` 做，使用者說「弄一弄，全部上main，push」，11-01 晚已併入 main（刪 26、argv 11、檔 3；aos-round 刪，loop.json 直接叫 aos-fsm、五格拿 `AOS_CD`，→ [03](../proto8/thinking/2026-11-01-playground-bob/03-旋鈕改-argv-與檔-實作.md)）；試驗場 nia-idle 已跟著改
  - 11-02 晚使用者：「明天早上再說，或者我們這樣子一點一點的，也算是了」。今晚已刪 demo agent-dan、agent-dan-q（`7dcc3dc6`，使用者「都刪掉，過時了」）、eca 不封存。**明早候選**：`demo/llm-kernel`、`demo/self-improve`（使用者「完全沒有印象...」「明天應該會刪掉」；刪了環境變數第 4 題的 `AOS_IVY_BRAIN`、`AOS_IMPROVE_RUN` 就跟著消失）、Lua／Janet `agent_dan` 範例與 nvim 外掛 smoke（讀已刪的 agent-dan、測試已 skip，待使用者定）、10-23 agent-dan artifact；proc 改名想法 → [ctl-state-names](../proto8/thinking/2026-11-02-ctl-state-names.md)
- **open｜環境變數第 4 題傳話筒剩 `AOS_IVY_BRAIN`、`AOS_IMPROVE_RUN` 待裁**（使用者 11-01 晚沒聽懂、未答；`AOS_ROUND_AGENT` 隨刪 aos-round 消失）→ [02 § 使用者裁定](../proto8/thinking/2026-11-01-playground-bob/02-環境變數要使用者裁的問題.md#使用者裁定11-01-晚)
- **open｜公司 WSL 試驗場 `agents/amy` 待刪**（11-02 晚頂層問 amy 要不要留，使用者：「刪掉」；只在公司 WSL `~/code/playground`、不在 git，回公司時刪資料夾即可；11-01 晚「整個都怪怪」不再追）
- **open｜介質：規劃已照「都照建議」定案、條文已落、實作八步做完（10-29）**（10-30 晚回信改走 `reply_to`、重複的代號與信號產生法下放 aos-util 也做了，見實作時代定 14、15），剩：10-29 傍晚又定 agent 的輸入是 queue、接單以後放 tools（agent 做完事自己用 tool 看信箱，決定 32），晚上在試驗場做了最小版（見下 playground 條），看完後兩個使用場景都用不到看信箱、那兩題先擱著 → [10-28 medium 決定 32](../proto8/thinking/2026-10-28-medium.md)、 [thinking 10-29 medium-plan § 實作時代定](../proto8/thinking/2026-10-29-medium-plan.md#實作時代定10-29隊長與工人照原則定的細節可翻案)
- **open｜agent 一輪 round 實作完第一版（10-28 晚）**：§ 7 第 0～11 步都做了（aos-parts、endpoint fake／openai、queue、history、compact、act、round、範本 agent-nia、aos-ai spawn 認 parts.json、ask_round 外部接口；第 10 步照設計不用做）；**10-30 晚 round 骨架換成 aos-round**（`bin/aos-round`＋`lib/agent/round/` 兩張 fsm 表與五個薄格；舊 `_entry`、`--step`、`hook/pause`、round 的 `unit` trace 刪了，ask_round 改一格一格叫 aos-round、`AOS_ASK_MAX_STEPS`，→ [thinking 10-30 aos-round](../proto8/thinking/2026-10-30-aos-round.md)）；條文 P-23、P-41、P-25、C-61、P-20、P-33、C-52、N-43、N-53、C-25 已加註；代定 1～47 在 agent-round 文末（含「必要的格找不到不退 lib 標準件、報 PartMissing」）；LiteLLM 真腦與 Claude Code 經 aos-mcp 問 agent-nia 頂層 10-30 晚代跑都過（[10-30 真腦實測](session_logs/2026-10/2026-10-30-真腦實測/README.md)）；**剩**：on_error 讀 endpoint 的 stderr 跟 C-52／P-21「不讀下層 stderr」字面上的緊張等使用者看 → [thinking 10-28 agent-round](../proto8/thinking/2026-10-28-agent-round.md)、[agent-ops](../proto8/thinking/2026-10-28-agent-ops.md)
- **open｜使用者看現況地圖後的十一點（10-30）**：只剩第 1 點（plan 9 式檔案串流）、第 7 點（post／lock 補指令）開著（使用者「之後有遇到再說」），其餘已做／已定，逐點去向見 → [map-review § 結論](../proto8/thinking/2026-10-30-map-review.md#結論10-31-補)
- **open｜playground（10-26 起）**：aos-hub 10-30 改做 aos-eca-hub（11-03 改名 aos-eca-ctl；建在 aos-daemon 上、`AOS_HUB` 退場），試驗場四隻（bob-1、bob-2、nia-idle、dan-pause）在 WSL `~/code/playground/` 建好、假 CLI 跑過；家機 `~/code/playground` 11-02 晚重建後補 `agents/eca_bob`＋用 `daemons/main` 當 hub 的 daemon（真的 `claude -p`〔haiku〕跑過非互動部分、清回起始狀態），`open` 畫面那段使用者 11-02 晚親手玩完（「好了，我玩完了，體驗不錯。」）；開著：停著改 history 再繼續（外部 agent 要 aos-eca-turn 重開 session，→ [eca § 之後再改](../proto8/thinking/2026-10-30-eca.md#之後再改停著時改-history-再繼續10-30使用者先記下)）、aos-eca-turn 定義檔只認固定名字（10-31 使用者判準：現階段維持固定，→ [eca § 10-31](../proto8/thinking/2026-10-30-eca.md#10-31-使用者原文turn-的定義檔只認固定名字先記之後處理)）、pi coding agent 沒裝只有適配表；aos-round 10-30 晚做完（第 1～7 步；第 8 步只記不做）（queue 空的停法 11-01 已改 argv `aos-round --on-empty`，A 題 → [parts-round](../proto8/thinking/2026-10-31-parts-round.md#決定11-01-使用者)），agent-nia 經 aos-round 接真腦 10-30 晚頂層代跑過了（`aos_ws.py` 失敗判法 11-02 已改）→ [thinking 10-30 aos-round](../proto8/thinking/2026-10-30-aos-round.md) → [thinking 10-30 eca](../proto8/thinking/2026-10-30-eca.md)、[thinking 10-26 playground](../proto8/thinking/2026-10-26-playground.md)、統整頁 https://claude.ai/artifact/W7aXZvCPTf1u2qExH6CEMM
- **open｜固定名字判準（C-51 10-31 加註）：使用者尚有後續想法待追究** → [eca § 10-31 原則](../proto8/thinking/2026-10-30-eca.md#10-31-使用者原則固定名字可以但限縮範圍判準)
- **open｜topdown 的 7 個測試紅（11-03，trace.jsonl 拿掉之後；topdown/ 沒動）**：galtxt-a 4 案、galtxt-b 3 案讀 fsm 的 trace 量格序與時間，等使用者挑辦法 → [thinking 11-03 trace § 要使用者看的](../proto8/thinking/2026-11-03-trace.md#要使用者看的topdown-兩個實驗靠-trace-量東西未決頂層沒動-topdown)
- **open｜`test_topdown_galtxt_b_fold` 偶爾紅（10-29 查到原因，程式沒改；11-03 起 trace 拿掉，這條跟上面那條一起看）**：galtxt-b `deliver/_entry` 的 measure 用「trace 行的 started_at（牆上時間）＋elapsed_ms（單調時間）≥ brief.json 的 mtime − 5 ms」挑這題的行；WSL 的牆上時間每幾十秒會往前跳約 0.55 秒（實測 90 秒兩次），跳在 brief 那格裡就把寫 brief.json 的那行漏掉，q08 的 counter_cycles 2→1、cells 少一格，verify 兩邊比就紅（循環跑 15 次紅 1 次，test_verify）。要修得改挑行的方式（例如不比時間、照 trace 行的位置），是乙隊 round2 §4 的量法，先等使用者／乙隊收線那條一起看 → [乙隊 HANDOFF](../proto8/topdown/galtxt-b/HANDOFF.md)
- **open｜10-25 galtxt 由上而下兩隊：都已收線，等使用者想完說他抓到的問題點**（使用者 10-30：很複雜，先拖著；再動之前先問）；topdown 自己的 `GALTXT_*`／`OPTKIT_*`／`SELFOPT_*` 33 個沒補 AOS_ 前綴（10-31 照預設暫不動、可重訪，→ [naming-method § 10-31 已改](../proto8/thinking/2026-10-23-naming-method.md#10-31-已改隊長與工人照-r8r9-代定新名可翻案)）：兩隊沒做的見 [甲隊 HANDOFF](../proto8/topdown/galtxt-a/HANDOFF.md)、[乙隊 HANDOFF](../proto8/topdown/galtxt-b/HANDOFF.md)；統整頁 https://claude.ai/artifact/9sj3ZkRhK4ZYomb8WeSzrA ；代定清單與今天做了哪些 → [session log 10-25](session_logs/2026-10-parts/13-10-25至10-27.md#2026-10-25)
- **open｜10-24 其餘下一步**（代定可翻案）：代定落條文、沙箱殘項（`accept` 跟「純靠 Linux」衝突待使用者，[sandbox S18](../proto8/thinking/2026-10-24-sandbox.md)）、compact 與 P-41 → [session log 10-24](session_logs/2026-10-parts/12-10-24.md#下一步open)
- **open｜還是草稿的條文**：N-34 tasks（沒有實作可對；N-14 窗總則、N-15 鎖、N-16 信箱 10-29 介質實作後已定） → [NORMS 待定](../proto8/docs/NORMS/08-待定.md)；使用者 10-31：tasks、seq、if 之後順便做；單檔整合指 round、先單體按需析出的方針已記 → [aos-round § 10-31](../proto8/thinking/2026-10-30-aos-round.md#10-31-使用者想法控制流不拉-seqif-拼整合成單檔tasksseqif-之後順便做先記之後處理)
- **待照新做法重寫**：還沒做的 tasks、通用 kernel 停滯（10-30）（[plan § 1.2](../proto8/thinking/2026-10-21-plan.md)）；loop／daemon／fsm、tick（9d618174）、腦的工具呼叫（10-23）、LLM kernel（10-24）已做；[rewrite-order](../proto8/thinking/2026-10-19-rewrite-order.md)、[NORMS 待定](../proto8/docs/NORMS/08-待定.md)。
- **open｜LLM kernel 下一步**：`_metainfo` 第二步 → [session log 10-24 § LLM kernel 下一步](session_logs/2026-10-parts/12-10-24.md#llm-kernel-下一步從-session-log-逐字搬來)
- **KISS 批次 2～6 暫停**（批次 1 已做完；10-16 使用者撤回「都照推薦」）→ [10-15 § KISS 批次 1](session_logs/2026-10-parts/03-10-15.md#kiss-批次-1純刪照做10-15-深夜fable)。
- **10-15 剩的兩個候選題**（只有標題、沒展開過）：對話太長（10-24 有一個可用做法：agent-kai 按意圖組 context，見 [thinking 10-24 intent-context](../proto8/thinking/2026-10-24-intent-context.md)）、規範草稿定稿（NORMS 多數條文還標草稿）→ [10-15](session_logs/2026-10-parts/03-10-15.md#2026-10-15)。其餘 10-15 動工自定點與總原則四條已隨 10-19 刪舊程式作廢或併入現行規範（10-21 清點，使用者同意清掉）。
- **proto8（主線）**導覽：[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/docs/CONCEPTS.md)、[NORMS](../proto8/docs/NORMS.md)、[bin README](../proto8/bin/README.md)；[restart](../proto8/thinking/2026-10-11-restart.md) §4 列了他停在半路的幾處。
- 10-09 留下的約定（全文 [→](session_logs/2026-10-parts/01-10-02至10-09.md#2026-10-09)）：對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰（原本的合併腳本 `aos-wt/merge.sh` 10-23 已刪、作廢，照一般 git）。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
