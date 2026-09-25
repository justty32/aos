← [team](README.md)｜目錄 [catalog D 節 T-spawn](../../notes/2026-09-24-tool-era/catalog.md#t-spawn)｜報告 [w3a](../../notes/2026-09-24-tool-era/w3a/README.md)

# 生新成員：`spawn_member` → 郵差檢查 → 生（或等人批）

第三波 W3-1，2026-09-24 第 1 版；**2026-09-25 第 2 版：使用者翻案 WAIT_USER 39——預設開、預設不用人批，每個成員各自可設**。
程式：[`lib/aos_team_spawn.py`](../../lib/aos_team_spawn.py)、工具 [`tools/task/spawn_member`](../../tools/task/spawn_member)。

成員覺得人手不夠，可以申請多一個成員。生出來的就是名冊多一列，跟人手寫的成員一模一樣：

- **一律平的**：沒有父子樹、沒有「小孩」資料夾。申請者不能管新成員（不能改它人格、不能停它），只能跟它通信。
- **一律經郵差**：新成員的信跟其他人一樣走 `team/outbox/`，郵差投。

```text
領隊 spawn_member {"template":"importer","name":"importer-a","reason":"…"}
   └─ 自己 outbox 放一份 kind: spawn 申請，這輪結束
郵差 on_spawn：照名冊檢查（〈檢查〉）→ 記 team/spawns/s-0001.json
   ├─ 不過：退一封 FAILED 給申請者，說哪條不過
   ├─ 不用人批（預設）：當場生——改 team.json（新成員一列＋申請者 mail_to 多這個名字）→ aos-team init
   │     （生家、更新每個成員工具裡的名冊快照）→ aos-agent start（有 AOS_KERNEL_HOME 才做）
   │     → 回 DONE 給申請者，另寄一封給 human 知會（誰生了誰、理由、怎麼收掉）
   └─ 要人批（名冊 approve: true）：開一題「[成員] …」（team/wait-user/q-NNNN）
         ├─ 批准：aos-team spawn approve q-NNNN（再驗一次，做上面「當場生」那串，回覆申請者）
         └─ 不要：aos-team answer q-NNNN 不要（申請者收到答案；什麼都不生）
```

## 誰能生、生了要不要人批（名冊，逐成員）

三層，**後面蓋過前面**：

1. **出廠值**：模板 `may` 有 `spawn` 的能生（內建只有 `lead`）；能生哪些＝內建模板都可以；不用人批。
2. **團隊層** `team.json` 的 `spawn`：`{"templates": [...], "approve": false}`。
   - `templates` 沒寫＝內建模板都可以；**寫 `[]`＝沒在成員層另寫 `templates` 的都不准生**；寫幾個名字＝只能生這幾種。
   - `approve` 沒寫＝`false`（郵差直接生）；`true`＝每個都要人批。
3. **成員層** `members.<名>.spawn`：
   - `false`＝這個成員不能生（就算模板有 `spawn`）；`true`＝能生（就算模板沒有），其他照團隊層。
   - 物件 `{"allow": 布林, "templates": [...], "approve": 布林}`：三格都可省，有寫的蓋過團隊層；`allow` 沒寫＝照模板 `may`。

```json
"spawn": {"approve": false},
"members": {
  "lead":     {"template": "lead",   "mail_to": ["worker-1", "human"], "spawn": {"approve": true}},
  "worker-1": {"template": "worker", "mail_to": ["lead", "human"],     "spawn": {"allow": true, "templates": ["worker"]}}
}
```

上面：領隊生人要人批；工人被開了、只能生工人、不用批。

- 程式裡算這個的是 `aos_team_format.spawn_policy(名冊, 名字)`（`None`＝不能；否則 `{"templates", "approve"}`）；郵差查「能不能寄 spawn 申請」也看它（`member_may`），不再只看模板。
- **改了成員層開關要重生工具**：`spawn_member` 這支工具只裝給能生的成員（`aos-team init` 生家時決定）。已經生好的家，改了開關要 `aos-team rm 名字` 再 `init` 才換；但能生哪些、要不要批的快照每次 `init` 都會更新，郵差也每次重驗，所以**關掉**不必重生家就生效。
- 名冊只收內建模板名：自訂模板的資料夾可能在模型改得到的地方。
- 改 `team.json` 的三條程式路（郵差不用人批生、人 `spawn approve`、`aos-team rm`）共用一把鎖 `team/.roster.lock`（讀→檢查→改→寫一口氣做完，不會互相蓋掉）；郵差生完馬上重讀名冊，同一輪後面寄給新成員的信不會被當成寄錯人。人用文字編輯器改名冊不受這把鎖管，別在團隊跑的時候改。

## 申請（`kind: spawn`）

| 鍵 | 必填 | 意思 |
|---|---|---|
| `template` | 是 | 內建模板名（不含 `/`），要在申請者能生的清單 |
| `name` | 是 | 新成員名字，規則同名冊（`[a-z][a-z0-9_-]{0,31}`，不能是 `human`／`post`／`beat`、不能跟人撞） |
| `reason` | 是 | 1～500 字；照抄進問人的題目或知會人的信 |
| `mail_to` | 否 | 新成員能寄給誰；沒寫＝申請者自己＋（申請者能寄 human 的話）`human` |

其他欄位（`mounts`、`tools`、`model`…）一律 `BadArguments`：新成員的權限只來自模板，申請者加不了料。

## 檢查（生之前一次；人批的 `approve` 時再一次）

**不用人批以後牆照樣關牢**，每一條都跟以前一樣擋：

| 代號 | 什麼時候 |
|---|---|
| `NotAllowed` | 申請者不能生（成員層 `false`、或模板沒 `spawn` 又沒被開） |
| `BadTemplate` | 模板不在申請者能生的清單、含 `/`、找不到模板資料夾 |
| `NameTaken` | 名字已在名冊、是保留名、或已有一份同名申請還沒辦完 |
| `TooMany` | 名冊人數＋還沒辦完的＋1 ＞ `limits.max_members` |
| `MailToExceeds` | 新成員的 `mail_to` 有申請者自己寄不到的人（只能是申請者本人或它 `mail_to` 裡的） |
| `MayExceeds` | 新成員模板的 `may` 有申請者沒有的申請種類（`ask`、`compact`、`lock`、`review_result`、`tool_draft` 例外：只碰自己的東西或本來就要人批） |
| `BadArguments`／`FormatInvalid` | 欄位多了、型別不對、名字格式不對 |

- **新成員不比申請者寬**：新成員的模板也能生（例：生一個 lead）時，如果申請者的設定跟團隊層不一樣（例：它被設成要人批、或只能生 importer），新成員那一列會**照抄申請者的** `spawn`（`templates`＋`approve`）；一樣就不寫、跟著團隊層。
- **「權限」怎麼算**（代裁）：看模板的 `may`（能寄哪些申請）與 `mail_to`。專案讀寫（`project: rw`）不比：內建領隊是唯讀，照字面連工人都生不出來；能不能寫專案由白名單決定。

## 紀錄 `team/spawns/s-NNNN.json`（只有郵差寫）

`{"_metainfo": {"_type": "aos_team_spawn", "_version": 1}, "id", "request", "from", "template", "name", "mail_to", "reason", "q", "at", "effects", "status", "log"?, "recovered"?}`。
- `q`：要人批的是題號；不用人批的是 `null`。
- `status`：`done`＝生完（名冊寫了、init 過了）；`failed`＝郵差生到一半失敗；`null`＝還在辦。**已生看 `status`，不看名冊有沒有這個名字**（astra 09-25）：生完又被 `rm` 掉的不會變回「還沒生」再佔名額；名冊寫了但 init 沒過的也不算已生。
- 其他狀態：`q` 是 `null` 而沒 `done`＝該生還沒生完（`aos-team spawn approve s-NNNN` 補做）；題目開著＝等人批；答了批准但沒 `done`＝還沒跑 `approve`；答別的＝人不要。
- 人數上限算「名冊人數＋還沒辦完、名字也還不在名冊的」。
- 冪等：同一份申請（看 `request`）再來＝回同一份動作。一律先記紀錄（`effects: null`）再辦，崩了重來會補辦；**補辦前重看一次要不要人批**——崩的那段時間人把申請者改成要批，就改成開題，不直接生。
- `recovered`：郵差那次失敗、人 `approve s-NNNN` 補做成功時，另從 `team/post/outbox/` 補寄一封 DONE 給申請者，這格記信的 id（只寄一次）。
- `log`：不用人批時郵差生家那段的輸出（init 印的字），出事時看。

## 人的指令

- `aos-team spawn ls [--json]`：一份申請一行（`s-0001  -  lead 想生 importer-a（importer）  已生（不用人批）  理由：…`）。
- `aos-team spawn approve q-NNNN|s-NNNN`：批准要人批的；或補做郵差生到一半的（補好會補寄 DONE 給申請者）。**重跑安全**：名冊已有就跳過、init 本來就能重跑、`start` 撞已登記＝沒事、回覆前先看 `outbox/human/`（含 `done/`）有沒有同一題的回覆。
  人先用 `aos-team answer q-NNNN 批准` 答了也行：再跑 `approve` 會照做，回覆改成另寄一封信（題目已經關了）。
- 停掉、收掉：跟其他成員一樣，`aos-agent stop --target <家>`（或 `aos-team stop` 全停）→ `aos-team rm 名字`（家搬進 `members/.removed/`、名冊與別人的 `mail_to` 拿掉）。這版**沒有**給模型「收掉成員」的申請。

## 沒做的

- 模型申請收掉成員、改新成員的 `model`／多掛資料夾：都只給人。
- 一次申請好幾個：一份一個名字；要三個就寄三份。
- 造工具（[toolsmith.md](toolsmith.md)）還是一律要人批；沒有做成同一套「團隊層＋成員層」開關（留下一輪）。
