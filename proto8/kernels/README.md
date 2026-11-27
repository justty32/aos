照名字找的 kernel 設定：`mini.py --kernels aos/base-low,aos/llm/fake -- 指令` 裡的每個名字，就是這個夾底下的一份 `<名字>.json`（使用者 11-27 晚定第 1 題：放 `$AOS_HOME/kernels/<名字>.json`），或一個有 `_chain.json` 的夾＝一包 kernel（11-27 深夜，例 `aos/base/`；包裡可以寫 `merge`、`use`＋`replace`／`without`，11-27 深夜七題）。

# kernels

← [proto8](../README.md)｜用它的程式：[proto9/mini-sandbox](../../proto9/mini-sandbox/README.md)（說明、驗收都在那邊）

- **怎麼找**：`mini.py` 先找 `$MINI_KERNELS_PATH`（冒號分隔的夾，可不設），再找 `$AOS_HOME/kernels/`；第一個找到的算。兩個都沒設就報錯、什麼都不跑。
- **一份長這樣**：`{"description": "一行英文", "program": "cg_kernel.py", "config": {…}}`。`program` 只寫檔名＝mini 自己的程式（跟 `mini.py` 同一夾）；寫了 `/` 才當路徑（`$變數`、`~` 會展開，相對路徑從這份 json 的夾算）【擬】。`config` 各 kernel 自己的欄位，見 mini-sandbox 的 README。
- **一包 kernel**（使用者 11-27 深夜：「是否自由組合定義後，這種一包的kernel也能用？比如我用--kernels aos/base，他其實是aos/base/底下一堆東西的結合（可能還會加上一些ext/xxx），只是用aos/base/底下的某個檔把他們串起來。」）：一個夾裡放 `_chain.json`＝`{"description": "…", "chain": ["cg", "mask", "aos/llm/fake"]}`，由外到內列出展開成哪一串。沒有 `/` 的名字是這一包自己的（`cg`＝`aos/base/cg.json`），有 `/` 的是全名（照上面的找法）。一包裡可以再引用一包（最多 8 層）；互相引用、太深都報錯並印出整串；能跟單名混著寫（`--kernels aos/base,aos/net/xxx`）。展開後跟直接寫一串一樣（嵌套順序、自動遮蔽、`KernelOrderBad` 都照展開後的算），`--dry-run` 先印展開後的每一層。同一個夾裡 `aos/base.json` 和 `aos/base/_chain.json` 都在時報錯（`KernelNameClash`）要你改名。細節在 mini-sandbox README 的「一包 kernel」。
- **寫在前面的是外層**：`--kernels a,b,c` 的 `a` 最外面，pi 住在最裡面；裝了資源上限、網路或 llm kernel 時，mini 自動在最裡面加 `aos/mask/run-user`（`--no-auto-mask` 關掉；llm kernel 也算是使用者 11-27 深夜定的，見下）。
- **pi 在裡面會怎樣**：這些檔 pi 讀得到也改得到（檔案沒遮），改了要到下一次起的時候才生效。（跑起來之後各層交給它的宣告夾——`$AOS_ENV` 那邊——是唯讀的，那是另一回事，見下。）
- **pi 去哪找宣告**（11-27 深夜使用者定）：先看 `$AOS_ENV`，沒設就看 `/`（`/.aos/…`）。每個 kernel 在 `$AOS_ENV/.aos/interfaces/aos/<種類>/` 一定寫 `description`、`name`（這份設定的名字；一包展開的寫展開後的，例 `aos/base/cg`）、`layer`（第幾層，1＝最外）、`status`（狀態檔的絕對路徑，沒有就空檔），從一包來的多一個 `from`；狀態檔頭兩行固定 `state:`、`updated:`。這些宣告在交給內層前鎖成唯讀，pi 改不了也拆不掉（只有 `/run/user` 沒蓋時，經 D-Bus 在沙箱外起的行程寫得到）。

| 名字 | 是什麼 |
|---|---|
| `aos/base-low` | 資源上限：CPU 一顆核的 20%、記憶體 512M（不用 swap）、行程＋執行緒 64 |
| `aos/base-high` | 資源上限：200%、4G、1024 |
| `aos/net/base-litellm-proxy` | 網路：只放行這台的 `127.0.0.1:4000`（LiteLLM），頻寬與總量有上限；跟 llm kernel 一起用時要寫在 llm kernel 前面（外層）；寫在後面（`aos/llm/litellm-luna,aos/net/base-litellm-proxy`）會讓 pi 繞過 llm kernel 直連 LiteLLM，mini 拒絕起來（`KernelOrderBad`） |
| `aos/mask/run-user` | 檔案遮蔽：`/run/user/<你的 uid>` 蓋成空夾（關住經 D-Bus 跳出沙箱那條路） |
| `aos/mask/ssh` | 檔案遮蔽：`~/.ssh` 蓋成空夾 |
| `aos/uid/1` | 切成 uid 1（外面是你第一個 subuid）；寫在哪都行，mini 自動排到最裡面（11-27 深夜第 5 題） |
| `aos/llm/fake` | llm kernel，劇本腦（不叫模型）：`fake-model`、每次跑 50 次（沒寫 `state`，每次重算） |
| `aos/base`（一包，夾） | `_chain.json` 串 `cg`（資源上限：20%、512M、64）、`mask`（蓋 `/run/user`）、`aos/llm/fake`；pi 有上限、跳不出去、沒網路、經 socket 問得到劇本腦。`aos/base/cg`、`aos/base/mask` 也能單獨用 |
| `aos/llm/litellm-luna` | llm kernel，上游是這台的 LiteLLM：只准 `chatgpt-gpt-6-luna-nothink`、每次跑 10 次（沒寫 `state`，每次重算）；放在網路 kernel 外面 |

## 使用者定的三題（11-27 深夜，原話「都先按照推薦」）

題目是 kernel 設定檔格式說明（家機 `~/.aos/scratch/kernel-format-1127/report.html`）第 07 節，三題都選推薦的甲：

1. **llm kernel 也觸發自動加 `aos/mask/run-user`**：保留。不遮的話 pi 經 D-Bus 叫 systemd 起一隻沙箱外的程式，直接連 LiteLLM，次數和模型的限制就白設。
2. **llm 的額度每次跑都重算，跑完就清；要累計就在設定寫 `state`**：例 `"state": "~/.aos/llm-state/{name}"`。注意兩件事：之後把 `limit` 改大不生效（額度檔裡的上限只會往下調，要自己刪 `budget.json`）；**同時跑兩隻共用同一個 `state` 會算錯**（兩支程式之間沒有鎖，可能少算、超過上限），要同時跑就各給一個夾。細節在 mini-sandbox README 的「`state`：額度要累計時」。
3. **網路 kernel 放行了 llm kernel 的上游、又寫在 llm kernel 後面（內層）時，直接拒絕起來**：mini 在起任何東西之前報錯、退出碼 2、什麼都沒跑（`--dry-run` 也報）。改法：把網路 kernel 寫在 llm kernel 前面，或從它的 `host_ports`（上游是 `127.0.0.1`）／`allow`（上游是別的位址）拿掉那個 port。

## 統一介面四題與一包 kernel（11-27 深夜，原話「先按照推薦」）

1. 每個 kernel 那一格固定補 `name`、`layer`、`status`，狀態檔頭兩行固定 `state:`、`updated:`。
2. 宣告夾交給內層前鎖成唯讀（實測 pi 拆不掉，試法與結果在 mini-sandbox README 的「唯讀鎖」）。
3. pi 先看 `$AOS_ENV`，沒設就看 `/`。
4. 同名不同義的（`kind`、路徑相對或絕對、沒上限寫 `max` 還是空檔）先不改，跟決策審查第 3 題（`aos/ctl` 的形狀）一起定。

一包 kernel 照上面「一包 kernel」那條做；串接檔叫 `_chain.json`、單檔與夾同名時報錯，這兩點使用者 11-27 深夜定了：「都先按照推薦。」

## 多包重疊、攤平七題（11-27 深夜，原話「好，都按照推薦。」）

題目在家機 `~/.aos/scratch/kernel-overlap-1127/report.html`（不進 git），七題都選推薦。細節、實測與驗收在 mini-sandbox README 的「第六段」；這裡只講寫設定的人要知道的。

1. **同一份設定在展開後出現兩次，只留最外面那次**（看的是真正的那個檔，不是名字），mini 印一行，例 `mini: aos/llm/fake appears twice (from aos/base, aos/dev); kept the outer one`。所以兩包都引用 `aos/llm/fake` 沒事：pi 只有一隻腦、一本帳。
2. **同種、不同設定照舊疊兩層，取緊**；要合成一層才在 `_chain.json` 明寫 `{"merge": ["a", "b"]}`。合法：上限（cpu、mem、pids、quota、up、down、limit）取小；`allow`、`host_ports`、`models` 取交集（照位址範圍與 port 範圍算，不照文字）；mask 的路徑取聯集、同一條路徑有一份蓋掉就蓋掉、`keep` 只留每一份都留的洞。`upstream`、`state`、`fake_script`、uid 號碼、`subnet`、`host_addr` 不一樣時報 `KernelMergeBad`（比不出誰緊）；種類不同、或其中一份是你自己寫的程式（`program` 不是 mini 那幾支）也報 `KernelMergeBad`。合成的那層名字是 `a+b`。
3. **兩個 llm kernel 沒串起來時拒絕起來**：內層那個的 `upstream` 不是 `"outer"`（或不寫）、外層也是 llm 時，mini 在起任何東西之前報 `KernelOrderBad`，教你改成 `"upstream": "outer"` 或拿掉一個。內層 llm 一律把外層的 socket 蓋掉。
4. **一包改另一包：整層換掉或拿掉**：

   ```json
   {"description": "aos/dev: aos/base with more memory and no brain",
    "chain": [{"use": "aos/base", "replace": {"cg": "aos/base-high"}, "without": ["aos/llm/fake"]},
              "aos/mask/ssh"]}
   ```

   `replace`、`without` 的鍵是 `aos/base` 那一包 `chain` 裡寫的名字（`cg`、`mask`、`aos/llm/fake`），寫了不存在的報 `KernelBundleBad` 並列出有哪些；換上去的那個名字照寫 `use` 的這一包來讀。`--dry-run` 會印誰被誰換掉、拿掉了什麼、每層是哪個檔。換上去的可以比原本鬆（這是寫設定的人明講的）。
5. **uid 寫在哪都行，mini 自動排到最裡面**（自動加的 `aos/mask/run-user` 仍在它前面），印一行；兩份 uid 同號只留一份，不同號報 `KernelUidClash`。
6. **連在一起的 cgroup 與 mask kernel 攤平成一層**（中間不隔網路或 llm kernel）：cgroup 取最小、只開一層，mask 合成一張表在一個 namespace 照順序掛；`.aos/kernels` 照樣一行一層、每層的宣告照寫，多一個 `flattened` 檔寫哪幾層是一起做的。網路與 llm kernel 照舊一層一層真開。起之前先算整串要幾層 user namespace（cgroup、mask、uid、llm、攤平的一層各 1，網路 2，最裡那步 1），在這台上超過 24 層就報 `KernelTooDeep`、什麼都不起（Linux 最多 33 層，留 9 層給 pi 自己在裡面再開沙箱；24 與 9 是我定的【擬】）。
7. **每次起來寫 `$AOS_ENV/.aos/effective/`**（攤平後 pi 真正拿到的值，一種一個夾、一個欄位一個檔，加一個 `blame` 檔每行 `<欄位> <值> <- layer N <名字> [from <包>]`）和 `.aos/lock.json`（每層的 `layer`、`kind`、`name`、`from`、`file`、`sha256`、`config`）。`mini.py --explain --kernels …` 印同一份給你看（不起任何東西），`mini.py --diff A B`（`A`、`B` 是 lock 檔或一串名字）比兩次展開。內層寫得比外層鬆時，不再一項一行，只印一行「N 項寫得比外層鬆，詳見 `--explain`」。
