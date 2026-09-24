← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 3. 門

1. 逐條解（中心 agent 家）、逐條看到了沒（[agent.md §4.2](../agent/state.md)）。解不開＝讀驗錯，退 1。
2. 有到了的：取一個新的消費 id，**一次寫** `state.json`——到了的條目從 `waits` 劃掉（按索引），其中開 `consume` 的，把要搬的檔（資料夾就是當下裡面所有 `*.json`）
   以 `{"src": 絕對路徑, "dst": 封存名}` 加進 `consuming`（封存名見 [agent.md §4.1](../agent/state.md)：`<src 所在資料夾>/done/<src 檔名>.<消費 id>.done`（09-24 試玩 r1 補））。然後照第 2 節第 2 步搬、清 `consuming`。
3. 表還有剩＝退 101（有劃掉的已經寫回，進度留著）；表空了＝往下走。

崩在「劃掉」之後、搬完之前：`consuming` 裡有記，下次第 2 步補做，不會又被同一道門關住；已經搬過的（`dst` 在）不會再去動原路徑上新放的同名檔。
人要它暫停：加一條指到不存在的檔（例如 `{"$opt":"consume","$val":"continue.json"}`）；要它繼續：touch 那個檔。
門關著時當批也不收：回音留在 K，開門後再收。

# 4. `batch` 是 `null` 時照 `state` 走

| 現在是 | 情況 | 做什麼 | 退出碼 |
|---|---|---|---|
| `idle` | `intake` 非 null，或 `input` 有東西 | 收輸入（§8），state 改 `think` | 0 |
| `idle` | 都沒有 | 不動 | 101 |
| `think` | — | 建一批 think、送出（§5） | 0 |
| `act` | 記憶尾巴是帶非空 `tool_calls` 的 `assistant` | 建一批 act、送出（§5） | 0 |
| `act` | 其他 | 沒東西可跑：state 改 `think` | 0 |
