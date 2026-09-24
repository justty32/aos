← [team](README.md)｜目錄 [catalog D 節 T-spawn](../../notes/2026-09-24-tool-era/catalog.md#t-spawn)｜報告 [w3a](../../notes/2026-09-24-tool-era/w3a/README.md)

# 生新成員：`spawn_member` → 人批 → `aos-team spawn approve`

第三波 W3-1，2026-09-24 第 1 版。程式：[`lib/aos_team_spawn.py`](../../lib/aos_team_spawn.py)、工具 [`tools/task/spawn_member`](../../tools/task/spawn_member)。

成員（內建只有領隊）覺得人手不夠，可以**申請**多一個成員；**人批了才生**。生出來的就是名冊多一列，跟人手寫的成員一模一樣：

- **一律平的**：沒有父子樹、沒有「小孩」資料夾。申請者不能管新成員（不能改它人格、不能停它），只能跟它通信。
- **一律經郵差**：新成員的信跟其他人一樣走 `team/outbox/`，郵差投。

```text
領隊 spawn_member {"template":"importer","name":"importer-a","reason":"…"}
   └─ 自己 outbox 放一份 kind: spawn 申請，這輪結束
郵差 on_spawn：照名冊檢查（下表）→ 記 team/spawns/s-0001.json → 開一題「[成員] …」（team/wait-user/q-NNNN）
   ├─ 不過：退一封 FAILED 給申請者，說哪條不過
人 aos-team wait ls／spawn ls 看到
   ├─ 批准：aos-team spawn approve q-NNNN
   │     再驗一次 → 改 team.json（新成員一列＋申請者 mail_to 多這個名字）→ aos-team init（生家、
   │     更新每個成員工具裡的名冊快照）→ aos-agent start（有 AOS_KERNEL_HOME 才做）→ 回覆申請者
   └─ 不要：aos-team answer q-NNNN 不要（申請者收到答案；什麼都不生）
```

## 申請（`kind: spawn`）

| 鍵 | 必填 | 意思 |
|---|---|---|
| `template` | 是 | 內建模板名（不含 `/`），要在名冊的 `spawn.templates` |
| `name` | 是 | 新成員名字，規則同名冊（`[a-z][a-z0-9_-]{0,31}`，不能是 `human`／`post`／`beat`、不能跟人撞） |
| `reason` | 是 | 1～500 字，照抄進問人的題目 |
| `mail_to` | 否 | 新成員能寄給誰；沒寫＝申請者自己＋（申請者能寄 human 的話）`human` |

其他欄位（`mounts`、`tools`、`model`…）一律 `BadArguments`：新成員的權限只來自模板，申請者加不了料。
誰能寄：模板 `may` 有 `spawn` 的（內建只有 `lead`）。

## 名冊：`spawn`

```json
"spawn": {"templates": ["importer", "worker"]}
```

- 成員能申請生哪幾種；**沒寫＝`[]`＝這隊不准成員生**（預設關）。只收內建模板名，自訂模板的資料夾可能在模型改得到的地方。
- `limits.max_members` 照舊是上限，**等人批的也算**（免得一口氣申請十個、批的時候才爆）。
- 白名單會抄進每個成員 task 包的 `config.json`（`spawn_templates`），`spawn_member` 先擋手誤，省一趟郵差。

## 檢查（郵差開題前一次、`approve` 時再一次）

| 代號 | 什麼時候 |
|---|---|
| `BadTemplate` | 模板不在 `spawn.templates`、含 `/`、找不到模板資料夾 |
| `NameTaken` | 名字已在名冊、是保留名、或已有一份同名申請在等人批 |
| `TooMany` | 名冊人數＋等人批的＋1 ＞ `limits.max_members` |
| `MailToExceeds` | 新成員的 `mail_to` 有申請者自己寄不到的人（只能是申請者本人或它 `mail_to` 裡的） |
| `MayExceeds` | 新成員模板的 `may` 有申請者模板沒有的申請種類（`ask`、`compact`、`lock`、`review_result`、`tool_draft` 例外：只碰自己的東西或本來就要人批） |
| `BadArguments`／`FormatInvalid` | 欄位多了、型別不對、名字格式不對 |

- **「權限」怎麼算**（代裁）：看的是模板的 `may`（能寄哪些申請）與 `mail_to`。專案讀寫（`project: rw`）不比：內建領隊是唯讀，照「不能超過申請者」它連工人都生不出來；專案能不能寫由**人寫的白名單**決定——白名單放 `importer` 就是人同意「領隊可以申請一個能寫專案的導入工人」。
- `approve` 再驗一次，因為名冊可能在等的時候被人改了（白名單拿掉、人數滿了）。

## 紀錄 `team/spawns/s-NNNN.json`（只有郵差寫）

`{"_metainfo": {"_type": "aos_team_spawn", "_version": 1}, "id", "request", "from", "template", "name", "mail_to", "reason", "q", "at", "effects"}`。
狀態不另存，從題目與名冊推：題目開著＝等人批；名冊有這個名字＝已生；答了批准但名冊還沒有＝還沒跑 `approve`；答別的＝人不要。
冪等：同一份申請（看 `request`）再來＝回同一份動作，不再開題。

## 人的指令

- `aos-team spawn ls [--json]`：一份申請一行（`s-0001  q-0003  lead 想生 importer-a（importer）  等你批  理由：…`）。
- `aos-team spawn approve q-NNNN|s-NNNN`：上圖那串。**重跑安全**：名冊已有就跳過、init 本來就能重跑、`start` 撞已登記＝沒事、回覆前先看 `outbox/human/`（含 `done/`）有沒有同一題的回覆。
  人先用 `aos-team answer q-NNNN 批准` 答了也行：再跑 `approve` 會照做，回覆改成另寄一封信（題目已經關了）。
- 停掉、收掉：跟其他成員一樣，`aos-agent stop --target <家>`（或 `aos-team stop` 全停）→ `aos-team rm 名字`（家搬進 `members/.removed/`、名冊與別人的 `mail_to` 拿掉）。這版**沒有**給模型「收掉成員」的申請。

## 沒做的

- 模型申請收掉成員、改新成員的 `model`／多掛資料夾：都只給人。
- 一次申請好幾個：一份一個名字；要三個就寄三份（人也批三次，見報告的對照）。
