← [hooks：外掛掛點](../hooks.md)（分檔 3/3）｜所在段落：B-635：hooks：一格裡各個時機跑的一串｜[上一份](02-B-635-何時跑與紀錄.md)

### 範例：用 hook 加普通 git 指令管版本

`aos-git` 第十七批搬暫緩區（[暫緩區 git](../../deferred/git.md)），原本它做的事用 hooks 加普通 git 指令就做得到。下面只是**範例說明**，aos 不提供這些腳本、不保證它們跟哪個模組配得起來：

```json
{"tasks": [{"id": "fetch", "argv": ["./fetch.sh"]}, {"id": "report", "argv": ["./report.sh"]}],
 "hooks": {
   "before_all": [{"id": "recover", "argv": ["sh", "-c",
     "python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get(\"ended\", True) else 1)' .aos/tick/last/record.json || git checkout -- . && git clean -fdq -e .aos"]}],
   "after_every_task": [{"id": "commit", "argv": ["sh", "-c",
     "if [ \"$AOS_TASK_EXIT\" = 0 ]; then git add -A && git commit -qm \"tick: $AOS_TASK_ID\" || true; else git checkout -- . && git clean -fdq -e .aos; fi"]}]}}
```

- `before_all` 看上一格紀錄：`ended:false`（上一格跑到一半被殺）就把工作樹還原到上次 commit。
- `after_every_task` 看 `AOS_TASK_EXIT`：成功就 commit 這一項的改動，失敗就還原這一項寫到一半的東西。只想管某幾項就改用 `after_task`。
- `.aos/`（紀錄、鎖、tasks-blocked）要排除在版本外，自己寫進 `.gitignore`。

依據：使用者 2026-10-01 第十七批（`before_all`、`after_task`、`after_every_task`、`AOS_TASK_EXIT`：「那確實是需要AOS_TASK_EXIT」「"hooks":{"after_task":{"a":..., "b":...}}，然後是after_every_task。」「都照你說的，排給agent做。git這塊先不要進範本。」）；使用者 2026-10-01 第十批（hook 的環境變數：「hook這塊，幫我添加AOS_HOOK_TYPE, AOS_HOOK_INDEX, AOS_HOOK_ID……AOS_HOOK_INDEX, _ID會替代TASK_ID, INDEX。但對於hook到特定任務的前後的，還是會有AOS_TASK_INDEX, AOS_TASK_ID，只是這時候他就是指向那個被hook的任務。」，[verdicts 11 篇末](../../../../notes/verdicts/11-tick-as-unit/13-1001-第十十一批.md#2026-10-01-第十批hook-的環境變數)）；使用者 2026-10-01 第九批（紀錄拆檔，`hook-exits.json`）；使用者 2026-10-01 第六批裁定（[verdicts 11 篇末](../../../../notes/verdicts/11-tick-as-unit/11-1001-第六七批.md#2026-10-01-第六批tick-的-hooks外掛掛點)）：「那就做外掛掛點，這個hooks就是模組」「after_cell？我以為是after_all，我們有cell嗎？ 2.可以一串。 3.吃，hooks中的掛點所提供的，比如"after_cell":[{},{},...]，就比照tasks。4.會記錄。 剩下都建議」；同日改成頂層鍵：「所以目前唯一的模組就是hooks...就不讓他當模組了，直接讓他變頂層key」。

**驗收：**〔第十七批〕`before_all` 在第一項（與 tasks-blocked 的檢查）之前跑、擋板／busy／表壞時不跑；`after_task.<id>` 只在那一項跑完後跑、先於 `after_every_task`，不存在的 id 不跑也不報錯；兩者拿到剛跑完那一項的 `AOS_TASK_ID`／`INDEX`／`EXIT`（被 SIGKILL 是 137），被 tasks-blocked 擋下的項不觸發；`AOS_TASK_EXIT` 只有這兩個掛點有（外層帶進來的也拿掉）；不是 0 的記進紀錄、帶 `task_index`。沒寫 `hooks`（或 `hooks` 裡一個掛點都沒寫）時紀錄沒有 `hooks`、行為照舊；寫在 `modules.hooks` 底下的不跑。`after_all` 三項依序在任務之後跑，沒寫 id 的用位置字串；頂層 `argv`、`envs` 當預設，項自己寫的 `envs` 整包蓋過。`hooks`、`after_all`、某項各自 `$ref` 到別的檔照跑；項裡 `argv` 元素的 `#/k` 指合併後的這一項。hook 拿到的 `AOS_TICK_CWD` 是工作資料夾、`AOS_HOOK_POINT` 是 `after_all`、`AOS_HOOK_INDEX`／`AOS_HOOK_ID` 是自己的（沒寫 id 時是位置字串），沒有 `AOS_TASK_ID`／`AOS_TASK_INDEX`（外層環境帶進來的也沒有）；任務拿不到 `AOS_HOOK_*`。任務寫了 tasks-blocked：後面的任務不跑、`after_all` 照跑，hook 再寫也不擋下一個 hook。hook 回 3、被 SIGKILL、找不到程式（127，stderr `exec_failed: after_all/<id>:`）都照記（帶 `index`）、回 0 的不記、下一個照跑、tick 回 0。擋板、busy、表壞時一個 hook 都不跑。`after_all` 不是陣列、某項不是物件、合併後沒 `argv`、`hooks` 不是物件、讀表那一層 `$ref` 解不開：`bad_table`、回 1、紀錄與 `seq` 不動。紀錄的 `hooks.after_all` 下一格進 `last/`（`hook-exits.json`）。測試：`src/py/tests/test_tick_hooks.py`。
