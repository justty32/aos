# galtxt-a — 由上而下拆的 galgame 台詞管線（甲隊，第一輪極小版）

← [proto8](../../README.md)｜規劃（照它做）：[plan/round1.md](plan/round1.md)｜實測：[plan/round1-measure.md](plan/round1-measure.md)｜題目來源（只讀）：`~/repo/ai_core/sub_projs/galtxt/corpus`｜測試：`proto8/tests/test_topdown_galtxt_a.py`

給一組場景條件（地點、兩個人物、一個小事件、風格意圖），寫幾份 galgame 台詞草稿、用純程式過護欄、讓評審打語意分、挑一份交卷。另一個模式是 corpus 的「挖空一句台詞」評測題（現在只有 Q01）。

使用者 10-25：「這是一個龐大的目標，我會建議先從極小需求開始」——這一輪只有一個定點：河鹿堂、主角＋森下晴子、讓書事件。

## 怎麼跑

先建好 `proto8/impls`（[testing](../../../wf/workflows/testing.md) 的 proto8 段），把 aos-exec、aos-loop、aos-fsm 三支放進 PATH：

```sh
export PATH=$PWD/proto8/impls/aos-exec/bin:$PWD/proto8/impls/aos-loop/bin:$PWD/proto8/impls/aos-fsm/bin:$PATH
mkdir -p ws/new && cp proto8/topdown/galtxt-a/plan/examples/Q01.json ws/new/
aos-exec --ws ws proto8/topdown/galtxt-a                                        # 假腦（離線）
AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws ws proto8/topdown/galtxt-a # 真腦（家機 LiteLLM）
cat ws/out/Q01/answer.txt ws/out/Q01/score.json
```

模型名在寫手、評審各自的 `.env`（`chatgpt-gpt-6-luna-low`）；腦的位置由外面給 `AOS_BRAIN_URL`，沒給＝假腦。

## 輸入、輸出

題目放 `ws/new/<題名>.json`，一題一檔（範例在 [plan/examples/](plan/examples/)）：

- 場景模式：`{"mode": "scene", "place": "河鹿堂", "cast": ["佐伯悠", "森下晴子"], "event": "…", "season", "time", "intent", "rank": 1, "min_lines": 5, "max_lines": 10, "drafts": 3}`
- 挖空模式：`{"mode": "fill", "bench": "Q01", "drafts": 3}`——前後文、護欄關鍵詞、正解都在 `data/bench/Q01.json`，正解只有 `pick/` 讀。

做完：

| 在哪 | 是什麼 |
|---|---|
| `ws/out/<題名>/answer.txt` | 挑中的那份台詞（旁白「（…）」、對白「角色：「台詞」」一行一句；挖空模式恰好一行） |
| `ws/out/<題名>/score.json` | 每份草稿的 Tier 0（護欄）、Tier 1（語域 0～2）、Tier 2（評審 0～3）、總分，挑了第幾份；挖空模式多 `bench`（跟正解的字元二元組重疊率、護欄關鍵詞有沒有全中） |
| `ws/done/<題名>.json` | 做完的題目 |
| `ws/.stack/` | 執行中的一切：`brief.json`、`rules.json`、`drafts/`、`checks.json`、`judge.json`、`trace.jsonl`，寫手與評審的小格 `writer/runs/NNN/`、`judge/runs/NNN/`（寫手、評審問真腦時各記一份 `usage.jsonl`） |

## 樹

```
galtxt-a/                 [agent] _entry → aos-loop loop.json → fsm.json：idle → brief → write → check → judge → pick → idle
├─ idle/                  [純程式] 有題退 0、沒題退 10
├─ brief/                 [純程式] 認領題目，data/ → brief.json（給寫手）＋ rules.json（給 lint）
├─ write/                 [黏合格] 開小格 ×N、叫寫手、收 drafts/N.txt（已有的不重寫）
│  └─ tools/writer/       [agent] 寫手（agent-dan 範本；假腦＝模板填槽）
│     └─ tools/lint ─捷徑─▶ ../../../../check/tools/lint
├─ check/                 [純程式格] 每份草稿 aos-exec --ws $AOS_STACK tools/lint → checks.json
│  └─ tools/lint/         [純程式工具] Tier 0 護欄＋Tier 1 語域；被 check 與寫手兩處叫
├─ judge/                 [黏合格] 過了護欄的草稿逐份叫評審 → judge.json
│  └─ tools/judge/        [agent] 評審（沒有工具；回「分數：N」「理由：…」；假腦固定 2 分）
├─ pick/                  [純程式] 合分、嚴格比大小、平手編號小的贏；寫 out/、cur/ → done/
├─ data/                  [資料] corpus 手抄的固化表（每張帶 source）：cast/ places/ bench/ samples/ address.json forbidden.json styles.json
└─ plan/                  規劃書、實測、題目範例
```

每個資料夾都有一份 `_metainfo`（規劃 § 4；多出的 key：`kind`、`grow_level`、`reads`／`writes`、`fs_needs`、`callers`、`llm_model`／`llm_endpoint`），寫手、評審的 think 格另有內嵌在 `fsm.json` 單子裡的一份。數字是作者的估計，實測在 [plan/round1-measure.md](plan/round1-measure.md)、不回寫 `_metainfo`。

## 評分

總分＝Tier 1＋Tier 2（0～5）；Tier 0 沒過的那份總分 0。Tier 0、Tier 1 是 `lint` 純程式算的（規則全在 `rules.json`，由 brief 從 `data/` 組）；Tier 2 才問腦。全部沒過 Tier 0 時照樣挑違規最少的那份、`score.json` 標 `pass: false`、結束碼 0。
