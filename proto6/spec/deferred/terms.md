# 暫緩的名詞：舊 daemon 用語

← [暫緩區](README.md)｜[名詞（現行）](../terms.md)｜[舊 daemon](daemon/README.md)

**這篇整篇在暫緩區。** 只有 T-09，從[名詞](../terms.md)搬來，條號不變。這些詞（收尾、排空停機、熱重載、逃生口、runner）全是舊 daemon 設計的用語；2026-10-01 daemon 改成只定期叫 `aos-exec` 的最核心版本，這些功能第一版都不做。現行 daemon 的用語看 [T-11](../terms.md)。

## T-09．收尾、排空停機、熱重載、逃生口

> **暫緩**（2026-10-01）：daemon 改成只叫 aos-exec、不認得 node；收尾、排空停機、熱重載、逃生口、runner 都是舊 daemon 的功能，最核心 daemon 第一版不做（使用者 2026-10-01）。條號保留、不重用。

幾個容易混的詞，都屬 daemon，不在任務表上。這裡只給詞義，做法看正本。

| 詞 | 意思 | 正本 |
|---|---|---|
| 收尾 | daemon 清掉一個範圍的固定做法：先請停、等寬限、再強制，確認全空；有 cgroup 時最後用 `cgroup.kill` 兜底。重啟、停機、解除登記、砍掉掛載行程、取消在跑的工作都用它 | [B-604](daemon/lifecycle.md) |
| 格後收尾 | 一格正常結束後，殺掉沒人收的殘留 | [B-601](daemon/runtime.md) |
| 排空停機 | daemon 停收新工作，等在途的做完再停；可設上限時間 | [B-604](daemon/lifecycle.md) |
| 熱重載 | 不重開 daemon，重讀設定並套用「免重開」的部分 | [B-608](daemon/reload.md) |
| 逃生口 | 有 cgroup 時，node 在自己框下另開子框、刻意留住的常駐程序。不在 aos 管轄範圍內，aos 不管；重啟與解除時殺不殺看 `kill_escape_cgroups` | [B-605](daemon/cgroup.md) |
| runner | daemon（或 helper）開每一格、每個掛載行程時用的固定程式 `aos-runner`：照 [inst](../inst.md) 執行一次（就是 proto5 aos-exec 的慣例），並當收屍人，清空它名下的所有程序 | [B-601](daemon/runtime.md) |

- 「排空」只指停機；解除登記那套叫「收尾」。
- 表中的「逃生口」指 node 自開的子框，跟 [T-07](../terms.md)「唯一逃生口是通道」不是同一件事；它不在 aos 管轄範圍內，所以不算衝突（納入 cgroup 與 git 疑-7）。

依據：第十八批（詞義；Q19 逃生口可調、預設不管）；第二十批（歸 daemon，詞義不變）；納入 cgroup 與 git 疑-7（逃生口准、不管）。
