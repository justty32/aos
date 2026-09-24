← [kernel](README.md)｜[spec 總導航](../README.md)

# 實作補記（2026-09-24）

依 [實作審查報告](../../notes/2026-09-23-rearch/impl-review-report.md) 與 [LM Studio 真跑](../../notes/2026-09-23-rearch/lmstudio-run.md) 回寫；修正輪紀錄見 [impl-fix-round1.md](../../notes/2026-09-23-rearch/impl-fix-round1.md)。不改上面的節號，只把句子補進原節：

- §1.1：cpu 家「缺的補齊、不覆蓋」（審查 C-1）。
- §1.3：ack 名加 digest（A-3、B-5）；boot-kill 兩顆時加 cpu 名（B-6）。
- §2：省略 name 從 0 起（B-7）。
- §3 第 10 步：空格不寫 log（真跑 ⑤-4）；log 不保證涵蓋崩潰中途（B-11）。
- §6：init `--cpu`、`ack`、`ls` 摘要／`--json`、`-h`（真跑 ⑤-2、3、5）；boot 第 2 步交接兩顆 kcpu（A-4、B-6）與硬砍例外（B-12）；
  第 3 步只丟未出貨的 stops（B-10）；第 4 步補齊家（C-1）。
- §3 第 4／10 步（09-24 kernel-crash，C-7／C-8 真 KILL 實測，見[報告](../../notes/2026-09-24-kernel-crash/README.md)）：出貨「送出後、清帳前」崩潰，下一格照「EEXIST 當已放」重放，
  保守讀法是**接收者可能已經處理完**：ack 重放用新一格的 seq 取名，同一則回音可能收到兩份不同名的 ack（第二份無害）；
  stop 若接收的 cpu 已消化並退出，重放會在它家留下一份同名 `stop-<chain>.json`，下次 boot 的新 cpu 讀到就退 0、下一格第 7 步再拉起（同 B-10 跨代 stop，等使用者拍）。

## 池式納入（2026-09-24 proto5-2）

上面幾條講的 `stops`、`boot-kill`、孩子表，池式納入後已不存在（§1.2、§1.3、§6 boot 已改寫）。實作時跟 proto5-2 草稿字面不同、已寫進本資料夾的決定（編號是 proto5-2 實作隊的 D-n）：

- §1.1：`skip` 寫入時不丟任何一號、退休號只增不減（D-4／D-38，09-24 裁定）；從沒確認過的位置直接換（D-49）。
- §1.2：多 `halting`、`stale`、`boot_redeclare`、`acquired`，`pools.kernel` 只有四格（D-20、D-48、D-49）；`want` 初值 null（D-21）；scale 單重放前先看回音（D-25）。
- §3：stop 控制檔進 `deletes`（D-26）；discard 且兩個檔都不在直接取消（D-27）；通知 home 解析出錯也是壞通知（D-49b）、K 經過 symlink 用 realpath 再比（D-80）。
- §3.1：解不出 daemon 的新池不建格（D-24）；出錯後不自動重試的判法（D-23）；「池消失」只認確定不在（D-49a／D-66）。
- §6 boot：等 draining 0（D-5，09-24 裁定）；交接完重讀帳本（D-47）；兩個 kernel 池的檔名（D-28）；第 1 版帳本不接手（D-29）；半途失敗的 ack（D-30）；印 `booted N pools, M cpus`（D-36）。
- §6：cpu add／rm 的邊界與 `NotLiteral`（D-37、D-39）、「kernel 沒在跑」怎麼判（D-40）、cpu ls 欄位與尾註字眼（D-41、D-120～D-123）、halt 的 not running（D-31）、health 的碼與順序（D-43）、check 的細節（D-44、D-124）。
- §5：池刪掉後舊鏈晚到的 scale 單列保證外（D-69，09-24 裁定）。
