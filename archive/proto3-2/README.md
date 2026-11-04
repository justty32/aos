# proto3-2 — 使用者寫偽碼、我補全

← [proto3-1](../proto3-1/README.md)（上一版：list 當世界、eval 求值，Janet＋CL 兩套）

2026-09-08 開的。框架跟 proto3-1 一樣（Janet、jpm、spork；`src/`、`test/`、`notes/`），這次**沒有 CL 版**。
做法：使用者在 `src/` 寫偽碼，我補成能跑的 Janet。

## 現在有什麼

- `src/agent.janet`：補全了——agent 就是一個 list，`(agent/next a)` 求值它、回傳下一個 agent；三態 idle／think／act。
- `src/clock.janet`、`src/kernel.janet`、`src/main.janet`：還是使用者的偽碼，沒動。
- `test/agent.janet`：19 條。
- `notes/`：使用者的想法與我的理解。

## 怎麼跑

```sh
cd proto3-2
jpm test                 # 跑 test/*.janet
janet src/main.janet     # 有 main 之後
```
