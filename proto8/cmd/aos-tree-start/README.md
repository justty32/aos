# aos-tree-start：起樹前先看殼裡有沒有別棵樹的 AOS_*

← [cmd](../README.md)｜出處：[agents-feedback T07](../../thinking/2026-11/13/agents-feedback-1113-題目.md#t07-在-agent-的-shell-裡起樹會起錯位置)、[gotchas/05](../../../wf/workflows/common/gotchas/05-在跑著的樹旁邊做事.md)

```sh
cd ~/aos-home && source env.sh && aos-tree-start root      # 等於 aos-exec root，前景跑
```

做兩件事：

1. 看環境裡有沒有 `AOS_HOME` 以外的 `AOS_*`。有＝這個殼是別棵樹（或樹裡某隻 agent）起的，新根會把那棵的 stack、daemon 當成自己的（11-13 15:24 `eca_main` 的殼起樹，`AOS_STACK` 沒清，根把那隻 agent 的格子當成 root stack）。這時拒絕，錯誤行只列變數名、不印值：
   `aos-tree-start: error: EnvBad AOS_DAEMON, AOS_STACK set in this shell (inherited from another tree or an agent's shell?): the root would use them; clear every AOS_* except AOS_HOME first (cd TREE && source env.sh, in bash), or pass --force`
2. 沒有就 `exec aos-exec 參數…`（pid 不變、結束碼就是 aos-exec 的）。

- `--force`：照樣起，印一行提醒列出帶著的名字（測試裡故意巢狀起樹時用）。
- aos-exec 的參數以 `-` 開頭時放在 `--` 後：`aos-tree-start -- --stack stacks/root defs`。
- 不給參數＝`ArgumentsBad`（三扇門慣例；不偷偷補 `root`）。
- 允許 `AOS_HOME`：`env.sh` 清完全部 `AOS_*` 會設它，範本 [daemon-root](../../templates/daemon-root/README.md) 的 `.env` 也要它。

**為什麼擋在這支、不擋在 aos-exec／aos-daemon**：樹裡的巢狀呼叫（daemon 起子項、單子裡再叫 aos-exec）本來就帶 `AOS_STACK`、`AOS_DAEMON`，從環境分不出「這次是在起一棵新樹」；只有明說要起樹的這支知道。所以直接打 `aos-exec root` 照舊不擋，起樹請用這支（或照舊先 `source env.sh`）。

測試：`python3 -m unittest discover -s proto8/cmd/aos-tree-start/tests`（PATH 上放假的 `aos-exec`，不起任何行程）。新指令要跑一次 `proto8/install.sh` 才會出現在 `~/.local/bin`。
