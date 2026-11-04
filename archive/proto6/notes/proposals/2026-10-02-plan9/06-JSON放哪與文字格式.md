# 六、JSON 放哪裡合適、哪裡該用一行文字

← [提案入口](README.md)｜上一份：[agent 與 kernel 的視野](05-agent與kernel的namespace.md)｜下一份：[推到極限與代價](07-推到極限與代價.md)

使用者的前提是「JSON 仍可當通用格式」。Plan 9 沒有 JSON，但也不是純文字（draw、stat、AuthInfo 都是二進位）。Linux 自己的分界線是：**設定與控制用字串檔；要原子性、型別、結構的地方用別的**。照這條線切：

## 分界原則

| 這種東西 | 用 | 理由 |
|---|---|---|
| **指令**（wake、pause、reload、connect） | 一行文字，空白分隔 | 動詞加幾個旗標，不需要巢狀；`echo` 就能送；Plan 9 ctl 檔慣例 |
| **狀態一行能講完的**（status、usage、exit） | 一行 `key=value` | `cut`、`awk` 就能切；daemon stdout 已經是這格式 |
| **一個值一個檔**（ran、seq、exit） | 純數字或字串加換行 | 現在 `ran.json` 就是一個數字；去掉引號跟 `.json` 就是了 |
| **存在與否就是意思**（擋板、鎖、`/llm` 在不在） | 空檔或目錄 | 第十六批已裁 |
| **訊息**（信、summary、grant、request） | **JSON**，一行一封 | 多欄位、巢狀、要 schema；plumber 的訊息也是多欄位，只是用自家格式 |
| **設定檔**（tasks.json、daemon 設定、inst、agent.json、tools.json） | **JSON** | 人寫一次、程式整份讀；要 `$ref`、要 schema、要原子快照（[04](04-tick與inst變成目錄.md)講過目錄版的壞處） |
| **LLM 請求與回應** | **JSON**（OpenAI 本文原樣） | 外部世界規定的格式，不碰 |
| **紀錄裡的陣列**（task-exits、hook-exits） | 兩者皆可；建議**一行一筆文字** | `id=report index=1 exit=3` 一行一項，`grep exit=` 就能查；要驗再轉 |

一句話：**動詞與單值用文字，名詞與結構用 JSON**。

## 錯誤怎麼回：三個選項

現在 `{"ok":false,"error":"stopped","detail":"…"}`。寫檔沒有「回應」這個位置，只有 errno。

| 選項 | 樣子 | 好 | 壞 |
|---|---|---|---|
| a. 只用 errno | `write: EBUSY`（stopped）、`ENOENT`（unknown_inst）、`EINVAL`（bad_request） | 零發明；shell 的 `$?` 就能判 | 代碼對應要查表；`detail` 沒地方放 |
| b. errno＋`error` 檔 | 同上，再 `cat /aos/me/error` 看最後一次失敗的一行 | 保留白話 | 多一次讀；多人同時失敗會蓋 |
| c. rpc 檔（Plan 9 factotum 式） | 同一個 fd：write 請求、read 回應 `ok` 或 `error stopped: …` | 最接近現在的「一問一答」 | 要 `open` 一次拿一個對話；`echo > ctl` 這種一行式沒了 |

建議 **a 為主、b 補白話**。理由：C-08 說「0 預料之中、非 0 要處理，讀別人的碼只分 0 與非 0」——errno 剛好對上這個粗度，細節本來就只是給人看。

## 寫成例子

`/aos/d/insts/a/status`（一行）：

```text
inst=a running=0 pending=0 paused=0 stopped=0 last_exit=0 last_end=2026-10-02T15:04:05+08:00 next=2026-10-02T15:05:05+08:00
```

`/aos/d/insts/a/tick/current/task-exits`（一行一筆）：

```text
id=report index=1 exit=3
id=clean index=2 signal=9
```

`/aos/d/insts/a/inbox`（一行一封 JSON，讀完取走）：

```text
{"type":"grant","version":1,"to":"agents/bob","kernel_seq":1203,"llm":{"calls":20,"tokens":50000,"window_ticks":10}}
{"type":"say","version":1,"from":"agents/amy","text":"x.md 算好了嗎？","ref":"amy-7"}
```

`/llm/N/usage`（一行）：

```text
prompt=51230 completion=8120 ms=4210
```

`/llm/N/ctl`（一行一指令，可寫多次）：

```text
model deepseek-chat
temperature 0.2
timeout 120000
```

## `key=value` 一行的規矩（推想，若採用要寫進 conventions）

- 空白分隔、`key=value`、值裡不准有空白與換行；要放句子就另開一個檔（Plan 9 的 `note` 也是這樣分開放）。
- 讀的一方不認得的 key 直接忽略（對上 C-07）。
- 布林寫 `0`／`1`，不寫 `true`／`false`（`awk` 好比）。
- 時間點照 C-01：格數用 `seq`、毫秒用 `_ms`、牆鐘只給人看。

## schema 怎麼辦

JSON 的那幾類照舊用 JSON Schema。一行文字的部分，schema 驗不了；兩個做法：

1. 不驗。這是 Plan 9 的做法，也是「默認一切正常」的做法——讀錯就讓程式自然丟錯。
2. 寫一支 `aos-fmt-check <種類>` 讀 stdin 驗一行，測試裡用。大約五十行 Python。

建議 1，理由同上。真要驗的東西本來就該是 JSON。

## 跟現有 spec 衝突的地方

- P-002「一份檔案或一行訊息恰好一個 JSON object」——inbox 一行一封仍合；status 與 task-exits 改文字就不合，要加一條「一行文字檔」的規矩。
- `tick-record` schema 驗的是展開後的 `record.json`；task-exits 改文字後 `$ref` 指不到 JSON，`aos_tick_record.read_record()` 要多認一種格式。這是改程式，不是改原則，但要承認工作量。
- C-10 的環境變數表會砍掉 `AOS_DAEMON_*` 三組（換成 `/aos/me`），`AOS_TICK_CWD`、`AOS_TASK_*`、`AOS_HOOK_*` 保留（tick 短命，不值得為它開樹）。
