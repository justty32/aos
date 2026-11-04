# event：外部事件要「盡快」被處理

跑：`python3 proto7-1/probes/run_all.py event`（約 13 秒）。

## 是什麼

probe.py 扮外部腳本，隨機間隔（0.35～1.2 秒）丟 12 個事件 `<node>/inbox/evt-N.json`（內容帶丟檔時間），同時丟給七個 node，每個 node 一種處理法，處理完記 `handled.jsonl`：

| node | interval | 寫法 |
|---|---|---|
| `watch` | 200 | keep 常駐任務自己每 10 ms 看 inbox（不靠 tock） |
| `tock200` | 200 | keep 常駐任務每收到 tock 看一次 |
| `each200`／`each2000` | 200／2000 | 每回合起一個 each 任務處理完就結束 |
| `ichg` | 2000 | 丟檔時把 timeline.json 改成 50 ms，處理完改回 |
| `rescan` | 2000 | 丟檔時寫 daemon ctl：rescan＋pause＋resume |
| `poke` | 2000 | 丟檔時把 timeline.json 改名，等 daemon 當 node 消失，再改回來 |

另外 `pokemid` 在回合中途（任務還在跑）做同樣的 poke 兩次。

## 結果（延遲 ms，p50／max）

- `watch` 3／6：跟 interval 無關。
- `tock200` 131／195、`each200` 115／182：約 interval 的一半，最慢一個 interval。
- `each2000` 955／1907：同上，放大 10 倍。
- `ichg` 905／1636：**改 interval 沒用**，目前這回合的結束時間在 tick 時就算好了。
- `rescan` 957／1908：跟 each2000 一樣，**rescan、pause＋resume 都催不動**。
- `poke` 66／82：**唯一催得動的是 hack**，node 重新出現時新時間線立刻 tick。代價：每次 log 多一對 `node-`／`node+`。在回合中途做（`pokemid`），那兩個回合**永遠沒有 tock**（rounds.jsonl 缺第 6、8 回合），任務收不到那回合的 tock.json。
- 沒事件時 each200 照樣每回合起一個 Python（一秒 5 個），tasks.json 沒有「有檔才起」的條件。
