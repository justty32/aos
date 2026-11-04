# eca — aos-eca：把外部 coding agent（claude／codex）掛到 aos-daemon 底下；三對指令 open／close、start／stop、add／rm

← [extras](../README.md)｜設計：[thinking 2026-10-30-eca](../../thinking/2026-10/30/eca/README.md)（C 結論 7～10、衝突 2～4、6、方向題 3）｜前身：[10-28 hub-adapter](../../thinking/2026-10/28/hub-adapter/README.md)、[10-28 hub-kernel](../../thinking/2026-10/28/hub-kernel/README.md)、[10-27 claude-switch](../../thinking/2026-10/27/claude-switch/README.md)｜接的是 [aos-daemon-ctl](../../bin/README.md)、[lib/agent/cli_session.py](../../lib/agent/cli_session.py)、[aos-eca-turn](../../bin/aos-eca-turn)｜測試 `proto8/tests/test_eca_cmd.py`

使用者 10-27：「往後搞不好會有很多claude code cli在跑……我cd過去某個資料夾，輸入指令，就可以打開正在該資料夾工作的claude code。」通用的那層是 aos-daemon，aos-eca 只做 daemon 做不到、只有外部 CLI 才需要的三件事——**畫面**（tmux 開／接／關、Ctrl-] 只跳出）、**對話接回**（`--resume`／`exec resume`，id 在 `session.txt`）、**CLI 自己的 session 檔**（`transcripts/` symlink）。

三對指令（使用者 11-02 晚「很好，所以三個對應：open/close, start/stop, add/remove」，[eca 14 § 決定](../../thinking/2026-10/30/eca/14-11-02-晚使用者想法.md#決定11-02-晚使用者)；11-03「統一成add/rm吧」，跟 aos-daemon-ctl 一樣）：`open`／`close`＝開／關畫面；`start`／`stop`＝**daemon 的起停**（`aos-daemon-ctl start`／`stop`：停著**還在 daemon 表上**、`phase` `stopped`、stack 留著、`where` 找得到、`aos-say` 照收，[thinking 11-03 procs](../../thinking/2026-11/03/procs/README.md) § 6 eca 那列）；`add`／`rm`＝建立與刪除（`rm`＝`aos-daemon-ctl rm`＋刪它的 stack，**不封存**，要留的人 rm 前自己複製）。每隻的 stack 一律拿 daemon 表上那一列的 `stack`；`add`（和 `open` 新建）收 `--stack S`（使用者「aos-eca add沒辦法指定stack嗎？aos-daemon-ctl add也是？」，[eca 18 § 11-03 procs 實作](../../thinking/2026-10/30/eca/18-11-03-單隻-add-rm.md#11-03-procs-實作stopstart-走-daemonadd---stack)）。

**每個子命令只管一隻**（使用者 11-03，[eca 18](../../thinking/2026-10/30/eca/18-11-03-單隻-add-rm.md)：「我預期aos-eca xxx這條指令，就是針對單個eca。如果要影響到所有eca，那得要等之後我們弄出aos-eca-hub這個繼承於daemon的新東西之後再說。」）；`ls` 暫時留著，以後歸到 aos-eca-hub。`add` 跟 `aos-daemon-ctl add XXX` 一樣，XXX 就是 eca 本身（「不應該有定義(template)這東西」），撞名在 add 時就報錯。

**資料夾的兩種意思**：`add XXX`（和 `open` 新建的那條）的資料夾＝**eca 本身**（頂層有 `cli.json` 的那個，例 `proto8/demo/eca-claude`）；其他子命令的 `資料夾`＝**工作區**（或小格裡面）。名字、資料夾都收的地方先比名字；都沒給＝cwd。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題（再按條號／頂層清單項）拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-是什麼](docs/01-是什麼.md) | 是什麼：開頭、它的 stack、對它說話＝--stack $(aos-daemon-ctl 、不封存、狀態、暫停 |
| [02-是什麼續與對它說話](docs/02-是什麼續與對它說話.md) | 是什麼（續）：畫面裡 Ctrl-]（或 Ctrl-\\）＝跳出、實例不、eca 資料夾、開場白檔、工具箱（thinking 11-03 eca-tools）；對它說話 |
| [03-已知限制](docs/03-已知限制.md) | 已知限制 |

<a id="是什麼"></a>
<a id="對它說話"></a>
<a id="已知限制"></a>
