# LLM 排隊優先度

LLM 世界每一格都會重排。舊數字還能用。新工作建議用 priority 物件。

## 會用到的介面

- `aos_llm.write_request()`：程式丟請求時用。`priority` 可給數字或物件。`requester` 寫誰丟的。
- `aos-llm ls`：想知道誰排前面、為什麼插隊時用。
- `aos-llm exec`：LLM 世界每一格自己叫。人通常不用手動叫。
- `aos-llm usage`：看今天按模型、按 requester 分開的用量。
- `aos-llm usage --by requester`：只看誰用了多少。

## priority 怎麼寫

```json
{
  "priority": {
    "level": 5,
    "deadline": "2026-09-06T22:00:00+08:00",
    "kind": "chat",
    "requester": "group-a/kid-1",
    "cost_class": "normal",
    "age_boost": 1
  }
}
```

- `level`：通常填 0 到 9。越大越急。預設 0。
- `deadline`：最晚開工時間。要帶時區。沒有就不填。
- `kind`：`chat`、`tool`、`think`、`background`。預設 `chat`。
- `requester`：建議寫 `集團/agent`。沒有斜線就整串算一個集團。
- `cost_class`：`cheap`、`normal`、`expensive`。以引擎設定為準。
- `age_boost`：每等一分鐘加幾分。預設 1。請求只能比資料夾預設低。

舊寫法仍可用：

```json
{"priority": 5}
```

它等於只寫 `{"level": 5}`。舊數字不會被限制在 0 到 9。

## 怎麼排

過期的 deadline 一定排在未過期的前面。其餘分數是：

`level × 100 + kind 分 + 等待分 - 費用分 - 近期占用分`

- kind：chat `+40`、tool `+20`、think `0`、background `-40`。
- 等待：等待分鐘乘 age_boost。最多 `+300`。
- 費用：cheap `0`、normal `-10`、expensive `-30`。
- 近期占用：同一集團在最近 10 次開工中，每次 `-25`。

最後看分數高、檔案較早、檔名較小。每成功開一筆，近期紀錄立刻更新，剩下的再算一次。某台引擎滿了，不會擋住別台。

`aos-llm ls` 會顯示這種理由：

```text
score=465 level=5 chat +40 wait=10 normal=-10 recent=-75 requester=group-a/kid-1
```

過期的會多一個 `deadline=late`。

## 預設設定

`defaults.json` 可以繼續放數字，也可以放物件：

```json
{
  "engine": "local",
  "priority": {"level": 0, "kind": "chat", "age_boost": 1, "cost_class": "normal"}
}
```

引擎知道自己的價格時，在 `engines.json` 那台旁邊寫 `"cost_class": "cheap"`。排程不信請求自己喊便宜。

## 用量帳本

新帳本有兩層：

```json
{"by-model": {"網址|模型": {}}, "by-requester": {"group-a/kid-1": {}}}
```

`requester` 先讀請求資料。沒有才拿檔名前綴。`aos-llm usage` 也讀得懂舊的平鋪帳本。

## 已知坑

- 已開跑的請求不會重排，也不會取消。
- 不處理兩台機器時間不同、時間倒退、requester 冒名。
- 大量排隊時，每開一筆都會重讀分數。先求簡單，還沒為效能加索引。
