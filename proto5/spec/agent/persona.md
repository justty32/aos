← [agent](README.md)｜工具檔：[info.md §3.3](info.md)｜團隊裡怎麼提案：[team/ask.md](../team/ask.md)

# 人格：`aos-agent persona`、模型的 `persona_propose`

第二波 C 隊，2026-09-24（catalog.md〈T-persona〉）。人格（`info.json` 的 `system`，預設指到 `prompts/system.json`
的 `content`）是信任資料——proto2 的 `improve_prompt` 曾經因為只能改 `prompt-overrides/`、拒絕寫使用者要的教訓，
這一輪照採「模型只能提案、人批了才寫」，跟 [T-access-req](../team/ask.md)（同一份文件〈借用〉那節）、
心跳的 `routine` 申請是同一個治理原則：**信任資料只有人的指令能改**。

## 人的指令（`lib/aos_agent_persona.py`）

- `aos-agent persona show [--json] [--target DIR]`：印目前的人格全文；檔不存在當空字串（不是錯）。
- `aos-agent persona set TEXT [--target DIR]`：**整份換掉**（TEXT 就是新的 `content`）。
- `aos-agent persona append TEXT [--target DIR]`：接一行到最後（原文沒結尾換行會先補一個）。
- 找人格檔：讀 `<家>/info.json` 的 `system`（相對＝相對 agent 家），沒有這個檔或沒寫 `system`＝`<家>/prompts/system.json`
  （跟 [aos_agent_home 的預設](../aos-agent/README.md) 一致）。三個動作都**不叫模型、不進牢**——`prompts/system.json`
  本來就只給 agent 自己的 runtime 讀，工具（含模型的 `persona_propose`）本來就碰不到它。
- 錯誤：`persona show` 不收 TEXT、`set`／`append` 沒給 TEXT、動作打錯字都是 `Usage`（退 2）；檔壞掉（不是含字串
  `content` 的物件）是 `MessageInvalid`。

## 模型的 `persona_propose`（`tools/task/persona_propose`）

模型自己改不到人格，只能寄一份提案，走 [T-ask 的待辦](../team/ask.md)：

```text
成員 persona_propose {"text": "遇到殘留一律先跑 wf_residue", "why": "省一次來回"}
  ──寄 kind=ask 申請（問句已經寫好人同意後要跑的指令）──▶ 郵差建 q-000N
人 aos-team wait ls                                    看到這一題
人 aos-team answer q-000N "同意"                        ──▶ 郵差投回發問者，問題結案
人（自己再跑一次，這支工具不會自動做）
  aos-agent persona append --target <該成員的家> "遇到殘留一律先跑 wf_residue"
```

跟 [T-access-req](../team/ask.md) 一樣：**同意這個答案本身不會讓任何東西自動生效**，人要自己照問句裡寫的指令再跑一次。
這樣「模型自己改不到」不是靠郵差記得檢查、是這條路本來就沒有自動寫入這一步（少一處要信任的程式碼）。

## 跟其他 agent 設定的分工

`info.json` 裡「代號、排程間隔、工具清單」這些**這一輪還是只給人改**（`aos-agent tools add/rm`、直接編輯或
[T-json](../team/ask.md) 的人用版）：模型沒有申請改這些的工具，理由同 catalog.md〈T-persona〉——先看人格這一種
夠不夠，其他設定要不要開模型申請之後再議。
