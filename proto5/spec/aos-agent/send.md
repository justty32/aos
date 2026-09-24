← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 5. 送出一批

## 5.1 建批

取批 id B、K＝`AOS_KERNEL_HOME`、L＝現在記憶的長度。

- **think**：`calls` 一筆 `{"name": "B-0", "done": null, "acked": false}`。
- **act**：記憶尾巴那則 assistant 的每個 `tool_calls[i]` 一筆，順序照 i：按 `function.name` 在工具裡找——
  找到 → `{"name": "B-i", "tool_call_id": id, "tool": 名, "done": null, "acked": false}`；
  找不到 → `name: null`、`done: {"content": "沒有這個工具：<名>"}`、`acked: true`。

**寫 state**：`batch = {"kind", "kernel": K, "base_len": L, "sent": false, "calls"}`。這一寫之前什麼都沒送。
（09-24 access-impl）act 批在這一寫之前另解一次 `access.json`，快照放進 `batch.access`（[access.md §1](access.md)）；之後送件、重送都用它，不重解。

## 5.2 送件（`sent:false` 時做；崩了下次重做同一段）

這一段的 K 一律是 `batch.kernel`，不重讀 `AOS_KERNEL_HOME`（中途換了 `AOS_KERNEL_HOME` 也不會往別的 kernel 查或放）。

對每一筆 `name` 非 null、`done` 是 null 的 call：

1. `work/N.inst.json` **不在** → 產生（think 照 §5.4；act 先寫 `work/N.in`，再照 §5.3 寫 inst）。都是 `.tmp` 再 rename，
   **inst 最後寫**，所以「inst 在」就表示這件的檔都齊了。act 的 `_meta` 解不過 → 這筆記成
   `done: {"content": "工具 <名> 跑不起來：<代號>: <白話>"}`、`acked: true`，不送（留到第 3 步一起寫）。
2. inst 在 → **查有沒有放過**；沒放過才放單：

   ```json
   {"jsonrpc": "2.0", "id": "N", "method": "add",
    "params": {"target": "/abs/agent-bob/work/N.inst.json", "name": "N", "once": true, "pool": "<池>", "timeout_ms": T}}
   ```

   think 的池＝`info.llm.pool`、T＝`info.llm.timeout_ms`；act 的池＝`info.tool_pool`、T＝那個工具的 `_timeout_ms`。
   `link` 回 EEXIST＝已經放過（只有自己前一次崩了才會），當成功。其他放檔錯誤＝退 1（`io`），`sent` 仍是 false，下次重做。
3. **寫 state**：`sent: true`，加上第 1 步本地結束的那幾筆。退 0。

**查有沒有放過**（照這個順序，一步不能換）：

1. `K/requests/N.json` 在 → 放過了（kernel 還沒收，或 kernel 已經 `stopped`、留到下次 boot 收）。
2. 偷看 `K/state.json`：`procs` 有 `N`，或 `replies` 有一筆 `name` 是 `N.json` → 放過了（在排隊、在跑、或回音在出貨）。
3. `K/responses/N.json` 在 → 放過了。
4. 都不在 → 沒放過。`K/state.json` 不在＝kernel 從沒 boot 過，當作第 2 步沒有；讀得到但壞掉＝退 1。

理由：kernel 先記帳（`procs`／`replies`）再刪原單、同一次寫把回音放進 `replies` 並拿掉 `procs`、先放回音檔再從 `replies` 拿掉（[kernel.md §2、§3](../kernel/syscall.md)），
一件工作只往後走；回音只有 ack 才消失，而 `done` 是 null 的從沒 ack 過；boot 保留 `procs`／`replies`。不能照搬 cpu 的「原單回音都不在＝沒放」。

## 5.3 act：工具的 inst

`_meta` 用 inst 的讀驗（`aos_inst.load_obj`，base＝agent 家）解完，**重新編成一份合法的字面 inst**——
不能把 `load_obj` 回傳的內部結構直接寫檔（形狀不同，aos-exec 會拒）。對照：

| 欄 | 寫成 |
|---|---|
| `_metainfo` | `{"_type": "posix", "_version": 1}` |
| `argv` | 解好的字串陣列，不改寫 |
| `cwd` | 絕對路徑；原本有 `mkdir` → `{"$opt": "mkdir", "$val": 絕對路徑}` |
| `envs` | 原本有 `clear` → **一定寫** `{"$opt": "clear", "$val": {…}}`（`$val` 是空物件也照寫——那就是完全空的環境）；沒 `clear` → 解好的物件，只有這時空物件才能省略 |
| `stderr`、`exit` | 沒寫就不寫；`inherit`／`merge` → `{"$opt": "inherit"}`／`{"$opt": "merge"}`；路徑 → 絕對路徑，帶 `append`／`mkdir` 時 → `{"$opt": [選項…], "$val": 絕對路徑}` |
| `stdin` | `/abs/agent-bob/work/N.in` |
| `stdout` | `{"$opt": "mkdir", "$val": "/abs/agent-bob/work/N.out"}` |

`work/N.in` 的內容是 `function.arguments` 字串原樣（UTF-8），不驗是不是 JSON。
`_meta` 的 `$env` 讀的是跑 aos-agent 那顆 cpu 的環境；工具要用自己那顆 cpu 的環境，就別寫 `$env`、也別 `clear`（不 clear 就整包繼承）。

（09-24 access-impl）**有 access 快照時**（不是 `null`、工具沒寫 `_jail: false`）上表的 `argv` 與 `envs` 改寫：`argv` 包成 `["aos-jail", …旗標…, "--", 程式, …]`、`_meta.envs` 改成 `--setenv`、外層不帶 `envs`，其餘欄照上表；
快照是 `error` 或找不到 `bwrap`＝這件照第 1 步「解不過」的路記成跑不起來、不送。牢裡不繼承 cpu 的環境（上一段的「整包繼承」只對不關牢的工具成立）。細節與例子在 [access.md §2](access.md)。

## 5.4 think：問模型的 inst

```json
{"_metainfo": {"_type": "posix", "_version": 1},
 "argv": ["aos-llm", "call", "/abs/agent-bob"], "cwd": "/abs/agent-bob",
 "stdout": {"$opt": "mkdir", "$val": "/abs/agent-bob/work/N.out"},
 "stderr": {"$opt": ["append", "mkdir"], "$val": "/abs/agent-bob/log/llm.err"}}
```

`argv[0]` 靠 llm 池那顆 cpu 的 PATH 找；模型表與金鑰也在那顆 cpu 的環境（[aos-llm.md §1](../aos-llm/usage.md)）。（09-24 fix-r4 改：`aos-llm-call` 改成 `aos-llm call`）
