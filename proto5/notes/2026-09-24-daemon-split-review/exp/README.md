← [daemon 分開的理由審查](../README.md)

# 實驗：不用 root 能不能「切使用者」（2026-09-24，Manjaro，使用者 lorkhan）

**沒 sudo、沒建使用者、沒改系統設定。** 只用系統原本就有的東西：`bwrap` 0.12、util-linux 2.42（`unshare`／`setpriv`）、
`newuidmap`（系統裝好的帶權限小幫手）、`/etc/subuid` 裡原本就配給 lorkhan 的 `100000:65536`。
擺設都在 scratchpad，輸出裡的路徑換成 `$SCRATCH`。原始輸出在 `exp*.out`。

## 1. 不是 root、不進 namespace，直接切 uid（[exp1](exp1-nonroot-setuid.sh)，[輸出](exp1.out)）

| 試 | 結果 |
|---|---|
| `setpriv --reuid 1234` | `Operation not permitted` |
| `runuser -u nobody` | `may not be used by non-root users` |
| `systemd-run --user -p DynamicUser=yes` | 單元設定不合法（使用者自己的 systemd 不能換人） |
| `systemd-run --user -p User=nobody` | 起得來但退 216（換不了人） |

→ **傳統「切成另一個真的 Linux 使用者」一定要 root**（或 sudo 白名單、或系統層 systemd）。使用者自己的 systemd 幫不上。

## 2. bwrap `--uid`／`unshare -U` 的單一對應（[exp2](exp2-single-map.sh)，[輸出](exp2.out)）

| 試 | 結果 |
|---|---|
| 2a `bwrap --unshare-user --uid 2001`，整台唯讀掛進去，讀另一個家的 600 檔 | `id` 顯示 2001，**照樣讀到** `secret-B`；檔案在裡面也顯示成 2001 擁有 |
| 2b `unshare -U --map-user=2001` 同上 | 同樣**讀到** |
| 2c 單一對應裡再 `setpriv` 成第二個 uid | `Invalid argument`（裡面只有一個 uid 可用） |
| 2d bwrap 只掛 homeA，不掛 homeB | 讀 homeB＝`No such file`（**擋住的是「沒掛」，不是 uid**） |

→ bwrap／`unshare -U` 的 `--uid` **只是換名牌**：裡面外面還是同一個 lorkhan，檔案權限一點都沒變。
bwrap 牢擋得住，是因為 mount namespace 只掛了表裡的資料夾（L 隊 [agent-access](../../2026-09-24-agent-access/README.md) 就是這樣做）。

## 3. 用副 uid 開多 uid 的 namespace，再降成不同 uid（[exp3](exp3-subuid.sh)，[輸出](exp3.out)）

像 rootless podman：`unshare --map-auto --map-root-user` 開一層，裡面 0＝外面的 lorkhan，1～65536＝外面的 100000～165535。
裡面把 homeA chown 給 1001、homeB 給 1002（700／600），再 `setpriv --reuid 1001` 降權（丟光能力）當「A 的孩子」。

| 試 | 結果 |
|---|---|
| 3a A 的孩子讀自己的家 | ✔ `secret-A` |
| 3b A 的孩子讀 B 的家 | **`Permission denied`**（真的擋住，靠核心的檔案權限） |
| 3c A 的孩子想再切成 1002 或 0 | `Operation not permitted` |
| 3d A 的孩子看 lorkhan 的 HOME | `Permission denied` |
| 3p A 的孩子走原路徑（祖先是 lorkhan 的 700 資料夾）進自己的家 | **`Permission denied`**——祖先資料夾擋路；要 bind mount 繞開，或把祖先開 `o+x` |
| 3e 外面的 lorkhan 看這兩個家 | 擁有者變成 `101000`、`101001`；**lorkhan 自己 `cat` 不到** |
| 3f 外面的 lorkhan `rm -rf` | **刪不掉**；要再進 namespace 才清得掉 |

→ **不用 root 也能做出「真的不同 uid、核心擋得住」的隔離**，前提是系統已配好 subuid（Manjaro 預設有）。
代價：開 namespace 的那支（要 chown、要降權的爸爸）在裡面是「假 root」，讀得到所有孩子的家；
人從外面反而看不到、刪不掉孩子的家（`ls`／`cat` 範式受傷），要多一支「進 namespace 看」的小工具；
祖先資料夾（HOME 是 700）要另外處理；每個孩子的 uid 要有人分配、記帳。

## 4. 每次啟動的代價（[exp4](exp4-cost.sh)，[輸出](exp4.out)，各跑 200 次 `/bin/true`）

| 做法 | 每次 |
|---|---|
| 直接跑 | 0.19 ms |
| `unshare -U -r` | 0.34 ms |
| `bwrap --unshare-user --uid`（整台唯讀） | 0.72 ms |
| `bwrap --unshare-all` 只掛 `/usr`（L 隊那種牢） | 1.19 ms |
| `unshare --map-auto`（每次叫 newuidmap）＋`setpriv` | 1.43 ms |

→ 都是毫秒以下到一毫秒多，跟一次 Python 啟動（約 20 ms，見 [idle-wait](../../../../proto5-2/notes/2026-09-24-idle-wait/measure.md)）比都很小；
上千顆 cpu 啟動時不是瓶頸。多 uid 那種若只在 daemon 開機開一次 namespace、孩子只 `setpriv`，每顆只多零點幾毫秒。
