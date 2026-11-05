← [回入口 README.md](../README.md)｜段落：新功能原型的假腦劇本（11-05 午 feat-proto）｜上一份：[04-kernel-modes](04-kernel-modes.md)｜下一份：—

## 新功能原型的假腦劇本：agent 自改工具、能力包與排程、agent 生 agent、資源份額（11-05 午）

使用者 11-05 午：「讓agent給自己改tool，把endpoint打包成smart-high, stupid-fast, ...這類，並且附上各種屬性(各種temperature也固定)，讓kernel能根據信件中額外附送的priority之類資訊做排程，讓agent利用aos指令產出另一個agent」「啊，還有，會想要限制特定aos proc所占用的資源。以及daemon/kernel自己本身被限制占用資源，並且會分配份額給proc」。設計：[thinking feat-proto](../../thinking/2026-11/05/feat-proto/README.md)。

下面四段都是假腦（[03](03-llm-kernel.md) 的 `fake-demo-*` 包照劇本回答），零成本、可重跑；每段從空的 `/tmp/feat-s9-*` 起、各起自己的 llm daemon，跑完 `kill` 收工。PATH 放 `proto8/impls/*/bin`、`proto8/bin`、`proto8/extras/agent/bin`（或跑過 `proto8/install.sh`）；`P` 換成你的 repo。11-05 在 WSL 照抄跑過。

### 件 1：agent 給自己加工具（`self_tools`）

```sh
P=~/repo/simple_tools/aos/proto8
T=/tmp/feat-s9-self && rm -rf $T && mkdir -p $T/ws/.stack && cd $T
aos-exec --stack $T/k $P/demo/llm-kernel > k.log 2>&1 &          # llm daemon（假腦包都在它的 kernel.json）
export AOS_LLM_KERNEL=$T/k
echo '{"interval_ms": 300}' > daemon.json
AOS_STACK=$T/ws/.stack/ aos-daemon daemon.json > d.log 2>&1 &     # 跑 agent 的 daemon（環境帶著 AOS_LLM_KERNEL）
sleep 1 && cd ws                                                   # cwd 有 .stack＝aos-agent 找得到 daemon
aos-agent ctl add --name fsm1 $P/demo/agent-fsm
aos-agent tools --target fsm1 add self_tools $P/lib/agent/self_tools   # 人先塞第一個（範本不內建）
aos-agent llm --target fsm1 set endpoint=fake-demo-self                # 換成劇本腦
aos-agent say --target fsm1 give yourself a math tool && aos-agent listen --target fsm1
# I added math to my own tools and used it right away: 17*23 = 391.
aos-agent tools --target fsm1 ls          # 多一行 math（定義疊這隻的覆蓋層）
aos-agent ctl state --target fsm1         # tools   overlay: 2 added, 0 removed (+self_tools, +math)
kill %1 %2
```

劇本三步：叫 `self_tools {"op": "add", "name": "math", "path": "<repo>/proto8/lib/base/math"}`（工具裡 `aos-agent ctl who` 查 daemon 表認出「我是 fsm1」，再 `aos-agent tools --target fsm1 add`）→ 下一格 brain 重讀就看到 math、叫 `math {"expr": "17*23"}` 得 `391` → 答一句。history 裡看得到兩則 tool 結果（`added math (…) to your tools; available from your next turn`、`391`）。定義資料夾沒動；`aos-agent tools --target fsm1 reset` 一刀回定義。

### 件 2、3：能力包與排程（包的 `slots` 補位、`speed` 先後）

```sh
T=/tmp/feat-s9-sched && rm -rf $T && mkdir -p $T && cd $T
aos-exec --stack $T/k $P/demo/llm-kernel > k.log 2>&1 &
export AOS_LLM_KERNEL=$T/k && sleep 1
aos-llm ls                                # 一行一包；fake-demo-fast／slow 的 slots 是 1
echo '{"endpoint": "smart-high", "request": {"messages": [{"role": "user", "content": "hi"}], "temperature": 1}}' | aos-llm ask
# aos-llm: RequestBad temperature is fixed by endpoint smart-high (remove it from the request; to change it pick another endpoint name)
for e in fake-demo-slow fake-demo-slow fake-demo-fast fake-demo-fast; do
  echo "{\"endpoint\": \"$e\", \"request\": {\"messages\": [{\"role\": \"user\", \"content\": \"hi $e\"}]}}" | aos-llm send --reply-to box
done                                      # 印四個信件名稱（先寄兩封 slow、再兩封 fast）
sleep 1 && aos-daemon-ctl --daemon $T/k ls   # 只有兩列 running：第 3 封（fast）、第 1 封（slow）
sleep 8 && ls box/new | wc -l             # 4：四封回信都到了（FAKE ANSWER to: hi …）
kill %1
```

kernel 總 `slots` 2、兩包各 `slots` 1、每封 3 秒：同級的信 fast 包排前面；fast 包第二封因為包滿了被**跳過**，讓 slow 包的第一封補上第二格（不是整列卡住）。3 秒後收成品、再掛各包的第二封。`smart-high` 那封沒掛出去：信寫了包釘死的 `temperature`。

### 件 4：agent 生 agent（`agents`；判官 `max_running` 4）

```sh
T=/tmp/feat-s9-spawn && rm -rf $T && mkdir -p $T/ws && cd $T
aos-exec --stack $T/k $P/demo/llm-kernel > k.log 2>&1 &
export AOS_LLM_KERNEL=$T/k AOS_DAEMON=$T/st AOS_KERNEL=$T/st/requests   # 掛 proc 都先過判官（demo/docs/04 模式 1）
aos-exec --stack $T/st $P/demo/daemon-judge > d.log 2>&1 &              # 帶判官的 daemon：allowed 有 fsm1、kid、kid1～4，max_running 4
sleep 1
aos-agent ctl add --name fsm1 --ws $T/ws $P/demo/agent-fsm
aos-agent tools --target fsm1 add agents $P/lib/agent/agents
aos-agent llm --target fsm1 set endpoint=fake-demo-spawn
aos-agent say --target fsm1 start a kid and ask it the time && aos-agent listen --target fsm1
# I started kid, asked it the time (its answer is in the tool result above) and removed it again.
aos-agent say --target fsm1 now start four kids && aos-agent listen --target fsm1
# Only three kids fit: the judge allows 4 running at once and I count too, so kid4 was refused (SlotMissing). I removed the three again.
aos-agent ctl ls                          # 只剩 fsm1
tail -1 d.log                             # judge: SlotMissing letter … refused: max_running is 4, 4 running now …
kill %1 %2 && unset AOS_DAEMON AOS_KERNEL
```

第一題劇本：`agents add {"name": "kid", "def": "<repo>/proto8/demo/agent-fsm", "endpoint": "fake"}` → `ask kid "what time is it?"`（kid 的假腦先叫 clock、答 `FAKE ANSWER to: what time is it? (tool said: 2026-11-05T…Z)`，成了 fsm1 的 tool 結果）→ `rm kid`。第二題一次 add kid1～kid4：fsm1＋三隻＝4 隻 running，kid4 被判官擋，回給腦一則 `agents: AddRejected AOS_KERNEL refused the add letter: SlotMissing …`；再 rm 三隻。kid 用的是自己定義裡的腦與工具（不繼承 fsm1 的），工作區跟 fsm1 同一個；`agents` 只收自己生的（`$AOS_STACK/children.json`）。

### 件 5：資源份額（daemon 那半未做）

```sh
T=/tmp/feat-s9-limits && rm -rf $T && mkdir -p $T/ws/.stack $T/hog && cd $T
echo '{"interval_ms": 300}' > daemon.json
echo '{"aos-agent": {"limits": {"mem_mb": 256}}}' > hog/interfaces.json     # 這隻建議的份額
echo '["aos-loop", "loop.json"]' > hog/_entry
echo '{"exec": {"argv": ["python3", "-c", "b = bytearray(300 * 2**20)"]}, "max": 1}' > hog/loop.json   # 吃 300 MB
cp -r hog hog-big && sed -i s/300/3000/ hog-big/loop.json                   # 吃 3000 MB
AOS_STACK=$T/ws/.stack/ prlimit --as=2048000000 aos-daemon daemon.json > d.log 2>&1 &   # daemon 自己被限 2 GB（起它的人包；同 ulimit -v 2000000）
sleep 1 && cd ws
aos-agent ctl add ../hog                  # (note: limits mem_mb=256 not applied: the daemon does not take limits yet …)；吃完 300 MB 退 0、下表
aos-agent ctl add ../hog-big && sleep 2
aos-agent ctl state --target hog-big      # state stopped、reason failed while running: exited with code 1: MemoryError
kill %1
```

- **現在就看得到的**：daemon 被 `ulimit -v` 限住，它掛的子項天生超不過（rlimit 繼承）——hog-big 要 3 GB、撞到 daemon 的 2 GB＝Python `MemoryError`、退 1、表上留 `stopped`＋`reason`（不加新的錯誤路徑）。
- **邊緣隊 E1／E2 做好之後**（[feat-proto 05](../../thinking/2026-11/05/feat-proto/05-資源份額.md)）：`ctl add ../hog` 的宣告 `mem_mb: 256` 會送到 daemon、daemon 在子行程 `setrlimit`——hog 吃 300 MB 就 `MemoryError`、`ctl state` 多一行 `limits  mem_mb=256`；`aos-agent ctl add --limits '{"mem_mb": 1024}' ../hog` 蓋過宣告、正常吃完。現在只會看到上面那行 `(note: …)`。
- **天然差異**：份額是每個行程各自的上限、不從 daemon 總額扣（三隻各 1024 加起來可以超過 daemon 的 2 GB）。
- **llm kernel 的份額**＝包的 `budget`＋每個寄件人的 `budget.senders`。範本限了寄件人 `/tmp/aos-demo-sender` 每天 1 次（帳記在 kernel 的 `used.json`，新起一台就從 0 算）：

```sh
T=/tmp/feat-s9-quota && rm -rf $T && mkdir -p $T /tmp/aos-demo-sender && cd $T
aos-exec --stack $T/k $P/demo/llm-kernel > k.log 2>&1 &
export AOS_LLM_KERNEL=$T/k && sleep 1
echo '{"request": {"messages": [{"role": "user", "content": "hi"}]}}' | AOS_WS=/tmp/aos-demo-sender aos-llm ask   # FAKE ANSWER to: hi
echo '{"request": {"messages": [{"role": "user", "content": "hi"}]}}' | AOS_WS=/tmp/aos-demo-sender aos-llm ask
# aos-llm: BudgetMissing sender /tmp/aos-demo-sender: max_calls 1 reached in this window (day); not run
echo '{"request": {"messages": [{"role": "user", "content": "hi"}]}}' | aos-llm ask                                # 別的寄件人照答
kill %1
```

### 真腦（使用者試）

把件 1、件 4 的 `llm set endpoint=…` 換成真腦就是同一件事、腦自己決定怎麼叫工具：`stupid-fast`（LM Studio 開在 `localhost:1234`、載 `qwen3-1.7b`）或 `smart-high`（LiteLLM `localhost:4000` 的 claude haiku，整輪遠低於 0.5 美金；model 真名以 `curl localhost:4000/v1/models` 為準，對不上改 kernel.json）。真腦不保證照劇本走：工具描述在 `lib/agent/self_tools`、`lib/agent/agents` 的 `_tooldef.json`。
