# box_check — 檢查關箱探測輸出與主機暫存檔是否符合隔離界線。

```mermaid
flowchart LR
  O[got/stdout.json] --> C[五個結果與執行檔清單] --> S[score：0 或 1]
  H[主機暫存檔] --> C
```

比對器給 box-probe 探測用（五個逃脫探測經 `tools/shell` 跑、再交 measure 比對；探測指令原本放在 `proto8/cases/box-probe/`，11-17 刪掉，現在只留在 [tests/test_acceptance.py](tests/test_acceptance.py) 的 `PROBE`）；任一探測缺漏或越界就給零分。

<details>
<summary>判準與執行</summary>

stdin 依 measure 的比對器契約（[measure README](../measure/README.md)「輸入契約」）給 `expect`、`got`、`input`。R1 必須成功但主機 `/tmp/aos-box-probe` 不得存在；R2 網路必須失敗；第 5 條必須有唯一的 `P5 <路徑>`，並以主機上該路徑不存在為通過條件，不看 R5 的結束碼；R3、R4 列舉必須成功；不得列出主機使用者家目錄的內容。執行檔集合取自 shell-boxed 的公開 `_metainfo.json#/sandbox/ro`，同時容許 Python 捷徑的實體檔。主機探測檔若存在會清除並判零分。P5 保留 `$AOS_STACK/../../history.jsonl` 的原字串（含 `../..`），沙箱空殼目錄寫入成功仍可通過。

`python3 -m unittest discover -s proto8/py/tools/aos/box_check/tests -v`

測試實際呼叫 aos-exec、aos-sandbox 與 measure；不把 sandbox 權限失敗跳過成通過。

</details>
