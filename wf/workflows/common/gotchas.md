# 共通踩坑（跨工作流）

← [INDEX](../../INDEX.md)

不專屬任一工作流、任何人都可能撞到的坑，記/查這裡。某工作流專屬的坑記在該工作流自己的 `gotchas.md`（長出來後在下表加一列導流）。

## 哪類坑記哪裡

| 坑的性質 | 記/查這裡 |
|---------|----------|
| 不專屬任一工作流的共通坑 | **common/gotchas**（本檔）|
| 從 Windows 驅動 WSL、複製場地、跑 codex 開黑客松 | [hackathon/gotchas](../hackathon/gotchas.md) |

---

## 建置與相依

- **私有相依會偷偷變成使用者的義務**：`target_link_libraries(x PRIVATE dep)` 會在
  `INTERFACE_LINK_LIBRARIES` 留下 `$<LINK_ONLY:dep>`，匯出之後使用者的
  `find_package(aos)` 就得先找得到 `dep`——即使它是 header-only、即使符號全被
  hidden 蓋掉。`aos_add_subproject()` 已經會把它剝掉；**自己手寫 target 時要記得**。
  症狀是使用者在沒有 vcpkg 的環境 configure 直接失敗。

- **外部消費測試沒有 `env -u VCPKG_ROOT` 等於白測**：有 vcpkg 在的話，本來會失敗的
  相依問題會被它悄悄補上，問題留到使用者手上才爆。上面那個坑就是這樣被漏掉的。

- **公開標頭漏標 `AOS_API` 不會在編譯期爆**：編譯過、`#include` 也過，連結時才找不到
  符號——而且通常是**外部使用者先撞到**，自己在 repo 裡跑測試不一定會發現（測試若連的是
  OBJECT library 就繞過了可見度）。

- **`aos_add_subproject()` 的 `EXPORT_NAME` 不能省**：不設的話匯出後外部看到的是
  `aos::aos_inst` 而不是 `aos::inst`，而且 `find_package` 那一步不會報錯，錯誤延到
  `target_link_libraries` 才說「target not found」。

## 使用 aos

- **`aos exec` 的退出碼不反映子行程成敗**：`/bin/false` 回 1，但正常完成該回合的 `aos exec` 回 **0**；`.runi` 已存在則回 3。
  指令不存在、逾時被砍、重導向的檔開不起來也都回 0。要判斷子行程的結果得讀 `exit`
  欄位寫出的那個檔。詳見 [`docs/usage.md`](../../../docs/usage.md)。

## 改文件

- **批次改文件用非貪婪正則可能吃掉整段**：`.*?` 配上 `re.DOTALL`，如果終止字串在檔案
  更後面又出現一次，會從起點一路吃到那裡。這個坑真的發生過——`code-map.md` 被砍掉
  130 行還 commit 進去了，因為當時只 `grep` 關鍵字確認「殘留清乾淨」，沒看檔案剩幾行。
  **批次改完一定要看行數與章節數**，`grep` 只能證明某段不在，不能證明別的還在。

- **`\b` 邊界在 `-Iinst/include` 這種字串上不成立**：`inst` 前面是 `I`（word 字元），
  所以 `\binst/` 匹配不到。批次替換路徑之後，`grep` 一次確認沒有漏網的。
