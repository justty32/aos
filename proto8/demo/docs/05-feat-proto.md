← [回入口 README.md](../README.md)｜段落：新功能原型的假腦劇本（11-05 午 feat-proto）｜上一份：[04-kernel-modes](04-kernel-modes.md)｜下一份：—

## 新功能原型的假腦劇本：agent 自改工具、能力包與排程、agent 生 agent、資源份額（11-05 午）

使用者 11-05 午：「讓agent給自己改tool，把endpoint打包成smart-high, stupid-fast, ...這類，並且附上各種屬性(各種temperature也固定)，讓kernel能根據信件中額外附送的priority之類資訊做排程，讓agent利用aos指令產出另一個agent」「啊，還有，會想要限制特定aos proc所占用的資源。以及daemon/kernel自己本身被限制占用資源，並且會分配份額給proc」。設計：[thinking feat-proto](../../thinking/2026-11/05/feat-proto/README.md)。

下面四段都是假腦（[03](03-llm-kernel.md) 的 `fake-demo-*` 包照劇本回答），零成本、可重跑；每段從空的 `/tmp/feat-s9-*` 起、各起自己的 llm daemon（背景，`K=$!`／`D=$!` 記 pid），跑完 `kill` 收工。PATH 放 `proto8/impls/*/bin`、`proto8/bin`、`proto8/extras/agent/bin`（或跑過 `proto8/install.sh`）；`P` 換成你的 repo。11-05 在 WSL 照抄跑過。

### 件 1：agent 給自己加工具（`self_tools`）

```sh
P=~/repo/simple_tools/aos/proto8
T=/tmp/feat-s9-self && rm -rf $T && mkdir -p $T/ws/.stack && cd $T
aos-exec --stack $T/k $P/demo/llm-kernel > k.log 2>&1 & K=$!     # llm daemon（假腦包都在它的 kernel.json）；K 記它的 pid 好收工
export AOS_LLM_KERNEL=$T/k
echo '{"interval_ms": 300}' > daemon.json
AOS_STACK=$T/ws/.stack/ aos-daemon daemon.json > d.log 2>&1 & D=$!   # 跑 agent 的 daemon（環境帶著 AOS_LLM_KERNEL）
sleep 1 && cd ws                                                   # cwd 有 .stack＝aos-agent 找得到 daemon
aos-agent ctl add --name fsm1 $P/demo/agent-fsm
aos-agent llm --target fsm1 set endpoint=fake-demo-self                # 換成劇本腦（self_tools 範本內建，11-05 使用者裁「內建」）
aos-agent say --target fsm1 give yourself a math tool && aos-agent listen --target fsm1
# I added math to my own tools and used it right away: 17*23 = 391.
aos-agent tools --target fsm1 ls          # 多一行 math（定義疊這隻的覆蓋層）
aos-agent ctl state --target fsm1         # tools   overlay: 1 added, 0 removed (+math)
kill $K $D                                # 收工（daemon 把它掛的收掉）
```

劇本三步：叫 `self_tools {"op": "add", "name": "math", "path": "<repo>/proto8/lib/base/math"}`（工具裡 `aos-agent ctl who` 查 daemon 表認出「我是 fsm1」，再 `aos-agent tools --target fsm1 add`）→ 下一格 brain 重讀就看到 math、叫 `math {"expr": "17*23"}` 得 `391` → 答一句。history 裡看得到兩則 tool 結果（`added math (…) to your tools; available from your next turn`、`391`）。定義資料夾沒動；`aos-agent tools --target fsm1 reset` 一刀回定義。

### 件 2、3：能力包與排程（包的 `slots` 補位、`speed` 先後）

```sh
T=/tmp/feat-s9-sched && rm -rf $T && mkdir -p $T && cd $T
aos-exec --stack $T/k $P/demo/llm-kernel > k.log 2>&1 & K=$!
export AOS_LLM_KERNEL=$T/k && sleep 1
aos-llm ls                                # 一行一包；fake-demo-fast／slow 的 slots 是 1
echo '{"endpoint": "smart-high", "request": {"messages": [{"role": "user", "content": "hi"}], "temperature": 1}}' | aos-llm ask
# aos-llm: error: RequestBad temperature is fixed by endpoint smart-high (remove it from the request; to change it pick another endpoint name)
for e in fake-demo-slow fake-demo-slow fake-demo-fast fake-demo-fast; do
  echo "{\"endpoint\": \"$e\", \"request\": {\"messages\": [{\"role\": \"user\", \"content\": \"hi $e\"}]}}" | aos-llm send --reply-to box
done                                      # 印四個信件名稱（先寄兩封 slow、再兩封 fast）
sleep 1 && aos-daemon-ctl --daemon $T/k ls   # 只有兩列 running：第 3 封（fast）、第 1 封（slow）
sleep 8 && ls box/new | wc -l             # 4：四封回信都到了（FAKE ANSWER to: hi …）
kill $K
```

kernel 總 `slots` 2、兩包各 `slots` 1、每封 3 秒：同級的信 fast 包排前面；fast 包第二封因為包滿了被**跳過**，讓 slow 包的第一封補上第二格（不是整列卡住）。3 秒後收成品、再掛各包的第二封。`smart-high` 那封沒掛出去：信寫了包釘死的 `temperature`。

### 件 4：agent 生 agent（`agents`；判官 `max_running` 4）

```sh
T=/tmp/feat-s9-spawn && rm -rf $T && mkdir -p $T/ws && cd $T
aos-exec --stack $T/k $P/demo/llm-kernel > k.log 2>&1 & K=$!
export AOS_LLM_KERNEL=$T/k AOS_DAEMON=$T/st AOS_KERNEL=$T/st/requests   # 掛 proc 都先過判官（demo/docs/04 模式 1）
aos-exec --stack $T/st $P/demo/daemon-judge > d.log 2>&1 & D=$!         # 帶判官的 daemon：allowed 有 fsm1、kid、kid1～4，max_running 4
sleep 1
aos-agent ctl add --name fsm1 --ws $T/ws $P/demo/agent-fsm
aos-agent llm --target fsm1 set endpoint=fake-demo-spawn             # agents 範本內建（11-05「內建」）
aos-agent say --target fsm1 start a kid and ask it the time && aos-agent listen --target fsm1
# I started kid, asked it the time (its answer is in the tool result above) and removed it again.
aos-agent say --target fsm1 now start four kids && aos-agent listen --target fsm1
# I wrote defs/helper and started kid1 from it, kid2 and kid3 from the same definition; kid4 was refused by the judge (4 running at once, I count too). I removed the three again.
aos-agent ctl ls                          # 只剩 fsm1
ls ws/defs/helper                         # kid1 那時寫出的定義留著（普通定義資料夾，可再 add）
tail -1 d.log                             # judge: warning: letter … refused: SlotMissing max_running is 4, 4 running now …
kill $K $D && unset AOS_DAEMON AOS_KERNEL
```

第一題劇本（生法 (b) 用現有定義）：`agents add {"name": "kid", "def": "<repo>/proto8/demo/agent-fsm", "llm": {"endpoint": "fake"}}`（`llm` 走 kid 自己的覆蓋層 `<kid stack>/llm.json`，定義不動）→ `ask kid "what time is it?"`（kid 的假腦先叫 clock〔`fake` 包寫 `"tool": "clock"`〕、答 `FAKE ANSWER to: what time is it? (tool said: 2026-11-05T…Z)`，成了 fsm1 的 tool 結果）→ `rm kid`。第二題一次叫四個：kid1 用生法 (a) `agents new {"path": "defs/helper", "from": "<repo>/proto8/demo/agent-fsm", "files": {"system.txt": …}, "llm": {"endpoint": "fake"}}`——範本整份抄到 `ws/defs/helper`、換掉 `system.txt`、`llm.json` 寫進 `endpoint`、`tools.json` 的相對路徑改成絕對，再掛上；kid2、kid3 用 (b) `add {"def": "defs/helper"}` 重用它（kid3 另給 `"ws": "kid3"`＝`ws/kid3/`）；fsm1＋三隻＝4 隻 running，kid4 被判官擋，回給腦一則 `agents: error: AddRejected AOS_KERNEL refused the add letter: SlotMissing …`；再 rm 三隻。kid 用的是自己定義裡的腦與工具（不繼承 fsm1 的）；`ws` 沒給＝跟 fsm1 同一個；`agents` 只收自己生的（`$AOS_STACK/children.json`）。

**兩道關**：`agents` 工具自己數這隻父生了幾隻（`max_children`，範本 `agents.json` 寫 4；記在父 stack 裡工具小格的 `children.json`，每次叫先跟 daemon 表對帳），超過＝工具直接回錯、不寄信；判官 `max_running` 數的是整台 daemon 的總量（含父）。上面第二題撞的是判官（父只有三隻，工具放行）。要看工具那道，照 act 格的叫法手叫一次（接在上面 `kill` 之前；`FS` 是 fsm1 的 stack）：

```sh
FS=$T/st/procs/fsm1 && export AOS_STACK=$FS/tools/agents/ AOS_WS=$T/ws
echo '{"max_children": 1}' > $FS/agents.json        # 這隻父的覆蓋層：只放改過的鍵（定義 agents.json 不動）
echo '{"op": "add", "name": "kid1", "def": "defs/helper"}' | aos-tools --file $P/demo/agent-fsm/tools.json call agents
# added kid1 (stack …/procs/kid1); children 1/1
echo '{"op": "add", "name": "kid2", "def": "defs/helper"}' | aos-tools --file $P/demo/agent-fsm/tools.json call agents; echo $?
# agents: error: ChildSlotMissing you already have 1 of max 1 children (kid1); remove one with op rm first (…)   ← stdout 與 stderr 各一行
# 1                                         （判官信箱沒多信：工具在寄信前就擋了）
aos-agent ctl rm kid1                     # 別處收掉也行：下次叫工具時對帳、kid1 被忘掉
echo '{"op": "ls"}' | aos-tools --file $P/demo/agent-fsm/tools.json call agents   # … "children": [], "max_children": 1}
rm $FS/agents.json && unset AOS_STACK AOS_WS
```

### 件 5：資源份額（daemon 在子行程 setrlimit）

```sh
T=/tmp/feat-s9-limits && rm -rf $T && mkdir -p $T/ws/.stack $T/hog && cd $T
echo '{"interval_ms": 300}' > daemon.json
echo '{"aos-agent": {"limits": {"mem_mb": 256}}}' > hog/interfaces.json     # 這隻建議的份額
echo '["aos-loop", "loop.json"]' > hog/_entry
echo '{"exec": {"argv": ["python3", "-c", "b = bytearray(300 * 2**20)"]}, "max": 1}' > hog/loop.json   # 吃 300 MB
cp -r hog hog-big && sed -i s/300/3000/ hog-big/loop.json                   # 吃 3000 MB
AOS_STACK=$T/ws/.stack/ prlimit --as=2048000000 aos-daemon daemon.json > d.log 2>&1 & D=$!   # daemon 自己被限 2 GB（起它的人包；同 ulimit -v 2000000）
sleep 1 && cd ws
aos-agent ctl add ../hog && sleep 2       # 宣告的 mem_mb 256 送到 daemon：吃 300 MB 撞上
aos-agent ctl state --target hog          # state stopped、reason failed to start: … (code 1): MemoryError；limits  mem_mb=256
aos-agent ctl add --name hog2 --limits '{"mem_mb": 1024}' ../hog && sleep 2   # --limits 蓋過宣告：吃完 300 MB 退 0、下表
aos-agent ctl add --name big --limits '{"mem_mb": 4096}' ../hog-big && sleep 2
aos-agent ctl state --target big          # reason … aos-daemon: error: LimitBad mem_mb 4096 exceeds the daemon's own hard limit
aos-agent ctl add --name big2 --limits '{}' ../hog-big && sleep 2              # {}＝自己不限，但超不過 daemon 的 2 GB
aos-agent ctl state --target big2         # reason failed to start: … (code 1): MemoryError
aos-agent ctl ls                          # hog、big、big2 stopped＋reason；hog2 吃完已下表
kill $D
```

- **daemon 包子項**（使用者「讓daemon偷偷給底下的proc包s6」）：表那列的 `limits`（定義宣告的，或 `ctl add --limits` 蓋過的）由 daemon 在子行程裡 `setrlimit`（等同 s6-softlimit；proc 自己不知道）——hog 宣告 `mem_mb: 256`、要 300 MB＝Python `MemoryError`、退 1、表上留 `stopped`＋`reason`；`--limits '{"mem_mb": 1024}'` 的 hog2 照常吃完、下表。規則見 [aos-daemon docs/09](../../impls/aos-daemon/docs/09-份額.md)。
- **daemon 自己被限**：起它的人包（這裡 `prlimit --as`），rlimit 繼承——big 寫 `mem_mb: 4096` 比 daemon 的 2 GB 寬＝不自動夾，那隻起不來（`LimitBad`）；big2 自己不限（`{}`），要 3 GB 照樣撞 daemon 的 2 GB＝`MemoryError`。
- **天然差異**：份額是每個行程各自的上限、不從 daemon 總額扣（三隻各 1024 加起來可以超過 daemon 的 2 GB）。
- **llm kernel 的份額**＝包的 `budget`＋每個寄件人的 `budget.senders`。範本限了寄件人 `/tmp/aos-demo-sender` 每天 1 次（帳記在 kernel 的 `used.json`，新起一台就從 0 算）：

```sh
T=/tmp/feat-s9-quota && rm -rf $T && mkdir -p $T /tmp/aos-demo-sender && cd $T
aos-exec --stack $T/k $P/demo/llm-kernel > k.log 2>&1 & K=$!
export AOS_LLM_KERNEL=$T/k && sleep 1
echo '{"request": {"messages": [{"role": "user", "content": "hi"}]}}' | AOS_WS=/tmp/aos-demo-sender aos-llm ask   # FAKE ANSWER to: hi
echo '{"request": {"messages": [{"role": "user", "content": "hi"}]}}' | AOS_WS=/tmp/aos-demo-sender aos-llm ask
# aos-llm: error: BudgetMissing sender /tmp/aos-demo-sender: max_calls 1 reached in this window (day); not run
echo '{"request": {"messages": [{"role": "user", "content": "hi"}]}}' | aos-llm ask                                # 別的寄件人照答
kill $K
```

### 真腦（使用者試）

把件 1、件 4 的 `llm set endpoint=…` 換成真腦就是同一件事、腦自己決定怎麼叫工具：`stupid-fast`（LM Studio 開在 `localhost:1234`、載 `qwen3-1.7b`）或 `smart-high`（LiteLLM `localhost:4000` 的 claude haiku，整輪遠低於 0.5 美金；model 真名以 `curl localhost:4000/v1/models` 為準，對不上改 kernel.json）。真腦不保證照劇本走：工具描述在 `lib/agent/self_tools`、`lib/agent/agents` 的 `_tooldef.json`。
