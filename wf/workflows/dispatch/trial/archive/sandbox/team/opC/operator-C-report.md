# aos 試用隊 L2／操作者 C 實測

環境照劇本設為 `W=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a3827d89ce88223e5`、`PATH=$W/build/bin:$PATH`、`T=$W/wf/workflows/dispatch/trial/sandbox/team`；只建立及寫入 `$T/opC`，沒有重編、沒有碰 `core/`、沒有 git add／commit，也沒有操作 LM Studio。

## 步驟 1：看誰在忙

步驟 / 期待 / 實際 / 缺哪個原語 / 跟 Claude Code 開隊的對照：步驟 1；期待用一個 `aos` 指令看到 boss／w1／w2 誰在忙及各自回合；實際在第一輪查詢的快照中，boss 是 `thinking`、turn 1（detail：`處理本回合`），w1 是 `idle`、turn 0，w2 是 `idle`、turn 0，最少仍要對三個世界各查一次，共 3 個 `aos` 指令；缺少「依目前世界通訊錄批次讀取所有 contact 狀態」的原語，例如 `aos contact status`；Claude Code／Codex 的隊伍控制層通常集中維護子 agent 生命週期，操作者可以在一個隊伍視圖看全員，不必自己逐資料夾查。

最少取得三人狀態的 3 個 `aos` 指令是：

```sh
cd $T/boss && aos state
aos agent state ../w1 w1
aos agent state ../w2 w2
```

步驟 1 實測期間實際輸入的所有 shell 指令如下，共 9 個（另按過一次 `q` 離開 `cat` 在本機 alias 到的 pager，`q` 不是 shell 指令）：

```sh
cd $T/boss && aos state
aos agent state ../w1 w1
cat $T/w1/.aos/state.json
aos agent state ../w2 w2
aos contact status
aos contact ls
cat $T/boss/.aos/state.json $T/w2/.aos/state.json
command cat $T/boss/.aos/state.json $T/w2/.aos/state.json
aos --help
```

步驟 / 期待 / 實際 / 缺哪個原語 / 跟 Claude Code 開隊的對照：步驟 1 的各路徑；期待 `aos state`、跨資料夾的 `aos agent state` 與直接讀檔至少能各自說清狀態；實際三條路都能讀單一世界，`aos state` 在世界內可用，`aos agent state ../w1 w1` 和對 w2 的同型指令也可用，直接 `cat` 也可用，但 `aos contact status` 只回 usage，顯示 contact 只有 `add`／`ls`／`rm`，所以「一個指令列出通訊錄所有人狀態」做不到；缺少批次 status 與同時呈現 world phase、running、agent status 的統一查詢；Claude Code／Codex 由宿主替操作者彙整狀態，aos 現在只提供單點查詢與靜態通訊錄列表。

`aos contact status` 的原話是：

```text
usage: aos contact add <name> <folder> [--agent A] [--note TEXT] [--folder-root F]
       aos contact ls [--folder-root F] [--json]
       aos contact rm <name> [--folder-root F]
```

步驟 / 期待 / 實際 / 缺哪個原語 / 跟 Claude Code 開隊的對照：步驟 1 的 `state.json` 範圍；期待本世界或隊伍狀態的涵蓋範圍一眼可辨；實際 boss 的 `agents` 只有 `boss`、w1 只有 `w1`、w2 只有 `w2`，完全沒有把通訊錄 contact 合進來，而且 boss 忙碌期間曾出現 root `turn: 2`／`phase: running`，但 `agents.boss` 仍是 turn 1／idle，表示 world 執行態與 agent 對話態是兩組可能不同步的欄位；缺少隊伍聚合狀態與清楚區分兩種 turn 的呈現；Claude Code／Codex 的宿主層會把 running／idle 與子 agent 身分集中對齊。

## 步驟 2：一個主世界推子世界

步驟 / 期待 / 實際 / 缺哪個原語 / 跟 Claude Code 開隊的對照：步驟 2 的 fan-out；期待在 main 跑 3 回合時 sub1／sub2 也各前進 3 回合；實際 `cd $T/opC/main && aos run --step 3` 每回合都顯示 `3 insts (3 every)`，立即查看 main、sub1、sub2 的 `.aos/turn` 都是 `4`（run 輸出為 turn 1～3，turn 檔保存下一個回合號），main 的 sub1／sub2 out JSON 都是 exit 0、stderr 空白，沒有錯誤訊息；缺少不用手寫兩份 every JSON 的「建立並掛載子世界」原語，以及一次顯示子世界結果／狀態的摘要；Claude Code／Codex 通常由父 agent 建立子 agent、追蹤執行並收回結果，操作者不用自己維護回合 fan-out 指令檔。

主世界輸出原話：

```text
turn 1: 3 insts (3 every), 8 ms
turn 2: 3 insts (3 every), 8 ms
turn 3: 3 insts (3 every), 8 ms
```

步驟 / 期待 / 實際 / 缺哪個原語 / 跟 Claude Code 開隊的對照：步驟 2 的相對路徑；期待知道 `argv` 中 `sub1`／`sub2` 相對誰解析；實際兩條 `aos run subN --step 1` 都成功，證明它們相對 main 世界的執行 cwd（`$T/opC/main`）解析，而 nested run 進入的就是各自子世界；缺少在 inst／out 中顯式記錄 cwd，現在只能由成功結果反推；Claude Code／Codex 的子任務通常把 workspace／cwd 當成派任務參數或執行上下文直接展示。

步驟 / 期待 / 實際 / 缺哪個原語 / 跟 Claude Code 開隊的對照：步驟 2 的操作手感；期待比較三個世界各自 `aos run` 與一個 main 推兩個子世界；實際各自跑要下 3 個命令，好處是啟停及錯誤歸屬直接，缺點是人工 fan-out、回合容易不同步；main fan-out 只要 1 個命令且每回合自動推兩個 child，較順手，但先要手建 worlds 和 every JSON，之後仍沒有任務分派、全隊狀態、結果聚合與單一 child 重試；缺少 team/spawn/assign/status/collect/retry 這組隊伍原語；Claude Code／Codex 的父 agent／宿主會負責這些協調工作。

步驟 / 期待 / 實際 / 缺哪個原語 / 跟 Claude Code 開隊的對照：步驟 2 的 `find_folder`；期待從 `$T/opC/main/sub1` 執行 `aos say "hi"` 時選最近的 `.aos/`；實際訊息寫入 `main/sub1/.aos/agents/sub1/say/...md`，內容是 `hi`，main 的 say 目錄沒有該訊息，所以找到的是 sub1；缺少 `say` 成功後回顯解析到的 world／agent，無輸出時只能再查檔確認；Claude Code／Codex 派任務時通常直接顯示收件子 agent 身分。

## 步驟 3：對照 Claude Code／Codex 開隊

- Claude Code／Codex 類工具通常由操作者提出一次「開三隻並分工」請求，再由父 agent 呼叫 spawn；aos 要操作者先逐一建三個資料夾與 agent。
- Claude Code／Codex 的宿主替每隻子 agent 綁定 workspace／worktree；aos 的資料夾歸屬要靠操作者自己建立並在相對路徑中維持正確性。
- Claude Code／Codex 由父 agent 直接把任務送給具名子 agent；aos 要另建 contact、使用 `say`／inbox，或手寫 every inst 才有派送通道。
- Claude Code／Codex 的並行啟動、等待與喚回由宿主控制；aos 目前是 `aos run` 回合與 every JSON，沒有 team-level spawn／wait。
- Claude Code／Codex 能從一個控制面看到 running／idle／done；aos 的 `state` 只看單一 agent，`contact ls` 又不帶狀態。
- Claude Code／Codex 的子 agent 完成後會把摘要回傳父 agent；aos 沒有 collect/report 原語，操作者要自己 `listen` 或讀各世界檔案。
- Claude Code／Codex 的錯誤通常附著在特定子任務並回到父 agent；aos 的 nested out 雖可追 exit/stderr，但沒有主畫面的跨世界錯誤摘要。

## 步驟 4：錯誤訊息指不指路

步驟 / 期待 / 實際 / 缺哪個原語 / 跟 Claude Code 開隊的對照：在沒有 agent 的 `$T/opC` 執行 `aos say "hi"`；期待指出缺什麼以及下一步；實際原話是 `aos say: 這個資料夾還沒有 agent；請先跑 aos agent init`，看完知道下一步，這項有指路；缺少的只是把實際解析資料夾印出來；Claude Code／Codex 也會在沒有目標 agent 時要求先建立或指定目標。

步驟 / 期待 / 實際 / 缺哪個原語 / 跟 Claude Code 開隊的對照：在 main 執行 `aos say --to nobody "hi"`；期待指出通訊錄沒有此人並告知如何補；實際原話是 `aos say: 通訊錄裡沒有 nobody`，知道原因但不知道下一個完整命令，評為部分指路；缺少附上 `aos contact add nobody <folder>` 或建議先跑 `aos contact ls`；Claude Code／Codex 通常會列可用子 agent 或要求改用有效 id。

步驟 / 期待 / 實際 / 缺哪個原語 / 跟 Claude Code 開隊的對照：加入不存在路徑 x 再傳訊；期待 add 當場拒絕不存在路徑，或 say 清楚指出 contact 的目標路徑不存在；實際 add 原話是 `已登記聯絡人 x -> /不存在的路徑`，之後 say 原話卻是 `aos say: 這個資料夾還沒有 agent；請先跑 aos agent init`，會讓人誤以為只需在目前 main init，沒有指出實際解析的是 `/不存在的路徑`，看完不知道正確下一步；缺少 contact add 路徑驗證，以及 say 的目標路徑／contact 名稱上下文；Claude Code／Codex 的 spawn/dispatch 通常在目標不存在時直接綁定失敗的 agent id 或 workspace 回報。

步驟 / 期待 / 實際 / 缺哪個原語 / 跟 Claude Code 開隊的對照：加入不存在執行檔 bad 再 `aos tool ls`；期待指出 executable 不存在且不登記；實際 add 原話是 `aos tool: 探測不到表述，請用 --description 手填；探測行程退出碼是 127`，`aos tool ls` 隨後只有 cat／ls／sh，確認 bad 沒加入；訊息雖給了下一個形式步驟，卻把不存在執行檔包裝成「缺 description」，照做仍無法執行，評為錯誤指路；缺少 executable existence／exec failure 的直接診斷；Claude Code／Codex 的工具註冊層通常會把 schema/description 問題與 executable 找不到分開回報。

步驟 / 期待 / 實際 / 缺哪個原語 / 跟 Claude Code 開隊的對照：執行 `aos run --step 1 --step 2`；期待拒絕重複旗標並指出只能給一次；實際沒有任何錯誤訊息，反而跑了 turn 4 與 turn 5，等同採用最後一個 `--step 2`，還推進 sub1／sub2，因此看完完全不知道自己下錯；缺少 duplicate-option validation；Claude Code／Codex 的 CLI 解析層一般應在真正執行前拒絕歧義參數。

重複旗標的完整 stdout（stderr 空白）是：

```text
turn 4: 3 insts (3 every), 5028 ms
turn 5: 3 insts (3 every), 8 ms
```

附帶現象：因步驟 2 的 `aos say "hi"` 是排隊而非立即回覆，步驟 4 這個未被拒絕的 run 在 turn 4 處理了 sub1 的訊息並產生 assistant 回覆，因而間接使用既有 LLM 設定；操作者沒有操作 LM Studio。
