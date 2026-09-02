# tools — tool 登記表、表述、呼叫迴路、agent 通訊錄（規劃，2026-08-30）

← [ideas](../README.md)｜交接書 [proto-T-tools](../../dispatch/proto/done/proto-T-tools.md)｜采風合成 [synthesis](../ai-core-field/synthesis.md)

純規劃、未寫程式。使用者原話：「任何支持 POSIX 呼叫的程式都可以是 tool，要有一個檔案作為 tool 的登記列表，還有表述」；「子 agent 不登記、就是一份通訊錄」。

| 檔 | 內容 |
|---|---|
| [registry](registry.md) | 登記表住哪、欄位、來源優先序、`aos tool add` 行為、白名單、9 個真實程式的範例 JSON |
| [description](description.md) | 給模型看的一行、給機器看的 JSON 與匯出映射、argv list 呼叫格式與 tooljson 的界線 |
| [call-loop](call-loop.md) | 對照 `tools.cpp` 的差異清單、三回合往返、結構化錯誤、危險工具、pi 回填 `batch/`、多步工具鏈 |
| [contacts](contacts.md) | 通訊錄：名字→資料夾，欄位、誰維護、「寄信給 bob」是什麼、跟 llm pu 的關係 |

術語：ai_core 的 `nondeterministic` 軸一律改稱**可預期性**（結果是否符合人類預期，非同輸入同輸出）。
版控：靜態清單（`.aos/tools/`、`.aos/contacts.json`）進版控，動態狀態不進——同 heartbeat 規則。

## 要使用者拍板的清單

| # | 問題 | 選項 | 建議 | 代價 |
|---|---|---|---|---|
| 1 | 登記表住哪 | A 單檔 `.aos/tools.json`／B 一資料夾一 tool／C 一檔一 tool `.aos/tools/<name>.json`／D 維持 agent 層 | C | help／自述不原樣保存，要時另加 sidecar |
| 2 | 最少必填幾欄 | A 只 argv／B `name`＋`argv`＋`description`／C 再強制 schema | B | 參數型別只靠預設 |
| 3 | 欄位名跟 ai_core 九軸還是自創 | A 照 ai_core／B F3 的 `exec/model/meta` 分層、內部沿用 ai_core 詞 | B | 匯出時要一張映射表 |
| 4 | `args` 形狀 | A 維持 `{args}` 字串／B 一律 list／C 依登記 `list\|string\|none` | C | parser 與舊 `tools.json` 相容遷移 |
| 5 | 具名槽 `{param}` 要不要 | A 不做／B 有限單 token 替換／C schema 綁定編譯 | A（B 之後可加；C＝tooljson 失敗路） | A 表達力低 |
| 6 | 自述旗標 | A `--metadata`／B `--metainfo`／C 都探 | B，第三方要 opt-in 才試 A | 舊 ai_core 工具多一步 |
| 7 | LLM 類工具標記 | A 不強制／B 只強制 `predictability: low`／C 強制整組 meta | B | 粗粒度 |
| 8 | 給模型看的表述 | A 精簡文字行／B 一行 JSON／C 原生 tool calling | 先 A＋client 驗證，`aos llm --tools` 實測後升 C | A 模型可能寫錯字串 |
| 9 | 三回合往返 | A 不壓／B step 內同步 fork／C loop 同回合尾巴批／D 現況 | A／D；痛了再 C | C 破壞「一回合一批」 |
| 10 | 錯誤退回與危險工具 | 拼文字／固定 JSON `tool` 訊息；不管／`confirm: true` 問人／白名單即安全 | 固定 JSON；安全先不管，交非開發者用時再加 confirm | 多一個 schema；初期安全在啟動 loop 的人 |
| 11 | pi 繞過 inst | A 事件回填 `batch/<turn>/out/`、標 `origin: pi`／B 收窄成 `aos_deliver` 走 inbox／C 接受洞 | A | 帳本是觀測紀錄不可重播 |
| 12 | 通訊錄住哪、誰維護 | 住：世界層 `.aos/contacts.json`／每 agent／Markdown／不存檔掃目錄；維護：init 自動／人手／`aos contact add` | 世界層＋`aos contact add`，`agent init` 不碰 | 快取會過期 |

## 使用者裁決（2026-08-30）

| # | 裁決 |
|---|---|
| 1 | **一檔一 tool** `.aos/tools/<name>.json`；膨大後照 wf 的方式拆，**現在不考慮膨大** |
| 2 | 必填 `name`＋`argv`＋`description` |
| 3 | **欄位名照 ai_core 九軸原樣**（不用 exec/model/meta 分層） |
| 4 | `args` 依登記 `list\|string\|none` |
| 5 | 不做具名槽 |
| 6 | 自述探 `--metainfo`；第三方 opt-in 才試 `--metadata` |
| 7 | LLM 類工具**不強制**標記（`predictability` 欄存在但由登記者填） |
| 8 | 給模型：精簡文字行＋client 驗證；實測後再升原生 tool calling |
| 9 | 三回合往返不壓 |
| 10 | 錯誤以固定 JSON tool 訊息退回；安全先不管 |
| 11 | pi 繞過 inst：先接受（另記在 dispatch/proto/done/proto-E-pi-cpu.md） |
| 12 | 通訊錄住世界層 `.aos/contacts.json`，`aos contact add` 手動維護，`agent init` 不碰 |
| 術語 | `nondeterministic` → **可預期性 `predictability`**：結果是否符合人類預期 |

實作交給 [dispatch/proto/proto-U-tools-impl](../../dispatch/proto/done/proto-U-tools-impl.md)。

## 實作註記（2026-08-30，隊 U）

12 條裁決已落地成程式碼，見 [dispatch/proto/reports/U](../../dispatch/proto/reports/U.md)。與規劃檔不同之處：

| 規劃檔寫的 | 實際做的 | 為什麼 |
|---|---|---|
| `registry.md` 範例用 `exec`／`model`／`meta` 三層 | 登記項是**扁平** JSON（`name`／`argv`／`description`／`args`…同一層） | 裁決 3「欄位名照 ai_core 九軸原樣」壓過 F3 的分層 |
| `contacts.md` 用 `{"contacts":[…]}` | `.aos/contacts.json` 頂層就是**陣列** | 交接書寫 `[{"name","folder"}]`，交接書是契約 |
| `aos tool` 併進 `core/agent` | 獨立成核心小專案 `core/tool`（`aos tool`／`aos contact`） | 登記表是**世界層**的東西，不該住在 agent 裡；agent 公開相依它 |
| `registry.md` 建議加 `probe` 子命令 | 只做 `add`／`ls`／`rm` | 最小原型；`add` 本來就會探測並印結果 |
