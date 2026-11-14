> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# F1 起源與方向——ai_core 的 roadmap／spec／ideas／kb 采風

← [ai-core-field](README.md)｜采風日 2026-08-30｜隊長 Fable，隊員 codex ×3（sol：roadmap＋overview／terra：spec 全部／luna：ideas＋kb）

範圍：`~/repo/ai_core/workflows/roadmap/`、`workflows/spec/`、`workflows/ideas/`、`docs/kb/`。只讀，未改。
引用一律寫 ai_core 相對路徑；aos 這邊寫 worktree 相對路徑。

## ① 那塊在講什麼（白話，給使用者回憶用）

**roadmap（北極星，不是規範）**：前提是 AI 泡沫後只剩便宜的本地 <10B 笨模型，所以要做鷹架去扶它；CLI 天生適合 LLM，
最初形態就是「一堆小命令行函式＋它們的組合」（`roadmap/s0-2-vision.md` §0–1）。三個核心主張：
(a) **LLM 退縮到兩介面**——成熟系統裡 LLM 只剩「人類意圖→結構化意圖的翻譯層」與「尚未固化的模糊前沿」，其餘都是確定性程式碼；
單位不是 skill，是「帶 LLM 留白的程序」，LLM 是 `switch` 的 `default:` 分支（`s3-endgame-governance.md` §3.1–3.3）。
(b) **拒絕為預設、憑證准入**——LLM 預設零領地，要進某環節得證明「非它不可」＋「測得夠穩」，並發證書（模型／測試組／穩定度 %），可撤照（§3.4）。
(c) **飛輪＝固化**——趁聰明模型便宜先當「資產工廠」轉幾圈，再逐步把 LLM 常處理的模糊案例凍成確定性 matcher；「誰來固化」仍未決（§3.5–3.6）。
第一目標是程式碼助手、v0 是「笨模型＋行數助手＋retry/guard 在錨點插一個函式」（`s4-6-design-target-v0.md`），**至今未開工**。

**spec（正式規範，自稱 Phase 1 未定論）**：從 POSIX terminal 出發把「函式的執行形式」建模（`spec/overview.md`）。
CLI 呼叫＝Lisp 呼叫的序列化：程式名是 car、positionals 是 bare 值、`--key v` 是 keyword pair（`cli_spec.md` §2.0）；JSON 是跨工具唯一通用格式（`data_format.md`）。
**所有工具必須實作 `--metadata`**，印一份純 JSON 描述自己（`cli_spec.md` §2.3）。描述的內容是**九軸**：I/O `entries`、`lifecycle`（one_shot／persistent）、`state`（stateless／stateful_external）、
`resources`、`interruptible`、`guarantee`（none／idempotent／transactional）、組合模式（**明言不入 metadata**）、環境模式（**明言不入 metadata**）、`nondeterministic`（第九軸，承載證書）
（`execution_forms/s0-axes.md` §0；欄位定義在 `lib_spec/`）。另有非軸活值 `reliability`。兩條複合慣例：工作目錄下 `.config/.cache/.state/.data/<program>` 的狀態目錄，
與 `.state/<program>/recovery.json` 的中斷恢復（`composite_spec/`）。

**ideas 與 kb**：kb-ss 是舊架構文件的白話版——`--metadata` 硬規則（JSON object、UTF-8、`tool sub --metadata` 合法）、推薦欄位 `name/summary/description/usage/io/examples/errors`、
`--json-errors`、容錯（沒 metadata 就標 `absent` 照列）（`docs/kb/kb-ss/doc_11_arch_protocol.md`）；**Function Hub** 掃資料夾、對每個候選跑 `--metadata` 整名冊、匯出 MCP／OpenAI tools／Agent Markdown（`doc_13_arch_hub.md`）；
LLM Entry Manager＝server＋wrapper CLI 排隊守 GPU（`doc_12_arch_entry_manager.md`）；馴化五層 L0 契約→L1 確定化→L2 驗證→L3 聚合→L4 編排（`doc_20_taming_framework.md`）。
ideas 是固化引擎 v0 藍圖（wake-sleep 庫學習、MDL 選候選、經濟淘汰）與四輪論文碰撞。

## ② aos 已承接的

| ai_core | aos 對應 | 證據 |
|---|---|---|
| 「一堆小命令行函式＋組合」、Unix 哲學、POSIX only（`spec/overview.md`、`roadmap/README.md`） | `aos` 本身就是子命令集；exec 只認 argv／env／cwd／stdin | `core/exec/README.md`「只認 argv 與環境」 |
| JSON 是唯一跨工具格式（`data_format.md` §3.1） | 指令／結果／state 全是 JSON，`aos::wire` 是唯一懂形狀的一層 | `wire/README.md`、`PROTOCOL.md` §2–4 |
| terminal model 的 stdin／stdout／stderr／exit code 慣例（`terminal_model.md` §1.2） | 結果 JSON 原樣保存 `exit/signal/stdout/stderr`，不自創錯誤模型 | `PROTOCOL.md` §3 |
| 4.7 Detached／fire-and-forget、4.8 fan-out/fan-in（`execution_forms/s4-forms-1.md`） | 投遞匣＋「整批並行 fork、統一等完」＝一回合就是一次 fan-out/fan-in | `loop/README.md` |
| 4.18 Agentic loop「執行期動態生成的觀察→思考→行動」（`s4-forms-2.md`） | `aos agent` 靠 `every/` 自我投遞 step；工具 N 投遞、N+1 執行、N+2 收 | `core/agent/README.md`「工具往返」 |
| LLM Entry Manager 是**獨立 server**，別讓 10 個 AI 同時塞爆顯卡（`doc_12`） | 「LLM 不是被呼叫的函式，是另一台跑同一套協定的機器」、全域 LLM CPU | `ideas/top-down-cli.md` §三、`ideas/llm-cpu.md` |
| 馴化 L4「LLM 只負責決定用哪個確定性工具，重活交給腳本」（`doc_20`） | agent 的模型只能在最後一行點名**已登記**工具，執行交給 loop | `core/agent/src/tools.cpp` `extract_tool_call` |
| 「宣告與攔截分離」——讀 metadata 不可觸發執行（`lib_spec/register-intercept-lifecycle-state.md`） | `tools.json` 是靜態檔，讀名冊不跑任何程式 | `tools.cpp` `read_tools` |
| 原子寫（temp＋rename）、4.12 Transactional 的 terminal 表現 | inbox `.json.tmp`→`rename`；state.json 同法 | `PROTOCOL.md` §1、§4 |

一句話：**aos 把 ai_core 的「執行機制」那半（POSIX、JSON、fan-out、agentic loop、LLM 獨立成機器）接得很實**。

## ③ aos 漏掉／走偏的（附證據）

判斷用的尺：ai_core 的靈魂在 **①(a)(b)(c)**——函數自我描述、LLM 憑證准入、固化飛輪。aos 現在接到的全是機制，靈魂三件一件都還沒。

1. **tool 沒有自我描述，只有給人讀的一句話。** ai_core：「為了速度，所以要規範函數的自我描述，如此可以用時間限制當參數去選函數」（`roadmap/README.md` L7）、
   「`--metadata` 所有工具必須實作」（`cli_spec.md` §2.3）。aos：`tools.json` 每項只有 `{name, description, argv[]}`（`core/agent/src/tools.cpp` L68–83），
   `description` 只拿來拼進 system prompt（同檔 `system_prompt`）。沒有任何機器可讀的軸——loop 不知道一條指令能不能重試、能不能並行、會不會寫外部狀態。
   這不是走偏，是**還沒開始**；但要小心方向：ai_core 的 metadata 是「怎麼跑」（operational），「做什麼／參數是什麼」在 ai_core 也**仍未定案**（`docs/kb/kb-ss/note_06_decisions_and_open_questions.md` §2）——aos 別以為抄過來就有語意層。

2. **「任何 POSIX 程式＝tool」與「所有工具必須 `--metadata`」正面衝突。** ai_core 的 hub 掃資料夾對每個檔跑 `<file> --metadata`（`doc_13_arch_hub.md` §2）；`ls`／`cat`／第三方 binary 永遠不會答。
   aos 的 default tools 正是 `sh -lc`／`ls`／`cat`（`tools.cpp` `default_tools`）。ai_core 自己也留了後路：沒 metadata 就標 `absent` 照列、不崩（`doc_11` §4、`doc_13` §4）。
   → 結論在 ④：**登記表必須能替工具代答**，自述是加分不是門票。

3. **LLM 留白沒有證書，也沒宣告自己是隨機的。** ai_core：「函式預設是確定性的；要讓一個環節由 LLM 填，得主動宣告 `nondeterministic`」，成熟期帶 `{model, test_set, stability}`（`axis_spec/s9-nondeterminism.md`、`lib_spec/s9-…` §9）。
   aos：`aos llm` 與 `aos agent step` 是 `every/` 裡一條普通指令，跟 `ls` 同級、無任何標記（`PROTOCOL.md` §1 `every/`）。aos 的 verdicts 已裁「CPU 類比三樣無解：原子性、封閉 ISA、確定性——認了」（`wf/workflows/ideas/verdicts.md` A 表）——
   **這裡走偏了**：ai_core 說的不是「機器不確定所以認了」，而是「哪一條指令不確定要標出來、要發證、要能撤」。認了確定性無解＝把 ai_core 最核心的治理原則整個放掉。至少該標 `nondeterministic: true`（開機期），這是零成本的。

4. **回合制把 persistent 壓扁成 one-shot，規範沒說。** ai_core lifecycle 只有兩值 one_shot／persistent，persistent＝「持續存活等請求，直到被顯式終止」（`lib_spec/register-…` §2）。
   aos 的 agent 是「每回合重新投遞的 one-shot」模擬 persistent；`--interface claude` 那種常駐程式「生命週期對不上」已被自己列為開放問題 11（`ideas/top-down-cli.md` §五）。
   這是 aos 刻意的選擇（世界回合制），不算偏；但**登記表若標 `lifecycle` 就得寫清楚「aos 回合內只跑 one_shot；persistent 工具由 `every/` 反覆投遞模擬，或住在另一台機器」**。

5. **`env` 只加不減，方向與 ai_core v0 相反。** ai_core v0：「`subprocess(env=白名單)` 軟隔離、三層護欄 fail-closed」（`roadmap/s4-6-design-target-v0.md` §6.1）。aos：「env 只加不減，疊在 loop 自己的環境上」（`PROTOCOL.md` §2），
   且 verdicts 裁「權限／安全交給上層」。原型期可以，但登記表是最自然的白名單掛點（見 ④）。

6. **有執行歷史，沒有溯源接力。** ai_core 用 `AI_CORE_TRACE_ID` env＋asset `trace[]` 逐站追加、不改寫上游（§6.1）。aos 有 `AOS_FOLDER`／`AOS_TURN` 兩個 env 與 `batch/<turn>/out/`，
   但工具結果與「哪一次 LLM 決定叫它」之間沒有 id 相連——agent 自己在 history 對號。kb-ext 的 trace schema 只要 `trace_id`＋`parent_id`（`docs/kb/kb-ext/ext_07_observability_and_provenance.md`）；
   aos 把 inst `id` 當 `trace_id` 注進 env、投遞時帶上 `parent_id`，就接上了。

7. **固化飛輪完全缺席，但 aos 其實已經有燃料。** `batch/<turn>/insts/`＋`out/` 就是 append-only 的 wake trace（`ideas/crystallization_engine_blueprint/s4-schemas.md` §4.2）。
   這條**不建議現在做**（ai_core 自己也未開工），只記一句：別把 batch 歷史設計成會被清掉的暫態。

8. **兩個「沒定案」別誤抄成定案**：ai_core 的 `spec/overview.md` 至今「待填：本質是什麼」；hub 的 registry 格式沒有 key／版本／覆寫規則（codex sol 報告 C3）。aos 拿它當起源沒錯，但起源自己也還在 Phase 1。

## ④ 對 tool 登記表與表述的具體建議

前提：tool＝任何 POSIX 可呼叫的程式。原則一句話——**登記表是「行為契約」不是 allowlist；自述是可選的來源，登記表能代答、也能覆寫。**

1. **三層來源，優先序固定**：`registry 覆寫 > 工具 `--metadata` 自述 > 預設`。預設就照 ai_core：缺席＝`one_shot`＋`stateless`＋`guarantee: none`＋`interruptible: unsafe`＋deterministic＋單一 stdio entry（`lib_spec/` 各檔「預設值」）。
   支援自述的工具（aos 自己的子命令先做）由 `aos tool probe <name>` 跑 `--metadata` 校對，不一致印警告不擋。

2. **登記項最小欄位**（照 ai_core 名字，不另創詞）：
   ```json
   {"name":"ls","argv":["ls","{args}"],"summary":"列出資料夾內容",
    "lifecycle":"one_shot","state":"stateless","guarantee":"idempotent",
    "nondeterministic":false,"resources":{"time":"~10ms"},
    "entries":{"stdout":{"able_out":true,"mode":"batch","type":"text"}}}
   ```
   `name/argv/summary` 必填；其餘缺席走預設。`argv` 沿用現在的 `{args}` 模板（`tools.cpp` `expand_argv`）。
   **不放**組合模式、環境模式——ai_core 明言兩者不是單一工具的屬性（`lib_spec/s9-…` §7–8），aos 的 loop 才是組合者。

3. **LLM 類工具（`aos llm`、`aos agent step`、任何包了模型的程式）強制 `nondeterministic`**：開機期寫 `true`，之後才升 `{model, test_set, stability}`；另留可變的 `reliability`（`lib_spec/s9-…`）。
   這一條是把 ③3 走偏拉回來的最低成本動作，也讓 `state.json` 有天能回答「這個世界現在有幾個隨機點」。

4. **loop 只消費三個欄位，其餘先存不用**：`guarantee`（idempotent 才允許崩潰後自動重跑，直接回答 verdicts B 表「沒有 `.runi`／崩潰恢復」）、`state`（stateful_external 的指令同回合不並行同一 cwd）、`resources.time`（配 `timeout_ms` 的預設）。
   其他欄位是給 agent 的 system prompt 與未來排程器看的，別讓 loop 現在就變聰明。

5. **表述給誰看，分兩份產出**：給模型的清單由 `summary`＋`when`（何時該用、一句）＋`entries` 生成（取代現在整段 `description` 拼 prompt）——ai_core 的研究層把描述拆成「觸發語意」與「可執行 grounding」兩層（`workflows/ideas/research/paper_collision_2026-06-27/ii-sparks-d-f.md`），
   aos 現況「模型選 tool、下一回合執行」剛好是這個分工；給機器的用完整 JSON。ai_core 的 Hub 匯出 MCP／OpenAI tools 格式（`doc_13` §5、`kb-ext/ext_04_interoperability_mcp.md` §2 映射表：`name→name`、`description`、input schema→`inputSchema`、`nondeterministic`／`guarantee` 進 metadata）——
   aos 的 `aos tool export --format openai` 可以直接照那張表做，讓 `aos llm` 走原生 tool call 而不是「最後一行 JSON」。

6. **登記檔位置與狀態目錄**：登記表放 `.aos/tools.json`（世界層）而非 `agents/<name>/tools.json`（現況，`paths.cpp` L70）——tool 是世界的，agent 只是使用者。
   `state: stateful_external` 的工具，其狀態照 ai_core 慣例放 `<folder>/.state/<name>/`、`.data/<name>/`（`composite_spec/state-dir-convention.md`），不要塞進 `.aos/`——`.aos/` 是 loop 的地盤。

7. **`env` 白名單掛在登記項**：`"env_allow":["PATH","HOME","LANG"]`，缺席＝現行「只加不減」。一行就把 ③5 的方向差補成可選項，不動 PROTOCOL 現行語意。

8. **兩份帳本別混**：`tools.json`（有哪些程序、怎麼呼叫、行為契約）與未來的 LLM 准入紀錄（哪個模型獲准在哪個洞、憑什麼、何時撤照）是兩件事（codex sol 觀察 E1）。現在只做前者，但欄位名先對齊，之後證書就是 `nondeterministic` 那個物件。

## ⑤ 值得直接抄的檔案

| 路徑（ai_core 相對） | 抄什麼、為什麼 |
|---|---|
| `workflows/spec/lib_spec/register-intercept-lifecycle-state.md` | `--metadata` 的攔截規則（`prog --metadata`／`prog <sub> --metadata`、純 JSON、宣告不執行）＋ `lifecycle`／`state` 的值與預設——aos 子命令的自述協定直接照抄 |
| `workflows/spec/lib_spec/s1-io-entries.md` | `entries` 的 `able_in/able_out/mode/type/format/schema/terminal_binding`——aos 現在只記事後的 stdout 文字，這是唯一一份「執行前就知道 I/O 長什麼樣」的可機讀格式，也是 agent 讀工具結果的 schema 來源 |
| `workflows/spec/lib_spec/s6-guarantee.md` | `guarantee: none/idempotent/transactional`＋`dry_run`——loop 崩潰後能不能自動重跑，只靠這一欄 |
| `workflows/spec/lib_spec/s9-nondeterminism-composition-env.md` | 第九軸與 `reliability`；**同時**抄它拒絕把組合／環境／memoize 塞進 metadata 的理由——aos 登記表最容易長歪的方向就是這三個 |
| `workflows/spec/cli_spec.md` §2.0 | CLI＝Lisp 呼叫；讓 `{args}` 模板之後能升級成 positionals＋flags 的結構化 args，而不是一整串字串 |
| `docs/kb/kb-ss/doc_11_arch_protocol.md` | 四條硬規則（JSON object、UTF-8、`--metadata` 前只准 positional）＋推薦欄位 `summary/usage/examples/errors{retriable}`＋`--json-errors`＋容錯（absent 照列）——比 spec 更貼「任意程式」的現實 |
| `docs/kb/kb-ss/doc_13_arch_hub.md` | Hub 的掃描策略與匯出格式表——`aos tool list/export` 的功能規格幾乎現成 |
| `docs/kb/kb-ext/ext_04_interoperability_mcp.md` §2 | ai_core 欄位→MCP tool 欄位映射表——`aos tool export` 的對照表直接用 |
| `workflows/roadmap/s3-endgame-governance.md` §3.2–3.4 | 不是抄格式，是抄**尺**：「LLM 是 `default:` 分支」「舉證責任在讓 LLM 進來那邊」——aos 每次想給 agent 加能力前拿它量一次 |
| `workflows/spec/composite_spec/state-dir-convention.md` | `.config/.cache/.state/.data/<name>` 四目錄語意與可刪性——給 stateful 工具一個不跟 `.aos/` 打架的家 |
| `docs/kb/kb-ext/ext_07_observability_and_provenance.md` | `trace_id/parent_id/event/context.model/metadata_snapshot` 的最小 trace 事件——aos 的 `out/<id>.json` 加兩個欄位就等價 |
| `docs/kb/kb-ss/doc_21_composition_dimension.md` §4 | Blackboard 模型（輪流讀寫共享狀態＋max rounds）——這就是 aos 回合制資料夾世界的前身，`--step N` 正是 max rounds；拿它來寫 aos 的自我定位一段 |

**不建議抄**：`composite_spec/interruption-recovery.md`（工具級 `recovery.json`——aos 的恢復該在 loop 層而非每個工具，先別兩邊都做）、`ideas/crystallization_engine_blueprint/`（未開工的未來）、`resources` 的細欄位（沒有排程器之前是裝飾）。
