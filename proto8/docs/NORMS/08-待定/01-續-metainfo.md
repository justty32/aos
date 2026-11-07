← [回入口 08-待定.md](../08-待定.md)｜段落：待定 _metainfo｜上一份：[01-待定之一](01-待定之一.md)｜下一份：[02-待定之二](02-待定之二.md)

## 待定 _metainfo

- 【基礎設施／inst＋kernel】**`_metainfo`**：單子裡給 kernel 參考的抽屜（九軸、資源特性），inst 格式的可選 key（地位同 `argv`）、inst 與完整實作忽略；裡面格式自由，通用的寫法（含資源）之後規定——出處 [thinking 10-13 §3](../../../thinking/2026-10/13/json-path/README.md)。**10-24 已照推薦定、待落條文**：使用者 10-24「一個函數是用_entry去跑。其特性我想要將其寫到_metainfo，裏面可以存放該函數要跑多久，要喫多少資源這種東西。相關的.json格式也要規劃。然後kernel也可以透過這個，來做參考」，規劃後「都按建議做」——三處同名（資料夾 `_metainfo` 檔、JSON 物件與單子的 key；**11-04 註**：資料夾裡的檔改名 `_metainfo.json`、key 名不變，使用者 11-04 題 8「留 _、加 .json」，[four-elements 06](../../../thinking/2026-11/04/four-elements/06-要使用者裁的題.md#使用者裁定11-04選項原文或他的話逐字)）、找法同找入口、通用 key 全選填、`timeout_ms` 才強制（逾時與估時拆開見 [N-68](../10-基礎設施-定義與工作區/10-N-68.md)）、實測不回寫，M1～M10 見 [thinking 10-24 `_metainfo`](../../../thinking/2026-10/24/metainfo/README.md)；CONCEPTS／NORMS 正文等頂層統一落。**11-07 註**：`cost` 與 `timeout_ms` 已寫成 [N-68](../10-基礎設施-定義與工作區/10-N-68.md)。
