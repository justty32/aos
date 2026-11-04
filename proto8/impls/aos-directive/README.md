# aos-directive

`aos-directive - 解 JSON 裡的指示詞（$ref、$env）`（NAME，C-54 R1）

**一句話：解 JSON 裡的指示詞——`{"$ref": "檔#/指標"}` 換成那份檔裡那個位置的值、`{"$env": "名字"}` 換成環境變數的值（可帶 `$path`、`$prefix`）。** 一個 lib（`lib/libaos-directive.a`）加一支命令列（`bin/aos-directive`，不對外提供）。
aos-exec 連這個 lib 解單子、argv 陣列入口與 JSON `.env` key 裡的指示詞（loop／fsm／daemon 的每一次都經 aos-exec）；
aos-loop、aos-daemon、aos-fsm 讀設定檔與 ctl 時也用它（使用者「aos 讀的 JSON 全部支援」，N-45；每支程式只解自己讀的格，用 `resolve_shallow` 一層層往下）。全家慣例見 [impls/README.md](../README.md)。
規範在 [N-45](../../docs/NORMS/06-基礎設施-命令列與指示詞.md)（`$ref` 的細則以本檔為準）。

```sh
echo '{"argv": {"$ref": "cfg.json#/tools/stamp"}, "out": {"$env": "AOS_STACK", "$path": "out", "$prefix": "--o="}}' | aos-directive
# {"argv": ["sh", "-c", "exit 3"], "out": "--o=/ws/.stack/out"}
```

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-用法等](docs/01-用法等.md) | 用法；元素；公開介面；建置與測試 |

<a id="用法"></a>
<a id="指示詞"></a>
<a id="命令列"></a>
<a id="元素"></a>
<a id="公開介面"></a>
<a id="建置與測試"></a>
