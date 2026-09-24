← [kernel](README.md)｜[spec 總導航](../README.md)

# 1. 家

```text
K/
  info.json                 身分、daemon 家、cpu 表、排程預設；人寫的
  state.json                帳本（§1.2）
  requests/ responses/      syscall（範式 §3）
  cpus/<name>/              每顆 cpu 的家（各自 info／state／requests／responses／inst.json）
  kernel.log                每格 append
```

`K/` 的主人是「當下正在跑的那一格 tick」（鏈保證同時只有一格，§7）；外人只能往 `requests/` 放單、
讀 `responses/` 然後放 `ack`；`state.json` 隨便偷看。`K/cpus/<name>/` 各是另一個家，主人是那顆 `aos-cpu`；
kernel 對它們也是外人，**只在家不存在時**替它們建家、寫 `info.json` 與 `inst.json`（初始化，不算動別人的家）；
已經有的一律不改寫，人可以自己編那顆的 `inst.json`（例如加環境變數，見 §1.1 `envs`）。
沒有 `procs/` 資料夾：行程紀錄全在帳本裡。

## 1.1 `info.json`

```json
{
  "_metainfo": {"_type": "kernel", "_version": 1},
  "daemon": "/abs/D",
  "cpus": {"k": {"pool": "kernel"}, "0": {}, "1": {},
           "llm": {"pool": "llm",
                   "envs": {"PATH": {"$fmt": {"$val": "/abs/tools/llm:${p}", "p": {"$env": "PATH"}}},
                            "LMSTUDIO_KEY": {"$env": "LMSTUDIO_KEY"}}}},
  "tick_ms": 1000,
  "interval_ms": 1000,
  "timeout_ms": 0,
  "done_exit": 100,
  "bad_after": 10
}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `daemon` | 絕對路徑 | boot 寫 | daemon 家；tick 靠它找 daemon |
| `cpus` | 物件 | 必填 | key 是 cpu 名（也是 `cpus/<name>/` 的資料夾名、給 daemon 的孩子名）；值 `{"pool": 字串, "envs": 物件}`，`pool` 沒寫＝`"default"`，`envs` 可省。**恰好一顆** pool 是 `kernel`（少於或多於一顆＝`FieldTypeMismatch`），一般行程不准進這個池 |
| `cpus.<c>.envs` | inst 的 `envs` 格 | 無 | kernel 建那顆的家時原樣抄進 `cpus/<c>/inst.json` 的 `envs`（含 `$opt` 選項）——這就是「這顆 cpu 帶什麼環境」（範式 §4.1）。家已經在就不管它 |
| `tick_ms` | 非負整數 | 1000 | 一格睡多久（§3 第 3 步） |
| `interval_ms` | 非負整數 | 1000 | 行程 `interval_ms` 的預設 |
| `timeout_ms` | 非負整數 | 0 | 行程 `timeout_ms` 的預設；tick 自己不限時 |
| `done_exit` | 0～255 | 100 | 反覆行程回這個碼＝完成；0＝關掉 |
| `bad_after` | 非負整數 | 10 | 連續失敗幾次退件；0＝關掉 |

整份解指示詞，中心是 K，不提供 `$opt`（`envs` 那格例外：它是要抄進 inst 的，原樣留著不解）。
**頂層必須是字面物件**（頂層整份 `$ref` ＝ `FieldTypeMismatch`），不然 boot 寫進去的 `daemon` 會被引用吃掉。
boot 把整份驗完才動任何東西（§6）。「專門打 LLM 的 cpu 只開一顆」就是開一顆 `{"pool":"llm","envs":…}`、
把 `aos-llm call` 那種行程標 `pool: "llm"`。要幾顆就寫幾顆，佔著沒關係。
改 info 之後：tick 每格重讀；多出來的 cpu 下格會拉，被拿掉的 cpu 若帳本裡還有 `req`，照樣收完那則才忘掉它；
池裡沒有 cpu 的行程就一直排隊，不算錯，`ls` 看得出。**kernel 池那顆例外**：帳本裡釘死的 `kcpu` 才算數，
改 info 不會換，要換就重 boot。

**要改一顆已經存在的 cpu 的環境**：`envs` 只在第一次建家時抄進去；之後得 `aos-kernel halt`、等那顆 cpu 退出
（`D/state.json` 裡消失），改 `K/cpus/<c>/inst.json`，再 boot。只改 info、或對還活著的 cpu 重 boot，環境都不會變。
那份 inst 裡的 `$env` 讀的是**daemon 的環境**（是 daemon 在拉它）；在別的終端 `export` 不會影響已經在跑的 daemon。

（09-24 補）「建家」是**缺的補齊**：資料夾、`info.json`、`inst.json` 各自不在才寫，已經在的一律不覆蓋（含人手改過的 `envs`）。
所以建到一半崩掉，下一格第 7 步或下次 boot 會補齊，不會卡住。
