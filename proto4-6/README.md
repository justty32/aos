← [proto4-3](../proto4-3/README.md)（inst.json 與 kernel）｜[逐步 lisp](../proto4-4/README.md)

# proto4-6 — 逐步 JSON

`aos-step-json` 是給 AI 寫、給人看的最簡逐步程式：一個 JSON 陣列，每個元素是一份 inst，每叫一次只跑下一份。

## 一份完整程式

把下面存成 `job.json`：

```json
[
  {
    "note": "第一格：寫一份資料",
    "argv": ["sh", "-c", "printf 'hello\\n' > message.txt"]
  },
  {
    "note": "第二格：讀它，再留下結果",
    "argv": ["sh", "-c", "tr a-z A-Z < message.txt > result.txt"]
  },
  {
    "note": "第三格：清理中間檔",
    "argv": ["rm", "message.txt"]
  }
]
```

`note` 只給人和 AI 看，執行前會拿掉。其餘七欄完全就是 proto4-3 的 inst.json：`argv` 必填，另有 `cwd`、`stdin`、`stdout`、`stderr`、`exit`、`envs`。

## 怎麼跑

```sh
/abs/proto4-6/aos-step-json job.json   # 跑第 0 格
/abs/proto4-6/aos-step-json job.json   # 跑第 1 格
/abs/proto4-6/aos-step-json job.json   # 跑第 2 格
/abs/proto4-6/aos-step-json job.json   # 已做完，不再執行；回 100
echo $?                                # 100

/abs/proto4-6/aos-step-json job.json --status
/abs/proto4-6/aos-step-json job.json --reset
```

看不到子程式的錯誤時，加 `--stderr -`；也能給路徑，原樣轉給 aos-exec：

```sh
/abs/proto4-6/aos-step-json job.json --stderr -
```

## 狀態檔

`job.json` 的狀態放在同資料夾的 `job.state.json`：

```json
{"pc":2,"n":3,"done":false,"src":{"n":3,"sha256":"..."},"last":{"pc":1,"exit":0,"kind":"child","at":"2026-09-13T12:00:00+00:00","ms":12},"history":[{"pc":0,"exit":0,"kind":"child","at":"...","ms":3}]}
```

`pc` 是下一格的 0 起算編號；`last` 是上一次結果；`history` 只留最近 50 次。狀態與送給 aos-exec 的 `.aos-step-json/current.json` 都先寫 `.tmp` 再 replace，不會露出半份 JSON。還沒有狀態檔時，`--status` 會印 `{"pc":0,"n":3,"done":false}`。

## 規則

- 子程式回 0：`pc` 加一。最後一格仍回 0，但狀態已是 `done:true`；下一次呼叫開始回 100。
- 子程式回非 0：`pc` 不動，原碼退回；修好後再叫就是重跑同一格。
- aos-exec 自己失敗回 125；用法或逐步 JSON 格式錯回 2；兩種都不推進。
- 沒寫 `cwd` 就用 `job.json` 所在資料夾；相對 `cwd` 也從那裡算。其他相對路徑仍照 inst 規則，以轉完的 cwd 為準。
- 每次都重讀整份程式。`pc > 0` 時內容的 SHA-256 對不上會警告，但仍照目前 `pc` 跑；確定要重來才用 `--reset`。
- `--reset` 只刪狀態檔，不刪程式產物，也不刪 `.aos-step-json/current.json`。

## 放上 kernel

行程 inst.json 可以這樣寫：

```json
{"argv":["/abs/proto4-6/aos-step-json","job.json"],"cwd":"/abs/那個資料夾","stderr":"err.txt"}
```

kernel 每格叫一次；全部完成後 `aos-step-json` 回 100，kernel 就把行程收進 `procs/done/`。

## 沒做什麼

這裡沒有變數、條件或迴圈，只有依序執行。那些是下一階段「逐步 Python」的事（來源筆記 §23.2）。也沒有鎖，同一份程式不要同時叫兩次。

## 出處

定案與使用者原話在 [proto4 筆記 §23](../proto4/notes/23-step-json-python.md)；inst 的完整語意見 [proto4-3 exec 文件](../proto4-3/docs/exec.md)。
