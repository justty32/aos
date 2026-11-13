fable 只讀 01 備料交的頂層設計，原樣收錄（標題降一級；opus 的修正在 03）。

← [入口](../kernel-limits-plan.md)｜上一份 [01 備料](01-備料.md)｜下一份 [03 opus 細化](03-opus細化.md)

## kernel 限資源與 uid：頂層設計（fable）

只讀了備料，沒實測；標「待驗」的三處是憑 Linux 知識推的。

**一句話**：kernel 只決定「這個請求該帶什麼限制、用誰的身分」，寫進放行的信；daemon 在 fork 時真的套上並守一道天花板。rlimit 管單支暴走，cgroup 管一整串總量，uid 管誰是誰，bwrap 管看得到什麼；要 root 的全隔成一支預設不裝的包。

```
使用者帳號 lorkhan(1000) ＝ 一棵樹（含名下 subuid 100000～165535）
│
├ kernel 站（通用基礎包，掛 before_verdict）   ← 只判斷、只改信
│    limits ＝ 夾(請求自帶 或 預設, 上限)；user ＝ 依寄件人查表
│
├ daemon（起 proc 的那層，真的動 Linux）        ← 保底
│    ① 天花板 limits_max 再夾一次  ② setrlimit（單支）
│    ③ cgroup 子格（一串總量，二期）④ 換 uid：sub:N（免 root）／帳號名（root 包）
│    ⑤ 收屍時翻譯「撞到哪一項」寫回表
│
├ aos-sandbox（bwrap）                         ← 看得到什麼：掛載、pid、網路
│
└ proc：agent 身／腦／工具
     aos-exec 只管牆鐘 timeout_ms，不變
```

## 1. 資源限制

- **誰定**：kernel 基礎包的規則加 `limits: {default, max}`，可按寄件人分。放行時算好寫進 `body.limits`；骨架不動，仍是 hook＋判斷。
- **請求自帶的 limits**：只能收緊。沒帶或 `{}` 用 default；超過 max 就夾到 max，並在表上記 `limits_clamped`。
- **`{}` 的洞**：語意改成「用預設」，不再是「不限」。daemon.json 另加 `limits_max` 當天花板，任何信都過不去；要不限只能樹主自己寫在 daemon.json。
- **為什麼 daemon 要再夾一次**：同 uid 下 agent 能繞過 kernel 直接寫 `procs_requests`，kernel 的夾擋不住，保底只能在 daemon。
- **在哪套**：daemon fork（現成）。aos-exec 不加 rlimit；aos-sandbox 照舊是呼叫方自願包的。
- **daemon/kernel 自己被限**：daemon 啟動時先對自己 setrlimit，hard 值往下繼承、子孫調不回去，份額天生只能往下收。
- **cgroup（二期）**：放在 daemon，只在偵測到有委派時啟用，只做 memory／pids。
  - 理由一：`mem_mb`→AS 對 node 類程式（Claude Code CLI）會直接起不來，要用 `memory.max`。
  - 理由二：agent 一串子孫的總量，rlimit 管不到。
  - 沒委派的機器（WSL 未查）退回只有 rlimit，表上寫 `cgroup: none`，不默默假裝。
- **超限回報**：列上記「實際套的 limits」，收屍時加一欄 `limit_hit`。
  - SIGXCPU→`cpu_s`；SIGXFSZ→`file_mb`。
  - cgroup 的 `memory.events` 裡 oom_kill 增加→`mem`；`pids.events` 的 max 增加→`procs`。
  - rlimit 記憶體到頂只會退 1，無法確定，記 `limit_suspect: mem_mb`，不硬猜。
  - 待驗：cpu 的 soft＝hard 時核心可能直接 SIGKILL，看不到 SIGXCPU；建議 hard＝soft＋1 秒。

## 2. 權限／uid

| 路 | 擋得住 | 擋不住／代價 |
|---|---|---|
| 甲 真帳號＋root helper | 檔案、訊號、ptrace、/proc 全分開 | 要 root、要建帳號；跨帳號共用檔要靠群組 |
| 乙 user ns＋subuid（家機可用） | 外面看就是真的 10xxxx：讀不了 1000 的 600／700 檔、殺不了別人的 proc；NPROC 終於各算各的 | 它寫的檔歸 10xxxx，樹主要進 ns 才動得了；依賴 newuidmap；WSL 未查 |
| 丙 bwrap 假 uid | uid 上什麼都沒擋，擋的是掛載視野 | 最便宜；寫出的檔仍歸 1000，分不出誰寫的 |

- **推薦**：乙為主，丙繼續管視野，甲進 root 包。
- **誰選 uid**：`user` 由 kernel 依寄件人查表寫入，請求自帶的一律丟掉。值是 `sub:N`（免 root）或帳號名（root 包）。
- **怎麼換**：一支免特權小程式 `aos-asuser`（unshare＋newuidmap＋setuid＋exec），daemon 與 aos-sandbox 共用。
- **檔案擁有者**：
  - agent 私有夾歸它的 subuid，700。
  - 共用工作區用一個共用 subgid＋setgid 夾＋umask 002。
  - 信箱夾歸 1000，做成投遞箱（別人能丟進去、不能列不能讀）。
  - 使用者專區歸 1000、700，只有 `mailbox/` 是投遞箱，這就是 L3。
- **`~/aos-home` 現在 755**：換 uid 後別人仍讀得到，要一起收緊，否則白換。
- **一棵樹**：subuid 段是 `/etc/subuid` 發給這個帳號的，樹主進 ns 就是它們的 root，不需要另一個人。我認為算同一棵樹（待裁）。
- **eca 身**：CLI 要讀寫 `~/.claude` 憑證（token 會更新）。agent 的 Bash 與 CLI 同 uid，憑證本來就藏不住它自己。所以 eca 換 uid 保護的是「別人」，不是憑證。第一步 eca 留在 1000，不套 AS，靠 bwrap 視野＋cgroup；之後再談專屬 subuid＋憑證綁進去。

## 3. 分工與接法

- **rlimit**：單支暴走（cpu、檔案大小、fd）。
- **cgroup**：一串總量（記憶體、行程數）。
- **uid**：誰是誰（擁有者、訊號）。
- **bwrap**：看得到什麼。
- **牆鐘**：aos-exec／kernel 期限，不變。
- **接 aos-sandbox**：limits key 同一套不變；加 `sub:N` 走 `aos-asuser`。T21「設定壞了照跑」建議改成拒跑，跟 daemon 的 `LimitBad` 一致。
- **接 L3／#8 寄件人自報**：uid 分開後，信檔的擁有者 uid 就是偽造不了的寄件人，kernel 與專區用 stat 驗，不信信裡自報。
- **接 #7／#10／#12**：靠乙＋目錄權限解，不靠黑名單。

## 4. 最小第一步（全免 root）

1. kernel 基礎包：`limits {default,max}`、夾、丟掉請求自帶的 `user`。
2. daemon：`{}` 改語意＋`limits_max`＋`limit_hit` 翻譯＋列上記實套值。
3. 二期：`aos-asuser`（sub:N）＋目錄權限收緊＋投遞箱。
4. 三期：cgroup 子格。

要 root 的部分併進現有 `cmd/aos-sandbox/root/` 那種形式：獨立一包、預設乾跑、不裝不影響任何功能，內容只有建帳號與「只准換成指定帳號」的 helper／sudoers。

## 待裁

| # | 題 | 選項 | 推薦＋理由 |
|---|---|---|---|
| 1 | 自帶 limits 超上限 | 夾／拒 | 夾並記號；agent 不必猜上限 |
| 2 | `{}` 改成「用預設」 | 改／不改 | 改；現在是一句話就解除限制 |
| 3 | 推翻「不做 cgroup」 | 二期做／不做 | 做，僅 memory＋pids；AS 對 node 不能用 |
| 4 | uid 主路 | 甲／乙／丙 | 乙；免 root 且是真 uid |
| 5 | subuid 算不算一棵樹 | 算／不算 | 算；仍只屬這個帳號 |
| 6 | eca 身的 uid | 留 1000／專屬 subuid | 先留 1000；憑證本來藏不住它 |
| 7 | root 包（真帳號、helper、sudoers） | 現在做／先不做 | 先不做；沿 11-12「root 小 daemon 先不做」 |
| 8 | 設定壞了 | 拒跑／照跑不套 | 拒跑；否則限制形同沒有 |
| 9 | 沒 s6 的機器 | daemon 自己 setrlimit 即可／一定要 s6 | 前者；s6 留給 aos-sandbox 選用 |

## 邊緣狀況

| 狀況 | 處理 |
|---|---|
| 同 uid 下 `procs`（NPROC）算的是整個帳號的行程，設小了會卡死使用者自己 | 沒換 uid 時不套 NPROC 或警告；總數交給 cgroup pids |
| user ns 裡 NPROC 的計法 | 待驗 |
| 樹主刪不掉 subuid 的檔 | 清理一律經 `aos-asuser` 進 ns 做 |
| agent 繞過 kernel 直寫 daemon 信箱 | 一期靠 `limits_max`；二期靠目錄權限讓它寫不進去 |
| cgroup「有行程的格不能再分子格」 | daemon 自己待葉子格，proc 各一格 |
| 子 daemon 算一格 | 它那格的 `memory.max` 就是整台總量，往下再分 |
| daemon 在行程內跑 `run_cli`（不 exec） | 換 uid 後已開的 fd 仍在，要先關 |
| WSL 無委派、無 newuidmap | 退回只有 rlimit＋bwrap，表上明寫缺哪層 |

