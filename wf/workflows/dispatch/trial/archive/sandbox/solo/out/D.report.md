D-01,L1,bug,2,錯誤1 無 agent 的 run,應非零結束並提示先跑 aos agent init,原文 `turn 1: idle`；exit=0；且在 nowhere 新建 `.aos/`,pi：`pi -p` 1 個指令且不用先建世界,repro/D-01.sh
D-02,L1,bug,3,錯誤3a agent 端點不通,run 應非零且 state 或 listen 應顯示失敗與修正端點的方法,run 原文只有 `turn 2: 1 insts (1 every)，3 ms` 且 exit=0；state 原文 `status: idle`；listen 只有使用者訊息；真正錯誤 `aos agent: LLM 連線失敗: Failed to connect to localhost port 19999 after 0 ms: Could not connect to server` 藏在 batch 且 inner exit=1,pi：1 個指令且連線錯誤在該前景命令回報,repro/D-02.sh
D-03,L1,bug,3,錯誤3b 模型不存在,指定 no/such-model 應被拒絕並指出可用模型,隊長實測：exit=0，回了一段正常英文回覆，沒有任何「模型不存在」的提示,pi：1 個指令；錯模型由同一前景命令回報,repro/D-03.sh
D-04,L1,awkward,2,錯誤4 pi 缺 key,init 就應提示設定 DEEPSEEK_API_KEY 的具體位置或指令,init 無輸出且 exit=0；run exit=0；listen 原文 `No API key found for deepseek.  Use /login to log into a provider via OAuth or API key.`，沒有 `DEEPSEEK_API_KEY`,直接 pi：1 個指令就於同一命令顯示缺 key；aos 到看見錯誤共 5 個指令,-
D-05,L1,awkward,1,錯誤5 工具子命令,直覺的 tool list 與 tool remove 應可用或免重試,原文 `aos tool ls [--folder F] [--json]` 與 `aos tool rm <name> [--folder F]`；tool list 與 tool remove nosuchtool 均 exit=2；tool add 少參數也 exit=2 且有正確用法,pi：不需工具登記；直接要求任務 1 個指令,-
D-06,L1,cannot,1,錯誤5 不存在工具,自然語言指定未登記的 make 後應能在 listen 看到 unknown_tool JSON,run 6 回合 exit=0；listen 沒有 unknown_tool，模型改呼叫 sh 且兩次原文 `工具 sh 的 args 必須是字串` 後才成功,pi：1 個指令直接用內建 bash 跑 make,-
D-07,L1,bug,2,錯誤6 不存在路徑,應明說 `/nonexistent/path` 不存在並提示改正路徑,原文 `aos run: 無法建立 /nonexistent/path/.aos/inbox: Permission denied`；exit=1,pi：在目標專案內 1 個指令；不需另傳世界路徑,repro/D-07.sh
D-08,L1,bug,3,錯誤3 前景用絕對 AOS 但 PATH 無 aos,依任務要求用絕對路徑呼叫就應能推進 agent 或立即指出 PATH 需求,run 兩回合都印 `1 insts (1 every)` 且 outer exit=0；batch 實際 argv 是裸的 `aos agent step` 且兩次 inner exit=127；state 仍 idle,pi：PATH 中已有 pi；1 個指令即可工作,repro/D-08.sh
D-09,L1,awkward,3,步驟7 最小編輯,一次指令應完成簡單追加且錯誤後能快速自我修正,前 12 回合 25.320 秒仍未改檔；原文 `工具 sh 的 args 必須是字串` 重複 5 次；補 3 回合 1.494 秒後才成功；總計 10 個終端指令與 15 回合,pi：`pi -p` 1 個指令，22.008 秒完成,-

敘事報告

劇本全走完，`/tmp/aos-d-empty` 已清。無 agent 與參數錯誤都有指路。最痛的是錯 port（inner 1）或 PATH（inner 127）時，run 仍 exit 0、state 仍 idle，真錯誤只在 batch JSON。pi init 也不提醒缺 key。

總帳第一列以 README 最小編輯代測 parse()；make 與記憶列皆實跑：

| 使用者心裡的一句話 | aos 指令 | 回合 | pi 指令 |
|---|---:|---:|---:|
| 改 parse() 回傳 optional | 10 | 15 | 1 |
| 它現在在幹嘛 | 1 | — | 0 |
| 跑測試 | 3 | 6 | 1 |
| 剛才叫你做什麼 | 3 | 1 | 1 |
| 開新 agent 工作 | 5 | — | 1 |

最小可用一輪的完整序列為：

```sh
mkdir -p "$SOLO/D/plain/.aos"
cd "$SOLO/D/plain"
$AOS agent init
$AOS say '幫我在 README.md 最後加一行 # tried'
timeout 900 $AOS run . --step 12
$AOS listen --once
tail -1 README.md
timeout 900 $AOS run . --step 3
$AOS listen --once
tail -1 README.md
```

aos 共 10 指令、15 回合，run 合計 26.814 秒；第一次驗證未改檔。`pi -p '在 README.md 最後加一行 # tried'` 共 1 指令、22.008 秒，一次成功。