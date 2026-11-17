# aos-json

`aos-json - 讀、改 aos 的 JSON 設定（檔#/指標、指示詞）`（NAME，C-54 R1）

**一句話：用 `檔#/指標` 讀或改一份 JSON 的某個位置；認得 `$ref`／`$env`：可以穿過 `$ref` 改被參照的檔、追一個值實際寫在哪、一層層看（漸進展開）、寫之前先驗形狀。**
一個 lib（`lib/libaos-json.a`，沒有公開標頭）加一支命令列（`bin/aos-json`）。給腦掛的工具在 lib：json 工具一族（[`lib/aos_json.py`](../../lib/aos_json.py)：簡單組 `lib/base/json_*` 七支（含 `json_len`）、複雜組 `lib/aos/jsonx_*` 六支、一次多格 `json_multi_get`／`json_multi_set`／`jsonx_multi_get`／`jsonx_multi_set`）。
嘗試性原型（使用者「做一套方便修改json的工具集，配合指示詞」），討論與代定見 [thinking 2026-10-24 aos-json](../../thinking/2026-10/24/aos-json.md)。

```sh
aos-json peek fsm.json                                   # 只看頂層，大的值摺起來
aos-json peek --follow fsm.json#/states/think            # 穿過 $ref 看下一層
aos-json get --resolve fsm.json#/states/think/exec       # 解開指示詞（跟 aos-fsm 讀的一樣）
aos-json where fsm.json#/states/think/next               # 這個值實際寫在哪份檔的哪裡（一站一行）
aos-json set --follow fsm.json#/states/think/next '"act"'    # 改被 $ref 的那份檔
aos-json ls --long cfg.json#/tags                        # 列孩子＋型別與大小（--offset／--limit 分頁）
aos-json search --key timeout cfg.json                   # 找 key／value（--value JSON、--contains、--up 往上）
aos-json add cfg.json#/tags/1 '"x"'                      # 插在第 1 項前面（已有的 key＝KeyExists）；印 cfg.json#/tags/1
echo '{"/max": 5, "/interval_ms": 100}' | aos-json batch loop.json   # 一次改很多個（全部成功才寫）
aos-json ref --move daemon.json#/procs daemon_procs.json # 把一塊拆成另一份檔，原地換成 $ref
aos-json check fsm.json                                  # $ref 指得到、寫法對、exec 形狀對
```

寫入值與寫入指示詞的程式位置，見[元素](docs/02-給腦用的兩個工具等.md#元素)。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-用法與寫回去-原子-只改變的那一塊](docs/01-用法與寫回去-原子-只改變的那一塊.md) | 用法；寫回去：原子、只改變的那一塊 |
| [02-給腦用的兩個工具等](docs/02-給腦用的兩個工具等.md) | 給腦用的工具（在 lib）；跟 aos-directive 的分工；元素；建置與測試 |

<a id="用法"></a>
<a id="寫回去原子只改變的那一塊"></a>
<a id="給腦用的兩個工具tools"></a>
<a id="給腦用的工具在-lib"></a>
<a id="跟-aos-directive-的分工"></a>
<a id="元素"></a>
<a id="建置與測試"></a>
