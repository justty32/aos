> 封存 2026-09-29：09-28 從 proto5 收錄的交接快照，是 proto6 的起點；09-29 起架構改為 node／kernel 樹，spec 已重寫。現行看 [spec](../../../../spec/README.md) 與 [kernel 樹](../../../../notes/2026-09-29-kernel-tree.md)。

# Linux 外牆調查

← [筆記索引](../../../README.md)

兩份 2026-09-28 歷史調查完整快照；內文的員工／固定 worker 用語反映當時問題，後續方向見[資源與任務排程](../2026-09-28-linux-resources-and-task-scheduling.md)。未在 proto6 部署或重新驗證。

- [宿主 root daemon 的第二道牆](proto5-host-root-second-wall.md)：權限與外層隔離的責任邊界。
- [Linux 外牆可行性](proto5-linux-wall-feasibility.md)：候選方案、成本、局部實測與限制。
