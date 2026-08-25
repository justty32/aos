# T5 agent loop 實測
← [experiments](README.md)

## 結論

**T5 驗收未全過。** 假模型的「模型 → 工具 → 模型看見工具結果」三回合完整跑通，回合之間的人工作業也會被下一次模型看見，每次單次 `aos exec` 都結束，沒有常駐 process；但是「中途 `Ctrl-C` 後再 `aos exec` 一次能從斷點繼續」只在 `aos exec --loop` 的優雅收尾語意下成立：第一次 SIGINT 會等當前回合跑完，停在回合邊界。單次 `aos exec` 真被 SIGINT 中止時會留下 `.runi`，下一次固定退出 3；人工把 `.runi` 搬回 `inst.json` 只能**重播整批**，不是從批次內斷點續跑，而且外部作用可能其實已完成。真模型未跑通：Codex 被沙盒唯讀狀態擋在初始化，Claude 的 OAuth 已過期，pi 未安裝。

實驗世界全部在 `/tmp/aos-t5/`，沒有把臨時腳本或 `.aos` 世界放進 repo。repo 只新增本資料夾的兩份紀錄。

## 實際做了什麼

### 1. 基線

從 repo 根目錄執行。configure 與 build 不是程式測試失敗，而是目前執行沙盒不允許 vcpkg 在 `/home/guanyu/dev/vcpkg/buildtrees/` 取得 write lock：

```text
$ cmake --preset default
Preset CMake variables:

  CMAKE_BUILD_TYPE="Debug"
  CMAKE_EXPORT_COMPILE_COMMANDS="ON"
  VCPKG_MANIFEST_FEATURES="tests"

-- Running vcpkg install
error: take_exclusive_file_lock("/home/guanyu/dev/vcpkg/buildtrees/vcpkg-running.lock"): Read-only file system
/home/guanyu/dev/vcpkg/buildtrees/vcpkg-running.lock: error: failed to take lock, another vcpkg may be running against the same directory
-- Running vcpkg install - failed
...
exit=1

$ cmake --build --preset default
-- Running vcpkg install
error: take_exclusive_file_lock("/home/guanyu/dev/vcpkg/buildtrees/vcpkg-running.lock"): Read-only file system
...
gmake: *** [Makefile:394: cmake_check_build_system] Error 1
exit=2
```

既有 build tree 的測試基線可執行，而且全綠，所以實驗使用既有的 `build/bin/aos`：

```text
$ ctest --preset default
Test project /mnt/c/code/mine/simple_tools/aos/build
    Start 1: aos_inst_tests
1/4 Test #1: aos_inst_tests ...................   Passed    7.63 sec
    Start 2: aos_inst_capi_tests
2/4 Test #2: aos_inst_capi_tests ..............   Passed    0.03 sec
    Start 3: aos_tooljson_tests
3/4 Test #3: aos_tooljson_tests ...............   Passed    0.09 sec
    Start 4: aos_llms_tests
4/4 Test #4: aos_llms_tests ...................   Passed    0.23 sec

100% tests passed, 0 tests failed out of 4

Total Test time (real) =   8.20 sec
exit=0
```

### 2. 假模型 golden slice

建立 `/tmp/aos-t5/` 後執行：

```text
$ /mnt/c/code/mine/simple_tools/aos/build/bin/aos init /tmp/aos-t5
exit=0
```

世界中的私有實驗腳本職責如下：

- `fake-model.sh` 讀 `prompt.txt`；沒有 `tool-result.txt` 時輸出固定具名 tool call，有結果時輸出 final。
- `model-to-next.sh` 只接受 `write_marker`，把固定 argv 寫到 `.aos/inst.tempd/<pid>.json.temp` 再 `mv` 成 `<pid>.json`；未知 tool 拒絕。
- `tool.sh` 執行具名工具並寫 `tool-result.txt`。
- `schedule-model.sh` 用同一套 temp＋rename 投下一次模型批次。

第一回合的真實結果：

```text
$ /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec /tmp/aos-t5
exit=0
stdout:

stderr:

model-output.json:
{"kind":"tool_call","tool":"write_marker","argument":"TOOL_OK"}

adapter.stdout:
published .aos/inst.tempd/11.json

.aos/inst.tempd/11.json:
[{"argv":["./tool.sh","TOOL_OK"],"stdout":"tool.stdout","stderr":"tool.stderr","exit":"tool.exit"},{"argv":["./schedule-model.sh"],"exit":"schedule.exit"}]
```

這一份 delivery 是陣列：同一回合要多筆且有順序時，放在同一 delivery 內可保留順序。接著在人為回合邊界把 prompt 改成：

```text
HUMAN_EDIT_BETWEEN_TURNS: report the tool result now.
```

工具回合與第二次模型回合：

```text
$ /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec /tmp/aos-t5
exit=0
stdout:
published .aos/inst.tempd/11.json
stderr:

tool-result.txt:
TOOL_OK
tool.exit:
0

$ /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec /tmp/aos-t5
exit=0
stdout:

stderr:

final.json:
{"kind":"final","text":"saw result: TOOL_OK; prompt: HUMAN_EDIT_BETWEEN_TURNS: report the tool result now."}
```

因此以下三項是實測通過，不是推測：具名工具在下一回合執行、再下一回合模型看見結果、人在回合之間的修改被下一回合看見。每次 `aos exec` 都返回，沒有 daemon。

### 3. 投遞：原子 rename、壞 JSON 與檔名碰撞

一份壞 JSON 和一份好 delivery 同時放入 inbox：

```text
$ /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec /tmp/aos-t5
exit=0
good_result=good-survived
stderr:
aos exec: warning: .aos/inst.tempd/1001.json: JsonSyntax
inbox:
1001.json.bad

$ cat .aos/inst.tempd/1001.json.bad
{"argv":[
```

壞檔照規格被隔離成 `.bad`，沒有擋住好檔。

為了測「直接寫 `<pid>.json` 不經 `.temp`」是否真的會壞，`direct-writer.sh` 先把 `{"argv":[` 寫入 ready 檔、停兩秒，再補完其餘內容；在停住時執行 `aos exec`：

```text
writer_pid=8 state_before_exec=partial-visible ready_exists=yes
$ /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec /tmp/aos-t5
exec_exit=0
writer_exit=0
writer_state=writer-finished
tool_ran=no
stderr:
aos exec: warning: .aos/inst.tempd/4242.json: JsonSyntax
inbox:
1001.json.bad size=10
4242.json.bad size=67

$ cat .aos/inst.tempd/4242.json.bad
{"argv":["/bin/sh","-c","printf should-not-run > direct-ran.txt"]}
```

也就是彙整者真的看見半份 JSON 並把它 rename 成 `.bad`；writer 已開啟的 fd 仍指向同一 inode，所以後來把內容補完整到 `.bad`，但該工作永遠不會執行。temp＋rename 不是形式要求，而是必要的可見性邊界。

只用 PID 也不夠表達「同一 producer 一回合投很多份」。同一 shell 連做兩次 temp＋rename，兩次都叫 `<同一 pid>.json`：

```text
$ ./pid-collision.sh
published twice as .aos/inst.tempd/8.json

$ cat .aos/inst.tempd/8.json
{"argv":["/bin/sh","-c","printf second > collision-second.txt"]}

$ /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec /tmp/aos-t5
exit=0
first_exists=no
second=second
```

第二次 `rename` 在 POSIX 上直接取代同名 ready 檔，第一份靜默遺失。腳本若要一回合多筆，必須把多筆包成同一 JSON array；若 API 要允許多次 deliver，檔名還需要 PID 之外的 counter／nonce，並避免覆蓋既有 ready 檔。

### 4. Ctrl-C、`.runi` 與「續跑」

先保留一個失敗嘗試：把 exec 放進非互動 bash 的背景後再 `kill -INT`，背景 job 繼承忽略 SIGINT，結果不是一次有效的 Ctrl-C 測試：

```text
aos_pid=9
before_SIGINT state=started runi=yes
after_SIGINT exit=0 state=completed runi=no
--- immediate second aos exec
exit=0
```

改用前景 `timeout` 真送 SIGINT：

```text
$ timeout --preserve-status -s INT 0.3 /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec /tmp/aos-t5
exit=130
state=started
runi=yes
child_exit=missing

$ /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec /tmp/aos-t5
exit=3
stderr:
aos exec: refusing /tmp/aos-t5: .aos/inst.json.runi already exists

six_seconds_later state=completed child_exit=missing runi=yes
```

最關鍵的現場是：parent 死後，子行程因自己的 process group 沒收到該 SIGINT，仍完成了 `state=completed`；但 parent 沒有機會 wait 並寫 `exit`，所以留下「作用看似完成、沒有 exit、`.runi` 仍在」的 unknown。

人工恢復只能自己選政策。把 `.runi` 搬回 queue 的結果是整批重播：

```text
$ mv .aos/inst.json.runi .aos/inst.json
$ /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec /tmp/aos-t5
exit=0
state=completed
child_exit=0
runi=no
```

這次作用只是覆寫同一檔，所以看起來安全；非冪等工具可能已重做。沒有「從 instruction 內部 program counter 繼續」這回事。

`--loop` 的第一次 SIGINT 是另一種語意，實作與規格第十二節一致：它等當前回合完整結束才退出。慢回合在結束前投下一批，0.3 秒時送 SIGINT：

```text
$ timeout --preserve-status -s INT 0.3 /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec --loop 100 /tmp/aos-t5
exit=0
loop_state=finished
child_exit=0
runi=no
inst_json=no
queued:
11.json

$ /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec /tmp/aos-t5
exit=0
continued=continued
runi=no
```

所以可可靠承諾的是「優雅 SIGINT 後停在**下一個完整回合邊界**」，不是「批次內斷點續跑」。

### 5. 空 `inst.json` 與沒有 `inst.json`

```text
$ stat -c %s .aos/inst.json
0
$ /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec /tmp/aos-t5
exit=1
inst_exists=no
runi_exists=no
stderr:
aos exec: .aos/inst.json.runi: JsonSyntax

$ /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec /tmp/aos-t5
exit=0
stdout:

stderr:
```

0-byte `inst.json` 是壞 JSON，實際退出 1 並清掉 `.runi`；「沒有 `inst.json`」才是規格所說的 no-op 0。

### 6. 真 agent CLI

本機候選：

```text
codex path=/home/guanyu/.local/bin/codex command_v_exit=0
pi path=missing command_v_exit=1
claude path=/home/guanyu/.local/bin/claude command_v_exit=0
```

Codex 的 help 證實 stdin、`--json`、`--output-last-message`、`--ephemeral` 與 resume 介面存在；但真呼叫沒進到模型：

```text
$ printf 'Reply with exactly REAL_CODEX_OK ...' | timeout 45 codex exec --ephemeral --json -o codex-final.txt -s read-only -C /tmp/aos-t5 --skip-git-repo-check -
exit=1
stderr:
WARNING: proceeding, even though we could not create PATH aliases: Read-only file system (os error 30)
Error: failed to initialize in-process app-server client: Read-only file system (os error 30)
jsonl:
final: missing
```

Claude 能從 stdin 回結構化單筆結果並給 session id，但帳號狀態不可用：

```text
$ printf 'Reply with exactly REAL_CLAUDE_OK ...' | timeout 45 claude -p --input-format text --output-format json --no-session-persistence --permission-mode dontAsk
exit=1
{"is_error":true,...,"session_id":"420b6757-7eb0-4a17-b8a6-f8b066a54d7e",...,"api_error_status":401,"result":"Failed to authenticate. API Error: 401 OAuth access token has expired. Re-authenticate to continue.","type":"result",...}
```

因此真模型明確是「試了但沒跑成」，不是「沒試」；取消成功呼叫、session resume 與真 tool-call event 都沒有可誠實報告的實測結果。

### 7. reliability 題的補充實驗

對 `request` 已寫、provider effect 已發生、`result.temp` 尚未 rename 三個時間點，各對同一支假三步 loop 送 SIGINT 與 SIGKILL：

```text
case=int_request signal=INT at=0.2s exit=130 files=request,
case=int_effect signal=INT at=0.6s exit=130 files=provider-effect,request,
case=int_result_temp signal=INT at=1.0s exit=130 files=provider-effect,request,result.temp,
case=kill_request signal=KILL at=0.2s exit=137 files=request,
case=kill_effect signal=KILL at=0.6s exit=137 files=provider-effect,request,
case=kill_result_temp signal=KILL at=1.0s exit=137 files=provider-effect,request,result.temp,
```

在這個只靠已落盤 marker 的假 loop 中，SIGINT 與 SIGKILL 留下同樣種類的判讀證據；hard kill 已足以逼出 request／effect／result-temp 三相狀態。這沒有測斷電與 fsync，不能外推成 power-loss durability。

假 provider 接到 key 後先記外部 ledger，再故意於回結果前斷線：

```text
--- first call: effect happened, result lost
exit=70
ledger_lines=1
provider accepted request-42, transport broke before result

--- policy A: stop
ledger_lines=1
no result produced

--- policy B: query by provider key
exit=0
result=recovered-result-for-request-42
ledger_lines=1

--- policy C: blind retry
exit=70
ledger_lines=2
ledger:
request-42
request-42
```

可對帳時查 key 能在不重做 effect 的情況下取回；盲目 retry 在這個假 provider 確實造成兩筆外部作用。

## 痛在哪：可直接寫成子命令的需求

### `aos deliver [WORLD] [-f FILE|-]`

我需要 `aos deliver`，因為三支不同腳本現在都得自己做：驗證 object／array、產生 inbox 檔名、write-all 到 `.json.temp`、rename 成 `.json`、處理 rename／I/O 錯誤。檔名不能只有 PID：同 process 第二次投遞會覆蓋第一份，PID 重用也有同類風險。命令至少要：

1. 接受單一 instruction 或 array，發布前用唯一 parser 驗完整批次。
2. 用 PID＋單調 counter 或不可碰撞 nonce 產生名稱，建立 temp 時拒絕既有檔。
3. ready 發布不得覆蓋既有名稱；成功回 machine-readable delivery id、count 與 target。
4. 永遠內建 temp＋rename，不暴露「直接寫 ready」的捷徑。

### `aos recover [WORLD]`

我需要 `aos recover`，因為 `.runi` 現在只說「未完成」，腳本／人還得自己查看 batch、世界作用、外部 request id 與缺少的 exit，然後徒手 `mv`。命令不能假裝有 program counter；它應先唯讀列出 `.runi`、每筆 exit/result 證據與可能仍活著的未知子行程，再要求明示選一個動作：

- `--replay`：把整批放回 queue，醒目標示可能重複作用。
- `--abandon`：保留 forensic 副本並解鎖，不重跑。
- `--adopt RECEIPT`：已有可對帳結果時記錄採用，再解鎖。

沒有足夠證據時預設必須停住，而不是自動重播。

### `aos status --json [WORLD]`

我需要穩定的 `status --json`，因為實驗每一步都用 `find`、`test -f`、`cat` 手工拼出 `inst.json`／`.runi`／ready／temp／bad／各 instruction exit 的現況，很容易漏掉「子行程已完成但 exit 缺失」這種組合。輸出要區分 `ready`、`running`、`blocked-runi`、`bad-delivery`、`no-work` 與 `unknown-effect`，但不要把 prompt 政策塞進 status。

### `aos agent step [WORLD]`

我需要一支仍受限於具名工具 registry 的 `agent step`，因為目前 adapter 自己 parse 模型 JSON、把 tool name 映到固定 argv、拒絕未知工具、安排工具後的下一次模型、保存 raw／final。這支命令要保存至少 `request-published → effect-started → result-temp → result-published → next-delivered` 的 phase evidence；否則 SIGINT 後只剩 `.runi`，不知道是否可重試。它不應讓模型輸出的任意 argv 直通。

### `aos agent emit-context [WORLD]`

我需要一個只輸出穩定 context envelope 的命令，因為第二次模型呼叫目前由腳本自己選 `prompt.txt`、`tool-result.txt` 與人工修改，再重組輸入。輸出需帶 turn、source path／hash、上一個 tool result 與 request id；不負責寫 provider-specific system prompt，也不從 raw `aos exec` stdout 猜結果。

## 哪幾題被實驗回答了

以下答案都是本次實測結果，不是意見；「回答」只到實驗所覆蓋的範圍。

### OPEN #2：近期 core 要回撤到哪裡？

私有 helper 已完成串行三回合；temp＋rename 邏輯在 `model-to-next.sh`、`schedule-model.sh`、`slow-publish.sh` 重寫三次；外部作用有一個本機無法自行判定的 unknown；沒有第二個工作需要 lane／join／控制平面。**實測支持近期先收掉 Deliver 的重複與 provider adapter 的 phase evidence；沒有實測證據支持先做完整控制平面。** 是否把 Effect 公開成 core API，這次仍未回答。

### OPEN #6：golden slice 先用哪支真 agent CLI？

在本環境 Codex 介面形狀合適但因 state 目錄唯讀無法初始化；Claude 可辨認 JSON final 與 session id，但 OAuth 401；pi 未安裝。**當下沒有一支候選能完成真模型 slice，因此本次只能用 fake model。** 這是環境可用性排除結果，不是永久產品選擇。

### OPEN #12：遠端效果變成 unknown 時預設怎麼辦？

假 provider 證明 blind retry 會把同 key 外部作用從一筆變兩筆；provider 可依 key 對帳時，query 能取回而不增加 ledger。**機制上的答案是：可對帳才有安全的自動恢復路；不可對帳時本機檔案不能證明外部沒做，必須保留 unknown。** 最終願不願意接受重複風險仍是政策選擇。

### OPEN #13：crash 要承諾到哪一級？

三個 kill point 的 SIGINT 與 SIGKILL 都留下可區分的磁碟 phase；單次 `aos exec` 的 SIGINT 也已產生「effect 完成、exit 缺失、`.runi` 留著」。**hard kill 已經逼出 phase evidence 與 recovery action 的需求；只測優雅 Ctrl-C 不足。** 斷電、page cache、file fsync 與 directory fsync 沒測，不能回答是否承諾 power loss。

### OPEN #4：模型與工具先給到什麼權限？

在 `/tmp` 玩具世界與現有宿主沙盒內，只有 `write_marker` 的固定映射可以無逐步人工批准完成閉環，未知 tool 由 adapter 拒絕。**這回答了玩具 slice 不需要每步人工批准；沒有證明同 UID 的具名映射是安全邊界，也沒有跑 unsandboxed 對照。**

### OPEN #18：stdout→stdin 的穩定 context 從哪裡來？

request file 方式可跑兩次模型，第二次讀到工具結果與人類修改；raw `aos exec` stdout 沒被當 context。**request file 可行，但腳本重複選檔與組 envelope。** 本次沒有實作假 `status --json`／`emit` 三方比較，所以尚不能決定公開介面。

## 哪幾題實驗後反而更不確定

- **OPEN #13 與 T5 的 Ctrl-C 契約**：`--loop` 的優雅 SIGINT 很乾淨，但它等待整回合完，不是斷點；單次 exec 才會留下 crash 現場，卻完全不能直接續。roadmap 的一句驗收同時像在描述兩者。
- **OPEN #8 的 delivery key**：PID 已證明不夠唯一，但改成 nonce 只解碰撞，不解 aggregate 後的重送記憶。要 correlation 還是耐久 dedupe ledger，這次沒有答案。
- **OPEN #19 的 session**：Claude 的 JSON 很容易取得 session id，Codex 也有 resume 介面，但兩者都沒完成一次真呼叫，無法比較 no-session 重建與 resume 的延遲／可靠度。
- **OPEN #24 的 tool set**：實驗流程實際用了 Init（一次性建世界）、Deliver（腳本）、Exec（外部 driver）與手工 Status；這顯示四種能力都有用途，卻沒有回答哪些該同時暴露給模型、哪些只屬人工／建置期。

## 規格與實作對不上的地方

1. **T5 的 Ctrl-C 驗收與既有 `.runi` 契約沒有共同的「續跑」定義。** `docs/aos-folder.md` 第六節明定 `.runi` 要人處理、存在時退出 3；實作完全照做。roadmap 卻寫「中途 Ctrl-C 之後再 `aos exec` 一次能從斷點繼續」。實測顯示只有 `--loop` 優雅停在完整回合邊界後符合較弱版本；真正中止單次 exec 時，第二次一定被擋。這至少是文件契約缺口，若 roadmap 的字面是要求自動續跑，則是尚未實作的功能。
2. **唯一真源第六節對壞 `inst.json` 的「正常返回」容易被讀成退出 0，第八節表格又沒列 JSON/schema 錯。** 0-byte `inst.json` 實際清掉 `.runi` 但退出 1；`docs/usage.md` 有明列這個 1。實作內部一致，問題是 `docs/aos-folder.md` 的退出碼表不完整／措辭含混。
3. **投遞協定只用 `<pid>.json` 無法安全表達同一 process 多次 deliver。** temp＋rename 本身有做到原子可見，但第二次 rename 會覆蓋同名 ready。規格只說 PID 防多 producer 共用檔名，沒有定同 producer 多次投遞的命名或 no-replace 規則；實作又尚無 Deliver 可統一補強。
4. **「子行程自成 process group」與單次 exec 的 SIGINT 會形成可觀察的 unknown。** parent 被 SIGINT 後子行程繼續完成，`.runi` 留著且 exit 缺失。規格有分別描述 process group 與 `.runi`，但沒有把這個組合寫進人工恢復契約；目前不是違反規格，而是缺少能安全操作的 recovery 規格與命令。

## 最後驗證

本紀錄建立後，從 repo 根目錄再次執行：

```text
$ ctest --preset default
Test project /mnt/c/code/mine/simple_tools/aos/build
    Start 1: aos_inst_tests
1/4 Test #1: aos_inst_tests ...................   Passed    8.08 sec
    Start 2: aos_inst_capi_tests
2/4 Test #2: aos_inst_capi_tests ..............   Passed    0.02 sec
    Start 3: aos_tooljson_tests
3/4 Test #3: aos_tooljson_tests ...............   Passed    0.04 sec
    Start 4: aos_llms_tests
4/4 Test #4: aos_llms_tests ...................   Passed    0.09 sec

100% tests passed, 0 tests failed out of 4

Total Test time (real) =   8.32 sec
exit=0
```
