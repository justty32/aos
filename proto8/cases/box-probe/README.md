# box-probe — 用 bash 內建指令檢查沙箱寫入、網路與可見路徑。

```mermaid
flowchart LR
  D[agent 定義 tools/bash] --> P[五個逃脫探測] --> C[box_check] --> M[measure 的 check.pass]
```

`defs` 指向待測 agent 定義夾；必須在呼叫 measure 時給 box_check 的絕對路徑。

```sh
printf '%s\n' '{"case":"/absolute/proto8/cases/box-probe","defs":"/absolute/agent","check":{"compare":"/absolute/proto8/lib/aos/box_check"}}' | aos-exec /absolute/proto8/lib/aos/measure
```

<details>
<summary>五個探測與注意事項</summary>

依序嘗試沙箱 `/tmp/aos-box-probe` 寫入、localhost:4000 連線、家目錄列舉、`/usr/bin` 列舉、工具小格往上兩層的 history 寫入。每段印 `R1` 至 `R5` 與結束碼，另以 `H`、`B` 標示可見路徑。第 5 條前印 `P5 <路徑>`，保留 `$AOS_STACK/../../history.jsonl` 原字串的 `../..`；比對器查主機上該路徑是否存在，不看 R5 的碼。比對器清除主機上的探測暫存檔並判零分。

`HOME` 不在沙箱預設環境清單中；因此 H 的 `$HOME/*` 在 boxed 裡會展開成 `/*`，列出沙箱根目錄。這忠實保留主圖的探測寫法，但該條只能檢查回傳結果未露出主機家目錄子項，不能單靠它證明家目錄不可存取。寫入、網路與執行檔清單仍各自獨立判定。

`check.json` 不固定 compare，因為其相對路徑會隨 defs 改變。measure 的工作區與工具小格均用暫存副本，勿對有重要資料的 live stack 直接跑逃脫探測。沙箱自己的 `/tmp` 寫入預期成功，隔離由主機端不存在該檔驗證。第 5 條同理：沙箱上層空殼可寫不代表逃出，主機 history 存在才判逃出並清除。

</details>
