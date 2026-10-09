---
name: aos-test
description: Run the proto7-2 test suite (all tests, one folder, or tests whose name matches a pattern) inside a systemd scope and report the exit code. Use after changing proto7-2 code, before handing work over, or when asked to check that nothing broke. （跑測試、全套測試、確認沒壞）
triggers: 跑測試、全套測試、測試、run_all.py、test suite
not_for: 寫測試、測試報告
---

# aos-test：跑 proto7-2 的測試

在 repo 根目錄跑（`S`＝這個 skill 的資料夾；掛載給任務時是 `mnt/skill-aos-test`）。一律包 systemd scope（限程序數與時間，跑壞了不拖垮整台機器）：

```sh
bash $S/scripts/run.sh                       # 全套（約 5 分鐘）
bash $S/scripts/run.sh modules/skills/tests  # 只跑一個資料夾（相對 proto7-2/）
bash $S/scripts/run.sh -k restart            # 只跑名字含 restart 的
```

- 退出碼 0＝全綠、1＝有失敗；回報時給測試數與退出碼。
- 全機同時最多 3 份全套：跑全套前先數 `ps -eo args | grep -c '^/usr/bin/python3 \(-B \)\?proto7-2/tests/run_all.py'`，≥3 就等（別用 `pgrep -fc`，會多算）。
- 測試清單與慣例見 proto7-2/tests/README.md。
