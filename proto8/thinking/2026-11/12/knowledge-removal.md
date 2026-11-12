# 拿掉 knowledge 工具、只給太大的出廠內容檔補 index：施工結果（11-12，公司 WSL）

← [11-12 日索引](README.md) ・ 前情：[11-12 index](index.md)（原話與 index 定義）、[11-12 json-tools](json-tools/README.md)（json 工具換新，同日先合）

## 使用者原文

- 「對了，關於knowlege這個工具，昨天說要改名回memory。我後來想想不用了，因為knowledge這個工具搞不好就直接沒了。」
- 「就是說，整個檔案系統+json，本來就可以作為agent的memory了，有需要啥就去讀啥，天然的分層。缺的是啥？」「description, index」
- 「knowledge沒用了，可以拿掉。」
- index 的定義（全文在 [index](index.md) 原話六、七）：「description和index是可以合起來的，或者說，本來就該合起來，統一叫_index.json/_index，也就是agent自己對這個節點的理解。格式就是{xxx:{description:...}, yyy:{...}}。」「放在天然位置的index，其實會是所謂的客觀index，而agent自己存的則是主觀。」「反正最基礎的就是這樣。後續什麼agent自己存、更新啥的，或是除了description外還要加啥，就後續再說」
- 頂層擬的範圍：「拿掉工具本身和開場『先查知識庫』的指示詞，出廠那批內容檔（`aos/*.json`）先留著當普通 json 檔」「root 收三種形狀不做了，跟著 knowledge 一起撤」；使用者答：「對，也可以順便給他們加上index。可以先做了吧」
- 拿掉後 agent 怎麼知道內容檔在哪：「4.不管。」
- 「對了，剛剛那套index，我這邊有些想法：agent的cache這個機制先不用做，反正我們就是訂下index是這樣，客觀index是這樣，agent自己要記錄自己的主觀的東西，就自己想想要放哪，我們不規定。cache這東西以後可能會做工具吧，但現在我們就不管。json檔案要不要加上_index，就是說，index我覺得有幾個主要用途，一個是agent可能會有自己的看法(cache)(或是agent們的通用看法，天然位置)，另一個是當節點下的某些東西太龐大了，所以用index給他做一個簡介。所以現有aos知識庫中，如果有些東西太大，那就補index.json/_index。如果夠小，那其實也不用做看法了，直接讀就是了。」

## 決定（已施工）

- **拿掉**：工具 `knowledge_read`／`knowledge_write`／`knowledge_export`／`knowledge_sync`、共用模組 `lib/agent/knowledge_fs.py`、檢查工具 `lib/aos/knowledge_check`、包 `lib/packs/knowledge.json`；工具夾設定檔 `_knowledge.json`、環境變數 `AOS_KNOWLEDGE`（aos-sandbox 的 ENV_BASE、cli_session 給 codex MCP 的環境清單）、代號 `KnowledgeMissing`／`KnowledgeBad`；brain.py 與 aos-mcp 的 `--knowledge`（開場叫工具把庫根塞進 system／MCP instructions 的整套）、eca 範本 `cli.json` 的 `tools_flags`、agent-fsm `fsm.json` think 格的旗標；`[aos] knowledge:` 這種 note；`aos/defs` 的分群欄 `knowledge`（review_round 一起）；假腦 `fake-demo-knowledge`。不留舊名、不做相容。
- **root 收三種形狀**（11-11 規劃、未施工）跟著 knowledge 一起撤。
- **agent 怎麼知道這批內容在哪：不管**（「4.不管。」）：指示詞、工具說明都不寫路徑；原本工具說明結尾的 `Details: knowledge_read aos/tools/….json.` 全刪。
- **範本工具數**：agent-fsm 45 支（十三包，含 json 包；json 包 11-12 加了 multi 兩支）、eca-claude 24 支（六包：gadgets、events、self、def、mailbox、json）、reviewer 11 支不變；`aos-tools --file templates/<名>/tools.json ls` 實數。
- **出廠內容檔**留在 `proto8/knowledge/`（夾名不改），當普通資料夾＋json 樹，內容沒刪。
- **cache、主觀 index 不做、不規定**。
- **客觀 index 只給太大的補**，格式 `{名: {"description": "英文一句"}}`，放天然位置（上一層）：
  - 資料夾 `_index.json` 留 3 份：`aos/`（20 個東西）、`aos/cli/`（22）、`aos/tools/`（35）；列出夾裡每個檔與子夾（自己除外），鍵不帶尾斜線。刪 6 份：`knowledge/`（4）、`docs/`（2）、`aos/agents/`（3）、`aos/errors/`（2）、`aos/me/`（7）、`aos/cli/parts/`（11）。
  - 檔內 `_index` 只留 `aos/packs.json`（16 個內容鍵）；其餘 51 份檔（含 main 同日新加的 json 節點）刪掉 `_index` 鍵（最大的 `aos/me.json` 拿掉後約 6.4 KB、9 個內容鍵）。沒有檔超過 8000 bytes。
  - 留著的都是 knowledge 時代那份表改成使用者格式（`_description`→`description`、去尾斜線），description 照現有內容。
  - agent 用一般讀檔／json 工具讀（沒有 index 專屬工具）；沒有 index 的夾或檔就是夠小，直接讀。

## 代定（可翻案）

1. **「太大」的門檻**：資料夾裡超過 15 個東西（`_index.json` 自己不算）才放 `_index.json`；一個 json 檔超過 8000 bytes（`json_get` 預設 `max_bytes`）或頂層內容鍵（不算 `_description`）超過 10 個才放 `_index`。放進檔內會弄壞讀它的程式時改放同夾 `_index.json`、鍵寫 `檔名#/鍵`（這批沒有這種情況）。寫在 `knowledge/README.md` 與 `docs/01`、`docs/02`。
2. 舊的 knowledge 專用表本來就叫 `_index.json`／`_index`（格是 `{"_description": …}`、資料夾鍵帶 `/`）：留著的直接改成使用者格式，沒有另開檔名。
3. 下列 knowledge 時代的格式原樣留著、不當 index：每夾的 `_description.json`（節點自己的正文，一個 JSON 字串）、json 檔頂層的 `_description` 正文鍵、`{"$ref": "…"}` 拆檔（`aos/me.json` 6 個、`aos/agents.json` 2 個、`aos/errors.json` 1 個）。留著的 `_index.json` 有一格介紹同夾的 `_description.json`。
4. 內容裡還在講已拆工具的段落原樣留著（`aos/_description.json` 最後一段、整份 `aos/knowledge.json`、`aos/packs.json#/knowledge`、`aos/errors/common.json#/knowledge`、`aos/rules.json`、`aos/world.json` 的 knowledge base 那列、`aos/body.json`、`aos/me/self_system.json`、`aos/me/self_tools.json#/add` 的例子、`aos/cli/mcp.json`、`aos/cli/sandbox.json`、`aos/cli/tool_env.json`）；`aos/_index.json` 那格照實寫 knowledge.json 描述的是已拆的工具。
5. `me`／`agents`／`errors` 三夾的說明改寫成「aos/me.json#/x points here with $ref」（原本靠 knowledge_read 跟 `$ref`）。
6. `knowledge/README.md`、`docs/01` 改寫成現況；`docs/02` 刪掉寫入、無鎖、出廠庫唯讀、暫存檔四段（都是 knowledge_write 的行為），留「節點怎麼寫」。
7. 條文：描述現況的事實句照改（N-63 hub 表、P-41 例子、附錄 3 對照兩列改寫成「11-12 拆掉」、附錄 4 刪 `_knowledge.json` 與 `<knowledge 根>/…` 兩列〔65 列：持久 45、暫時 20〕）；規範性內容加「11-12 註」待裁，不改寫（見下）。
8. 例子原本拿 `AOS_KNOWLEDGE` 示範的改成 `LANG=C.UTF-8`／`MY_DIR`（self_tools 錯誤訊息與說明、aos-tools 說明與測試、cmd/docs 01）；aos-feedback 的例子改 `lib/base/read`。

## 要使用者裁（已裁：兩件都刪，見下一節）

1. **條文加了 11-12 註、待裁要不要改**：CONCEPTS C-42（四處：落實 memory 工具與根進 system、知識庫便攜多隻共享、多庫假裝一庫、知識庫存什麼）、C-71（11-06 註：層級式記憶工具照這個做）、C-52（「其他一律」例子列了 knowledge_read）、CONVENTION **P-46「知識庫根進 system prompt」整條機制已拆，最該裁**（標題還在 CONVENTION 索引三處）、NORMS N-15（memory_write 寫入自動鎖的規劃）、N-17（knowledge_write 鎖用牆鐘的例外）。
2. 內容裡講已拆工具的段落（代定 4）要刪、改寫成普通 json 的讀法、還是留著當歷史。

## 使用者裁定與清理（11-12 下午）

使用者原文：

> 「知識庫有整理好了嗎？已經沒了的工具的相關段落也都刪掉了嗎？已經沒了的機制的條文(P-46)刪掉了嗎」

頂層解讀：上面兩件都刪。

### 決定

- 出廠內容裡講已拆工具（knowledge_*、`AOS_KNOWLEDGE`、`--knowledge`、知識庫根進 system）的節點、段落、檔都刪，對應的 index 項一起拿掉；現存工具的說明照現況改。代定 4 作廢。
- 條文：P-46 整條刪、編號留空不重排；其他條文裡講已拆 knowledge 機制的句子刪掉或改成現況，加的「11-12 註」一併拿掉。代定 7 的「規範性內容加註待裁」作廢。不留「原本是…」「已移除」之類的墓碑註記。
- 順手：已拆的 json_rewrite、json_read／json_write 在現行文件裡的「11-12 刪」註記也拿掉。

### 刪了哪些

- **內容檔**：整份刪 `aos/knowledge.json`；刪節點 `aos/packs.json#/knowledge`（含 `_index` 那格）、`aos/errors/common.json#/knowledge`（其碼 KnowledgeMissing／NodeMissing 等已沒有工具會報）、`aos/body.json#/system_history` 的開場知識庫根那段；刪段落 `aos/rules.json` 的 Knowledge 那條、`aos/world.json` 的 knowledge base 那列與環境變數裡的 `AOS_KNOWLEDGE`、`aos/cli/mcp.json` 的 `--knowledge`、`aos/cli/sandbox.json` 預設環境裡的 `AOS_KNOWLEDGE`。改成現況：`aos/_description.json` 最後一段（改成看同夾 `_index.json`）、`aos/packs.json#/about`（eca 七包是 gadgets、events、self、def、mailbox、json、index，25 支）、`aos/_index.json` 三格、`aos/me/self_tools.json#/add` 與 `aos/cli/tool_env.json` 的例子（`AOS_KNOWLEDGE` → `LANG=C.UTF-8`）、`aos/me/self_system.json`、`knowledge/README.md`、`docs/02`（「陣列只讀」是舊寫入工具的限制，拿掉）。index 對照：3 夾 `_index.json`＋`packs.json#/_index` 跟實際內容一致、沒有孤兒項、`$ref` 都接得到、沒有該補沒補的（`aos/` 剩 19 個東西、`packs.json` 16 個內容鍵，仍在門檻上）。
- **條文**：CONVENTION P-46 整份刪（`09-P-46.md`），CONVENTION 入口與 02 分檔表各刪一列、P-45 的「下一份」改「—」、05 刪「11-06 升為 P-46」那句、CONVENTION／NORMS 入口的範圍「P-05～P-46」改「P-05～P-45」；CONCEPTS C-42 刪「11-05 晚落實」memory 工具與根進 system 那句、刪「多庫假裝一庫」整項、「知識庫便攜」與 11-10 註刪 `AOS_MEMORY` 指法、「依託檔案系統」的「記憶工具」改「記憶」、「知識庫存什麼」刪 memory 讀 `#/` 的排程句，四個 11-12 註拿掉；C-71 刪「層級式記憶工具照這個做」與 11-12 註；C-52 與續（例外 ⑤）刪 memory／knowledge_read 例子與 json_rewrite 刪除註；CONCEPTS 附錄3 條號表 C-42 列刪「多庫與 memory_write」；NORMS N-15 刪「11-06 註／規劃中」整項（memory_write 寫入自動鎖）、N-17 刪 knowledge_write 鎖用牆鐘的例外句、N-63 刪 `AOS_MEMORY`／`AOS_KNOWLEDGE` 那半、待定之一刪 `json_rewrite`、附錄2 N-15 列刪 agent-knowledge 出處、附錄3 舊名對照刪 memory 工具與 `AOS_MEMORY` 兩列（現名都是「拆掉」）、附錄4 說明刪 knowledge 兩段改動紀錄；CONVENTION P-41 例子 `memory/add` 改 `notes/add`。
- **其他現行文件**：wf conventions、lib/docs/03、impls/aos-json README 與 docs/02 的 json_rewrite 刪除註；templates agent-fsm README、templates/docs/02 的「拿掉 knowledge 包」。

### 拿不準、沒動的

- CONCEPTS 附錄3 `02-各批出處.md`「11-06 lift-to-norms」那段還寫「P-45、P-46 見 CONVENTION」——是各批出處的歷史紀錄，沒改。
- `proto8/feedback/memory_write.jsonl`（agent 對舊工具的回饋紀錄）、`wf/tools/progress_board/designs.json`、`wf/HANDOFF.md`、`wf/inbox/done/` 裡的舊名：紀錄類，沒改。
- `knowledge/docs/02` 檔名「寫入與節點怎麼寫」的「寫入」是舊寫入工具留下的，改檔名會動到連結，沒改。

## 要重建什麼

- 舊定義或 stack 覆蓋層（`tools.json`）裡登記的 `knowledge_read`／`knowledge_write` 格、`_knowledge.json`、`.env` 裡的 `AOS_KNOWLEDGE` 刪掉即可（指的資料夾已不在，那格會 `PathMissing`）。範本的 agent 重建即可。
- eca 定義的 `cli.json` 若還寫 `"tools_flags": ["--knowledge", …]`，刪掉那行（aos-mcp 已不認 `--knowledge`＝`FlagUnknown`，MCP 起不來）；agent-fsm 定義的 `fsm.json` think 格同理拿掉 `--knowledge knowledge_read`。
- 讀 `proto8/knowledge/` 底下小夾 `_index.json` 或小檔 `_index` 的東西（目前 repo 裡沒有）改成直接 `ls`／讀檔。

## 驗證

- 測試（最後 rebase 到 `d7b08e809`〔json 第二輪、index-tools 圖紙〕之後；先前在 `47199075b`、`c79887c1b` 上各跑過一次，746 支、結果相同）：proto8 底下 49 個 `tests/` 夾各跑 `python3 -m unittest discover tests`，共 749 支，只紅既有 4 支（aos-agent `test_daemon_down` 2、box_check 2）；wf-lint broken 56（＝基準）；codemap 0 stale；`knowledge/README.md`、`docs/01` 的例子指令實跑過。
- 範本實數（`aos-tools --file templates/<名>/tools.json ls`，要 `AOS_HOME`）：agent-fsm 45、eca-claude 24、reviewer 11，都沒有 knowledge。
- 真腦（rebase 到 `47199075b` 之後、jsonx 改名之前跑的；eca 範本不掛 jsonx，工具清單不受改名影響；公司 WSL `/tmp/lk-1112b` 臨時樹＝範本 eca-claude 照抄、claude haiku、`aos-eca-turn` 直接跑一輪）：列 `mcp__aos__` 工具＝22 支（當時 json 包還沒有 multi 兩支）、沒有 knowledge；叫 `mcp__aos__json_get` 讀 `…/knowledge/aos/tools/_index.json#/read.json`，照實答出那格的 description。
