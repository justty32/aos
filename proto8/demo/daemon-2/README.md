# daemon-2：信箱模式的 daemon（10-29）

← [demo](../README.md)｜程式：[aos-daemon § 信箱模式](../../impls/aos-daemon/README.md)、[aos-post](../../impls/aos-post/README.md)｜設計：[thinking 10-29 medium-plan § 四 3](../../thinking/2026-10-29-medium-plan.md)、NORMS N-28 的 10-29 補、N-16

一個 daemon，名單的增減不寫 `loops_ctl.json`，改成**誰都可以投一封信**進它的信箱 `$AOS_STACK/loops_mailbox/`，它每圈（200 毫秒）把信全部收下、照名字順序套進名單、對一次表。這裡有兩個寄信人：

- **agent 格 `agent-sam/`**：daemon 起來就照 `daemon.json` 起它（跑一次，`max: 1`）；它只做一件事——`aos-post send` 一封信，請 daemon 加一個子項 `tick`（每 300 毫秒叫一次 `aos-tick`、時鐘檔在 tick 小格的 `tick.txt`）。不接腦。
- **人**：在命令列手寫 `aos-post send`（下面「怎麼寄」）。

| 檔 | 做什麼 |
|---|---|
| `_entry` | `exec aos-daemon "$@" daemon.json`（後面的參數原樣給 daemon，例 `--max 25`） |
| `daemon.json` | `loops_mailbox: "loops_mailbox"`（信箱模式；不開 `loops_ctl`）、`ctl`、`state`、`interval_ms` 200、沒寫 `max`＝一直跑；`loops` 只有 `sam` |
| `agent-sam/_entry` | `$1`＝信箱（daemon.json 給 `$AOS_STACK/../loops_mailbox`：sam 的 `AOS_STACK` 是自己的小格）；寄一封 `{"loops_added": {"tick": …}}` |

## 怎麼起

PATH 要有 aos-exec、aos-loop、aos-daemon、aos-post（C++，`proto8/impls/<名>/bin/`，先建，見 [testing](../../../wf/workflows/testing.md)）與 aos-tick（`proto8/bin/`）。在一個空的工作區裡：

```sh
R=~/repo/simple_tools/aos/proto8
export PATH=$R/bin:$R/impls/aos-exec/bin:$R/impls/aos-loop/bin:$R/impls/aos-daemon/bin:$R/impls/aos-post/bin:$PATH
ws=$(mktemp -d); cd $ws
aos-exec $R/demo/daemon-2 &          # 一直跑；stack 在 $ws/.stack/
```

起來後 `.stack/loops_mailbox/` 有 `tmp/`、`new/`、`cur/` 三格；sam 跑一次就寄出信，下一圈 `tick` 就起了。

## 怎麼寄（人）

```sh
aos-post init $ws/inbox               # 想收回信就先開一個自己的小信箱
echo '{"loops_added": {"tock": {"exec": {"argv": ["aos-tick", {"$env": "AOS_STACK", "$path": "tock.txt"}]}, "interval_ms": 500}}}' \
  | aos-post send --reply-to $ws/inbox $ws/.stack/loops_mailbox      # 印信號
cat $ws/inbox/new/*/letter.json       # daemon 套用完回的：body {"applied": true}、in_reply_to＝上面的信號
echo '{"loops_removed": ["tick"]}' | aos-post send $ws/.stack/loops_mailbox   # 刪 tick（沒寫 --reply-to＝不回）
```

- 信的 `body` 只認 `loops_added`（寫法同 daemon.json 的 `loops`）、`loops_removed`（名字的陣列）；相對路徑從 daemon 的 cwd（`demo/daemon-2/`）算。
- 同一圈好幾封：照名字（信號是時間開頭）順序套，後面的蓋前面的。
- 壞信（body 不是物件、型別錯、名字不合格或撞名…）丟掉、不回信，原因在 `loops_state.json` 的 `letter_warning`。

## 怎麼看

```sh
cat $ws/.stack/loops_state.json       # loops：sam（done）、tick、tock（running）…；letter_warning：最後一封壞信
cat $ws/.stack/tick/tick.txt          # tick 走到幾了
cat $ws/.stack/state.json             # daemon 自己（phase、counter_runs、心跳）
```

## 怎麼停

```sh
echo '{"stopped": true}' > $ws/.stack/ctl.json    # 收掉全部子項、寫好 state 才走（loops_state 裡 tick、tock 變 stopped）
wait; rm -rf $ws
```

暫停用 `{"paused": true}`：暫停時信留在 `new/` 不收，寫 `{}` 解除那圈才套。daemon 重起（例 `kill -9` 後再 `aos-exec`）時，信加進來、還活著的子項會被接回、**留在名單上**，直到有信 `loops_removed` 它。

`run.sh` 的 daemon-2 段：`--max 25`（約 5 秒）跑一次、中途人寄一封加 `tock`（帶 `--reply-to`），印工作區、回信與 stack 樹。自動測：`impls/aos-daemon/tests/test_demo.py`。
