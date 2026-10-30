# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> 完成的記日誌 [session_logs](session_logs/README.md)，寫法見 [user/02](workflows/common/user/02-交接與收工.md#日誌怎麼寫2026-10-26-定)。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **open｜介質：規劃已照「都照建議」定案、條文已落、實作八步做完（10-29）**，剩：aos-llm-send／aos-llm-kernel（10-30 由 aos-gate／aos-kernel-llm 改名）的回信改走 `reply_to`（決定 3 先留，實作第 6 步的後半）；重複的代號與信號產生法下放 aos-util；10-29 傍晚又定 agent 的輸入是 queue、接單以後放 tools（agent 做完事自己用 tool 看信箱，決定 32），晚上在試驗場做了最小版（見下 playground 條），看完後兩個使用場景都用不到看信箱、那兩題先擱著 → [10-28 medium 決定 32](../proto8/thinking/2026-10-28-medium.md)、 [thinking 10-29 medium-plan § 實作時代定](../proto8/thinking/2026-10-29-medium-plan.md#實作時代定10-29隊長與工人照原則定的細節可翻案)
- **open｜agent 一輪 round 實作完第一版（10-28 晚）**：§ 7 第 0～11 步都做了（aos-parts、endpoint fake／openai、queue、history、compact、act、round、範本 agent-nia、aos-ai spawn 認 parts.json、ask_round 外部接口；第 10 步照設計不用做）；**10-30 晚 round 骨架換成 aos-round**（`bin/aos-round`＋`lib/agent/round/` 兩張 fsm 表與五個薄格；舊 `_entry`、`--step`、`hook/pause`、round 的 `unit` trace 刪了，ask_round 改一格一格叫 aos-round、`ASK_MAX_STEPS`，→ [thinking 10-30 aos-round](../proto8/thinking/2026-10-30-aos-round.md)）；條文 P-23、P-41、P-25、C-61、P-20、P-33、C-52、N-43、N-53、C-25 已加註；代定 1～47 在 agent-round 文末（含「必要的格找不到不退 lib 標準件、報 PartMissing」）；**剩**：等使用者親手試（LiteLLM 真腦、Claude Code 經 aos-mcp 問 agent-nia，見 WAIT_USER）、on_error 讀 endpoint 的 stderr 跟 C-52／P-21「不讀下層 stderr」字面上的緊張等使用者看 → [thinking 10-28 agent-round](../proto8/thinking/2026-10-28-agent-round.md)、[agent-ops](../proto8/thinking/2026-10-28-agent-ops.md)
- **open｜aos-tools 做完第一版（10-28）**：後續剩一件——10-26 playground（家機 `~/code/try/playground/agent/`）的 mcp 設定還是舊寫法（給工具資料夾），要改成給 agent 資料夾＋`aos-tools add` → [thinking 10-28 aos-tools § 結論](../proto8/thinking/2026-10-28-aos-tools.md#結論10-28-實作照原則代定可翻案)
- **open｜agent-lifecycle 實作（10-30）：十步都做完了**（第 6、9 步與 P-42 暫緩的那句 10-30 改照 eca 做完，見 [thinking 10-30 eca](../proto8/thinking/2026-10-30-eca.md)），剩：round 的 `letter_warning`（Q-4）沒做（10-30 晚起 round 是 aos-round，要做就落在 idle 格） → [thinking 10-30 agent-lifecycle § 實作時代定](../proto8/thinking/2026-10-30-agent-lifecycle.md#實作時代定10-30隊長與工人照原則定的細節可翻案)
- **open｜使用者看現況地圖後的十一點（10-30）**：原文已記，第 6 點（掛到 daemon 的指令，自動識別 loop、不是就 `max: 1`）方向已定交實作隊長、第 9 點 aos-kernel-llm 改名 aos-llm-kernel 已定（十步之後做，`aos-<領域>-<功能>` 要不要成條文開著）、第 10 點（掛 daemon 的指令靠環境變數＋argv 決定 daemon home，細節交實作隊長照 N-63 代定）、第 11 點 aos-gate 改名已定（頂層建議 `aos-llm-send`、代定可翻案，跟 kernel 改名同一批）、第 7 點 post/lock 補指令開著不急；第 4 點（parts.json 維持）與第 5 點的名字已定（現有 aos-hub 改名 aos-eca-hub、通用層就是 aos-daemon、`aos-hub` 名字保留；怎麼改名交 fable 連第 3 點規劃）；第 1（plan 9 式檔案串流）、2 的框架題（round 能否待在 aos-loop／fsm 下：隊長查完，答在 [agent-lifecycle § 使用者問](../proto8/thinking/2026-10-30-agent-lifecycle.md#使用者問round-能不能放在-aos-loopfsm-的框架下實現10-30只查沒改)）、3（外部 agent 與 aos agent 平級、分兩塊比較做通用介面）、5（aos-hub 通用化、aos-eca-hub）開著，agent-lifecycle 實作第 6、9 步暫停；使用者說「剩下的我覺得之後有遇到再說」，看地圖這輪到此；第 6、10 點（aos-daemon-ctl）、第 9、11 點（改名）實作隊長 10-30 做了；頂層的回答待補成結論；**第 3、5 點 eca 規劃照「都照建議」實作九步做完（10-30）→ [thinking 10-30 eca](../proto8/thinking/2026-10-30-eca.md)；第 9 點的命名慣例已寫成 C-54 R13（可翻案）**；還開著的：第 1、7 點、頂層的回答待補成結論 → [thinking 10-30 map-review](../proto8/thinking/2026-10-30-map-review.md)
- **open｜playground（10-26 起）**：aos-hub 10-30 改做 aos-eca-hub（建在 aos-daemon 上、`AOS_HUB` 退場），試驗場四隻（bob-1、bob-2、nia-idle、dan-pause）在 WSL `~/code/playground/` 建好、假 CLI 跑過，**等使用者用真 CLI 親手試**（WAIT_USER）；開著：停著改 history 再繼續（外部 agent 要 turn 重開 session，→ [eca § 之後再改](../proto8/thinking/2026-10-30-eca.md#之後再改停著時改-history-再繼續10-30使用者先記下)）、pi coding agent 沒裝只有適配表；aos-round 10-30 晚做完（第 1～7 步；第 8 步只記不做），還開著：`aos_ws.py` 失敗判法那題等使用者裁、agent-nia 經 aos-round 接真腦的親手試（都在 WAIT_USER）→ [thinking 10-30 aos-round](../proto8/thinking/2026-10-30-aos-round.md) → [thinking 10-30 eca](../proto8/thinking/2026-10-30-eca.md)、[thinking 10-26 playground](../proto8/thinking/2026-10-26-playground.md)、統整頁 https://claude.ai/artifact/W7aXZvCPTf1u2qExH6CEMM
- **open｜`test_topdown_galtxt_b_fold` 偶爾紅（10-29 查到原因，程式沒改）**：galtxt-b `deliver/_entry` 的 measure 用「trace 行的 started_at（牆上時間）＋elapsed_ms（單調時間）≥ brief.json 的 mtime − 5 ms」挑這題的行；WSL 的牆上時間每幾十秒會往前跳約 0.55 秒（實測 90 秒兩次），跳在 brief 那格裡就把寫 brief.json 的那行漏掉，q08 的 counter_cycles 2→1、cells 少一格，verify 兩邊比就紅（循環跑 15 次紅 1 次，test_verify）。要修得改挑行的方式（例如不比時間、照 trace 行的位置），是乙隊 round2 §4 的量法，先等使用者／乙隊收線那條一起看 → [乙隊 HANDOFF](../proto8/topdown/galtxt-b/HANDOFF.md)
- **open｜10-25 galtxt 由上而下兩隊：都已收線，等使用者想完說他抓到的問題點**（使用者 10-30：很複雜，先拖著；再動之前先問）：兩隊沒做的見 [甲隊 HANDOFF](../proto8/topdown/galtxt-a/HANDOFF.md)、[乙隊 HANDOFF](../proto8/topdown/galtxt-b/HANDOFF.md)；統整頁 https://claude.ai/artifact/9sj3ZkRhK4ZYomb8WeSzrA ；代定清單與今天做了哪些 → [session log 10-25](session_logs/2026-10/2026-10-25.md)
- **open｜10-24 其餘下一步**（代定可翻案）：代定落條文、沙箱殘項（`accept` 跟「純靠 Linux」衝突待使用者，[sandbox S18](../proto8/thinking/2026-10-24-sandbox.md)）、compact 與 P-41 → [session log 10-24](session_logs/2026-10/2026-10-24.md#下一步open)
- **open｜還是草稿的條文**：N-34 tasks（沒有實作可對；N-14 窗總則、N-15 鎖、N-16 信箱 10-29 介質實作後已定） → [NORMS 待定](../proto8/docs/NORMS/08-待定.md)
- **待照新做法重寫**：還沒做的 tasks、通用 kernel 停滯（10-30）（[plan § 1.2](../proto8/thinking/2026-10-21-plan.md)）；loop／daemon／fsm、tick（9d618174）、腦的工具呼叫（10-23）、LLM kernel（10-24）已做；[rewrite-order](../proto8/thinking/2026-10-19-rewrite-order.md)、[NORMS 待定](../proto8/docs/NORMS/08-待定.md)。
- **open｜LLM kernel 下一步**：`_metainfo` 第二步 → [session log 10-24 § LLM kernel 下一步](session_logs/2026-10/2026-10-24.md#llm-kernel-下一步從-session-log-逐字搬來)
- **open｜agent-dan artifact**：https://claude.ai/artifact/4mhycShcVdr7jJskGWc92V ，agent-dan 改了就跟著更新（使用者 10-23「之後我們慢慢做好，這個artifact也會跟着更新」；改法：Artifact `read` 拿最新版、改完同網址重發）→ [demo README § agent-dan](../proto8/demo/README.md#agent-dan真腦工具10-23)
- **KISS 批次 2～6 暫停**（批次 1 已做完；10-16 使用者撤回「都照推薦」）→ [10-15 § KISS 批次 1](session_logs/2026-10/2026-10-15.md#kiss-批次-1純刪照做10-15-深夜fable)。
- **10-15 剩的兩個候選題**（只有標題、沒展開過）：對話太長（10-24 有一個可用做法：agent-kai 按意圖組 context，見 [thinking 10-24 intent-context](../proto8/thinking/2026-10-24-intent-context.md)）、規範草稿定稿（NORMS 多數條文還標草稿）→ [10-15](session_logs/2026-10/2026-10-15.md)。其餘 10-15 動工自定點與總原則四條已隨 10-19 刪舊程式作廢或併入現行規範（10-21 清點，使用者同意清掉）。
- **proto8（主線）**導覽：[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/docs/CONCEPTS.md)、[NORMS](../proto8/docs/NORMS.md)、[bin README](../proto8/bin/README.md)；[restart](../proto8/thinking/2026-10-11-restart.md) §4 列了他停在半路的幾處。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)）：對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰（原本的合併腳本 `aos-wt/merge.sh` 10-23 已刪、作廢，照一般 git）。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
