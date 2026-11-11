# subagent 改名：工具 agents_children 改叫 subagent，舊名不留

← [2026-11-11](README.md)｜[thinking](../../README.md)

## 使用者原話

11-11 早上：「對了，昨天開發的那個agents_children工具，幫我改名為subagent。」

## 決定

- 工具 `lib/agent/agents_children` 改名 `lib/agent/subagent`：夾名、登記名（`lib/packs/children.json` 裡的鍵與路徑）、錯誤行開頭（程式從夾名取）、`_tooldef.json` 的 Details 指標、knowledge 節點 `aos/agents.json#/agents_children` → `#/subagent`、kernel 假腦 `fake-demo-spawn` 劇本裡叫的工具名、`aos-agent ctl state` 讀的記帳檔位置、`review_round` 認子帳的夾名。proto8 不留舊名、不做相容（舊名＝不認得）。
- 條文（CONCEPTS、NORMS）裡 11-10 的註只加「（11-11 改名 `subagent`）」，現行表與現在式的句子直接改新名；NORMS 附錄 3 舊名對照加一列、附錄 4 持久檔改新位置。thinking 11-10 的紀錄照當時的名字，不改。
- 範圍只到這支工具的名字。沒動、留給使用者裁：包名 `children`（`lib/packs/children.json`）、配額設定檔 `children.json`、`max_children`、`Child*` 錯誤代號、`ls` 末行 `children N/MAX` 與 `json` 輸出的 `children` 鍵、`agents_ctl`、`agent_def`；tooldef 裡講「child agents」的說明句（是在講概念，不是工具名）。

## 要重建什麼

- 舊 stack 的記帳檔 `$AOS_STACK/tools/agents_children/children.json` 新工具不讀（新位置 `$AOS_STACK/tools/subagent/children.json`）：帳上的子不再算是誰的——要嘛手動 `aos-agent ctl rm`，要嘛把那份搬到新位置，要嘛整份 stack 重建。
- stack 覆蓋層或 repo 外登記檔裡寫死 `agents_children` 名字或 `lib/agent/agents_children` 路徑的格：重登記成 `subagent`。照範本走 `lib/packs/children.json` 的不用動。
- 腦的 history 裡還有叫 `agents_children` 的舊對話：再叫會得到 `ToolMissing agents_children is not registered`（後面列出現有工具），清掉 history 或讓它自己看新的工具列。
