# proto6 文件整理隊回報（2026-10-02）

範圍：`proto6/` 底下、`proto6/src/` 以外。沒碰 `proto6/src/`、`wf/`、`AGENTS.md`、其他 proto*。搬移清單在旁邊的 `moves.tsv`（`舊路徑<TAB>新路徑`，198 列：封存 20 列，拆檔 178 列，拆檔是一對多，原路徑留著當入口）。

分支：`worktree-agent-ac24c4ed256c6e7ff`，基準 `785eb05`。

## 一、封存

- `notes/reviews/2026-09-30/` 整個資料夾移到 `notes/archive/reviews-2026-09-30/`（14 份 md、4 份 json）。證據：資料夾 README 自己寫 77 條「待處理」，`items.json` 87 列全部已分類或裁定（第十八批審稿裁定 1～18 條，不成立的 10 條標「擬刪」）；第十八、十九、二十批的改寫計畫，以及納入 cgroup／git 的改寫計畫，疑點都已經在 `verdicts/09`、`10`、`11` 裁定（各份有「題號對應…計畫」的段落）；後來 cgroup／git 又整份搬進暫緩區（第十七、二十三批）。結論已經寫進 `spec/settled/` 與 `settled/deferred/`。
- `notes/reviews/2026-10-01/astra-spec-sync-report.md` 移到 `notes/archive/reviews-2026-10-01/`。證據：裁定 11 的「2026-10-01 第二批」已經處理這份審查，使用者原話是「不用特別弄清單，就全部」。
- 每份封存的 md 第一行都加了封存說明；`archive/README.md` 只追加兩列。活文件裡指向這些檔的 9 個連結都改成純文字（`notes/README.md`、`spec/settled/README.md`、`verdicts/09`、`10`、`11`）。`notes/reviews/` 清空後，裡面只剩本報告。
- 沒有拿不準、因此留著沒封存的檔。舊設計 spec 照指示沒動。

## 二、拆檔（B 法）

一共拆了 46 份，產生 178 個分檔。每份都在同名資料夾；`tick.md` 放 `tick/core/`，因為 `tick/` 已經是子篇資料夾；`README.md` 一律放 `readme/`。每個分檔第一行是導航（回入口、第幾份、所在段落、上一份／下一份）；入口保留原本的前言，後面接「## 分檔目錄」表。每份都用腳本驗過「原檔＝入口前言＋各分檔本體」：除了連結目標與空行，一字不差，46 份全部 `VERIFY OK`。

拆的檔：verdicts 11（24 份）、03、04、05、09、10；`spec/conformance.md`、`spec/README.md`；`settled/` 的 `tick.md`、`README.md`、`terms.md`、`conventions.md`、`tick/hooks.md`、`daemon/{core,control,mq,account}.md`、`protocol/tick.md`、`protocol/daemon/{core,control,mq}.md`，以及 `deferred/` 的 `README`、`tick`、`git`、`mq`、`helper`、`daemon/{cgroup,registration,runtime,lifecycle,channel,helper-actions}`、`protocol/tick`、`protocol/daemon/{provision-and-runner,startup-and-ipc,registration,channel}`；`spec/protocol/README.md`；`plan/` 的 `README`、`m1`、`m1h`、`m2`、`m3`、`m3m`、`m3n`；`notes/2026-10-01-tick-system-tasks.md`。

**錨點：採 (b)。** 範圍內的連結指到舊檔 `#錨點`，或檔內的 `#錨點`，都改指新分檔與新錨點（重複標題的 `-1`、`-2` 編號按分檔重算；標題前的顯式 `<a id>` 跟著標題走）。範圍外改不到的，就在入口目錄表那一列留同名的 ``，舊錨點仍然有落點，現在不會壞。

## 三、範圍外的連結（給調度者，可選擇改指新分檔）

目前都沒壞，靠入口的 `<a id>` 接住。改了之後，可以把入口表上的 `<a id>` 拿掉。

- `proto6/src/py/README.md`
  - 27：`11-tick-as-unit.md#aos-exec-不認得頂層-user待統一更新-spec` → `11-tick-as-unit/06-1001-互斥-狀態資料夾-user.md#…`
  - 41：`#aos_dirname-狀態資料夾的名字待統一更新-spec` → `11-tick-as-unit/06-1001-互斥-狀態資料夾-user.md#…`
  - 48、122：`#aos-結束碼慣例待統一更新-spec` → `11-tick-as-unit/04-1001-結束碼慣例.md#…`
  - 74：`#aos-tick---node-怎麼認待統一更新-spec` → `11-tick-as-unit/05-1001-tick-node與讀表檢查.md#…`
  - 181：`#aos-tick-讀任務表的極簡檢查待統一更新-spec` → 同上 05
  - 116：`#aos-tick-最簡互斥與讀表時機待統一更新-spec` → `11-tick-as-unit/06-1001-互斥-狀態資料夾-user.md#…`
  - 91：`#2026-10-01-第三批tasksjson-的-metainfo-與-modules` → `11-tick-as-unit/09-1001-第二三批.md#…`
  - 74、76、116、118、120、122：`plan/m1-tick-core.md#待問` → `plan/m1-tick-core/08-待問.md#待問`
  - 214：`spec/settled/tick/hooks.md#範例用-hook-加普通-git-指令管版本` → `spec/settled/tick/hooks/03-B-635-範例hook加git.md#…`
- `wf/SESSION-LOG.md`
  - 15：`11-tick-as-unit.md#2026-10-01-第二十二批廣播與頻道` → `11-tick-as-unit/24-1001-1002-第二十二二十三批.md#…`
  - 17：`#2026-10-01-第十二批cgroup-與帳號` → `11-tick-as-unit/14-1001-第十二批.md#…`
  - 17：`#2026-10-01-第十九批daemon-上下層用到的三件事` → `11-tick-as-unit/21-1001-第十九批.md#…`
  - 17：`plan/m3m-daemon-modules.md#做完了沒` → `plan/m3m-daemon-modules/09-做完了沒.md#做完了沒`

## 四、驗證（實際輸出）

```text
$ bash wf/tools/wf-lint.sh . 2>&1 | tail -1
TOTAL broken=76
$ bash wf/tools/wf-lint.sh . 2>&1 | grep BROKEN | grep proto6 | wc -l
0
$ find proto6 -name '*.md' -not -path '*/archive/*' -not -path 'proto6/src/*' -size +8192c | wc -l
85（前）→ 36（後）
$ python3 proto6/spec/check_ids.py | tail -1
引用 6480 個，定義 265 個，找不到 0 個，重號 5 個，只剩索引列 0 個，預留未寫 1 個
（基準 785eb05 也是重號 5 個（P-204／205／206／211／212，暫緩區與現行各一）、預留未寫 1 個，沒有新增）
$ git diff 785eb05 HEAD --name-status -M | 種類統計
178 A（分檔）、97 M（入口與改連結）、20 R（封存，全是 rename）、0 D
```

schema 與範例沒動（`spec/protocol/examples`、`schemas` 沒有 diff），所以沒跑 validate.py。只改文件，沒有 build。

## 五、剩下的 36 份超標檔與理由

- **單一標題下的連貫內容，不硬切（9 份）**：`conformance/02-V-01-正本表`（一張表）、`conformance/03-V-01-新條號`、`conformance/08-V-03-1001場景`、`settled/protocol/tick/02-P-202-任務註冊表`、`verdicts/11-tick-as-unit/07-1001-最核心daemon`、`verdicts/11-tick-as-unit/04-1001-結束碼慣例`、`plan/m1-tick-core/08-待問`（68 列清單，之後可以用 A 法抽成資料檔）、`plan/m3m-daemon-modules/09-做完了沒`、`spec/protocol/readme/05-條號索引`（給人看的導航表，8376 bytes）。
- **舊設計 spec，這輪不動（20 份）**：`spec/protocol/`（kernel-tasks、work、agent-tasks、messages、ops、resources、llm-work）、`spec/cli/`（commands、walkthrough、debugging）、`spec/scheduling/`（admission、llm、operations）、`spec/base/`（transport、execution、storage、inst）、`spec/agent/tools`、`spec/terms`、`spec/contracts`。使用者還沒宣告這些作廢，STRUCTURE 也把 spec 各章當成不可分的單體。
- **連貫筆記，保留（4 份）**：`notes/2026-10-01-daemon-core-sketch`、`notes/2026-10-01-account-manual`（WAIT_USER 照它手動驗收）、`notes/2026-09-29-kernel-tree`、`notes/2026-09-29-wsl-machine-check`。
- **原型資料夾 `proto6/proto/`（3 份）**：`notes/codex-task-1`、`notes/spec-gaps`、`README`，是舊原型的紀錄，沒動。
