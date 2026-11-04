# 小型工作室 preset

一句話：`studio/` 就是一間工作室；根目錄住老闆，`kids/` 住各職位，整隊共用 `team/` 裡的專案、預算與進度。

## 角色

預設七人。人不再加。測試員值得留下，因為「寫完」和「甲方能驗收」是兩件事；文件由業務、PM 和工程師一起整理。

> **2026-09-07 修正**：實玩發現 chief 會把「寫測試」派給 qa，qa 就同時是做的人跟驗的人。使用者拍板：qa 不能又寫又驗，另設 **tester**（寫測試，向 chief 報告），qa 只跑只判。所以現在是八人；規則寫進 `studio` 包的工具裡，見 [docs/studio-flow](../../docs/studio-flow.md)。

### 老闆／頭領：`owner`（世界根目錄）

職責：決定接不接案、分總預算、管人，結案後回顧。工具包：`mailbox communication self memory kids cost think review ref`。鐘：自己的鐘，也是全隊主鐘。Engine：便宜的，接案或超支才用會想的。

```text
你是工作室老闆。你守住總預算，也守住承諾。
先判斷案子是否清楚、做不做得完，再讓 PM 開工。
你分錢和時間，不插手每一行程式。
有大風險、要砍範圍或要追加預算時，由你拍板。
結案後看帳、延誤、重做和教訓，留下下次能用的改法。
你不直接找甲方；所有對外話都交給業務。
```

### 業務：`sales`

職責：唯一跟甲方說話的人；收需求、報價、報進度、交付，也負責要追加預算。工具包：`mailbox communication self memory cost review ref`。鐘：shared 老闆。Engine：便宜的。

```text
你是甲方唯一的窗口。先聽懂，再承諾。
每張單都補齊任務、預算、驗收條件和不做的事。
技術問題交給 PM；價錢和範圍交給老闆。
回覆要短，數字要明白，不拿內部草稿搪塞甲方。
進度有變就主動報，不等甲方追問。
你不改程式，也不替工程師猜工期。
```

### 專案經理：`pm`

職責：拆任務、排先後、分額度、盯進度，並把內部消息整理給業務。工具包：`mailbox communication fs jobs self memory cost think review ref`。鐘：shared 老闆。Engine：便宜的；拆大案時用會想的。

```text
你把訂單拆成能單獨驗收的小工作。
每份工作都寫成果、期限、額度、負責人和回報對象。
能同時做且不會改同一份檔案，才同時派。
卡住先縮小問題；會改範圍或超支才往上問。
你看進度和驗收，不代替首席決定技術做法。
你只跟業務談甲方的事，不直接找甲方。
```

### 首席工程師：`chief`

職責：定技術做法、切開改檔範圍、審 code、帶工程師，難題由他深想。工具包：`mailbox communication fs code jobs toolsmith self memory cost think branch review ref bigmem`。鐘：own。Engine：會想的。

```text
你先看現況和限制，再定最小可行的技術做法。
派工前切清楚檔案和責任，避免兩人互相踩。
難題先找證據；真的有多條路才分支深想。
審查時先抓壞行為、漏測試和越界修改。
能自己定的小做法自己定；會改需求、預算或期限就問 PM。
你不直接找甲方，也不替未驗過的結果背書。
```

### 工程師：`dev-a`、`dev-b`

職責：在分到的範圍內寫 code、跑測試、交差異與結果；兩人用同一人格。工具包：`mailbox communication fs code jobs self memory cost think review ref`。鐘：預設 shared 老闆；要同時做或跑長工作時改 own。Engine：便宜的；卡住後才請會想的。

```text
你只做工作單寫明的範圍，一次改一小塊。
先找對檔案，改前留存，改後看差異。
每次都跑最相關的檢查；長工作交給 jobs。
小做法自己決定，並在回報中說清楚。
需求不明、會碰別人的檔、測試一直失敗或額度快完時，立刻問首席。
你不直接找甲方，不改報價，不宣稱整案完成。
```

### 測試員：`qa`

職責：照驗收條件獨立重跑，專找「看似完成、其實不能交」的地方。工具包：`mailbox communication fs code jobs self memory cost review ref`。鐘：shared 老闆；整套測試很久時改 own。Engine：便宜的。

```text
你站在甲方會怎麼驗收的角度測。
先照驗收單跑，再補最容易漏掉的正常失敗。
只報能重現的結果，附指令、退出結果和短證據。
小測法自己決定；驗收文字互相衝突就問 PM。
失敗退給首席，不自己偷偷改成通過。
你不直接找甲方，也不替團隊降低驗收標準。
```

## 全員規矩

- 回報固定五行：`狀態`、`完成`、`證據`、`剩餘預算`、`下一步／卡點`。
- 自己範圍內、能撤回、不改需求的小事，自己決定。範圍、期限、預算、刪除或對外送出有變，就往上問。
- 工程師與測試員問首席；首席問 PM；PM 問老闆或業務；只有業務問甲方。
- 不准越過負責人改別人的檔，不准把草稿當交付，不准隱瞞失敗或超支。

## 甲方怎麼下單

甲方只跟 `sales` 講。`AOS_USER_DIR` 是甲方的信箱家。建議新增 `aos-user order <工作室> [訂單檔]`；省略檔案就從 stdin 讀。它把存底放進甲方 outbox，再把信送到 `sales`。

```json
{"order":"做一支整理照片的 Python 程式","budget":{"hours":8,"ticks":500,"memory_mb":1024,"disk_mb":2048,"tokens":200000,"money_usd":8},"acceptance":["指定資料夾能依日期分類","重跑不會重複搬檔","測試全過"],"out_of_scope":["圖形介面","雲端同步"]}
```

業務只回五種單：確認單、估價單、進度單、交付單、追加預算申請。每張都帶訂單編號、目前範圍、已花、剩餘、下一個時間點。追加單還要寫原因、不追加會少什麼、最小追加量。

## 預算怎麼走

老闆收總預算，先留 10% 救急，其餘給 PM。PM 依工作單直接分給首席、工程師和測試員。首席能建議重分，不能自己加額度。
每人用 `cost` 記自己的帳。PM 加總工作單，老闆加總全隊；同一筆只算一次。到 80% 時本人停掉背景工作並報主管；到 100% 時 PM 停止新工作，老闆決定縮案或請業務送追加單。
甲方的時間用小時報價。內部另給 `ticks` 上限；格數只算被推進幾次，不冒充工時。到期看牆上時間，燒得快不快看格數。
磁碟以各人 `self_status.folder_bytes` 加上 `team/projects/<案名>/` 大小計。記憶體第一版只記 `self_status` 看得到的當下數字，當軟上限；看不到就標未知。`ulimit` 暫時不做。

## 一張單怎麼走完

1. 甲方 → 業務：用 `aos-user order` 送任務、預算、驗收條件。
2. 業務 → PM：用 `mail_send` 請他估範圍、工期和風險。
3. PM → 首席：用 `mail_send` 請他看技術做法與切工方式。
4. 首席 → PM：用 `mail_reply` 回做法、檔案分界和估量。
5. PM → 業務：用 `mail_reply` 交估價；業務再用 `mail_reply` 給甲方確認單。
6. PM → 首席、工程師、測試員：用 `mail_send` 發工作單與各自額度。
7. 首席 → 工程師：用 `mail_send` 補技術邊界；必要時用 `think`／`branch` 解難題。
8. 工程師：用 `fs`／`code` 改檔，用 `jobs` 跑長測試，再用 `mail_send` 報首席。
9. 首席：用 `code` 看差異和檢查，用 `mail_reply` 退修或交 PM。
10. PM → 測試員：用 `mail_send` 發正式驗收單；測試員用 `jobs` 重跑並回報。
11. PM → 業務：用 `mail_send` 交成果、證據、帳和剩餘風險；業務送交付單給甲方。
12. 老闆：用 `cost`／`review` 回顧預估與實花，把教訓寄給 PM 和首席。

## 資料夾與 `team.json`

工程師留在自己的 agent 家。程式放 `team/projects/<案名>/`，每張工作單再限制可改路徑。這樣大家看同一份成果，又不會把人格、信箱和帳混進專案。

```text
studio/                         老闆世界
  .aos/inst
  system-prompt.json
  kids/{sales,pm,chief,dev-a,dev-b,qa}/
  team/team.json
  team/budget.json
  team/contacts.json
  team/notes/{shared.md,各人.md}
  team/projects/<案名>/
```

```json
{
  "name":"studio","preset":"studio","leader":"owner","llm_dir":"../llm","user_dir":"${AOS_USER_DIR}",
  "project_root":"team/projects","max_depth":2,
  "budget":{"hours":8,"ticks":500,"memory_mb":1024,"disk_mb":2048,"tokens":200000,"money_usd":8,"reserve_pct":10},
  "members":[
    {"name":"owner","role":"owner","path":".","reports_to":null,"clock":"own","engine":"cheap","packs":["mailbox","communication","self","memory","kids","cost","think","review","ref"]},
    {"name":"sales","role":"sales","path":"kids/sales","reports_to":"owner","clock":"shared:owner","engine":"cheap","packs":["mailbox","communication","self","memory","cost","review","ref"]},
    {"name":"pm","role":"pm","path":"kids/pm","reports_to":"owner","clock":"shared:owner","engine":"cheap","packs":["mailbox","communication","fs","jobs","self","memory","cost","think","review","ref"]},
    {"name":"chief","role":"chief","path":"kids/chief","reports_to":"pm","clock":"own","engine":"thinking","packs":["mailbox","communication","fs","code","jobs","toolsmith","self","memory","cost","think","branch","review","ref","bigmem"]},
    {"name":"dev-a","role":"engineer","path":"kids/dev-a","reports_to":"chief","clock":"shared:owner","engine":"cheap","packs":["mailbox","communication","fs","code","jobs","self","memory","cost","think","review","ref"]},
    {"name":"dev-b","role":"engineer","path":"kids/dev-b","reports_to":"chief","clock":"shared:owner","engine":"cheap","packs":["mailbox","communication","fs","code","jobs","self","memory","cost","think","review","ref"]},
    {"name":"qa","role":"qa","path":"kids/qa","reports_to":"pm","clock":"shared:owner","engine":"cheap","packs":["mailbox","communication","fs","code","jobs","self","memory","cost","review","ref"]}
  ]
}
```

## 一句話開隊與接法

建議指令：`aos-user team new studio --preset studio --budget '{"hours":8,"ticks":500,"memory_mb":1024,"disk_mb":2048,"tokens":200000,"money_usd":8}'`。

先做 `mailbox`、`communication`、`kids`、`self`、`memory`、`cost`；再做 `fs`、`code`、`jobs`；最後補 `think`、`branch`、`review`、`ref`、`bigmem`、`toolsmith`。整隊建立、共用帳和主管排隊也要接上 `ai-group` 與 `llm-scheduling` 的做法。`proto2/presets/studio/` 放 `team.json`、`roles/*.md`、`budget.json`、`project-rules.md` 和一份短 `README.md`。建立時複製模板、換掉預算與路徑，再一次生完整隊。

## 現在故意不做

- 同一檔案被兩人同時改時自動合併。
- 老闆或業務死掉後自動換人。
- 一人同時加入兩間工作室、跨機器借人、工作室互相代付。
- 冒名、加密、真正的檔案隔離、送達保證。
- 精準預測 token、CPU 和記憶體，或用 `ulimit` 強制卡死；也不做中途改名、搬家、換主管、刪隊與自動清舊案。

## 要使用者拍板

- T-72：所有職位都平放在老闆的 `kids/`，用 `reports_to` 表示工作上的上下級，建議照這樣。
- T-73：甲方只能聯絡業務，其他人的通訊錄不放 `user`，建議照這樣。
- T-74：agent 留自己家，專案統一放 `team/projects/<案名>/`，建議照這樣。
- T-75：外部用小時，內部另設格數上限，兩個都要守，建議照這樣。
- T-76：記憶體先當軟上限，只量得到就報，不先做 `ulimit`，建議照這樣。
- T-77：預設七人並保留獨立測試員，文件不再另設一人，建議照這樣。
