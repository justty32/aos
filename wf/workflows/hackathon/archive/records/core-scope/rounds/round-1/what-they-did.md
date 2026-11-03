# 第 1 輪紀錄 — 各人做了什麼

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 →](../round-2/what-they-did.md)

## 1. 各人做了什麼

四位都用現成 `aos` 跑單一 world、串行三回合、假模型＋假 provider，再注入 SIGINT、SIGKILL、rename 前中止；事故都靠人工處理現場走回 final。

- **Carmack persona**：固定 argv 工具；另做 provider accepted／dropped 兩案本機 snapshot 相同的對照。
- **Armstrong persona**：POSIX shell，所有本機狀態共用一支 `atomic-publish.sh`；做了一次盲重試。
- **Cantrill persona**：phase marker 定位故障點，假 provider 可 query。
- **Thompson persona**：三行 `deliver.sh` 的最小鏈，另以不含 `aos` 的三行 shell 跑 happy path 對照。

坑見 [坑的總表](pits.md)。
