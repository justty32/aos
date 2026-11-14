線安 ok-sec 的 02 fable 設計稿：aos 怎麼借 Linux 的 uid 與檔案權限變安全——威脅模型、uid 分法、檔案存取表、跨 uid 怎麼溝通、root 縮到多小、分期，以及給使用者拍板的題；只是規劃，現在不施工。

← [sec-1114 紀錄](../sec-1114.md)｜上一份 [01 備料](01-備料.md)

> 依據只有 01 備料，另外翻了 `kernel-limits-plan/08-群組用法.md` 開頭（三個底層事實與 G1～G3）。標「待試」的是我照 Linux 規則推的、沒人實測過，排在第 0 期。P1～P8 一條都沒推翻。

## 一、結論先講

1. **分三圈，一圈一種 uid**。內圈＝使用者自己的帳號（使用者、專區、daemon、頂層站、金鑰）；中圈＝每隻 agent 一個 subuid（`sub:N`，免 root）；外圈＝agent 跑的外來程式，一律進 aos-sandbox。
2. **所有夾都還是使用者擁有，用 ACL 一格一格開給 agent**。不靠 setgid、不靠 chgrp，setgid 坑從此不會再踩到。
3. **不寫新的 root 小幫手**。主線全程免 root：換 uid 靠系統本來就有的 newuidmap，開門靠使用者在自己夾上寫 ACL，「代辦」的角色就是 daemon 自己。root 只留三件可選的事（aos-run 帳號、cgroup 委派、照 uid 管網路）。
4. **P1 就這樣落地**：daemon 的 ctl 箱只有內圈寫得進去，中圈 agent 只寫得進「上一站的投遞口」。繞過 gate 不是被程式擋，是 Linux 回 `EACCES`。
5. **老實講的洞**：eca 身（Claude Code）前幾期還在使用者帳號裡，等於內圈；這一類只能靠 aos 層（ok-onboard）和 CLI 自己的沙箱管，OS 層擋不了它。第 5 期才給「eca 也換 uid」的選項。
6. **全部可選、預設關**（P2）。開關一個：daemon.json `security: off|on`。開了但機器條件不夠就拒起、講清楚缺什麼，不默默退回（跟 P6 同一個脾氣）。

```
+- 內圈：使用者帳號（uid 1000）------+
| 使用者、~/.aos/user 專區、daemon、頂層 kernel 站、LLM kernel
| 金鑰與 token、aos 程式與 knowledge（擁有者）、tmux server
| 〔前幾期：eca 身也在這裡〕
|      | daemon 用 aos-asuser 把人送出去      ^ 只收投遞口的信
|      v
| +- 中圈：每隻 agent 一個 sub:N，同 daemon 共一個群組 sub:G +
| | 自己的 stack：讀寫    別人的 stack：進不去
| | 工作區：照 ACL        knowledge／程式：唯讀
| | daemon ctl 箱：寫不進 上一站投遞口：只能丟信
| |   +- 外圈：aos-sandbox（bwrap）------+
| |   | 外來程式、測試、裝套件：只看得到綁進來的夾、
| |   | 預設斷網
| |   +------+
| +------+
+------+

```

## 二、威脅模型（題 1）

**要防的，照優先序：**

| # | 防誰 | 它會做什麼 | 靠哪一層擋 |
|---|---|---|---|
| T1 | **寫錯的 agent**（最常見） | 路徑打錯、`rm -rf` 到別人的夾、覆寫別人的 stack、殺錯行程 | 中圈 uid＋ACL |
| T2 | **被提示注入的 agent**（有 shell） | 讀 `.env`／token、直寫 ctl 箱繞過 gate、改別人的 hooks.json、假冒使用者回信、冒別人名字吃 LLM 額度 | 中圈 uid＋ACL＋金鑰留內圈＋一人一個投遞口 |
| T3 | **agent 跑的外來程式**（npm、pip、別人的 repo、測試） | 掃家目錄、偷金鑰、往外傳 | 外圈 sandbox（看不到、沒網路） |
| T4 | **同一台機器上的別的 Linux 使用者** | 讀你的 aos-home、信、歷史 | 頂層夾對 other 全關（第 1 期，最便宜） |

**明講不防的：**

- **內圈自己**：使用者本人、root、拿到使用者帳號的人。eca 身還在 uid 1000 的期間，它也算這一類。
- **Linux 核心或 sudo、newuidmap、bwrap 本身的漏洞**。
- **信的內容**：agent A 寫一封很會騙的信給 agent B，B 照做——這是 aos 層與紀律的事（P4、「提示注入風險自己承擔」不變）。OS 層只保證「B 被騙之後能做的事，不超過 B 那個 uid 的範圍」。
- **同一隊共寫夾裡互相蓋檔**：開了共寫就是互信。
- **沒進 sandbox 的 agent 往外連網**：免 root 沒辦法照 uid 斷網（要 root 的 nftables，見第五節）。
- **吃光磁碟**：rlimit 管不了總量；quota 要 root。cgroup 管得到的記憶體、行程數交給 B5。
- **LLM 服務商那頭**、旁路攻擊、同隊之間偷傳話。

## 三、uid 怎麼分（題 2）

**推薦：每隻 agent 一個 uid，一台 daemon 一個群組**（照 K4、K6）。

- 一隻一個 uid 的好處：別人的 stack 天生進不去；rlimit 的 `procs`（算整個 uid 的行程數）才真的變成「這隻的行程數」；`ls -l` 一看就知道哪個檔是誰寫的。
- 群組只拿來做「同一台 daemon 的人能互丟信、能進共用夾」。每隊一群組照 K6 留作進階。

**帳號怎麼來、怎麼收：**

| 事 | 做法 |
|---|---|
| 誰發號 | daemon（內圈）。agent 定義寫 `limits.user: "sub:auto"` 就自動配；寫死 `"sub:17"` 也行；沒寫且 `security: off`＝不換（今天的樣子）。 |
| 帳本 | daemon stack 裡一份 `uids.json`：agent 名 → N。**同名永遠同號**（重啟、重掛都一樣），這樣它舊檔還是它的。 |
| 號段 | daemon.json `uid_range: [起, 迄]`，預設給頂層 daemon 1～1000；子 daemon 沒寫就由父 daemon 切一段給它（跟 K18 群組「沒寫沿用父的」同款）。群組號另用高段（60001 起），不跟 agent 私人的 gid 撞。 |
| 回收 | `ctl remove` 連 stack 一起刪時：先把它留在工作區的檔還給使用者（`aos-asuser --fix`），帳本那格標「已退」。**號不重發**——往上數，60000 個夠用很久；用完再整批回收。重發號最怕新人接到舊人沒清乾淨的檔。 |
| 上限 | 一個使用者的 subuid 通常 65536 個；aos-asuser 收 1～60000。一台 daemon 預設 1000 隻，要多自己調號段。 |

**幾個要先知道的硬限制：**

1. **只有內圈能發 uid**。已經在 `sub:N` 裡的 agent 沒辦法再變出別的 subuid（Linux 規定）。所以：daemon 與 kernel 站留在內圈；agent 自己再起的 daemon，底下的 proc 都跟它同 uid（整棵子樹一個 uid，自然形成「每 kernel 子樹一個 uid」）。想讓子樹成員各有 uid，就照 P4 把 `ctl add` 寄給 `AOS_KERNEL`，由內圈的 daemon 來掛。
2. **中圈 agent 要跑外來程式**：再套 bwrap 就好（同 uid、但看不到東西、沒網路），不用再換 uid。**內圈的身（eca）要跑外來程式**：sandbox 的 `user` 用 `sub:M`（免 root）或 `aos-run`（P6 那條 sudo 鏈）。
3. **信任池**（幾個固定 uid、大家共用）不推薦當主線：省不了什麼，卻讓同池的 agent 互相看得到 stack。留作「機器 subuid 很少」時的退路。

## 四、檔案存取表（題 3）

**總規則三條：**

- **夾的擁有者一律是使用者**（daemon 建的也是）。給 agent 的權限全寫成 ACL，並且每個夾都加「預設 ACL：使用者 rwx」——agent 之後建的檔，使用者照樣能改能刪。
- **預設不給**。表裡沒寫到的就是進不去。other 那一格一律 0。
- **只有一支工具動權限**：`aos-share`（daemon 自動呼叫它，照 K16）。人和 agent 都不手打 chmod／setfacl。

| 東西 | 使用者／daemon（內圈） | agent 自己 | 同 daemon 其他 agent | 外圈 sandbox |
|---|---|---|---|---|
| `~/aos-home` 頂層、程式、`knowledge/` | 讀寫 | 唯讀（G2 唯讀分享） | 唯讀 | 只綁要用的、唯讀 |
| agent 的**定義夾**（system、tools.json、hooks.json、`.env`） | 讀寫 | 唯讀；`.env` 讀不到（見下） | 進不去 | 不綁 |
| 自己的 **stack**（queue、history、overlay、`hooks/<名>/`、`tools/<名>/`、stage） | 讀寫 | 讀寫 | 進不去 | 只綁工具自己那格 |
| stack 裡的啟動設定 `exec.json`、`stderr.txt` | 讀寫 | exec.json 讀不到；stderr 只能接著寫 | 進不去 | 不綁 |
| 自己的 **mailbox** `tmp/`、`new/` | 讀寫 | 讀寫（擁有者是它，見下） | **只能丟信**（進得去、寫得進、列不出來） | 不綁 |
| mailbox `cur/` | 讀寫 | 讀寫 | 進不去 | 不綁 |
| **daemon stack**、ctl 箱 `new/`、`tmp/`、`procs_ctl.json` | 讀寫 | **寫不進**（P1） | 寫不進 | 不綁 |
| daemon 的 `procs_requests/` | 讀寫 | 只能丟信 | 只能丟信 | 不綁 |
| daemon 表 `procs_state.json` | 讀寫 | 唯讀（可調成讀不到，見題 Q5） | 唯讀 | 不綁 |
| kernel 站／LLM kernel 的投遞口 | 讀寫 | 只能丟信 | 只能丟信 | 照 sandbox.json 明列 |
| **工作區** | 讀寫 | 照分配（接口，見下） | 照分配 | 明列才綁 |
| **repo** | 讀寫、**只有內圈 commit** | 唯讀；被分到的子夾可寫 | 同左 | 唯讀綁 |
| **使用者專區** `~/.aos/user`（done、log、keys、web） | 讀寫 | 進不去 | 進不去 | 不綁 |
| 專區的收信口 | 讀寫 | 只能丟信 | 只能丟信 | 不綁 |
| 金鑰、token、`.env` | 讀寫（檔 600） | 讀不到；真的要用才開「金鑰門」（G3） | 讀不到 | 不綁、環境也不帶 |

**幾格要多講一句：**

- **定義夾唯讀＝agent 改不了自己的原廠 tools.json／hooks.json**。它還是能在 stack 寫 overlay（self_tools、self_hook 照常）。「overlay 能不能關掉某條守門 hook」是 aos 層的規則，歸 ok-onboard；OS 層只保證原廠那份動不了。
- **mailbox 的擁有者要是收件 agent 自己**（daemon 建夾時進 ns 把這三個小夾轉給它；08 的事實 2 說這免 root）。原因：`tmp/`、`new/` 要加 sticky（不然寄件人能刪、能換別人的信），而 sticky 夾裡只有「信的主人」或「夾的主人」搬得動信——收件人不是寄件人，那它就得是夾的主人。再加預設 ACL 讓收件人對丟進來的信有 rwx。**待試 E2**。
- **`exec.json` 會有明文環境變數**（01 §4.4 E）：改成只有內圈讀得到；秘密本來就不該走 `--envs`，這條只是補網。
- **金鑰的首選不是金鑰門，是「agent 根本不拿金鑰」**：問腦走 LLM kernel（在內圈、它拿金鑰），agent 只丟請求信。金鑰門留給非得自己拿 token 的工具。
- **ACL 要不要用？要。** 這是整個設計的地基（08 事實 1：使用者能在自己的夾上寫別的 uid 的 ACL，免 root、不用是成員）。代價：檔案系統要支援 ACL（ext4、btrfs、WSL 裡的 ext4 都行；`/mnt/c` 那種不行）——開 `security: on` 時預檢。

**setgid 坑怎麼根治：**

坑的來源是兩件事湊在一起：「靠 setgid 讓新檔繼承群組」＋「使用者不是那個群組的成員，一 chmod 核心就把 setgid 拿掉、又不能 chgrp 回去」。

1. **subuid 這條路：完全不用 setgid**。繼承改靠「預設 ACL」——預設 ACL 不看 setgid、不會被 chmod 順手清掉、使用者不是成員也能設。所以坑不存在。
2. **真帳號 aos-run 這條路**（P6）：照使用者已裁的，setup 那一次就把使用者加進 aos-run 群組（成員 chmod 不掉 setgid）；`/srv/aos-run` 再疊一層預設 ACL 當雙保險。
3. **ACL 自己的坑也一起收**：`chmod g-w` 會把 ACL 的 mask 砍掉、整條失效（08 G1）；`mv` 進來的檔不繼承預設 ACL。對策：`aos-share check PATH`（只看、報哪裡壞）與 `aos-share repair PATH`（照登記重鋪），daemon 起來時對自己管的夾自動 check 一次。

**接口（留給之後的「工作區與 stack 分配」計劃，本稿不設計）：**

> **〔接口 W〕** 誰擁有哪個工作區夾、隊員的夾怎麼掛在隊長底下、隊長能不能讀隊員的 history、哪些子夾共寫——由那份計劃決定。它只需要用本稿給的四個積木講：`read`（唯讀）、`work`（共寫）、`drop`（只能丟）、`stack`（單一 uid 私有），對象是 `sub:N`（一隻）或 `sub:G`（一群）。本稿保證這四個積木在 OS 層是真的。建議那份計劃跟 ok-onboard 的「寫檔範圍」用**同一份宣告**：一份清單，aos 層拿去攔工具，OS 層拿去鋪 ACL。

## 五、跨 uid 怎麼溝通（題 4）

**原則（P1）：不驗信封上的 sender。誰能寄，看的是「這個投遞口 Linux 讓誰寫」。**

| 通道 | 換 uid 之後怎麼過 |
|---|---|
| **agent ↔ agent 寄信** | 收件人 mailbox 的 `tmp/`、`new/` 對同 daemon 群組開「只能丟」。跨 daemon 預設不通——經上一站轉，或由接口 W 明講開給哪一群。 |
| **使用者 → agent**（say、插話、寄信） | 使用者是所有夾的擁有者，又在每個預設 ACL 裡，直接寫。tmux server 是使用者開的，畫面照舊。 |
| **agent → 使用者** | 專區收信口對 agent 群組開「只能丟」；專區其他部分進不去。 |
| **daemon 控制**（add、remove、起停、睡醒） | agent 只寫得進 `AOS_KERNEL` 那站的投遞口（P4）。站放行後往下一站寄；**daemon 的 ctl 箱只開給「鏈上最後一站」**——預設只有內圈；daemon.json `ctl_writers` 可以再加一個 uid（例如當隊長的 fsm agent）。中圈 agent 跑 `aos-daemon-ctl` 直寫會拿到 `EACCES`，工具把它翻成一句人話（「你沒有直寫權，請寄給你的 kernel」）。 |
| **kernel_gate** | gate 站長在某隻 agent 的 `hooks/kernel_gate/` 裡，跑的是那隻 agent 的 uid。它的投遞口對它管的那群人開「只能丟」；它往上寄的那一口，只開給它。規則一句話：**每個箱只開給上一站**。 |
| **問腦（LLM kernel）** | LLM kernel 在內圈、拿金鑰。agent 丟請求信、回信由站寫回 agent 的 mailbox（站是內圈，寫得進）。**進階（第 4 期）：一個寄件人一個投遞口**——口只開給那個 uid，`budget.senders` 的額度改記在「哪個口進來的」，不用驗 sender 就冒不了名，跟 P1、P3 同一個精神。 |
| **查 daemon 表** | 預設同 daemon 群組可讀；要嚴就關掉、只走 `procs_state_path` 問站（站可以回刪減過的表）。 |
| **訊號、收養、清掃** | daemon（內圈）對自己送出去的 `sub:N` 行程照 Linux 規則有權送訊號、讀 `/proc/<pid>/environ`（它是那個 user ns 的主人）——**待試 E1**。退路：用 `aos-asuser sub:N -- kill` 以同 uid 去殺，一定行。**adopt「讀不到就當是自己的」（`adopt.cpp:54`）在換 uid 前一定要改成「讀不到就不收」**——交給管 daemon 的線。 |

**最小 helper 長什麼樣？——沒有新的。** 免 root 主線需要「有權的人代辦」的事只有三件：發 uid、建夾鋪 ACL、把行程送進 uid。三件都是 daemon（內圈）用現成的 `aos-asuser`、`aos-share` 做。所以不寫 setuid 程式、不加 sudo 規則。

**順手撿到的好處（要使用者點頭，見 Q4）：** 換 uid 之後，信夾的「Linux 擁有者」就是真寄件人，偽造不了。aos 仍然不驗 sender，但可以把它**照實顯示**在信旁邊；專區的回信驗證也可以多看一眼「這封是不是使用者帳號寫的」——P7 那個「同帳號 agent 連留底一起造假」的洞，對中圈 agent 就關上了，不用等 L2 簽章。

## 六、一定要 root 的，縮到最小（題 5）

**主線：零。** 前提是機器上 `/etc/subuid`、`/etc/subgid` 有使用者那一行、裝了 newuidmap（多數發行版建帳號時就有）。沒有的話是一次性的一行 `usermod --add-subuids …`，預檢會直接印出這一行。

**可選的 root 項目，三件，每件都是「一次設定、之後不用 root」：**

| # | 做什麼 | 換到什麼 | 形式 |
|---|---|---|---|
| R-a | aos-run 真帳號＋一條固定 sudo 規則（已經有：`setup.sh`、P6、B6） | 內圈的身跑外來程式時多一個選擇；不支援 user ns 的機器的退路 | 一次 setup；規則只准「變成 aos-run」，變不成別人 |
| R-b | cgroup 委派（沒有 `systemd-run --user` 的機器） | B5 的總量上限 | 一次設定 |
| R-c | 照 uid 管網路（nftables） | 沒進 sandbox 的中圈 agent 也能斷網或只准連白名單 | 一次設定；subuid 是固定號段，規則寫一段就好 |

**不做的：** 自己寫 setuid helper（寫壞就是 root 洞，而且主線用不到）；常駐的 root daemon；每次起 agent 都要 sudo。

**怎麼保持可選（P2、K8）：** `security: off` 時這一整套完全不跑、不檢查、不抱怨，跟今天一樣。R-a～R-c 各自獨立，沒設就只是那個功能不能用，設了一半就清楚報錯。

## 七、跟 sandbox、cgroup 怎麼疊（題 6）

**四層各管一件事，不重疊：**

| 層 | 管什麼 | 管不到什麼 |
|---|---|---|
| **uid＋ACL**（本線） | 整台機器上「這個身分」碰得到哪些檔、殺得到誰 | 網路、用量 |
| **bwrap sandbox** | 這個行程「看得到」哪些夾、有沒有網路 | 綁進來的夾裡它照樣能亂寫 |
| **rlimit**（limits） | 單一行程的記憶體、CPU 秒、開檔數；`procs` 算整個 uid | 整棵樹的總量 |
| **cgroup**（B5） | 一台 daemon 底下的總記憶體、總行程數、一鍵全殺 | 檔案 |
| aos 層（ok-onboard） | 給哪些工具、hook 攔什麼 | 有 shell 就繞得過——所以才要下面四層 |

**接鏈順序**（由外到內）：daemon →（放進 cgroup）→ `aos-asuser sub:N` → rlimit →〔要的話〕`aos-sandbox`（bwrap）→ `aos-exec` → agent。sandbox 的 `user: "sub:5"` 已經驗收過（01 §4.1 C），順序不用改。

**疊起來補掉的洞：**

- B5 記的「同 uid 的 proc 能自己改 cgroupfs」：agent 換到 `sub:N` 後，cgroup 夾是使用者的，它寫不進去——洞自己關了。
- rlimit `procs` 從「全體 agent 共用一個數」變成「一隻一個數」。
- sandbox「綁工作區會連帶露出裡面的 daemon stack／ctl」：就算露出來，中圈 uid 也寫不進 ctl 箱。兩層互補。

**本線對別條線的要求（不改它們的圖紙，只提）：** `security: on` 時，sandbox「設定壞掉就警告、不套」要變成拒起（01 §4.1 G 第一條）。

## 八、日常麻煩怎麼壓低（題 7）

| 麻煩 | 對策 |
|---|---|
| **使用者要改 agent 寫的檔** | 每個夾的預設 ACL 都有使用者 rwx，照常編、照常刪。真的卡住：`aos-asuser --fix -R 夾` 一行收回。 |
| **`ls -l` 只看到 100004 這種數字** | `aos-agent ps` 加一欄 uid；`aos-share who PATH` 把數字翻成 agent 名。 |
| **想知道某隻 agent 到底碰得到什麼** | `aos-asuser sub:N -- bash` 直接變成它試。 |
| **repo 裡 git** | 只有內圈 commit（跟現有的「隊員交 patch、上層 commit」做法一致）。agent 在 repo 只對分到的子夾可寫。agent 建的檔擁有者是 subuid，git 不在意。git 換版後檔案權限會不會把 ACL 壓小——**待試 E4**，壓到了就 `aos-share repair`。 |
| **tmux 畫面** | tmux server 一直是使用者開的（socket 的 uid 檢查照過），只有格子裡跑的指令前面多接 `aos-asuser sub:N --`。使用者接畫面的方式不變。**待試 E3**。 |
| **eca 身還在 uid 1000** | 前幾期照舊，一點都不變——所以也一點都沒被 OS 層管到。把它當內圈看：只給使用者信得過的角色（頂層調度、隊長）用 eca；會跑外來東西的工作派給中圈的 fsm，或叫 eca 把外來程式丟進 sandbox 跑。CLI 自己的沙箱旗標、PreToolUse 守門歸 ok-onboard。 |
| **agent 被擋時看不懂** | 工具把 `EACCES` 翻成固定錯誤碼＋一句「你要的話寄信給誰」。不讓 agent 自己猜、自己亂試。 |
| **備份、搬機器** | ACL 要帶著走（`rsync -A`、`tar --acls`）；搬完跑一次 `aos-share repair`。帳號與號段不會跟著搬（跟 sandbox 現況一樣），預檢會講。 |
| **嫌麻煩** | `security: off`。一個字。 |

## 九、分期（題 8）

| 期 | 做什麼 | 使用者看得到的安裝／用法變不變 | 怎麼退 |
|---|---|---|---|
| **0 試驗** | 只做實測、不改程式：E1 內圈對 `sub:N` 行程送訊號與讀 environ；E2 跨 uid 丟信與收信（sticky＋預設 ACL）；E3 tmux 格子裡換 uid；E4 git 與預設 ACL；E5 公司 WSL 上 user ns 與 ACL 行不行。 | 不變 | 沒東西要退 |
| **1 關門不換人**（最小） | 不換任何 uid。只做：aos-home、專區、daemon stack 對 other 全關；金鑰／token／`exec.json` 收成 600 並在權限太鬆時警告；新增唯讀體檢 `aos-share check`；adopt 讀不到改成不收。擋的是 T4 與手滑外流。 | 不變（沒有新指令要學、沒有新設定要填） | 權限位改回去就好 |
| **2 自願換 uid** | daemon 認得 `limits.user: "sub:N"`、自動鋪 stack ACL（K16／G6，ok-limits 段 3 本來就排了）。只有定義裡寫了的 agent 才換。先拿唯讀蒐集、外來碼這兩類試。 | **可選、預設關**；沒寫就跟以前一樣 | 把那格拿掉 |
| **3 整台開** | `security: on`：自動配號（`sub:auto`、帳本、號段）、ctl 箱上鎖（P1 落地）、mailbox 丟信口、knowledge 唯讀分享、預檢與清楚報錯。 | **會變**（多一個開關、多一段預檢、裝機多一步確認 subuid）→ **排在 ok-release 公開 demo 之後**，且預設關 | 改回 `off`，跑一次 `aos-asuser --fix` |
| **4 金鑰與額度** | 金鑰只留內圈、問腦一人一口、專區回信多看擁有者、信旁顯示真寄件人。 | 會變一點（fsm agent 的定義不再放 key）→ 發佈版之後 | 各項獨立可關 |
| **5 eca 也換 uid** | eca 身進 `sub:N`：自己的家目錄、自己的 CLI 登入檔。 | 會變（CLI 登入要多做一次）→ 發佈版之後、可選 | 不開就沒事 |
| **6 有 root 的加碼** | R-c 照 uid 管網路、磁碟 quota、其他 R 草案。有人要才做。 | 可選 | 拿掉規則 |

**跟 ok-release 的關係：** 第 0、1 期不改用法，可以平行做，不擋發佈；第 1 期要不要跟發佈版一起出去，由 xiaosi 那邊看時程決定。第 3 期以後一律在發佈版之後。

## 十、給 ok-onboard 的分工

**(1) 哪些角色換 uid、哪些進 sandbox（建議的預設，開了 `security: on` 才生效）：**

| 角色 | uid | sandbox | 說明 |
|---|---|---|---|
| 使用者、頂層調度（eca） | 不換（內圈） | 不進 | 靠 aos 層守門＋CLI 自己的設定 |
| 隊長（eca） | 不換（內圈），第 5 期可選 | 不進 | 同上；它是 commit 的人 |
| 隊長（fsm，掛 kernel_gate） | `sub:auto` | 不進 | 列進它那棵子樹的 `ctl_writers`（或往上寄給內圈的站） |
| 設計、審稿（只讀＋寫一份稿） | `sub:auto` | 不進 | repo 唯讀，只開它的輸出夾 |
| 蒐集（唯讀） | `sub:auto` | 不進 | 全部唯讀 |
| 施工（改程式、跑測試） | `sub:auto` | **跑測試、裝套件、跑別人的程式時進**（預設斷網） | 工作區照接口 W |
| kernel 站、LLM kernel、daemon | 不換（內圈） | 不進 | 它們就是「帳號 A」 |
| 任何「跑外來程式」的工具 | 跟呼叫者 | **一律進** | 外圈 |

**(2) 定義裡 aos 層要留的欄位（OS 層會讀，請不要改名、不要吃掉）：**

- agent 定義：`limits.user`（不寫／`"sub:N"`／`"sub:auto"`／真帳號名）、`limits` 五個數字鍵、`sandbox`（指到 sandbox.json）、〔接口 W 定案後〕一份「讀寫範圍」宣告——建議 ok-onboard 的寫檔範圍 hook 與本線的 ACL 讀同一份。
- daemon.json：`group`（K18）、`security`、`uid_range`、`ctl_writers`、`limits_max`。
- 分界一句話：**ok-onboard 決定「該不該讓它做」，本線保證「不該做的真的做不到」**。兩邊對同一件事的答案要來自同一份宣告，不要各寫一份。

## 十一、要請使用者拍板的題

**Q1　uid 分多細？**
1. **每隻 agent 一個 uid**（推薦）——互相進不了 stack、`procs` 一隻一算、看得出檔是誰寫的。代價：共用夾都要靠 ACL，`ls` 會看到很多數字。
2. 一台 daemon 一個 uid——簡單很多，擋得住「agent 碰內圈」，擋不住同 daemon 的 agent 互相亂寫。
3. 三個信任池（高／中／低各一個 uid）——介於中間；同池互相看得到。

**Q2　eca 身（Claude Code 這類）怎麼辦？**
1. **先留在使用者帳號、當內圈看，之後第 5 期給可選的換 uid**（推薦）——現在零麻煩；代價是最強的那類 agent 這幾期 OS 層管不到，只能靠 aos 層與「派工時挑角色」。
2. 第 3 期就一起換——安全早到位；代價是 CLI 登入、設定檔、畫面要一起動，風險集中在一期。
3. 永遠不換——最省事；洞永遠在。

**Q3　開關長什麼樣？**
1. **daemon.json 一個 `security: off|on`，預設 off；on 但條件不夠就拒起**（推薦）——行為只有兩種，好懂。
2. 加一個 `auto`（條件夠就開、不夠就默默不開）——省事；代價是使用者以為有開其實沒開。
3. 穩定之後預設改 on——新裝的人預設就安全；代價是裝機多一步，P2「嫌麻煩的人」要自己關。

**Q4　要不要把「信夾的 Linux 擁有者」當真寄件人顯示出來，專區回信驗證也多看這一眼？**
1. **要**（推薦）——aos 還是不驗 sender、不擋信，只是把 Linux 知道的事照實給收件人看；P7 的洞對中圈 agent 關上。代價：多一欄、要一張 uid→名字的表。
2. 不要——完全照 P1 字面，aos 一眼都不看寄件人；專區假回信繼續等 L2 簽章。

**Q5　daemon 表（誰在跑）給不給中圈 agent 直接讀？**
1. **同 daemon 群組可讀**（推薦）——工具照舊、少一趟問站。代價：agent 看得到同台所有 proc 的名字與狀態。
2. 讀不到、只能問 kernel 站——站可以只回該看的；代價是每次查都多一封信、站掛了就查不了。

**Q6　金鑰放哪？**
1. **只留內圈，agent 問腦一律走 LLM kernel**（推薦）——agent 被注入也偷不到 key。代價：沒有 LLM kernel 的小場面要先起一個站。
2. 金鑰門（要用的 agent 才進金鑰群）——現在的用法幾乎不變；代價是進了群的 agent 就讀得到 key。

**Q7　沒進 sandbox 的中圈 agent 能不能連網？**
1. **先照舊能連，寫進「不防」清單**（推薦）——免 root 做不到照 uid 斷網；要斷就把那件事丟進 sandbox。
2. 施工類 agent 整隻都進 sandbox（斷網）——擋得住外傳；代價是要抓套件、查網路的工作要另開口。
3. 走 root 的 R-c——最乾淨；代價是要一次 root 設定，P2 的人用不到。

**Q8　機器不支援（沒 subuid、檔案系統沒 ACL、WSL 關了 user ns）又開了 on，怎麼辦？**
1. **拒起，印出缺什麼與補救的那一行指令**（推薦；跟 P6 同脾氣）。
2. 警告後照沒開的樣子跑——不擋工作；代價同 Q3 選項 2。
