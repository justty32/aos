# human — 人評契約與匯入

← [galtxt-b](../README.md)｜設計：[plan/round4.md §6](../plan/round4.md)｜測試：`proto8/tests/test_topdown_galtxt_b_train.py`

使用者的時間少，人評是稀缺資源：**每輪最多 6 筆、只挑自動評分最拿不準的**（`train/pick` 挑），評完只拿來**校正**自動評分（寫進 `_metainfo.ratings.human` 與校正表），**不算進分數**。

## 三份檔

| 檔 | 誰寫 | 形狀 |
|---|---|---|
| `samples.json` | `train/pick`（這裡這份是第 4 輪基準輪挑的 6 筆，給頂層做網頁） | 陣列，每筆 `{"id": "b-r<輪>-<題>-<次>", "team": "b", "round", "scene": {cast, place, season, time, summary, event, intent, style}, "lines": [台詞與旁白，不含【標題】], "produced_by": "產出台詞的資料夾（相對 galtxt-b）", "auto_scores": {val, total, max_total, dims, register_agree}, "why_picked"}` |
| `questions.json` | 人（這份是設計） | 網頁照它出題：`overall`（good／ok／bad 一鍵）、`tags`（叉的話點一個）、`dims`（選填滑桿 0～1）、`note` |
| `ratings.json` | 網頁寫回 | 陣列，每筆 `{"id", "overall", "tags": [...], "dims": {名: 0～1}, "comment", "rated_at"}` |

`auto_scores.dims` 的每一維是 0～1 的數字，或長成物件時原值在 `val`（例：語意 `{"val": 0.67, "承接": 0.8, "含蓄": 0.9, "角色味": 0.7}`）；讀的人兩形都收。

## 匯入 `import/`

```sh
aos-exec --ws 訓練場 proto8/topdown/galtxt-b/human/import
```

訓練場要有 `human/{samples.json,ratings.json}` 與 `tree/`（galtxt-b 的工作複本）。做三件事：

1. 每筆評級對 `id` 找樣本 → `produced_by`、`scene.style`；同一節點同一風格合成第 2 級評級 `{"val": 多數票（平手取較差的）, "tags": 次數前三, 各 dims 的平均, "counter_samples", "rated_at", "source"}`，寫進 `tree/<produced_by>/_metainfo` 與 `tree/_metainfo` 的 `ratings.human.<風格>`。
2. 寫 `human/calibration.json`：`counter_rated`、`agreement`（自動 `val` 跟人的 `overall` 一樣的比例，整體與分風格）、`confusion`（不一樣的那幾組，帶 ids 與 tags）、`suggest`（規則式的一句建議：自動比人寬＝評分器對這個風格太鬆）。
3. `tree/judge/tools/critic/_metainfo` 的 `ratings.calibration` 記一致率（critic 被評的是準不準）。

**只動 `ratings` 這個 key**：其餘 key 照原文一個字元都不動。單筆有問題不擋整批（stderr 一行 `import: SampleUnknown <id>`／`import: RatingBad <id> 原因`、跳過）；`ratings.json` 不在＝什麼都不做。
