# 痛在哪：可直接寫成子命令的需求
← [t5-agent-loop](README.md)｜[實測現場](record.md)

## `aos deliver [WORLD] [-f FILE|-]`

我需要 `aos deliver`，因為三支不同腳本現在都得自己做：驗證 object／array、產生 inbox 檔名、write-all 到 `.json.temp`、rename 成 `.json`、處理 rename／I/O 錯誤。檔名不能只有 PID：同 process 第二次投遞會覆蓋第一份，PID 重用也有同類風險。命令至少要：

1. 接受單一 instruction 或 array，發布前用唯一 parser 驗完整批次。
2. 用 PID＋單調 counter 或不可碰撞 nonce 產生名稱，建立 temp 時拒絕既有檔。
3. ready 發布不得覆蓋既有名稱；成功回 machine-readable delivery id、count 與 target。
4. 永遠內建 temp＋rename，不暴露「直接寫 ready」的捷徑。

## `aos recover [WORLD]`

我需要 `aos recover`，因為 `.runi` 現在只說「未完成」，腳本／人還得自己查看 batch、世界作用、外部 request id 與缺少的 exit，然後徒手 `mv`。命令不能假裝有 program counter；它應先唯讀列出 `.runi`、每筆 exit/result 證據與可能仍活著的未知子行程，再要求明示選一個動作：

- `--replay`：把整批放回 queue，醒目標示可能重複作用。
- `--abandon`：保留 forensic 副本並解鎖，不重跑。
- `--adopt RECEIPT`：已有可對帳結果時記錄採用，再解鎖。

沒有足夠證據時預設必須停住，而不是自動重播。

## `aos status --json [WORLD]`

我需要穩定的 `status --json`，因為實驗每一步都用 `find`、`test -f`、`cat` 手工拼出 `inst.json`／`.runi`／ready／temp／bad／各 instruction exit 的現況，很容易漏掉「子行程已完成但 exit 缺失」這種組合。輸出要區分 `ready`、`running`、`blocked-runi`、`bad-delivery`、`no-work` 與 `unknown-effect`，但不要把 prompt 政策塞進 status。

## `aos agent step [WORLD]`

我需要一支仍受限於具名工具 registry 的 `agent step`，因為目前 adapter 自己 parse 模型 JSON、把 tool name 映到固定 argv、拒絕未知工具、安排工具後的下一次模型、保存 raw／final。這支命令要保存至少 `request-published → effect-started → result-temp → result-published → next-delivered` 的 phase evidence；否則 SIGINT 後只剩 `.runi`，不知道是否可重試。它不應讓模型輸出的任意 argv 直通。

## `aos agent emit-context [WORLD]`

我需要一個只輸出穩定 context envelope 的命令，因為第二次模型呼叫目前由腳本自己選 `prompt.txt`、`tool-result.txt` 與人工修改，再重組輸入。輸出需帶 turn、source path／hash、上一個 tool result 與 request id；不負責寫 provider-specific system prompt，也不從 raw `aos exec` stdout 猜結果。
