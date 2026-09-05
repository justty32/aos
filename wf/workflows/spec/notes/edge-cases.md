# aos 構想集：實作第一週會撞到什麼（邊緣狀況總表）

替 spec 審稿用。三組（空間 01–05／時間 06–08／介面 09–12）各交 30／30／30 條共 90 條，合併去重（20 條是跨組講同一件事）後 **83 條**：擋路 50、該補 21、可放 12。

依據：使用者 2026-09-05 拍板的 8 條（M-01、F-02、G-01、E-01、I-01～I-04）為最高，其餘照 ideas/README 的建議預設。不拿現有程式碼當憑據，評的是構想。

每條的「情境」都寫成一個具體時刻，可以直接改寫成一個測試。
「該進哪份 spec」用這組名字：01-terms、02-layout、03-source-and-compile、04-inst-format、05-series-format、06-exec-and-run、07-call-and-delivery、08-daemon、09-llm-world、10-agent、11-tools-and-contacts、12-cli、13-doorman-l1。

## 資料檔

三段（擋路 B01–B50、該補 S01–S21、可放 L01–L12）已抽到 [edge-cases.json](edge-cases.json)（83 列）。

欄位：

- `tier` — 分級：`擋路`／`該補`／`可放`
- `id` — 編號（`B01`…`B50`、`S01`…`S21`、`L01`…`L12`）
- `scenario` — 情境
- `bad_outcome` — 會發生什麼壞事
- `covered_in_ideas` — 構想集有沒有講到
- `spec_requirement` — spec 該規定什麼
- `target_spec` — 該進哪份 spec

查法見工作流的資料檔說明（[data-files](../../common/data-files.md)）。例如查全部「擋路」級用 `find tier=擋路`；查某一條用 `find id=B10`；查該進 09-llm-world 的所有條目（含合寫兩份的）用 `grep 09-llm-world`。

## 統計與落點分佈

- 合併前 90 條（空間 30、時間 30、介面 30），跨組重複 20 條，去重後 **83 條**：擋路 50（B01–B50）、該補 21（S01–S21）、可放 12（L01–L12）。
- 落點分佈：07-call-and-delivery 21｜08-daemon 11｜06-exec-and-run 11｜09-llm-world 9｜02-layout 9｜11-tools-and-contacts 6｜03-source-and-compile 5｜05-series-format 4｜10-agent 4｜12-cli 4｜13-doorman-l1 2｜04-inst-format 1｜01-terms 0。前三份 spec 的審稿要花掉一半以上的時間。
- 三條規則反覆惹事，spec 每寫一節都該回頭對一次：
  1. **「結果檔不在＝還沒好」**（I-02）。檔案不存在同時也是「子被殺了」「父死了寫不進去」「daemon 逾期清掉了」「落點指錯了」的長相，全部退化成父永遠等。
  2. **「沒產出新指令就停」**（M-01／H-02）。任何「在等」的狀態都會被它當成「沒事做」而停掉。
  3. **「一塊地只看得到自己地上的東西」**（M-01）碰上 **「結果落點由父指定」**（I-01）。跨世界寫入的授權、daemon 的清理權、LLM 世界讀設定檔，三處都卡在這個交點。
