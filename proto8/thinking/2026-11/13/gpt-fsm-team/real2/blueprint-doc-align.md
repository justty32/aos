# 圖紙 real2：兩份 11-13 thinking 補「換樹後」註（gpt 隊第二次真工作，線隊二 11-13 23 點）

← [gpt-fsm-team](../../gpt-fsm-team.md)｜來源：`wf/SESSION-LOG.md`「11-13 文件裡還沒對齊的幾處」那條（eca-as-kernel 生效表、workflows-into-aos「趕不上今天的重抄」）

**只加註、不改原文、不判斷設計。** 全隊對本圖紙唯讀。

## 能改的檔（只有這兩個）

- `proto8/thinking/2026-11/13/workflows-into-aos.md`
- `proto8/thinking/2026-11/13/eca-as-kernel.md`

其他檔一律不動（包含 `wf/SESSION-LOG.md`、本圖紙、日索引）。

## 先驗的事實（唯讀指令，全部要成立；有一條不成立＝BLOCKED，不要改檔）

在 `/home/lorkhan/repo/aos` 下：

| # | 指令 | 預期 |
|---|---|---|
| F1 | `git --no-optional-locks cat-file -t 54789088d:proto8/knowledge/wf/workflows` | `tree` |
| F2 | `git --no-optional-locks cat-file -t 54789088d:proto8/knowledge/wf/knowledge` | `tree` |
| F3 | `git --no-optional-locks cat-file -t 54789088d:proto8/lib/aos/kernel/hold.py` | `blob` |
| F4 | `git --no-optional-locks cat-file -t 54789088d:proto8/lib/agent/kernel_gate` | `tree` |
| F5 | `git --no-optional-locks cat-file -t 54789088d:proto8/lib/packs/kernel_gate.json` | `blob` |
| F6 | `git --no-optional-locks cat-file -t 54789088d:proto8/knowledge/aos/kernel.json` | `blob` |
| F7 | `grep -c '^\*\*活樹有沒有\*\*：第 1 塊寫的時候以為趕不上今天的重抄' proto8/thinking/2026-11/13/workflows-into-aos.md` | `1` |
| F8 | `grep -c '^| `kernel/`、`extras/kernel-chain-check`、條文、thinking | 不在活樹裡用 |$' proto8/thinking/2026-11/13/eca-as-kernel.md` | `1` |

## 改法

### A `workflows-into-aos.md`

在 F7 找到的那一行（以 `**活樹有沒有**：` 開頭的段落，整段只有一行）**正後面**插入兩行：一行空行，接著這一行（逐字照抄，含全形括號）：

```
（11-13 23 點註：家機活樹 22:55 換樹到 `54789088d`，上段說「要等下一次重抄」的第 2 塊——`knowledge/wf/` 底下的 `workflows/`、`knowledge/` 兩夾——已在家機活樹；公司 WSL 活樹沒查。）
```

### B `eca-as-kernel.md`

在 F8 找到的那一行（「生效表」的最後一列）**正後面**插入兩行：一行空行，接著這一行（逐字照抄）：

```
（11-13 23 點註：家機活樹 22:55 換樹到 `54789088d`，表上前三列（`lib/aos/kernel`、`lib/agent/kernel_gate` 與 `lib/packs/kernel_gate.json`、`knowledge/aos/kernel.json`）都已包含在內；「15:08 釘住的 commit 不含」那句以 SESSION-LOG 為準記為過時；公司 WSL 活樹沒查。）
```

## 驗收（全部要成立）

| # | 指令 | 預期 |
|---|---|---|
| C1 | `git --no-optional-locks diff --numstat -- proto8/thinking/2026-11/13/workflows-into-aos.md proto8/thinking/2026-11/13/eca-as-kernel.md` | 兩行，各是 `2	0	<檔名>` |
| C2 | `grep -c '11-13 23 點註' proto8/thinking/2026-11/13/workflows-into-aos.md proto8/thinking/2026-11/13/eca-as-kernel.md` | 兩個檔各 `1` |
| C3 | 讀 `git --no-optional-locks diff` 全文 | 只有上面兩處插入、內容與本圖紙逐字相同、沒有改到原有任何一行（包括行尾空白、檔尾換行） |
| C4 | `git --no-optional-locks status --porcelain` | 隊伍造成的變動只有這兩個檔（別人同時在改的其他檔不算，也不要碰） |

圖紙沒說或說不通的：BLOCKED，不要自己決定。
