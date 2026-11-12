# 11-07 五份設計的實作規劃（fable 一次性規劃）

← [impl-plan](README.md)｜原話：[kb-ideas](../kb-ideas/README.md)、[隊形 03](../../../../../wf/workflows/dispatch/aos-teams/03-使用者原話.md)｜條文：[C-84](../../../../docs/CONCEPTS/05-agent/03-C-84.md)、[N-68](../../../../docs/NORMS/10-基礎設施-定義與工作區/10-N-68.md)

fable 的規劃已全部施工完（每批做了什麼見 [14 完成總結](14-完成總結.md)）；細節跟[代定](代定.md)不同時以代定為準。這裡只留規劃定下、現在仍有效的結論。

## 分批

本線只動 `proto8/`，排成 9 批串行、一批一個 commit：批 1 雜活（R2～R7、E10）→ 批 2 `_metainfo` 改格式 → 批 3 帳 → 批 4 量 → 批 5 換上／退回、裁判 → 批 6 審視者＋watch → 批 7～8 kernel 嵌套 C++ → 批 9 工具權限與定義樹（另插批 4b；實際批 9 提到批 7 前，代定 15）。

## 位置與名字

| 東西 | 放哪、叫什麼 |
|---|---|
| measure（含門、consistency） | `lib/aos/measure/`；只印 JSON 到 stdout、不寫檔，寫到 `reviews/` 是審視者的事（C-52） |
| promote／rollback | `lib/aos/promote/`、`lib/aos/rollback/` 兩個工具夾、共用一個小模組 |
| watch | `lib/aos/watch/`，純腳本、不用 LLM（C-22）；判準在工具的 `_metainfo.json#/rules` |
| metainfo_check、shell_report | `lib/aos/`（檢查的是定義，不是 agent 自己的記憶）；`lib/agent/` 留給 agent 管自己 |
| case 夾 | 新頂層 `proto8/cases/<名>/`，進 repo；試驗場自己的 case 放試驗場 |
| 子帳抄本 | 自己 stack 小格內 `observed/<子名>/`，不進 agent 定義夾；ltn-5「stack 照刪、刪前抄子帳」，stack 一刪就清掉（等於定期清理），`.gitignore` 加 `observed/`、`observed.jsonl` |
| review／watch 紀錄、前版、裁判 | 見代定 11、13、14 |

## 跟原則的衝突怎麼解（fable 定，不用再問）

1. **R8 不塞進 promote**（C-52「不認身份、可認公開介面」）：改成審視者定義自己的 `ladder.json#/promote_by`，gpt 腦的審視者寫 `claude`、自己不叫 promote、只留 `pending_promote`，由 Claude 審視者或隊長叫。promote 本身不看腦。
2. 成本計數 key 用 `counter_calls`（N-68、C-54 計數一律 `counter_`），不用 `calls`；`eval_cost` 變數名同理（`in_bytes`、`counter_calls`）。
3. 上層讀下層的帳只准照 `interfaces.json` 宣告的 `aos-observed` 路徑找，不准硬編相對位置猜子 stack。
4. K5 透明轉交是 C-53 的例外（kn-5:B 使用者已裁），記進 C-52 例外表。
5. 不做相容（11-05「一律當成沒有舊版」）vs 同時在用的試驗場：同 commit 附一次性改檔腳本、交棒檔列出會斷的檔、arknights 隊長挑地點之間跑；本線不改試驗場。
6. watch 的成本窗不滿 3 個 case：只記不判。
7. promote 判「正用著」只讀 daemon 公開的窗（實作見代定 14）；沒 daemon 的 ws 當沒人用。

## 這輪不做的

| 步 | 理由 |
|---|---|
| E15、A6（審視者自己寫副本） | 要「做滿三個地點」、有 3 個 case 的 review.json 才驗得了（C-84） |
| E16（從好答案挑範例） | 要先有被 watch 轉正（kept）的真輪（evo-C） |
| T9 自動 `box`／`unshell` | 要 T5、T7、E13 跑過真資料；批 9 只放處方 |
| 想法 16 的「complexity」抽象指標 | 使用者自己說留第四、五輪 |
