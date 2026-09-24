← [team](README.md)｜郵差：[post.md](post.md)｜申請：[mail.md](mail.md)

# 短期獨佔鎖：`lock` 工具、`aos-team lock`

第二波 C 隊，2026-09-24。給多工人同一個專案用：想改同一個檔或資料夾之前先搶一把鎖，別人搶不到就直接知道誰拿著。
程式：[`lib/aos_team_lock.py`](../../lib/aos_team_lock.py)（申請 `kind: lock` 的處理函式 `on_lock`）；工具：[`tools/task/lock`](../../tools/task/lock)。

## 為什麼是非同步的（模型那一端）

catalog.md 的草案設想「acquire 拿不到立即回 Busy、不等」，但模型端**沒有同步等待這種東西**：
工具送出去這一輪就結束，回信是下一輪的新輸入（跟這個團隊裡其他工具一樣）。所以模型用的 `lock` 工具，三種操作
（`acquire`／`release`／`ls`）全部走 outbox → 郵差 → 回信，跟 `ask_human`／`compact_me` 同一套路，
不是另外開一條同步通道。「拿不到立即知道」變成「下一輪的信就是結果」，一樣快，只是隔了一輪。
**人不受這個限制**：`aos-team lock ls` 直接讀 `team/locks/`（見下面〈人的指令〉），是同步的；
astra 審查 S2 問過要不要也給模型一個同步唯讀的 `ls`（像 `board` 讀 `team/tasks/`）——可以，但要多開一個保留
mount 名字（B 隊 access.json 地盤），這一版沒做，列進 §6〈給其他隊〉。

## 一個檔＝一把鎖

`team/locks/<名>.json`，只有郵差寫：

```json
{"name": "docs/WORKFLOWS.md", "owner": "worker-1", "acquired_at": "2026-09-25T10:00:00+08:00",
 "expires_at": "2026-09-25T10:30:00+08:00", "ttl_seconds": 1800, "why": "改共用檔",
 "request": "<acquire 申請 id>", "effects": […],
 "released_at": null, "release_request": null, "release_effects": []}
```

鎖的名字不是成員名，是「檔或資料夾的識別碼」：英數與 `. _ - /`、可含中文，不能以 `/` 開頭、不能含 `..` 段，上限 200 字
（例如 `docs/WORKFLOWS.md`、`shared-config`）。跟實際檔案系統路徑沒有強制對應——名字只是雙方講好的識別碼，
郵差不會去 `p/` 底下確認那個檔真的在。

**檔名不是名字本身**（09-24 astra 審查 M2 修）：名字可以含 `/`、中文，直接拿來當檔名會撞「要先建子目錄」
「`.hidden` 被 `json_files` 排除」「檔名位元組長度上限」三個坑；改成用 `sha256(名字)` 當固定長度、平面、
非隱藏的檔名（`Layout.lock()`），原名存在 JSON 內容的 `name` 欄位裡，`ls`／`describe` 都讀內容不讀檔名。

## 申請 `kind: lock`

`{"id", "from", "kind": "lock", "at", "op": "acquire"|"release"|"ls", "name"?, "why"?, "ttl_seconds"?}`。
`name` 在 `acquire`／`release` 才要；`ls` 不用。`ttl_seconds`（只有 `acquire` 收）：60～86400，沒寫＝1800（30 分）。

- **acquire**：鎖不存在、或沒人拿著、或**已過期**、或**就是同一個持有者**（續租）→ 取得，回一封 DONE「取得鎖 …（到期 …）」。
  否則丟 `TeamError('Busy', …)`，郵差照共同規則搬進 `outbox/<名>/rejected/`、退一封 FAILED 給寄件人，文字裡有現在誰拿著、到期時間。
- **release**：持有者本人，或鎖已過期（誰都能幫忙清）→ 放掉，回一封 DONE。不是持有者、也還沒過期＝`NotOwner`；
  沒有這把鎖＝`NoSuchLock`。
- **ls**：回一封 DONE，內容是所有鎖一行一把（`名字  持有者 拿著（到期 …）  理由`，沒人拿著寫「沒人拿著」）。
- **逾時自動放**：`acquire`／`release` 都不用另外檢查「持有者的 agent 還在不在」——過期就是過期，下一個 `acquire` 直接拿走。
  這比 catalog 草案的「郵差確認持有者已撤銷、state.json 沒有在途工具才收」簡單：那個做法要跨到 agent 家去看 `state.json`，
  這裡只看時間，代價是持有者真的還在用、但忘記續租時會被搶走——**代裁**：這一版先用時間（簡單、可預期），
  真的要延長就再 acquire 一次續租；使用者要翻案的話再加跨 agent 檢查。
- **冪等**：同一份 `acquire` 申請（看鎖檔的 `request`）、同一份 `release` 申請（看 `release_request`）重跑回同一份效果。
- **到期時間不信申請裡的 `at`**（09-24 astra 審查 M1 修）：跟 `on_ask`／`on_routine` 不一樣，`expires_at` 一律用
  郵差自己的時鐘算，不用 `req['at']`——`at` 是寄件人（模型）自己填的，若拿它算到期，模型能在自己 outbox 塞一份
  帶未來時刻 `at` 的申請，把鎖的到期日推到很遠、繞過 `ttl_seconds` 上限。

## 人的指令

- `aos-team lock ls [--json]`：直接讀 `team/locks/`（唯讀，不用等郵差，跟 `aos-team task show` 一樣）。
- `aos-team lock acquire NAME [--why 文字] [--ttl 秒]`／`aos-team lock release NAME`：往 `team/outbox/human/` 放申請，
  印「已交給郵差」；結果要看下一次 `aos-team mail` 或 `aos-team lock ls`。
