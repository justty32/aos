# `_metainfo` 整合的圖紙（11-12 下午，只規劃、沒施工）：節點底下 aos 自己的東西只剩 `_entry` 與 `_metainfo`，`_index`／`_tooldef`／`_description` 搬進去、去掉底線；待裁兩題

← [11-12 日索引](../README.md) ・ 前情：[index](../index.md)（原話一～十）、[index-tools](../index-tools/README.md)（`index_view`、`spot()`）、[10-24 `_metainfo`](../../../2026-10/24/metainfo/README.md)（函數特性，M1～M10）、條文 [N-68](../../../../docs/NORMS/10-基礎設施-定義與工作區/10-N-68.md)、[待定 `_metainfo`](../../../../docs/NORMS/08-待定/01-續-metainfo.md)、[P-41](../../../../docs/CONVENTION/02-題目stack停錯腦/06-P-41.md)

| 分檔 | 涵蓋 |
|---|---|
| [01-盤點](01-盤點.md) | 現在有哪些底線開頭的名字、誰讀誰寫、哪條條文、搬不搬 |
| [02-設計](02-設計.md) | `_metainfo` 長怎樣、搬進去後的名字、留外面的、裝不下時、工具怎麼跟上、邊緣狀況 |
| [03-施工切法](03-施工切法.md) | 四步、每步動哪些檔、怎麼驗、多大、要重建什麼 |
| [04-題與代定](04-題與代定.md) | 要使用者裁的兩題（a/b＋推薦）、代定 M1～M13 |

## 使用者原文

11-12 下午（開這條線的話）：

> 「啊，metainfo感覺也可以開始先弄了，派fable幫忙想想吧」

11-12 稍早（全文在 [index](../index.md) 原話九與其後的答覆）：

> 「…ps.我記得以前還有_metainfo, _tooldef那些，搞不好_index,_tooldef也會被整合進metainfo....啊，或許可以這樣說，_metainfo就是一個天然的，蒐集那些同節點下散落的(aos體系中的)各種_*」

> 「…metainfo這塊就是搬進去，_index進去後就是index，去掉_。現在先不用做，這是後續想法。_entry確實不能搬進去，所以就是有些能搬有些不能搬，我們就是開了metainfo這個口子，要用不用都可以。json檔案也一樣。_metainfo整合應該會是一兩個禮拜後的事情了。」

## 決定（使用者已講的）

- `_metainfo` 蒐集同節點下散落的、aos 體系的各種 `_*`。
- 搬進去就去掉 `_`：`_index` → `index`。
- `_entry` 不搬；有些能搬有些不能搬。
- 是個口子，要用不用都可以；json 檔也一樣。
- 11-12 下午起可以開始弄（原本說一兩週後）。

## 結論（圖紙，細節在分檔）

- **`_metainfo` 本來就在**：10-24 起它是「函數的特性」（`summary`、`cost`、`timeout_ms`、九軸、`sandbox`…，N-68），資料夾裡是 `_metainfo.json`（現有 74 份）、json 物件與單子裡是 `_metainfo` 鍵。這次不是新做一個東西，是把它的意思從「給 kernel 參考的函數特性」放寬成「這個節點的附屬資訊」，再把別的 `_*` 收進來。
- **位置與檔名不變**：資料夾 `DIR/_metainfo.json`、json 物件（含整份 json 檔）`_metainfo` 鍵。
- **形狀：一個物件、平鋪**。原有特性 key 原地不動，並排加三格：`index`（原 `_index`／`_index.json`）、`tooldef`（原 `_tooldef`／`_tooldef.json`，待裁）、`description`（原 `_description`／`_description.json`）。

  ```json
  {
    "summary": "List a folder one page at a time",
    "timeout_ms": 2000,
    "cost": {"time_ms": 30},
    "tooldef": {"description": "List a folder. ...", "parameters": {"type": "object"}},
    "index": {"docs": {"description": "how it works"}, "tests": {"description": "unit tests"}},
    "description": "# ls\n\nLonger text about this folder itself."
  }
  ```

- **留外面的只有「跑起來要用的」**：`_entry`（與 `_entry.json`）、`.env`。判準一句：aos-exec 跑它用不用得到；用得到的留外面，其餘進 `_metainfo`。C++ 基礎層（aos-exec、inst、loop、fsm、daemon）照舊永遠不開 `_metainfo`。
- **裝不下的節點**（陣列、別人的 json、可執行檔）：只有 index 照既有規則延伸——放最近一個裝得下的上層節點的 `_metainfo` 的 `index`，鍵寫相對路徑；其他項目不延伸，沒寫就是沒說。
- **工具**：`index_view` 改 `spot()` 與 `natural()` 的資料夾分支；`ls`／`json_ls` 不藏 `_metainfo`（index 才是視角，ls 是客觀；`_` 開頭照 C-48 沒有特別意思）；tooldef 那步動 `aos-tools`、`tool_io`、`tool_spec`、`tools_def`。
- **施工四步**：① index 搬（小）② description 搬（小，純內容）③ tooldef 搬（中到大，等裁）④ 條文落成正式一條（中）。
- **跟既有條文打架、要使用者裁的兩題**：`_tooldef` 搬不搬（P-41 與 11-04「留 _、加 .json」、10-24 M10）；「要用不用都可以」是只認裡面一處、還是裡外都認 → [04](04-題與代定.md)。

## 未決

- 上面兩題。
- [index](../index.md) 原本的未定（鍵裡的路徑相對誰、index 過時、cache）這份不碰。
