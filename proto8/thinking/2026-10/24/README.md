# proto8 討論紀錄：2026-10-24

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-24 fsm 格的 exec 能不能相對於這格](exec-relative/README.md) | `AOS_CO` 是每跳重設的入口位置、指示詞不內插，拼不出「相對於這格」；loop／fsm／daemon 的 `exec` 可直接放單子物件、行程內跑（使用者「不過exec本來就應該要可以直接放內嵌單子吧」「好，就這樣做」），demo 全改內嵌；審後照建議：跑單子前相對的 `AOS_WS`／`AOS_STACK` 轉絕對、捷徑設定檔走實際的資料夾、daemon SIGKILL 連子 loop 底下的單子一起收、認領跳過 `.` 開頭的暫存檔 |
| [2026-10-24 agent 當工具給 agent 叫](agent-as-tool.md) | demo/agent-eve：腦只有一個工具 pyfix，pyfix 的 `_entry` 把 task 轉成子 agent（agent-dan 範本、專修 Python）的一道題、回報告＋實際 diff；代定：轉接寫在工具自己的 `_entry`、每次新小格不帶記憶、`--dotenv-override` 讓子 agent 用自己的模型；未決：子 agent 要不要接著聊、要不要用更強的模型 |
| [2026-10-24 給人用的 say／listen](say-listen/README.md) | 三支 `aos-say`／`aos-listen`／`aos-chat`：對工作區（`--ws`）不對 agent 資料夾、題名＝UTC ISO 8601 基本格式、看 /proc 判斷有沒有人在跑、chat 給了 agent 就替你跑、常駐用 aos-loop 包；連問接同一段 history；未決：只用假腦跑過 |
| [2026-10-24 仿 pi coding agent 的基本工具組](pi-tools/README.md) | 照 pi 只做 read、bash、edit、write 四個工具（demo/pi-tools）與 demo/agent-pip（工具出的問題回給腦）；資料夾與檔案的工具另做 file-tools（ls、stat、view、json_edit、mkdir、move、copy、trash，輸出一律 JSON、刪除＝搬進 .trash）；現收進 lib/base（見工具＝函式庫） |
| [2026-10-24 claude／codex CLI 當工具、人可以接進去](cli-tools/README.md) | demo/agent-fay：工具 claude、codex 共用一段對話；平常走非互動續對話，人用 `attach` 開 tmux 互動畫面、跳出後畫面留著、agent 改從畫面送字；保守權限；未決：兩家有穩定的背景 session 機制時改走 CLI 自家的 |
| [2026-10-24 `_metainfo`：函數的特性](metainfo/README.md) | 三處同名（資料夾 `_metainfo` 檔、JSON 物件與單子的 key）、走找入口同一條路取第一份、通用 key 全選填（數量寫數字或 `{val, max}`）、`time_ms` 是宣告、`timeout_ms` 才強制、`priority` 不進、實測寫 kernel 自己的 stack、寫壞當沒寫；附 LLM kernel 接法；條文待頂層統一落 |
| [2026-10-24 給 AI 用的 aos 工具集](ai-tools/README.md) | proto8/ai_tools：命令列 `aos-ai`（每次一行 JSON，只寫 root 底下、不刪東西）、Claude Code skill（也是 plugin）、agent-dan 可掛的 spawn_agent／ask_agent／agent_status；`aos-ai make` 生成 JSON 與骨架、概念速成 concepts.md＋`aos-ai explain`；未決：MCP server、有題才叫、子 agent 放哪等選項 |
| [2026-10-24 記憶庫：在記憶庫裡存放各類東西](memory.md) | demo/agent-meg：記憶庫＝`$AOS_HEAP`（預設 `$AOS_WS/.heap/`，指同一個＝共用）、六類（prefs、facts、outcomes、gotchas、snippets、skills）各一份 wf-table 索引＋一筆一 md、forget 搬 archive；一個工具 `memory`（save／search／read／forget）；每題把偏好＋有關的幾筆接在 system 後（不進 history） |
| [2026-10-24 agent 之間寄信](agent-talk/README.md) | demo/talk：member＋工具 send_message／check_inbox、team 用 aos-daemon 跑；地址＝對方工作區、信＝`new/<id>.json` 一到就是題目、要回答的信自動寄回（自動回信不再回）、`max_hops`／`max_sends` 擋迴圈；未決：自動寄回還是模型自己寄、整串總封數、信箱跟 LLM kernel 統一、名冊生出 `loops` |
| [2026-10-24 函數成長：太大或特性到了就長成資料夾](fn-grow/README.md) | 函數六級（0 內嵌、1 同檔具名、2 單檔 `x.json`、3 資料夾只有 `_entry`、4 不只入口、5 有子函數），第 2 級起呼叫方只寫 `"x"`、長大不改呼叫方，門檻沿用 STRUCTURE 加被幾處叫／伴隨檔／`_metainfo` 特性；搬的時候只改 `cwd`、`$ref`、`$env AOS_CD`；原型 aos-grow（`up`／`down`、`--dry-run`、`--take`）；條文待頂層統一落 |
| [2026-10-24 小念頭：先規劃 steps、每步 fork、只帶結論](thoughts/README.md) | demo/agent-gus（idle → plan → fork → think → act）：腦回 `{context, steps}`、fork＝再跑一次自己、needs 齊了就起、結論一步一則接進 history；小念頭能再拆（深度與額度往下帶）；給摘要不複製 history、小念頭失敗回給母體的腦；`thought.json` 給別的程式一步進、結論出 |
| [2026-10-24 Janet 編成 aos](janet-compile.md) | `aos-janet` 把普通 Janet 原始檔（`(def program (dir …))`）編成資料夾＋JSON＋短腳本；函數＝範本、巨集只用在 fsm 狀態名與 janet-main；`(dir …)`＝長成同層子資料夾；seq／par／if 編成 shell 入口；入口用 argv 陣列不用 sh；未決：反編譯、組合子改用 fsm、單子太大自動長成檔、jpm 套件 |
| [2026-10-24 改 JSON 的工具集（aos-json）](aos-json.md) | impls 的 aos-json（get／peek 漸進展開／where 追 `$ref`／set／batch／del／append／merge／env／ref --move／check；`--follow`、`--check`、原子寫入）與給腦的 `tools/json`、`tools/json_edit`（兩步：找 key → 提供值）；代定可翻案 |
| [2026-10-24 Lua 寫 aos、接進 nvim](lua-nvim/README.md) | langs/lua（`aos.lua` 建構子、寫的當下查形狀、`aos-lua build／json／ls`）與 editors/nvim（`:AosExec[!]`、`:AosTrace`、`:AosSay[!]`、`:AosGoto`、`:AosLuaPreview`、`:AosLuaBuild`，叫外部程式、結果放下方視窗）；未決：Fennel、aos-lua 要不要進 aos-exec 的入口 |
| [2026-10-24 按意圖組 context（agent-kai）](intent-context/README.md) | demo/agent-kai：history.jsonl 照存，問腦時另組工作 context（system＋對話目錄＋挑出來的舊題只帶問題與結論＋這題完整訊息）；程式照字面挑＋腦用 recall 工具漸進展開、不做摘要；未決：只靠程式、只靠腦、先問小模型、寫摘要、prompt cache 等選項 |
| [2026-10-24 自我改進流程](self-improve/README.md) | demo/self-improve：aos-loop＋fsm 三格 run → judge → improve；判準是例子或檢查程式、改進者＝另一隻 agent（看不到判準、不給 bash）、每一版拍在 `versions/vNNN/`、新版從最好那版改、預算 rounds／elapsed_ms／tokens；未決：只用假腦跑過 |
| [2026-10-24 LLM kernel 第一版](llm-kernel/README.md) | impls 的 aos-gate（單子寄進 `$AOS_KERNEL` 信箱、等回信、原樣交回）與 aos-kernel-llm（被 loop／daemon 一次次拍：收拾、排隊〔級數＋aging → deadline → `_metainfo.time_ms` 短的先 → 等得久 → 先寄〕、`slots` 封一起跑、回信、`served.jsonl`）；寄的人在不在看 `sender.lock`；token 回報走 `AOS_KERNEL_REPORT`、額度認次數與 token；agent 範本不改、走 kernel 的版本在 demo/kernel-llm；未決：`llm_tokens` 要擋時拿 `val` 還是 `max` |
| [2026-10-24 工具＝函式庫](tool-lib/README.md) | agent＝函數、工具＝外部函數，函式庫收成一份被引用；三層 `lib/base`（原語）→ `lib/aos` → `lib/agent`；一個工具＝`_entry`＋`tool.json`＋`_metainfo`，契約（stdin JSON、stdout 結果、錯一律退 1 且 stdout 同一行、沙盒只認 `$AOS_WS`…）；引用＝一條相對捷徑一個工具；各處工具已遷進 lib；agent-gus 的小念頭不搬（10-25） |
| [2026-10-24 土法 compact（agent-hal）](compact/README.md) | demo/agent-hal（idle → compact → think → act）與資料夾程式 compact/：history 超過門檻才壓，① 每則工具呼叫各一句 ② 逐段摘要＋挑幾行原樣保留 ③ 修成一份；新 history＝摘要＋最近 2 題原樣；原檔輪替進 `compact/<run>/`；未決：跟 P-41「只附加」的衝突（現用輪替，要使用者看）與幾個選項 |
| [2026-10-24 Linux 權限與沙箱（aos-sandbox）](sandbox/README.md) | `aos-sandbox 設定檔 prog...`（chain-loading）：身分 s6-setuidgid＋命名空間 bwrap、上限 s6-softlimit，接在叫的那一方 argv 最前面、aos-exec 不改；強制只在 argv、宣告放 `_metainfo` 的 `sandbox`；設定白名單（net、env 預設不給）；self-improve 預設就關；要 root 的寫成 setup.sh（預設乾跑）；存取控制純靠 Linux（S17）；未決：kernel 照信跑單子會跳出沙箱（S18 `accept` 暫留），三條路待選 |
