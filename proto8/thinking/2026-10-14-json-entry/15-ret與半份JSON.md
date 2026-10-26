# 2026-10-14 深夜收尾：ret／err 增長、半份 JSON、今晚交接

← [JSON 入口](../2026-10-14-json-entry.md)｜上一份：[14-h拍板](14-h拍板.md)

## 42. 使用者拍板（經協調 agent 轉達，使用者兩題都說「隨你」）

1. **【拍板】ret／err 無限增長＝方案 B。** 基礎實作：daemon 起子 loop 時 stdout 接 `/dev/null`，結果一律從 state 窗讀；stderr 照舊 append 到 `work_dir/N/err.json`，只在出錯時長，`ret.json` 不再有。標準實作才做：stdout／stderr 選填路徑＋上限輪替、不帶 `load` 重起時清掉 table 沒列到的舊格子。[NORMS 待定](../../docs/NORMS/08-待定.md)該條結案。
2. **【拍板】被殺時 stdout 最後一份只寫一半＝半份不算。** 讀的人只認完整、能解析的 JSON；解析不了就忽略；因此找不到結果＝沒有結果。落成 [N-12](../../docs/NORMS/01-總則.md) 附註。

## 44. 今晚交接（明天從這裡開始）

**尚未決定**：見 [NORMS 待定](../../docs/NORMS/08-待定.md)。10-15 早清帳：`檔#/位置`＝[N-35](../../docs/NORMS/01-總則.md)、aos-fsm＝N-36～N-41 已定；資料夾別亂弄結案；argv[0] 程式的規矩擱置；kernel 公告、時鐘格式、`_metainfo` 通用寫法晚點再說；a～f 暫定預設全部可改。

**fsm 心跳**：fsm 是單次程式、壽命一拍，不適用 N-17／N-32 的每秒心跳，生死看拍它的 loop 的 state 窗（[N-39](../../docs/NORMS/07-基礎設施-組合子.md#fsm)；使用者 10-15「基礎實作中連時間都不寫，保持極簡」，見 [thinking 10-15](../2026-10-15-topics.md)）。58 題頁第三組 Q12 寫 agent 心跳「可選」，以此為準。
