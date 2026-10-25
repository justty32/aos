# galtxt-a — 由上而下拆的 galgame 台詞管線（甲隊，第一輪極小版，第二輪收攏後）

← [proto8](../../README.md)｜規劃（照它做）：[plan/round1.md](plan/round1.md)｜實測：[plan/round1-measure.md](plan/round1-measure.md)｜第二輪收攏：[規劃](plan/round2-collapse.md)、[結果](plan/round2-result.md)｜題目來源（只讀）：`~/repo/ai_core/sub_projs/galtxt/corpus`｜測試：`proto8/tests/test_topdown_galtxt_a.py`

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
- 挖空模式：`{"mode": "fill", "bench": "Q01", "drafts": 3}`——前後文、護欄關鍵詞、正解都在 `data/bench/Q01.json`，正解只有 `pick.py` 讀。

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
├─ idle/                  [純程式] 有題退 0、沒題退 10；真身，寫手、評審的 idle 是指過來的捷徑（callers 3）
├─ brief.py               [純程式] 認領題目，data/ → brief.json（給寫手）＋ rules.json（給 lint）
├─ write.py               [黏合格] 開小格 ×N、叫寫手 writer/、收 drafts/N.txt（已有的不重寫）
├─ check.py               [純程式格] 每份草稿 aos-exec --ws $AOS_STACK tools/lint → checks.json
├─ judge.py               [黏合格] 過了護欄的草稿逐份叫評審 grader/ → judge.json
├─ pick.py                [純程式] 合分、嚴格比大小、平手編號小的贏；寫 out/、cur/ → done/
├─ tools/lint/            [純程式工具] Tier 0 護欄＋Tier 1 語域；被 check.py 與寫手兩處叫
├─ writer/                [agent] 寫手（agent-dan 範本；假腦＝模板填槽）
│  ├─ idle ─捷徑─▶ ../idle
│  └─ tools/lint ─捷徑─▶ ../../tools/lint
├─ grader/                [agent] 評審（沒有工具；回「分數：N」「理由：…」；假腦固定 2 分）
│  └─ idle ─捷徑─▶ ../idle
├─ data/                  [資料] corpus 手抄的固化表（每張帶 source）：cast.json places.json samples.json（{名: 卡}）address.json forbidden.json styles.json；bench/（一題一檔、含正解，只有 pick.py 讀）
├─ meta/                  這棵樹自己的工具：metatable（收 _metainfo 成表、--suggest 列收攏候選）、collapse（收攏）；每輪收的表
└─ plan/                  規劃書、實測、題目範例
```

fsm.json 的五格（brief、write、check、judge、pick）是內嵌單子 `{"argv": ["python3", "X.py"], "timeout_ms", "_metainfo"}`，在 fsm 行程內跑、cwd＝galtxt-a 根（第二輪從 `X/_entry` 收攏成這樣，見 [plan/round2-result.md](plan/round2-result.md)）。

每個資料夾都有一份 `_metainfo`（規劃 § 4；多出的 key：`kind`、`grow_level`、`reads`／`writes`、`fs_needs`、`callers`、`llm_model`／`llm_endpoint`）；五格與寫手、評審的 think 格的 `_metainfo` 內嵌在各自 `fsm.json` 的單子裡。數字是作者的估計，實測在 [plan/round1-measure.md](plan/round1-measure.md)、不回寫 `_metainfo`。

## 評分

總分＝Tier 1＋Tier 2（0～5）；Tier 0 沒過的那份總分 0。Tier 0、Tier 1 是 `lint` 純程式算的（規則全在 `rules.json`，由 brief 從 `data/` 組）；Tier 2 才問腦。全部沒過 Tier 0 時照樣挑違規最少的那份、`score.json` 標 `pass: false`、結束碼 0。

## 收攏工具（meta/，第二輪）

```sh
G=proto8/topdown/galtxt-a
$G/meta/metatable/_entry --suggest $G     # 收 _metainfo 成表，後面多一張收攏候選表（判準 plan/round2-collapse.md § 1；只列不做）
$G/meta/collapse/_entry --dry-run inline fsm.json#/states/brief/exec   # 在要收的那棵樹裡跑；先看會做什麼，拿掉 --dry-run 才做
```

`collapse` 四個子命令：`inline CFG#/指標`（資料夾格 → `X.py`＋內嵌單子，`_metainfo` 併進那格、`grow_level` 改 0）、`unwrap C [--name N]`（拿掉只裝一個子資料夾的純容器，整棵樹的相對捷徑跟著改）、`table D [--source S]`（資料表資料夾 → `D.json`，`_metainfo` 併進上一層 `children`、讀者的 `reads` 跟著改）、`dedupe REAL COPY...`（一模一樣的葉片換捷徑、`callers` 加到真身）。腳本裡的 `__file__`、`sys.path`、相對 cwd 的路徑、拿資料夾名拼路徑的地方不改，印成「手改清單」。錯：stderr 一行 `collapse: 代號 原因`、退 1、什麼都不寫（`ArgumentsBad`、`FlagUnknown`、`CfgMissing`、`CfgBad`、`TargetBad`、`NameBad`、`WriteFailed`）。

收攏前後不保證一樣的地方：五格少了一跳 aos-exec，`brief.py` 這種檔不見時的錯從 `aos-exec: EntryMissing` 變成 python 的 `can't open file`（只有字不同）；五格的 cwd 從 `X/` 變成 galtxt-a 根（腳本裡相對 cwd 的路徑已照手改清單改）。
