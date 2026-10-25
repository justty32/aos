# galtxt-b 第 1 輪：只拆頂層（乙隊規劃者 fable，2026-10-25）

← [galtxt-b](../README.md)｜題目與使用者原文：[thinking 2026-10-25 top-down](../../../thinking/2026-10-25-top-down.md)｜依據：CONCEPTS（C-13 九軸、C-22 能寫死的節點換成程式、C-25、C-46、C-52、C-53、C-56、C-61、C-65～C-67）、NORMS（N-36、N-38、N-43、N-50、N-53、N-55、N-57～N-62）、CONVENTION（P-05～P-41）、[`_metainfo` M1～M10](../../../thinking/2026-10-24-metainfo.md)、[函數成長六級](../../../thinking/2026-10-24-fn-grow.md)、[工具＝函式庫](../../../thinking/2026-10-24-tool-lib.md)｜素材（只讀）：`~/repo/ai_core/sub_projs/galtxt`（corpus/評測、人物、固化、世界）與 idea 礦脈的固化階梯、雙錨驗證、評分級聯

這份是原型資料（留給使用者評拆法），不受 thinking「只留結論」的限制；AI 的分析與理由都寫在這裡。

## 1. 題目怎麼理解、極小範圍是什麼

**題目**：用 aos 體系寫一支程式，「場景條件（人物、地點、事件、風格／意圖）→ 一場 galgame 台詞」。galtxt 那邊的想法是三件事（idea 礦脈 §二、§四）：**固化階梯**（能用查表、規則、模板算掉的先算掉，LLM 只填真正要創意的洞）、**雙錨驗證**（程式護欄＋語料錨是下限，人是精修）、**評分級聯**（Tier 0 確定性護欄免費→Tier 1 語料統計→Tier 2 LLM judge→Tier 3 人抽查，便宜的先跑、短路早退）。所以這支程式的骨架其實就是評分級聯本身：**寫一稿 → 便宜的檢核 → 貴的打分**，護欄與打分能用純程式的就用純程式（使用者原話），寫稿與「要讀懂才判得動」的那段問腦。

**極小範圍**（使用者 10-25「這是一個龐大的目標，我會建議先從極小需求開始」）：

- **一處地點**：河鹿堂（corpus 裡設定最厚的一個點：店誌、梅花章、進新書日、耳背爺爺）。
- **兩個人物**：主角（佐伯悠）、森下晴子（文靜書卷、河鹿堂常客、愛《銀河鐵道之夜》）。兩人都有 `corpus/人物/` 的 dossier。
- **一個小事件**：兩人同時伸手拿同一本《銀河鐵道之夜》，晴子讓書、留下「想聽你讀後感」的鉤子。稱謂階固定在 1（她叫「主角同學」，他叫「森下」），一場戲不升階、不告白。
- **輸出**：5～10 句台詞（可加少量旁白），用 corpus 的格式：`【標題】`、`（旁白）`獨立一行、`名：「台詞」`一行一句。
- **腦**：LiteLLM `http://localhost:4000/v1`、`chatgpt-gpt-6-luna-low`（寫在各 agent 的 `.env`，不蓋外面）；`AOS_BRAIN_URL` 沒設＝假腦，測試不碰網路。

**輸入長什麼樣**（`$AOS_WS/new/<題名>.json`；完整範例在 [examples/q01_河鹿堂讓書.json](../examples/q01_河鹿堂讓書.json)）：

```json
{"summary": "四月午後的河鹿堂，兩人同時伸手拿同一本《銀河鐵道之夜》；晴子讓書，留下「想聽你讀後感」的鉤子",
 "place": "河鹿堂", "season": "四月", "time": "午後",
 "cast": ["主角", "森下晴子"], "relation_level": 1,
 "event": "兩人的手同時搭上同一本《銀河鐵道之夜》……本場不升階、不告白。",
 "intent": "靜",
 "must_mention": [["銀河鐵道之夜", "宮澤賢治"], ["讓給", "先看"]],
 "nice_to_mention": ["梅花章"],
 "lines": {"min": 5, "max": 10}, "max_redrafts": 2,
 "benchmark": "q01"}
```

`must_mention` 每組擇一命中（這是 benchmark 的「護欄關鍵詞」，由出題的人抄進場景，writer 看得到、check 也用同一份——生成的約束與檢核的約束來自同一個源，雙錨才對得起來）。`benchmark` 只給 judge 看：正解不進 writer 的 prompt。

**輸出長什麼樣**（`$AOS_WS/out/<題名>/`）：`answer.txt`（稿子）、`score.json`（三層分）、`check.json`（每一稿的違規清單＝固化的礦：✗ 的理由）。真腦跑 q01 的實際產出（第一稿就過，5.5 秒，6/6）：

```
【四月午後・河鹿堂】
（推開卡卡的木門，門鈴響了一聲。舊紙的味道裡，木百葉窗把書架的陰影拉得很長。）
（左牆的書架前，兩人的手同時搭上同一本《銀河鐵道之夜》。）
主角：「森下同學，妳先請。」
森下晴子：「……佐伯同學不是也在找這本嗎？」
主角：「是是，只是一本舊書。妳先看也沒差。」
（晴子沿著書背滑下一遍，才把手收回。）
森下晴子：「那……這本讓給佐伯同學吧。我下次再來。」
主角：「那我就不客氣了。梅花章也還在呢。」
森下晴子：「嗯……我更想知道，佐伯同學讀完之後會怎麼想。」
（沒有人再說話。百葉窗的光一點一點退回去，把這個午後輕輕收了起來。）
```

**用哪兩題 benchmark、怎麼當評分依據**：`corpus/評測` 是「挖空一句」題，19 題裡只有 Q01（河鹿堂讓書，四月）與 Q08（河鹿堂進新書日，梅雨）同時滿足「兩人都有 dossier、同一地點、護欄型（有可程式驗的關鍵詞）」——所以極小版用這兩題，**換季節與事件不換樹**。用法：

| 層 | 誰算 | 分 | 從 benchmark 拿什麼 |
|---|---|---|---|
| 護欄命中 | `check/`（純程式，Tier 0） | 0／1 | 題目的「護欄關鍵詞」抄成場景的 `must_mention`；禁語、地點穿幫、格式也在這層 |
| 語域相符 | `check/`（純程式，Tier 1） | 0～2 | 稱謂階（02 表）、感嘆號／口頭禪預算、句長（01 表＋定點 04 的句型預算） |
| 語意契合 | `judge/`（LLM，Tier 2） | 0～3 | 把題目的 context、挖空對白、正解、評分要點 (a)(b)(c) 給 critic，問「這稿完成同樣的戲劇動作了嗎、油不油」 |

總分 0～6。critic 另外也給一個它看到的語域分 `register_by_judge`，只拿來跟程式算的對照（`register_agree`）：兩邊不合就是「規則表漏了什麼、或 judge 偏了」的訊號，這是雙錨落在程式裡的樣子。評測 README 說的「蓋住正解」照做：正解只在 `judge/benchmarks/`。

**什麼叫「跑出來了」**：`aos-exec --ws ws galtxt-b` 結束碼 0；`out/<題名>/answer.txt` 存在且 `check.json` 的 Tier 0 全過；`score.json` 有三層分。假腦要能跑完同一條路（含「打回重寫」那條）；真腦跑 Q01、Q08 各一次看分數。

## 2. 頂層切成哪幾塊、為什麼

一圈六格，`fsm.json` 固定順序 `idle → brief → draft → check → judge → deliver → idle`：

| 格 | 純程式／agent | 做什麼 | 讀 | 寫 | 為什麼獨立成一塊 |
|---|---|---|---|---|---|
| `idle/` | 純程式（sh） | 工作區還有題就 0，沒有就 10 | `$AOS_WS/{cur,new}/*.json` | — | 範本的標準形（P-08）：終止條件只有它知道 |
| `brief/` | 純程式（python）＋`tables/` | 認領場景、查表編成**稿紙** `brief.json`：人物卡、稱謂階、地點硬設定、禁語、開場收尾句 | 場景、`tables/*.json` | `$AOS_STACK/brief.json`、`current.txt`、`cur/` | 這就是固化階梯的 1～3 級（查表、規則分支、模板）落成一個執行期零 LLM 的節點；它編出來的稿紙**同時餵 writer 與 check**——「真源＝規則，表＝快取」（固化 README 終點形態）的具體形狀 |
| `draft/` | 黏合（python）→ `tools/writer/` **agent** | 把稿紙（第 2 稿起附打回理由）放進 writer 的小格工作區、叫它、收成 `draft.json` | `brief.json`、`check.json` | `draft.json`、`$AOS_STACK/writer/` | 貴而不確定的節點單獨一塊，`_metainfo` 才估得準；黏合跟 agent 分開是 agent-bob「格＝黏合、agent＝格底下的工具」的形（P-25、P-33） |
| `check/` | 純程式（python） | Tier 0（格式、關鍵詞、禁語 A/B/C、地點穿幫）＋Tier 1（稱謂階、感嘆號、口頭禪、句長）→ `check.json`，**判定是資料不是錯，永遠退 0** | `brief.json`、`draft.json` | `check.json`（含每稿 history） | 使用者要「護欄能用純程式就用純程式」；它免費、確定性，所以放在貴的 judge 前面短路（評分級聯）；違規理由是中文，原樣回給 writer 當打回理由（礦） |
| `judge/` | 黏合（python）→ `tools/critic/` **agent** | 定稿後把稿子＋`benchmarks/<id>.json` 正解交給 critic，合成 `score.json` | `check.json`、`brief.json`、`draft.json`、`benchmarks/` | `score.json`、`$AOS_STACK/critic/` | Tier 2 要讀懂才判得動，只能 LLM；跟 writer 分開是因為「寫的人不打自己的分」，而且它只在定稿後跑一次（省 token） |
| `deliver/` | 純程式（python） | 寫 `out/<題名>/`、題目 `cur/→done/`、清掉這題在 stack 的檔 | `score.json`、`draft.json`… | `out/`、`done/` | 能寫死的搬檔步驟放程式格（P-24）；薄，預期被收攏（§6） |

**為什麼是「固定一圈、每格自己判要不要做事」而不是條件分支**：aos-fsm 刻意沒有條件轉移（N-36 只有 `exec`＋`next`；格退非 0＝整隻停下等人，P-20）。「check 打回 → 再寫一稿」是這題的核心迴圈，但它不是錯誤、是正常路徑，不能拿結束碼表示。agent-dan 的做法給了答案：fsm 永遠是固定的圈，**要不要做、做第幾次寫在 stack 的檔裡**（有沒有 `brief.json`、`check.json` 的 `pass`／`final`、`draft.json` 的 `attempt`），每一格看檔決定「這是不是我的回合」，不是就退 0 什麼都不做；idle 看工作區決定整個什麼時候停。好處：fsm 表一眼看完、trace 一格一行、任何一格失敗停下來人修好再 `aos-exec` 就從那格接著做（P-20）；重寫幾次由 loop 的 `max` 與場景的 `max_redrafts` 管，agent 自己不數連錯（N-53）。代價：打回那一圈 judge、deliver 各跑一次空的（各幾十毫秒），trace 裡看得到。

**資料怎麼在塊之間傳**：全走 `$AOS_STACK` 的檔（P-10，不走 stdout）：`current.txt → brief.json → draft.json → check.json → score.json`，一題一組，deliver 收尾時刪掉。工作區只放交辦與成果（`new/ cur/ done/ out/`，C-65、P-14）。叫子 agent 照 P-17／P-32：小格 `$AOS_STACK/writer/`、它的工作區 `$AOS_STACK/writer/ws/`（題目放 `new/<第幾稿>.json`、答案收 `out/<第幾稿>.txt`）；critic 同樣 `$AOS_STACK/critic/`。所以 stack 樹就是呼叫樹（P-38）：`.stack/{writer/ws/…, critic/ws/…, trace.jsonl}`。

**兩隻 agent 都照 agent-dan 範本**（`_entry`→`aos-loop loop.json`→`fsm.json` 三態 idle／think／act，`brain.py`、`act.py`、`system.txt`、`.env`）。改的只有：題目是 JSON 不是純文字（`brain.py` 的 `render`）、答案叫 `out/<n>.txt`、假腦的內容。writer 第 1 輪沒有工具，但 `tools/*/tool.json` 那段照留，之後掛工具不用改程式。

**writer 為什麼要是一整隻 agent而不是一張 think 單子**：它有真正的續聊需求——第 2 稿接在第 1 稿與打回理由後面（同一個小格、history 自然累積，C-65「續聊＝同一個 stack 再跑」），而且下一輪會長出工具（自檢、翻語料）。critic 相反：單發、沒工具、每次清小格重來——它只是為了跟 writer 同一個形狀才做成 agent，`_metainfo` 已標 `shrink_candidate`（§6）。

## 3. 刻意不拆的

- **不做 `distill/`（從 corpus 蒸餾規則表的工廠期節點）**：`brief/tables/` 第 1 輪是手工抄的快取（兩個人、一個地點、幾十個禁詞）。蒸餾是離線、LLM 重、人審的工廠期工作（idea 礦脈 §三「批次固化」），不在執行期的樹上；極小版先證明「笨模型＋稿紙＋護欄」這條執行期管線能走，表的來源之後再接。
- **不做 overgenerate-and-rank（一次炸 N 稿、成本排序取優）**：galtxt 的終點形態，但極小版一稿＋打回重寫就夠跑通；N 稿是 draft 格裡的事（`tools/writer` 叫 N 次或 N 個小格），樹不用變。
- **不做 Tier 1 語料統計匹配（n-gram／用詞分布）**：需要先把 corpus 做成統計表；第 1 輪的 Tier 1 只做規則表能判的語域（稱謂階、預算）。
- **不做 Tier 3 人工抽查與 rating 工具**：那是人的介面，不在這支程式裡；`check.json` 的 history 與 `score.json` 的 reasons 已經是它要吃的礦的形狀。
- **不拆 brief 的查表為多個子格**（人物卡一格、稱謂一格…）：都是幾毫秒的純函數，拆了只多六個資料夾與六次 aos-exec；函數成長的觸發點（被 ≥2 處叫、有伴隨檔、要自己保管東西）一個都沒到。
- **不做跨場景的記憶（heap）、不做多題並行**：一個工作區一隻 agent、一次一題（P-12、P-18）。
- **不做 writer 的工具**（自檢、翻語料）：留到第 2 輪（§6）。
- **不碰 galtxt 那個 repo**：只抄需要的片段進 `tables/` 與 `benchmarks/`，標明出處。

## 4. 頂層黏合怎麼做

- `galtxt-b/_entry`＝`#!/bin/sh` ＋ `exec aos-loop loop.json`（P-05 的 shebang 小殼；沒有 `sh -c`）。
- `loop.json`＝`{"exec": "fsm.json", "max": 30}`：一圈六格；一題通常 1 圈、最多 1＋`max_redrafts` 圈；30 是這次呼叫的圈數上限（10 題的最壞情況），跑滿以 0 結束、題目留在 `cur/`。
- `fsm.json`（自帶 `_entry: ["aos-fsm", {"$env": "AOS_CF"}]`）：四格是資料夾目標（`"idle"`、`"brief"`、`"check"`、`"deliver"`），兩格是內嵌單子 `{"argv": ["aos-exec", "draft"], "timeout_ms": 600000}`、`{"argv": ["aos-exec", "judge"], "timeout_ms": 300000}`——只有會卡在腦上的格要逾時，照 P-22 寫成單子、由 fsm 行程內當監工收整群（10-24 起 `exec` 可直接放單子）。逾時數字：外層 ≥ 內層一圈各格逾時之和×內層 `max`（P-36）：writer 的 think 180 秒＋act 30 秒，loop `max` 6 → 外層 600 秒夠。
- 黏合程式 `draft/_entry`、`judge/_entry` 各約 60 行 python：建小格工作區、寫題目、`subprocess.run(["aos-exec", "--ws", ws, "tools/writer"], env={AOS_STACK: 小格})`（argv 陣列、不經 sh）、讀答案、寫 stack。agent 的 stderr 不吞、不轉述（P-21）；它退非 0 就是黏合格自己 `WriterFailed` 退 1。
- 錯誤姿態（C-53）：每一格對上游的檔採「入口檢查」（缺或壞＝自己的錯一行退 1，代號照 C-54：`BriefMissing`、`DraftBad`、`CastUnknown`、`WriterFailed`、`ReplyBad`…）；對下游採「出口保證」（寫檔一律 `.暫存` 再改名，N-05）。check 的判定不是錯。
- 不動 PATH：`aos-exec`／`aos-loop`／`aos-fsm` 由呼叫者放進 PATH（`demo.sh` 示範，照 `tests/aos_bins.py`）。

## 5. 每個資料夾的 `_metainfo`

通用 key 照 10-24 規劃（M3：`summary`、`time_ms`、`resource`、`llm_calls`、`llm_tokens`、`lock`、`side_effect`、`idempotent`、`deterministic`、`interrupt`、`parallel`；數量類寫數字或 `{"val", "max"}`）。**加了幾個自訂 key，理由**：

| 自訂 key | 為什麼加 |
|---|---|
| `reads`／`writes` | 每格讀寫 stack／工作區哪些檔。之後對整棵樹做反向收攏時，「A 寫的只有 B 讀」就是「A、B 可併」的機械判準；也是一眼看出資料流的地方（九軸裡的 I/O 型態、碰外部檔案）。 |
| `llm_endpoint`、`llm_model` | 使用者原話：「需要消耗 token／endpoint 資源」。同一棵樹裡不同節點可能用不同端點／模型（寫稿用貴的、打分用便宜的），kernel 排隊與算錢要分得開。寫字面值不寫 `$env`（M 01 §5：特性是固定屬性，跟著環境變就不好比對）。 |
| `grow_level` | 函數成長六級（10-24）的現在級數；收攏時看哪些是第 4、5 級卻沒用到該級的理由。 |
| `tier` | 評分級聯的哪一層（領域 key，給人看）。 |
| `calls` | 黏合格叫了哪個工具；跟 `reads`／`writes` 一起就是呼叫圖。 |
| `shrink_candidate` | 預期會被反向收攏的，先標出來（§6）。 |
| `kind` | `data`（表、benchmark、範例）、`dir`（只裝工具的容器）——不是函數的資料夾也要有 `_metainfo`（使用者「每個資料夾」），用 R3 固定格 `kind` 標種類；函數不寫（預設）。 |
| `per_question` | 頂層：一題幾圈。 |

LLM 估計怎麼來的：writer 一次＝system 約 700 字＋稿紙約 1 300 字＋輸出約 300 字 ≈ 2 500 tokens，第 2、3 稿帶 history 到 7 000；critic 一次 ≈ 2 200（含正解與對白）；頂層一題典型 2 次（1 稿＋1 判）、最多 4 次（3 稿＋1 判）、tokens 典型 4 700、最多 25 000；時間典型 18 秒、上限 600 秒（實測真腦 q01 一題 5.5 秒、6/6）。

**頂層** `galtxt-b/_metainfo`：

```json
{"summary": "galtxt-b：工作區 new/<題名>.json 的場景（兩人、一地、一事、意圖）→ out/<題名>/answer.txt 一小段 galgame 台詞＋score.json；確定性護欄與打分用純程式，寫稿與語意分問腦",
 "time_ms": {"val": 18000, "max": 600000},
 "resource": ["llm", "cpu"],
 "llm_calls": {"val": 2, "max": 4},
 "llm_tokens": {"val": 4700, "max": 25000},
 "llm_endpoint": "http://localhost:4000/v1",
 "llm_model": "chatgpt-gpt-6-luna-low",
 "side_effect": true, "idempotent": false, "deterministic": false,
 "interrupt": "resumable", "parallel": true,
 "lock": [{"$env": "AOS_WS", "$prefix": "ws:"}],
 "reads": ["$AOS_WS/new/*.json", "$AOS_WS/cur/*.json"],
 "writes": ["$AOS_WS/cur/", "$AOS_WS/done/", "$AOS_WS/out/<題名>/{answer.txt,score.json,check.json}", "$AOS_STACK/*"],
 "grow_level": 5,
 "per_question": {"counter_cycles": {"val": 1, "max": 3}, "note": "一圈＝六格；check 打回就再一圈（最多 1＋max_redrafts 圈）；loop.json 的 max 30 是整次呼叫的圈數上限"}}
```

其餘每個資料夾的完整 JSON 直接看檔（都已建好）：

| 資料夾 | 一句 | 關鍵值 |
|---|---|---|
| [idle/](../idle/_metainfo) | 看工作區有沒有題 | cpu、5 ms、純函數、`parallel: true` |
| [brief/](../brief/_metainfo) | 查表編稿紙 | cpu+disk、60 ms、`idempotent: true`（已有 brief.json 就 no-op）、`deterministic: true`、`tier` 固化 1～3 級 |
| [brief/tables/](../brief/tables/_metainfo) | 規則表（資料） | `kind: data`、`source`、`refresh`（之後由 distill 重算） |
| [draft/](../draft/_metainfo) | 黏合→writer | llm+cpu、9.5 s／600 s、`llm_calls` 1、`llm_tokens` 2 500／7 000、`interrupt: resumable`、`calls: tools/writer`；llm 數字＝writer 的（M6 外層贏） |
| [draft/tools/writer/](../draft/tools/writer/_metainfo) | 寫稿 agent | 同上；`lock` 自己的 stack（同一小格不能同時兩份）；fsm.json 的 think／act 單子裡各有自己的 `_metainfo`（範例 3 的寫法） |
| [check/](../check/_metainfo) | 確定性檢核 | cpu、30 ms、`deterministic: true`、`tier` 0＋1、「判定是資料不是錯」 |
| [judge/](../judge/_metainfo) | 黏合→critic | llm+cpu、7.5 s／300 s、`llm_tokens` 2 200／4 500、`tier` 2 |
| [judge/benchmarks/](../judge/benchmarks/_metainfo) | 正解（資料） | `kind: data`，writer 看不到 |
| [judge/tools/critic/](../judge/tools/critic/_metainfo) | 打分 agent | 同 judge；`shrink_candidate` |
| [deliver/](../deliver/_metainfo) | 交件 | cpu+disk、20 ms、`idempotent: true`、`shrink_candidate` |
| [examples/](../examples/_metainfo)、[draft/tools/](../draft/tools/_metainfo)、[judge/tools/](../judge/tools/_metainfo) | 資料／容器 | `kind: data`／`dir` |

## 6. 下一輪往下拆哪幾塊、預期收攏哪些

**往下拆（方向）**：

1. **`draft/tools/writer/` 長工具**：`tools/check`（自檢：writer 交稿前自己跑一次確定性檢核，少一圈打回；同一個 check 函數被兩處叫＝函數成長「被 ≥2 處叫」，check 要長出 stdin→stdout 的工具介面與 `tool.json`）、`tools/corpus_peek`（翻定點語料當 few-shot，語料錨）。這一塊會變成「大量用到 agent 資料夾」的主場。
2. **`brief/` 往下**：`tables/` 從手抄變成 `distill/`（工廠期 agent，讀 corpus 蒸餾人物卡與禁語表、人審後入庫）的產物；brief 自己可能長出 `opener/`（開場收尾從查表升成小搜尋：定點 01 的 beat 文法）。這是整棵樹裡 LLM 最重、但只在離線跑的分支，`_metainfo` 要把它跟執行期分清楚。
3. **`check/` 往下**：Tier 1 加語料統計（n-gram 離群）、把定點 04 的句型預算做全；每條規則一個小函數、同一份表驅動——拆成子資料夾還是一張規則 JSON，看第 2 輪規則數量（≥10 條、互相獨立就拆成 `rules/<名>`）。
4. **`draft/` 的 overgenerate**：N 個小格各一稿、check 全跑、成本排序取優——樹不變，只是 draft 黏合格裡多一層迴圈。

**預期被反向收攏**：

- `judge/tools/critic/` → 縮回 `judge/` 裡的一張 think 單子（它單發、沒工具、不續聊；做成 agent 只是為了跟 writer 同形）。
- `deliver/` → 併進 judge 的尾巴或 idle 的頭（只有搬檔與清理，20 ms）。
- `draft/tools/` 與 `judge/tools/` 這兩層容器：若每個格永遠只有一個工具，`tools/<名>/` 的中間層就是「嵌套太深」的那種——但 P-25／P-33 的慣例是 `tools/<名>/`，要收攏得先問慣例要不要給「單工具格」開例外（§7）。
- `brief/tables/*.json` → 若表一直只有兩個人、一個地點，五份 JSON 可縮成一份 `tables.json`；反過來若要借檔案權限讓「只有 distill 能寫表、writer 只能讀」（C-64），就不縮、而且要分資料夾。
- `examples/` → 搬到 proto8/demo 或留，看第 2 輪。

## 7. 跟既有原則衝突、或原則推不出答案的（不自己拍板）

1. **fsm 沒有條件轉移 vs 這題核心是「打回重寫」迴圈**。我用「固定一圈、每格看 stack 的檔決定做不做」繞過去（§2），代價是打回那圈多跑兩個空格、每格都要寫「不是我的回合就退 0」這段。原則推不出「這是正解還是 tasks `if` 組合子（N-34 現無實作）該補上」——如果之後很多 agent 都長出這種條件迴圈，是要大家都寫 no-op 格，還是把 `if` 做出來？方向性問題。
2. **題目格式**：P-11 說題目是純文字一題一檔、P-13 需要附檔時升成資料夾（`prompt.txt`）。這裡題目是 JSON（場景條件天生是結構），我定成 `new/<題名>.json`、答案 `out/<題名>/`（資料夾，照 P-13），題名＝去掉 `.json` 的檔名。慣例說「一個 agent 認哪種形狀寫在它自己的說明」所以合規，但「JSON 題目」要不要進慣例當第三種形狀（純文字／資料夾／JSON），等使用者定。
3. **計數命名 `counter_*`（使用者 10-25 新規）vs `_metainfo` 通用 key `llm_calls`、`llm_tokens`（10-24 規劃的名字）**：照隊長指示，我新寫的計數欄位用 `counter_*`（`score.json` 的 `tier1.counter_violations`、頂層 `_metainfo` 的 `per_question.counter_cycles`），`_metainfo` 通用 key 照 10-24 原樣。兩套並存；`llm_calls`／`llm_tokens` 要不要改成 `counter_llm_calls`／`counter_llm_tokens`（或 `llm_counter_calls`，主題在前）等使用者定——改了 lib/、demo、kernel-llm 的讀法都要跟。另：`attempt`（第幾稿）我沒叫 `counter_*`，它是序號不是計數，比較像 R3 的 `seq`；要不要統一叫 `seq` 也一併看。
4. **`_metainfo` 的 `$env`**：M 01 §5 說少用，範例 2 的 `lock` 是「少數合理的用法」；我在頂層與 writer 的 `lock` 也用了 `$env`（`ws:` 與 `stack:` 前綴）。合不合「少數」，等規範落條文時看。
5. **不是函數的資料夾要不要 `_metainfo`**：使用者說「每個資料夾」，M1 只定義了函數的三處。我給資料與容器資料夾加了 `kind: data`／`dir` 的 `_metainfo`（只有 `summary`、`resource`、`side_effect`…幾格）；`kind` 是 R3 固定格，但「`kind` 用來分函數／資料／容器」是我代定的意思，可能跟之後 kernel 讀 `_metainfo` 的假設衝突（kernel 讀到 `kind: data` 的「函數」該怎麼辦——我的預期是忽略）。
6. **單工具格的 `tools/<名>/` 中間層**（§6）：P-25／P-33 的地址規則讓 `draft/tools/writer/` 必須有 `tools/` 這層；反向收攏想併掉它就撞慣例。要嘛接受這層永遠在（代價：每個黏合格多一層），要嘛給「這一格只有一個工具」開例外寫法（例 `draft/writer/`，格裡寫 `aos-exec writer`）——方向性問題。
7. **工具的錯回給腦 vs 黏合格停下**：lib/README 與 agent-dan 10-24 晚起「工具錯回給腦、不停」；這裡 writer 退非 0 時黏合格 `draft/` 直接停（`WriterFailed` 退 1、P-20 等人）。兩邊都合 C-52（停或回給腦由叫它的格決定），但樹裡於是有兩種姿態：腦叫的工具錯回給腦、格叫的工具錯就停。要不要統一，等使用者看過真腦的失敗案例再定。
8. **`check` 的 pass 門檻**（Tier 0 全過且 Tier 1 違規 ≤ 1）與 `max_redrafts` 預設 2：規則推不出數字，先寫死在 check 與場景 JSON；真腦跑幾十題後再調。
9. **`.env` 的 `AOS_BRAIN_MODEL` 預設不蓋外面已設的**（N-59 第 4 件）：使用者要求只用 gpt 系列；若外面的環境早就 export 了別的 `AOS_BRAIN_MODEL`，`.env` 擋不住，會跑到非 gpt 的模型。這是規範的既定行為，不是程式能改的；要嚴格就得在黏合格叫 agent 時明給（P-39「叫別人時明給」），我沒做，標出來。

## 跑過的驗證

- 假腦端到端：`sh proto8/topdown/galtxt-b/demo.sh <工作區>` 結束碼 0——q01 一圈六格、一稿過；q08 開 `GALTXT_FAKE_BAD_FIRST=1` 第 1 稿故意寫壞（叫錯名字、感嘆號、禁語、漏關鍵詞）→ check 記 3 條違規打回 → 第 2 圈 brief／judge／deliver 各 no-op、draft 重寫（writer 的 history 四則：稿紙→壞稿→打回理由→好稿）→ check 0 條 → judge → deliver。頂層 trace 20 行、每格一行；stack 樹 `.stack/{writer/ws, critic/ws}`。
- 真腦（LiteLLM `chatgpt-gpt-6-luna-low`）跑 q01 一次：5.5 秒、第一稿 Tier 0 全過、Tier 1 0 條、critic 語意 3、總分 6/6，稿子見 §1；程式算的語域分與 critic 給的一致（`register_agree: true`）。
- 沒跑：真腦 q08、多題連跑、check 的每條規則各餵一個應該被擋的輸入（「綠燈要證明能變紅」只做了假腦壞稿那一組：must_mention、banned_A、exclaim 三條紅過；address、line_length、catchphrase、place_canon、format、speaker 幾條還沒單獨證明會紅——第 2 輪補測試）。
