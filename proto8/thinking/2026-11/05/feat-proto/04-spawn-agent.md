← [入口](README.md)｜件 4：agent 用 aos 指令產出另一個 agent｜上一份 [03-scheduling](03-scheduling.md)｜下一份 [05-資源份額](05-資源份額.md)

# 件 4：agent 用 aos 指令產出另一個 agent（fable 照原則定，可翻案）

使用者原文（11-05 午，逐字）：「讓agent利用aos指令產出另一個agent」。現況：人用 `aos-agent ctl add [--name N] [--ws WS] <定義>` 掛一隻到 `AOS_DAEMON` 那台（[aos-agent](../../../../extras/agent/README.md)）、`say`／`listen` 對話、`ctl rm` 收掉；`AOS_KERNEL` 有設就先過判官（`max_running`、`allowed`，[demo/docs/04](../../../../demo/docs/04-kernel-modes.md)）；daemon 給子項 `AOS_DAEMON`，一路繼承到工具（N-63 ③）。

## 已定（照原則推得出）

- **「產出」＝掛一隻現成定義上 daemon，不是生程式碼**：定義（函數本體）可重複掛好幾隻（C-46 bob 是可重複使用的函數；11-05 aos-agent 已支援同定義多隻）。腦想「寫一隻新的」＝先用 `write` 工具在工作區抄一份範本改 `system.txt`，再掛——兩個工具接起來就是，不另造。
- **掛在管我的那台 daemon**：工具繼承到 `AOS_DAEMON`（portable-flow「基準點＝管我的 daemon」）；沒有＝`DaemonMissing` 回給腦。`AOS_KERNEL` 有設就自然過判官——**上限就是判官的 `max_running`**，不在工具裡再數一次（一件事一個地方，C-56）。
- **不繼承腦與工具**（C-52「什麼都不往下傳、不繼承」、C-46 要換子 agent 的腦＝給它的 stack 放 `llm.json` 副本）：子用它定義裡的設定；父要改就明寫，工具替它跑 `aos-agent llm set --target 子 endpoint=…`、`aos-agent tools add --target 子 …`。
- **跟它說話＝P-42 三樣**：`say`（寄進子的 queue）、`listen`（讀子的 history）。父看不到子的 stack 內部、子不知道誰生它（C-52）。
- **工具自己不跑任何東西**（判官同款）：全是 `aos-agent` 的轉手；aos-agent 退非 0 的那行印到 stdout 給腦（lib 契約規則 3）。

## 代定（照推薦定，可翻案）

1. **一個工具 `lib/agent/agents/`**（複數：裝同類），stdin `{"op": "add"|"say"|"ask"|"rm"|"ls", ...}`，動詞照 aos-agent（`ask`＝say＋listen 一刀，給腦最省事）：
   - `add {name, def, ws?, endpoint?, tools?: [{name, path}]}`：`def`＝範本資料夾（從 `$AOS_WS` 算、或 `lib/`／`demo/` 絕對路徑；要有 `interfaces.json` 的 `aos-agent` 宣告，不然 aos-agent 報 `InterfaceMissing`）→ `aos-agent ctl add --name <name> --ws <ws> <def>` → 有 `endpoint` 就 `llm set`、有 `tools` 就逐個 `tools add`；印 `added <name> (stack …)`。名字撞表＝aos-agent 的 `AddRejected` 原樣回。
   - `say {name, text}` 印信件名稱、馬上回；`ask {name, text, timeout_s?}`＝say＋`listen --timeout-s`（預設 600；act 格的 `timeout_ms` 1800000 包得住）印回答；`ls` 印 `ctl ls --json`；`rm {name}`＝`ctl rm`。
   - **只收自己生的**：`add` 成功後把名字記進工具小格 `$AOS_STACK/children.json`（P-17 小格、規則 8 中層以上才寫 stack）；`rm`／`say`／`ask` 的名字不在裡面＝`ChildUnknown`、不動手（父殺兄弟、殺父的最小護欄；aos 不驗身分，這只是工具自己的禮貌，不是權限）。`ls` 不限。
2. **子的工作區預設＝父的 `AOS_WS`**（留題 3）：兄弟協作同一堆檔；子的 stack 由 daemon 給（`<daemon>/procs/<name>/`），不撞。要分開就 `ws` 寫子資料夾（從 `$AOS_WS` 算）。
3. **遞迴爆量**：子的定義若也登記 `agents` 工具，子還能再生 → 全靠判官 `max_running`（留題 4：推薦 4，含父）；判官擋了＝`AddRejected: SlotMissing` 回給腦、腦自己收斂。不加深度計數、不在工具裡做名額（兩套上限打架）。沒設 `AOS_KERNEL`＝daemon 來者不拒＝自擔（使用者 11-05「linux權限沒設也可以…就自行承擔風險」同一口徑）。
4. **子出錯停在表上**（`stopped`＋`reason`，11-05 已裁）：`ask` 等到一半子停了，aos-agent listen 會提醒並照等直到 timeout → 工具印 `AnswerMissing` 那行回腦；腦可 `rm` 再 `add`。
5. **收掉**：父 `rm` 子＝刪子 stack（aos-agent 原規則：蓋住工作區／定義的不刪）。父自己被 `rm` 時子不會跟著走（daemon 不知道父子；要收人殼 `ctl ls` 看）——寫進已知限制。
6. **demo**：`demo/llm-kernel/kernel.json` 加劇本包 `fake-demo-spawn`：第 1 則叫 `agents add {name: "kid", def: "<repo>/proto8/demo/agent-fsm", endpoint: "fake"}`、第 2 則 `agents ask {name: "kid", text: "what time is it"}`、第 3 則答一句帶孩子的回答、第 4 則 `agents rm`。判官用 `demo/daemon-judge` 那台（`max_running` 改 4）演被擋。

## 衝突（哪條、在哪、各自後果）

- **C-52「agent 只看到自己的工具清單、不知道工具裡是不是另一個 agent」**：這裡父**明知**在生一隻 agent、還跟它對話。(a) 推薦：不算撞——`agents` 對父而言就是一個工具（C-42 aos 的每一樣都是 agent 的工具），裡面是 aos-agent 轉手；父知道的只有「名字＋一問一答」，子的 stack、腦、工具一概不碰（除了 `add` 時明寫的設定，那是叫它那一行的事，C-46）。(b) 把子包成純工具（agent_tool 模式：每次呼叫開一隻、答完收）——更乾淨，但使用者說的是「產出另一個 agent」（常駐、可多次對話），不是一次性函數。選 (a)。
- **鐵律 2「開新工作先確認」**：agent 生 agent＝程式自己開工、沒人確認。(a) 推薦：授權來源＝判官的 `judge.json`（人寫的上限與白名單）＋使用者這句原話；沒設判官＝自擔。(b) 每次 `add` 寄信問人——使用者睡覺時整隊卡住。選 (a)。
- **「不繼承」vs 使用者可能想「子跟我一樣」**：推薦不繼承（C-52），`add` 的 `endpoint`／`tools` 明寫一次就等於繼承；代價是腦要多寫兩個欄。可翻案：`add {inherit: true}` 把父的 `llm.json`（stack 疊定義）與覆蓋層抄給子——那要父讀自己的 stack（件 1 的 `ctl who`），做得到、先不做。
