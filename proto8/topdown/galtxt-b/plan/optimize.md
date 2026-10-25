# galtxt-b 優化盤點：只看 `_metainfo` 表（第 3 輪 A，fable，2026-10-25）

← [galtxt-b](../README.md)｜輸入：**只有** [metainfo_table.md](metainfo_table.md)／[metainfo_table.json](metainfo_table.json)（表裡並了真腦兩題 q01、q08 的實測）；沒讀程式、沒看稿子。目的是試「使用者說的：`_metainfo` 是之後對整棵樹做優化的參考」——只拿表能判斷到哪裡。

引用寫法：〔列 `路徑`，欄 `key`，值〕；實測寫 `q01:值／q08:值`。

## 1. 錢與時間花在哪（表上的數字）

| 誰 | 實測 llm_tokens（q01／q08） | 佔整題 | 實測 time_ms（q01／q08） | 佔整題 | llm_calls |
|---|---|---|---|---|---|
| `.`（整題） | 17115／17379 | 100% | 14365／18150 | 100% | 4／4 |
| `draft` | 13498／13839 | 79%／80% | 12339／15049 | 86%／83% | 3／3 |
| ├ `draft/tools/director` | 3416／3447 | 20% | 5643／6446 | **39%／36%** | 1／1 |
| ├ `draft/tools/writer` | 10082／10392 | **59%／60%** | 6633／8538 | 46%／47% | **2／2** |
| │ └ `…/writer/fsm.json#/states/think/exec`（每次問腦） | 5041／5196 | — | 3230／4183 | — | 1 |
| `judge`＝`judge/tools/critic` | 3617／3540 | 21%／20% | 1936／3012 | 13%／17% | 1／1 |
| `brief`＋`check`＋`deliver` | 0 | 0 | 21＋45＋0／20＋44＋0 | **<0.5%** | 0 |

三件事一眼看得出：

1. **writer 一題問兩次腦、吃掉六成 token**。`writer` 的 `llm_calls` 宣告 `1/3`、實測 `2/2`；每次問腦 `think/exec` 實測 5041／5196 tokens，兩次相加就是 10082／10392。兩題都是 2 次，不是偶發——表上 `.` 的 `per_question.note` 寫著「writer 每稿 1～3（自檢）」，所以那第二次就是自檢（腦先叫 lint、拿結果再交稿）。兩次問腦之間 history 整段重送，第二次至少跟第一次一樣大。
2. **director 一次問腦佔三到四成時間**：`director` 5643／6446 ms，其中 `think/exec` 5572／6375——幾乎全在等腦；它的 token（3416）跟 critic（3617）差不多，但時間是 critic 的三倍（1903／2978）。同一個模型、同一個端點（兩列 `llm_model`、`llm_endpoint` 相同），差在輸出長度：director 要吐一張 JSON 表，critic 只吐一行分數。
3. **純程式那三格免費**：brief 21、check 45、deliver 0 ms，加起來不到整題的 0.5%。表上 `deterministic: true` 的列全部都在這個量級——任何「併格省時間」的改動在時間上都量不出來，只有結構意義。

## 2. 哪裡不確定

`deterministic: false` 的列只有五個：`.`、`draft`、`director`、`writer`、`judge`（含它們底下的 `critic` 與三個 think 單子）。不確定全部來自三個問腦點，而且是**串起來的**：director 的表決定 writer 寫什麼，writer 的稿決定 critic 給幾分。表上看不到分數（見 §5 缺口 5），所以「director 多這一步有沒有讓稿子變好」在表上無從判斷——這是要看程式與產出才答得了的（§6）。

## 3. 怎麼優化（按預期收益排）

### 第 1 名：director 換成純程式（或先程式、不行才問腦）

- **依據**：`director` 列——`deterministic: false`、`llm_tokens` 3416／3447（20%）、`time_ms` 5643／6446（**39%／36%**，整棵樹最貴的一段時間）；它的 `summary` 說輸出是「beat 表 JSON（每拍誰、做什麼、帶哪個關鍵詞）」，而 `lib/plan_lint` 列的 `summary` 說這張表要合「B0 B1 B2 B3+ (B4) B5 (B6) B7、蓋章前要拿書、必提詞有拍認領、拍數」——**輸出空間已經被一張文法框死**。被文法框死的東西是固化階梯第 2～3 級（規則分支、模板），不該每題花 5 秒問腦重想一遍。
- **做法**：`draft` 先用 `brief/tables` 的 beats 表（`brief/tables` 列 `summary` 提到「beats（定點 01 的 beat 文法）」）填一張模板表：B0 定場、B1 偶遇／事件、B2 開口、B3×2 話題、B4 半步（放第二組必提詞）、B5 反差、B6 蓋章（地點有梅花章時）、B7 收尾（照 intent）；每拍的 `do` 用場景的 `event` 切句填。純程式、確定性、0 ms。director 降成「模板填不出來（例如 event 太短、必提詞分不完）才問」的後備。
- **預期**：時間 −36～39%、token −20%、`deterministic` 的節點多一個；一題問腦從 4 次降到 3 次。
- **風險（表上答不了）**：稿子品質會不會掉——director 的 `do` 是腦寫的「每拍一句意圖」，模板版的 `do` 只能是場景 event 的切片。要靠 Tier 2 分數對照（§5 缺口 5）才知道。

### 第 2 名：writer 的自檢從「腦決定叫不叫」改成「程式一定先跑」

- **依據**：`writer` 列 `llm_calls` 實測 2／2 vs 宣告 val 1；`think/exec` 每次 5041／5196 tokens；兩次中第一次的產出（稿）在第二次原樣重送。`check` 列 45 ms、`lib/lint` 列 `time_ms` 30 ms、`deterministic: true`——lint 是免費的，但現在要花一次腦（約 5000 tokens、3 秒）來「決定要叫 lint」。
- **做法**：writer 的 act 收到腦的稿子後**自己**跑一次 lint（程式，不問腦）；沒違規就直接交稿（一次問腦結束）；有違規才把違規接回 history、回 idle 再問一次。這是 C-22（能寫死的節點換成程式）用在「要不要自檢」這個決定上。
- **預期**：稿子一次就乾淨時（兩題實測 check 都只跑一次、`.` 的 `counter_cycles` 宣告 val 1）token −30%、時間 −20%；髒稿時跟現在一樣。
- **代價**：腦看不到 lint 當工具（`tools/lint` 那條捷徑可以留著給它主動叫，但預設不等它叫）。

### 第 3 名：稿紙分三種視圖，別把整份 brief 送三遍

- **依據**：三個問腦點的 prompt 大小——`director/think` 3416、`critic/think` 3617、`writer/think` 5041——相對它們的輸出（一張小表、一行分數、十行台詞）都偏大；三列的 `reads` 都是同一份 `$AOS_STACK/brief.json`（`draft`、`judge` 列的 `reads` 欄）。合理推測三份 prompt 裡有一大塊是同一份稿紙（人物卡、地點硬設定、禁語、樣本、beat 文法）被各送一次；director 不需要語料樣本、critic 不需要開場收尾句與 beat 文法。
- **做法**：`brief`（21 ms、`deterministic: true`，加工免費）多產三個子物件 `brief.for.director`／`for.writer`／`for.critic`，只放各自要的格；黏合格送對應的那份。
- **預期**：director、critic 的 prompt 各砍三到五成，整題 token 估 −15～20%。確切數字要看 prompt 組成（§5 缺口 4）。

### 其他（收益小或表上判不準）

- **合併純程式格**：`brief`／`check`／`deliver` 加起來 <100 ms，併了時間不變；併不併是結構問題（見 [round3-collapse](round3-collapse.md)）。
- **併行**：一題之內是一條嚴格的鏈（brief→director→writer→check→critic→deliver，每一步讀上一步寫的檔——各列 `reads`／`writes` 欄串起來就是這條鏈），**沒有可併行的段**。能併行的只有跨題：`.` 列 `parallel: true`、`lock` 綁 `ws:`——同一個工作區一次一題，不同工作區可以同時跑，交給外面（kernel／daemon）起多個，樹不用動。
- **快取**：`deterministic: true` 的列都快（<50 ms），快取沒意義；三個問腦點 `deterministic: false` 不能快取結果。唯一值得問的是**供應商端的 prompt prefix 快取**——三個 think 單子的 `llm_model` 相同、system 應該也相同（表上看不到，§5 缺口 4），若端點支援，system＋稿紙前綴每題只付一次。
- **換便宜模型**：三個 think 列 `llm_model` 全是 `chatgpt-gpt-6-luna-low`。critic 的工作（一行分數）與 director（一張小表）比 writer 簡單，`_metainfo` 一格一個 `llm_model` 本來就允許分開給——但使用者限定 gpt 系列、luna-low 已是低檔，這條先放著。
- **deliver 實測 0 ms 不可信**：`deliver` 列宣告 20 ms、實測 `q01:0 q08:0`；它的 `writes` 列了四個檔加搬檔加刪檔，0 ms 不可能。這是量測點的問題（deliver 自己量自己、起點放錯），不是優化點——記進 §5 缺口 8。

## 4. 宣告估得準不準、為什麼

表尾「差最多的幾列」加上 `超過 max` 欄全空，歸納成三句：

| 哪一類 | 宣告 vs 實測 | 準不準 | 為什麼 |
|---|---|---|---|
| **時間（val）全部高估** | `judge` 7500→1936／3012（0.26～0.40）；`critic` 7000→1903／2978；`writer/think` 8000→3230／4183（0.40）；`brief` 60→21（0.35）；`.` 26000→14365／18150（0.55～0.70） | 都在 `max` 內（超過 max 欄全空），但 val 普遍高 2～4 倍 | 估的時候拿「一次問腦 6～8 秒」當基準，luna-low 實際 2～4 秒；純程式格估 60 ms 是怕 python 啟動慢，實際 20 ms。**高估無害**（kernel 排隊只會把它排後面），但 val 的意思是「典型值」，寫成上限就失去參考價值 |
| **token（val）全部低估** | `writer` 3000→10082／10392（**3.4 倍**）；`writer/think` 2500→5041／5196（2.0）；`draft` 4300→13498（3.1）；`.` 7000→17115（2.4）；`director` 1800→3416（1.9）；`critic` 2200→3617（1.6） | 都沒超過 `max`，但 val 系統性低 2～3 倍 | 三個原因疊在一起：① 用「字數」估 token，中文 1 字≈1.5～2 token，直接少一半；② writer 宣告 `llm_calls` val 1、實測 2——自檢那次沒算進典型值，而且第二次重送 history，不是 2 倍是 2 倍多；③ 每次問腦都帶 system＋整份稿紙，稿紙比我估的大（§3 第 3 名） |
| **次數** | `.` `llm_calls` 3→4；`writer` 1→2；`director`、`critic` 1→1 | director、critic 準；writer 偏 1 次、整題跟著偏 1 | 同上 ②：自檢被當成「偶爾」寫進 max，實際每題都發生。**`max` 設得對**（11、3、5 都沒撞到），**val 設錯**——這正是「典型值該用實測回頭校正」的例子；M7 說實測不回寫 `_metainfo`，所以要靠這張表定期對、人手改 val |

估得準的：`director` 的 `time_ms`（6000 vs 5643／6446）、`draft` 的 `time_ms`（16000 vs 12339／15049）——這兩個是「上一輪已經有數字」後才寫的（round2 時 writer 真腦跑過一次 5.5 秒），**有實測底的宣告就準，憑空估的就偏**。結論：`_metainfo` 的 val 第一版只能當佔位，跑過一輪就該回填。

## 5. `_metainfo`（與這張表）缺什麼——只看表想知道卻查不到的

| # | 缺口 | 表上的症狀 | 提議（key 或寫法） |
|---|---|---|---|
| 1 | **每次 vs 每題混在一起** | `writer` 列 `llm_tokens` 宣告 3000 是「每次問腦」的意思，實測 10082 是「這題兩次合計」；`think/exec` 單子列才是每次。同一欄兩種單位，倍數表因此失真（3.4 倍其實是 1.7 倍×2 次） | `_metainfo` 加 `unit`：`"unit": "call"`（每被 aos-exec 一次）為預設，`"question"`／`"cycle"` 另標；實測欄同時給 `counter_invocations`（這題被叫幾次）與每次平均。表的「倍數」用同單位算 |
| 2 | **捷徑列是空的** | `check/tools/lint`、`draft/tools/plan_lint`、`writer/tools/lint` 三列只有「捷徑 → …」，實測欄全空；`lib/lint` 列也沒實測——lint 到底每題跑幾次、花多久，表上完全看不到（它在空小格裡沒留 trace） | 純函數工具也寫一行紀錄到呼叫方給的小格（例 `$AOS_STACK/lint/calls.jsonl`：`called_at`、`elapsed_ms`、`counter_violations`），deliver 彙整時把它算到**捷徑那一列**（＝按呼叫者歸戶），`lib/lint` 列顯示總和。`lib` 函數的 `_metainfo` 已有 `callers`，表應該把它展成反向連結 |
| 3 | **data／dir 列沒有大小** | `brief/tables`、`judge/benchmarks`、`examples` 只有 summary；要判斷「稿紙為什麼 5000 token」得知道表有多大 | `kind: data` 的 `_metainfo` 加 `counter_bytes`、`counter_files`、`format`（json／txt）；表加一欄 |
| 4 | **prompt 組成看不到** | 三個 think 列只有總 token；分不出 system／稿紙／history／輸出各佔多少，§3 第 3 名只能「合理推測」 | 宣告與實測都拆 `llm_tokens_prompt`／`llm_tokens_completion`（實測端 llm.jsonl 已有 `counter_tokens_prompt`，表沒接進來）；再加一格 `prompt_parts: {"system": 字數, "brief": 字數}` 的宣告 |
| 5 | **沒有品質欄** | 優化是「花多少換多好」，表只有花多少；q01 與 q08 哪題分高、director 這一步有沒有換到分數，表上答不了 | 實測並進 `score`（Tier 0／1／2 與總分）與 `counter_redrafts`；`_metainfo` 可宣告 `quality_target`（例 `{"score_min": 4}`） |
| 6 | **呼叫圖被截掉** | `reads`／`writes`／`calls` 塞在「其他 key」欄、被 `…` 截斷；要畫出 brief→director→writer→check→critic 這條鏈得點開 json | 表另出一節「邊」：誰寫的檔被誰讀（從 `writes`∩`reads` 機械算）、誰叫誰（`calls`）；每個函數都寫 `callers`（現在只有 lib 的有） |
| 7 | **idle 與 act 單子沒實測** | 四個 `idle` 列、三個 `act/exec` 列實測全空；只有 think 有（從 llm.jsonl 對上的）。agent 的牆上時間扣掉問腦還剩多少（流程開銷）算不出來 | 量測把各 agent 小格的 `trace.jsonl` 按 state 併進表（director 5643 − think 5572 ＝ 71 ms 開銷，這個數字其實量得到，只是沒進表） |
| 8 | **量測方法不透明** | `deliver` 實測 0 ms（不可能）；`.` 的 14365 是哪兩個時間點相減也不知道 | 實測欄每個數字帶 `measured_by`（`trace`／`llm.jsonl`／`self`）；自量的格（deliver）改由上一層的 trace 量（它那格在頂層 trace 本來就有一行，只是這題結束後才寫） |
| 9 | **樣本數與分布** | 兩題各一次，val 校正只能靠眼睛 | 實測欄給 `counter_samples`、`p50`、`max`；`_metainfo` 的雙形本來就允許 `{"val", "max", "p90"…}`（M3），表跟著顯示 |
| 10 | **時間沒分「等外面」與「自己算」** | director 5643 ms 幾乎全在等腦，brief 21 ms 全在算；同一欄 `time_ms` 分不出資源在誰手上 | 加 `wait_ms`（等 llm／net／human 的時間）宣告與實測；kernel 排隊時「等」的格可以跟別人疊 |
| 11 | **`lock`、`$env` 在表上不可讀** | `.`、`director`、`writer` 的 `lock` 是 `{"$env": …, "$prefix": …}`，表只印 key 名 | 表解開顯示成 `ws:$AOS_WS`；或 `_metainfo` 另給 `lock_summary` 一句 |
| 12 | **`interrupt: resumable` 沒驗** | 五列宣告 resumable，表上沒有任何實測能佐證（被殺過嗎、接得回來嗎） | 測試裡做一次「跑到 draft 殺掉、重跑」並把結果記進實測 `resumed: true/false`；表加一欄 |

## 6. 只看表能判斷什麼、什麼一定要看程式

**只看表就能判斷的**：錢與時間花在哪一列（§1）；哪些列不確定、不確定是不是串成鏈（§2，靠 `deterministic` 與 `reads`／`writes`）；宣告哪裡偏、偏幾倍、偏的方向一致不一致（§4）；哪些格免費到不值得為時間去併（§3 其他）；一題之內能不能併行（靠 `reads`／`writes` 的依賴鏈）；哪個 LLM 節點輸出被文法框死、值得換成程式（§3 第 1 名——靠 `summary` 與 `lib/plan_lint` 的存在推的）；自檢每題都發生而不是偶爾（靠 `llm_calls` 宣告 vs 實測）。

**一定要看程式（或產出）才能判斷的**：換掉 director 後稿子品質會不會掉（要分數與稿子）；三份 prompt 裡到底是什麼佔了 token（要看 render）；自檢那次腦到底改了什麼、lint 有沒有抓到東西（要看 history 與 check.json）；deliver 為什麼量到 0（要看量測程式）；`interrupt: resumable` 是真是假（要殺一次看）；哪些中間層薄到該併（要看檔有多少行、做幾件事——表只有 summary）。

所以這張表做到了「把該看哪裡指出來」，做不到「直接下刀」；§5 的十二個缺口補上大半（1、2、4、5、7、8）之後，§3 的前三名就能在表上算出收益、不用再猜。
