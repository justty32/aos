# 查證 G（sonnet 唯讀，fable 交稿後）：fable「我沒把握的」十題逐題查程式與活樹（唯讀），含活樹 agent 的 think 列數與 llm kernel 帳的實測中位數

## 1. history 對 observed 的 think 列
結論：部分。能對，但靠「順序」，不靠信名。
- observed think 列：{kind, letter, endpoint, model, usage, elapsed_ms}（templates/agent-fsm/wait.py:395-400）。沒有時間戳、沒有 history 行號。
- history 的 assistant 訊息只是 kernel 回信的 message（wait.py 寫進 history，約 :419），不帶 letter。所以 letter 只存在於 observed、think/sent.json、kernel 的 ledger id。對法＝第 n 個成功的 think 列 ↔ 第 n 則 assistant 訊息。
- 失敗（kernel 回錯）也寫一列：wait.py:408 `observe({})` 然後 BrainFailed，無對應 assistant；對不上的就是這種列。
- 會被裁剪：`aos-agent history rm/summarize`（lib/agent/self_history）與 cli_hook 的 /clear、/compact（lib/agent/cli_hook.py:55-145）。被換掉的原文搬到同夾 `history_removed.jsonl`（每行 {removed_at, op, line, message}）。agent-fsm 本身（brain/idle/act/wait）沒有自動 trim／compact，只有 append；brain.py 的 `--history task` 只影響送出的 request，不改 history。
- 實證：~/aos-home/ws/.stack/procs/gpt-lead：think 60 列；history 現有 assistant 33、history_removed 54 列（op 全是 summarize）其中 assistant 27；33+27=60，剛好對上。其他四隻（sol-T01/02/03、gpt-lead2）assistant 數＝think 數或差被 summarize 吃掉（gpt-lead2：14 vs 25）。
- think/request.json：每次覆蓋（brain.py:204-205 先寫 .request.json.tmp 再改名）；只留最後一次。think/sent.json 同樣只留最近一次。

## 2. fsm 狀態有沒有被記錄
結論：否（只有「當下」，沒有轉移紀錄）。
- `$AOS_STACK/stage.txt` 單行當下狀態名，內容沒變不重寫（impls/aos-fsm/docs/01-用法.md:32-34）；實例 procs/sol-T01/stage.txt = `idle`。
- state.json／state_flux.json 是 loop 的 phase、pid、ctl（`{"phase":"stopped",...}`），不含 idle/think/wait/act。
- observed.jsonl 的 kind 只有 self、think、tool；history 沒有。要還原狀態序列只能從 observed 列推（think→wait／act；tool→act），idle 看不到。

## 3. lib/aos/measure 的 case
結論：部分是。
- run.json 二選一：`{"exec","stdin"}` 或 `{"agent","say"}`（lib/aos/measure/runner.py:66-74）。`agent` 是相對 `--defs` 的定義夾路徑（`defs / run["agent"]`），`say` 是 case 夾內檔名，整檔內容當一則 say；選填 `timeout_s`（預設 60）。
- 起法（runner.py:40-63 agent_run）：在「目前 daemon」上 `aos-agent ctl add --name measure-<uuid> --ws <case 副本 ws> --stack <runs/N/stack> <定義>` → `aos-agent say --target … -` → `listen --timeout-s` → `ctl stop` → fold 帳 → `ctl rm --purge --yes`。不起暫存 daemon。每次 run 是全新 ws（複製 case/ws）與全新 stack，定義＝一份定義副本，故「定義副本＋一段輸入從頭跑」成立（review_round 就是這樣用）。
- 腦：沿用呼叫環境的 AOS_LLM_KERNEL／daemon，runner 不提供旗標指定 kernel 或 endpoint；endpoint 由定義的 llm.json 決定。要 fake 就讓環境的 kernel 指向 fake endpoint（lib/aos/measure/tests/test_fake_agent.py 自己起 daemon＋aos-llm-kernel＋lib/base/llm_fake，設 AOS_LLM_KERNEL）。不需真腦。

## 4. ~/aos-home 的 agent 與 think 數、試驗場
結論：~/aos-home 共 16 個 observed.jsonl，其中 5 隻是 agent（其餘 11 是 tools/shell 或 subagent 觀察副本）。
| agent（procs/） | think 列 | observed 總列 | history.jsonl 行 |
|---|---|---|---|
| gpt-lead | 60 | 116 | 68 |
| gpt-lead2 | 25 | 51 | 30 |
| sol-T01 | 5 | 10 | 10 |
| sol-T02 | 19 | 37 | 38 |
| sol-T03 | 16 | 33 | 33 |
（路徑 ~/aos-home/ws/.stack/procs/<名>/；gpt-lead 下 tools/subagent/observed/sol-T0x 是同批的觀察副本，無 history。）
- ~/code 試驗場：playground-ak 有 460 個 observed.jsonl（think 537 列）、playground-ak5 有 1078 個（think 1094 列）；playground/arc1/arc-play/qa 為 0。全 ~/code 共 1539 個。
- 前 10 大（bytes）全在 playground-ak/runs/2/：2762 places/poshan-baseline/raw/observed.jsonl；2637 attempts/poshan-text-v1/；2094 b8/qa/q05/raw/qa-02f38ca3b722/；2090 b8/qa/q04/…qa-e58dda050bd1/；2089 b8/qa/q03/…qa-2e06aebc692a/；2076 b7/h4/songxinshangu-b5-1/raw/reviewer-b5c72353d4af/；1835 b7/h4/qieernuoboge-b3-2/…；1828 b7/reviewer-wusasi/raw/reviewer-b3b69b4193fb/；1739 b7/h4/yibiliyazhiyan-b6-1/…；1736 b7/h4/songxinshangu-b5-2/…。都極小（<3 KB）＝每個只有幾列；量大是因為份數多（ak5 最大單檔 1431 B）。

## 5. kernel 框架 hook／llm kernel
結論：不能改排序、不能自己回信、無快取口；C++ 版根本沒 hook。
- lib/aos/kernel/hooks.py：三事件 before_verdict（可改 body、可攔）、after_verdict（可改 verdict／error／next，hold）、before_reply（可改代回 body；只有 reply_via_me 的 proc 包用）。排序是包的 `order(ctx, letters)`（問腦包在 lib/aos/kernel_llm/order.py:150 sorted），hook 無此口。
- 「自己回信」：hook 退 10 攔下＝回一封 error（HookRejected；README kernel_llm 40-47）；after_verdict 可改 refuse 並自訂 error {code,msg}。不能給 success 回信（回的是 error 物件，不是 `{message,usage}`）。問腦包的 before_reply 只在「掛出去跑過、有結果」的信上跑，能改回信 body（理論上可替換成別的內容，但仍需已跑過一次端點，不是跳過）。
- 問腦包 lib/aos/kernel_llm 有 hooks（TOP_KEYS 含 hooks，packs.py:12）；README 說「多了三個 hook 時機」。C++ impls/aos-llm-kernel/src：grep hook|cache 零命中＝沒有 hook、沒有快取。結論：「命中快取直接回信」兩邊都沒有口；before_verdict 改 body 之後仍會被掛去跑。

## 6. kernel.json 加新頂層 key
結論：全部忽略，不拒。
- Python lib/aos/kernel_llm/packs.py:178 `top = resolve({key: doc[key] for key in TOP_KEYS if key in doc}, base)`：只取已知 9 個 key（含 hooks），其他不碰（連指示詞都不解）。
- C++ impls/aos-llm-kernel/src/serve/config.cpp:24 `resolve_keys(doc, …, {"slots","reserved","aging_cycles","budget","exec","endpoint","timeout_ms","backends"})`，後面逐 key 取，無「未知頂層 key」檢查。
- lib/aos/kernel/procs_rules.py:8 load 註解「只驗這一包認得的設定，其他鍵照放」，未知鍵不報。
- 例外：`reserved` 內部有未知 key 會 CfgBad（只允許 high）；endpoints 之下各組形狀有驗。
- 注意：C++ 沒把 `hooks` 列進認得的 key，kernel.json 寫 hooks 它會忽略。

## 7. llm kernel ledger.jsonl
結論：是，兩支實作都有 seen_at、mounted_at、sender。
- Python lib/aos/kernel_llm/ledger.py:18-21：id、endpoint、sender、model、seen_at、mounted_at、finished_at、elapsed_ms、usage、code、child、switched。
- C++ impls/aos-llm-kernel/src/serve/reply.cpp:100-125 同欄位；docs/02-token-回報與額度.md:28 說明欄位順序。seen_at 抄自 queue.seen_at_ms/1000（抄不到＝null）；重掛 mounted_at 取最後一次、seen_at 保留第一次；elapsed_ms＝finished_at−mounted_at（不含排隊）。sender＝寄件人身分路徑（信封 sender，如 /home/lorkhan/repo/aos，是工作區路徑而非 agent 名）。
- 活樹只有一份：~/aos-home/ws/.stack/procs/llm-gpt/ledger.jsonl，127 列，0 錯誤。
  - 全部：elapsed_ms 中位 4446；(mounted_at−seen_at) 中位 1.3 ms；sender 4 種。
  - astra-high：86 列，elapsed 中位 4148.5，mount−seen 中位 1.4 ms。
  - sol-high：41 列，elapsed 中位 5129，mount−seen 中位 1.2 ms。
  （排隊延遲近 0＝槽夠用沒排隊；elapsed 不含排隊時間，但 seen→mount 已證明沒排隊。）

## 8. letter.json 頂層 key
結論：可加小欄位，讀端忽略，但經 aos-post send 寫不進、回信不保留。
- 格式：`{"sender","sent_at","sent_at_cycles"?,"reply_to"?,"in_reply_to"?,"body"}`（impls/aos-post/docs/01-用法與元素.md:29）。文件明說「沒有 kind；讀到也只是不認得的 key、忽略」。
- 壞信條件（take.cpp:75-90）只驗：sender／sent_at 字串、body 存在、sent_at_cycles 非負整數、reply_to／in_reply_to 字串；多餘頂層 key 不會被拒。
- 但：`aos-post send` 沒有「加自訂頂層 key」旗標（需另查旗標表；send.cpp 只寫上述欄位），寫信封欄位須手寫 letter.json 或擴 aos-post；kernel hooks 的 request_data（hooks.py）只轉 sender、sent_at、reply_to、body 給 hook，自訂 key 看不到；kernel 回信是新信、不帶回原信封的自訂 key。小欄位較穩的放法＝放進 body（body 形狀由收件程式自己驗；問腦包要不要拒 body 未知 key 未逐一查，llm 請求 body 有 endpoint／request／priority）。

## 9. reviewer 的處方
結論：格式有定義，沒找到實例（活樹與 ~/code 都沒有 extract／box／unshell 的 review.json）。
- templates/reviewer/system.txt:15-35：用 json_set 寫到 `<review.json>#/prescriptions`，值為 1～3 條的陣列，每條 `{"move": "fix"|"split"|"extract"|"box"|"unshell", "target": "<所選定義>", "why": "<review 證據>", "how": "<具體實作步驟>"}`。fix 只在 consistency.pass 明確為 true 時；否則 split。
- README（templates/reviewer/README.md:29）：extract＝為重複的 shell 工作開專用工具；box＝為任意執行加沙箱；unshell＝專用工具蓋住後拿掉任意執行。三者只是處方，不自動執行。
- 示意（按格式構造，非實例）：`[{"move":"extract","target":"defs/x","why":"shell 呼叫 grep 重複 7 次","how":"新增 tools/grep_count，tools.json 掛上，system.txt 改用之"}]`。
- 測試的 fake 實例：templates/tests/reviewer/endpoint.py（endpoint.prescription 直接塞一條，測試用 split）。
- ~/code/playground-ak 的 cases/*/place/review.json 是另一套（鍵 schema、place、move、prescription 單數、decision…），prescriptions 複數為 null，別混。

## 10. proto8/py/aos_metaopt
結論：不存在，沒被用過。
- ls：No such file or directory；`git log --oneline --all -- py/aos_metaopt` 空。
- 只在 thinking/2026-11/08/aos-self-opt（README.md:13）規劃「共用核心 py/aos_metaopt」，只規劃未施工。現有 proto8/py/ 僅 aos_clock_register.py、aos_clock_when.py、aos_flags.py、aos_sweep.py。
