# 2026-09-29 使用者裁定（五）：依賴

← [裁定索引](README.md)｜[筆記索引](../README.md)

本份收：第十四批（依賴）、追加、B1／B2。全部裁定後批優先，見[裁定索引](README.md)。

## 第十四批：依賴（同日晚，已落進 spec）

〔使用者方向 2026-09-29 晚〕題目見 依賴盤點第五節（已封存檔 2026-09-29-dependency-review.md，索引見 [archive/README.md](../archive/README.md)）、systemd 拆分第四節（已封存檔 2026-09-29-systemd-split.md）。第一輪只裁定一部分，其餘於同日晚追加裁定（見「追加（同日晚）」）。

**總原則**〔使用者方向 2026-09-29 晚〕：

- Python 盡量只用標準庫，不必另外 pip 安裝。唯一例外：執行期驗工具參數可用第三方 `jsonschema`。
- quota、systemd 都是**可選項**：有就用，沒有就用 aos 自帶的土方法。磁碟用量定期掃資料夾；程序管理由 daemon 自己做簡單的行程管理；難以實現的就不支援。（已被下方追加 1「初版不使用 systemd」取代。）
- **cgroup（v2）一定要**，是必要依賴。
- 遠期方向（很遠，只記錄）：aos 基底之後希望改用 C++11 乃至 C99；agent 這塊才開始引入 Python。

**依賴盤點各題**：

1. **quota 可選，沒有就掃資料夾**〔使用者方向 2026-09-29 晚〕：照建議的方向，但不是「砍掉」，是「有就用、沒有就掃」。
2. **systemd 可選，沒有底線**〔使用者方向 2026-09-29 晚，不照建議〕：不要求「委派 cgroup 子樹」這種最低必要範圍。（已被追加 1 取代）
3. **沒有 systemd 的 Linux 也要能跑**〔使用者方向 2026-09-29 晚，不照建議〕：推翻「首版不支援、啟動時報錯」，改成降級執行。（已被追加 1 取代）
4. **ACL**：已裁定，見下方追加（首版只用群組，不用 ACL）。
5. **執行期驗工具參數用 jsonschema**〔使用者方向 2026-09-29 晚，不照建議〕：不自寫子集；這是「只用標準庫」的唯一例外。
6. **最低版本自檢**：已裁定，見下方追加。（注意：「systemd 能委派三個 controller」那項現在要改成「有 systemd 時」。）
7. **tmpfs**：已裁定，見下方追加（首版拿掉）。
8. **檔案系統不限定**〔使用者方向 2026-09-29 晚，不照建議〕：node 放在不支援 aos 某些功能的地方，那些功能就不支援；不做明文白名單與拒絕清單。
9. **「用 sudo 開」不改**〔使用者方向 2026-09-29 晚，不照建議〕：要的就是能用 sudo 開。`run0` 是否設 `SUDO_UID` 那條不用查了。

**對 systemd 拆分筆記的意思**〔使用者方向 2026-09-29 晚〕：

- 依賴盤點問「systemd 底線」與拆分筆記「20 條交給 systemd」方向衝突，這次一併回答：那 20 條都改成「**有 systemd 時的做法**」；沒有 systemd 時，要嘛有 daemon 自己的退路，要嘛標成不支援。
- 拆分筆記第四節拍板題 1～8（部署形態、timer、unit 命名、fd 交接、daemon 死掉、上限放哪層、封鎖 user systemd、舊上限套回）：已裁定，見下方追加。

### 裁定帶出的待釐清處

只列問題，不替使用者決定。

- **cgroup 必要、systemd 可選：沒有 systemd 時，誰把一棵 cgroup 子樹交給 daemon？**
  - 問題：cgroup v2 的規矩是子樹要交給某個帳號（chown 那棵的資料夾與 `cgroup.procs`、`cgroup.subtree_control` 等檔）才能在裡面建框、寫上限。沒 systemd 就沒人幫忙。
  - 選項：開機時 root 一次性 mkdir＋chown；或用 sudo 開 daemon 時 daemon 自己建（helper 本來就是 root）；沒 sudo 的單帳號模式怎麼辦（要不要求使用者事先準備好）。
  - 相關：cgroup v2「內部程序」規則（成員程序要在葉端、上層開 controller）daemon 自己開框時要遵守。
- **（已裁定，見追加第 5 條）** 上一條 cgroup 子樹誰建：sudo 開時 daemon 自己建；不用 sudo 時使用者事先建好交給 daemon 帳號，沒有就報錯。
- **daemon 自己的土法行程管理其實可以靠 cgroup，不必靠 systemd。** 對照 systemd 拆分表（已封存檔 2026-09-29-systemd-split.md，索引見 [archive/README.md](../archive/README.md)），大概分法（還沒逐條驗證，待釐清）：
  - **沒 systemd 仍做得到**（用 `cgroup.kill`、`cgroup.procs`、`cgroup.events`、`memory.events`、直接寫 `cpu.max`／`memory.max`／`pids.max`，加上 daemon 自己 fork）：
    - D6 互斥（node 鎖＋登記表）、D7 開程序、D9 fd 交接（沒 systemd 只給三個 fd 的限制，反而更好做）、D10 建資源框、D11 寫上限、D12 讀實際值、D13 殺乾淨樹（`cgroup.kill`）、D15 逾時（daemon 計時）、D16 取消、D17 OOM 證據、D18 收尾程序在成員框外（自己排版）、D19 重啟全殺（掃 aos 子樹殺光）、D22／D23 停機與 unregister、D28 乾淨環境（fork 時自己清）、D29 收集 stderr。
    - H4～H6 helper 的切帳號、放進框、殺樹：本來就是原設計，helper 自己 fork＋setresuid＋寫 `cgroup.procs`。
  - **要標不支援，或只給一半**：
    - D21 開機自啟與崩潰重啟：沒 systemd 就交給使用者自己的 init，或不支援；可能只附一份範例。
    - H5 額外防護（`NoNewPrivileges`、`CapabilityBoundingSet` 等）：helper 自己用 `prctl` 大致能做，但 systemd 那套沙盒選項不會有。
    - 拆分筆記第 5 題 `BindsTo=`（daemon 一死在途 tick 立刻死）：沒 systemd 就靠 `PDEATHSIG`＋管道斷線＋下次啟動掃框，是否夠用要看。
    - 拆分筆記第 7、8 題（封鎖 user systemd、舊上限套回）：沒 systemd 時整題不存在。
    - D14 確認框真的空了：本來就是自己做，沒差別。
  - 問題：這樣分對不對？「土法」的範圍要不要明寫成一份「沒 systemd 時的行為表」？
- **「有就用」要靠設定檔開關，還是啟動時自動偵測？（已裁定：啟動時自動偵測，設定檔可強制關，見追加第 6 條）**
  - 問題：quota、systemd 各自要不要設定檔明寫「用／不用」？自動偵測到了但使用者不想用怎麼辦？偵測結果要不要記錄／顯示（`daemon` 啟動訊息、`node.show`）？降級時要不要警告？
- **依賴盤點提到、仍在的實作坑（只列指標，不展開）**：
  - 「不覆蓋發布用 hard link」：見依賴盤點第四節（已封存檔 2026-09-29-dependency-review.md，索引見 [archive/README.md](../archive/README.md)）。
  - 「helper 新帳號沒 git 設定」：同上。
  - 「safe.directory」：同上。
  - 舊 kernel 沒有 `cgroup.kill`（5.14 前）時，退路是反覆讀 `cgroup.procs` 逐個殺，見依賴盤點 2.1（已封存檔 2026-09-29-dependency-review.md，索引見 [archive/README.md](../archive/README.md)）。

### 追加（同日晚）

以下皆為〔使用者方向 2026-09-29 晚〕。

1. **初版不使用 systemd**〔使用者方向 2026-09-29 晚〕：整套首版不靠 systemd 跑。systemd 拆分筆記（已封存檔 2026-09-29-systemd-split.md，索引見 [archive/README.md](../archive/README.md)）那 20 條「交給 systemd」留到以後當可選增強。
2. **開機自動啟動**〔使用者方向 2026-09-29 晚〕：把 daemon 寫成一個 systemd service 即可，附範例 unit 檔，不算執行期依賴。
3. **沙盒防護**〔使用者方向 2026-09-29 晚〕：systemd 的 `CapabilityBoundingSet` 等沒有就是沒有，以後再考慮支援。
4. **daemon 死了**〔使用者方向 2026-09-29 晚〕：對正在跑的 tick 送信號，讓它們優雅結束。
5. **cgroup 子樹誰建**〔使用者方向 2026-09-29 晚〕：用 sudo 開 daemon 時由 daemon 自己建；不用 sudo 開時，要使用者事先建好並交給 daemon 帳號，沒有就報錯。（已被第十五批第 2 條取代：一律要事先準備好，另有開關讓 daemon 自己建，見 [06](06-cgroup-direct-delivery.md)。）
6. **「有就用」的功能（quota 等）**〔使用者方向 2026-09-29 晚〕：啟動時自動偵測，設定檔可強制關。
7. **部署形態（systemd 拆分第 3 題）**〔使用者方向 2026-09-29 晚〕：先不使用 systemd。
8. **資源上限設在 node 那層**〔使用者方向 2026-09-29 晚〕：不是每格設一次。
9. **依賴盤點第 4 題（ACL）**〔使用者方向 2026-09-29 晚〕：首版只用群組，不用 ACL。
10. **依賴盤點第 6 題（最低版本）**〔使用者方向 2026-09-29 晚〕：最低版本（kernel 約 5.14、Python 3.9）寫進 spec，啟動時自檢。
11. **依賴盤點第 7 題（tmpfs）**〔使用者方向 2026-09-29 晚〕：helper 的 tmpfs 掛載首版拿掉。
12. **systemd 拆分其餘題**〔使用者方向 2026-09-29 晚〕：timer 那題因為 daemon 本來就自己計時，視為不用 timer；unit 名稱、inst 快照交接、兩條封鎖、舊上限殘留都只在「有 systemd」路線才會碰到，隨初版不用 systemd 一起延後。

### 追加帶出的待釐清處

只列問題，不替使用者決定。

- **sudo 開時 daemon 建 cgroup 子樹的細節**：
  - 要在降權之前（或由 root helper）建好子樹。
  - 只 chown 子樹根的那幾個委派檔（`cgroup.procs`、`cgroup.subtree_control`、`cgroup.threads`），父層不 chown。
  - daemon 自己要先被搬進這棵子樹。搬程序需要對共同祖先的 `cgroup.procs` 有寫權，所以只能在還有 root 時做；之後在子樹內搬程序才不用 root。
- **有 systemd 的機器上不經 systemd 建子樹**（例如使用者的 Manjaro）：直接在 cgroup 根下建子樹，違反 systemd 的「單一寫入者」約定。實務上通常可行但不保證。要不要改成建在某個固定位置，或文件寫明風險？
- **daemon 被 SIGKILL 或當掉時沒機會送信號**：要不要在開 tick 時設 `PR_SET_PDEATHSIG`？注意它只作用於直接子程序，孫程序收不到，所以仍要靠下次啟動用 `cgroup.kill` 掃殘留。

### B1／B2（同日晚）

回答上面「追加帶出的待釐清處」。以下皆為〔使用者方向 2026-09-29 晚〕，已落進 spec（[B-603／B-605](../../spec/settled/daemon.md)）。B1 整套已被第十五批第 2 條的 cgroup 通用規則取代（見 [06](06-cgroup-direct-delivery.md)），B2 仍有效。

- **B1 cgroup 子樹建在哪**〔使用者方向 2026-09-29 晚〕（已被第十五批取代）：
  - daemon 由 systemd service 開機啟動時，範例 unit 檔寫 `Delegate=yes`，daemon 使用 systemd 劃給它的子樹。
  - 手動用 sudo 啟動時，daemon 先偵測：機器有 systemd 管 cgroup、但 systemd 沒有劃子樹給 daemon，就報錯退出，不自己在 cgroup 根下建。
  - 機器完全沒有 systemd 時，sudo 開的 daemon 自己建子樹（照追加第 5 條）。
  - 文件寫明：有 systemd 的機器上想手動開，用 `systemd-run --scope -p Delegate=yes sudo aos daemon …` 這類寫法讓 systemd 先劃子樹。
- **B2 daemon 當掉時孫程序怎麼清**〔使用者方向 2026-09-29 晚〕：
  - 所有 tick 程序（含孫程序）都在該 node 的 cgroup 裡，daemon 死了 cgroup 還在。
  - daemon 下次啟動時，對每個仍有程序的 node cgroup 先送 SIGTERM、等一段寬限時間讓它們優雅收尾，再用 `cgroup.kill` 殺掉剩下的。
  - 開 tick 時設 `PR_SET_PDEATHSIG` 只當加分（只作用於直接子程序），不是必要。
  - daemon 正常關閉時照舊由 daemon 送信號讓在途 tick 優雅結束。
  - 逃生口（讓 daemon 系譜的程序脫離管理）延後〔使用者方向 2026-09-29 晚〕：以後再設計，技術上可行（例如由 daemon 或 root helper 把程序搬出 node cgroup）。
