← [aos-agent](README.md)｜[spec 總導航](../README.md)｜檔案格式：[agent access.md](../agent/access.md)｜牢本身：[aos-jail](../aos-exec/aos-jail.md)

# 權限牆：送件包牢、快照、`access` 指令（09-24 access-impl）

## 1. 快照（建批時解一次）

act 批在 §5.1 建批、寫 state 之前，照 [agent access.md](../agent/access.md) 解 access 檔一次，存進 `batch.access`（[state.md §4.3](../agent/state.md)）：

| 情況 | `batch.access` |
|---|---|
| 沒 access 檔 | `null` |
| 解不過或重疊 | `{"error": "代號: 白話"}` |
| 好 | `{"mounts": {名: {"path": 絕對路徑, "ro": bool}}, "cwd": 名或 null, "net": bool}` |

- 同批每一件、崩了重送（§5.2 重跑）都用這份，**不重解**。所以一批裡不會混到新舊兩份表。
- think 批沒有這個鍵。舊版寫下的 state 沒有這個鍵＝當 `null`（不關牢）。

## 2. 送件包牢（§5.3 的補充）

對每一件要送的工具 call（inst 還不在時），先看這支要不要關牢：快照不是 `null`、而且工具沒寫 `_jail: false`。

- 要關，但快照是 `error` → 這件記 `done: {"content": "工具 <名> 跑不起來：<代號>: <白話>"}`、`acked: true`，不送（跟 `_meta` 解不過同一條路）。
- 要關，但 aos-agent 自己的 PATH 找不到 `bwrap` → 同上，內容 `工具 <名> 跑不起來：NoBwrap: 找不到 bwrap（bubblewrap）…安裝指令`。
- 要關、都好 → `_meta` 照 §5.3 解完，外層 inst 改成：

```json
{"argv": ["aos-jail", "--mount", "ws=/home/u/amy/workspace", "--mount-ro", "ref=/home/u/docs",
          "--chdir", "ws", "--net", "off", "--setenv", "FOO=bar",
          "--", "/home/u/amy/tools/base/bash", "…_meta.argv 其餘參數…"],
 "cwd": "/home/u/amy", "stdin": "…/work/N.in", "stdout": {"$opt": "mkdir", "$val": "…/work/N.out"}}
```

- mounts 照快照順序：可寫 `--mount`、唯讀 `--mount-ro`；`cwd` 有才 `--chdir`；`--net on|off` 一定寫。
- `_meta.argv[0]` 含 `/` 時先照 `_meta` 解出的 cwd 轉成絕對路徑（aos-jail 會把它的資料夾唯讀掛到 `/opt/tool`）；不含 `/` 就照牢裡的 PATH 找（牢裡只有 `/usr`）。
- `_meta.envs` 的每一對改成 `--setenv K=V`，**外層 inst 不帶 `envs`**（aos-jail 會 `--clearenv`，只留固定幾個與這些；名字像金鑰或 `AOS_*` 的會被丟掉）。
- 外層 `cwd`＝原本解出的（agent 家或 `_meta.cwd`）；`stdin`／`stdout`／`stderr`／`exit` 照 §5.3 不變——這幾個是 aos-exec 在牢外開好、fd 帶進牢裡的。
- **牢裡的起點只看 access 的 `cwd`**；`_meta.cwd` 只影響牢外（串流的相對路徑、`argv[0]` 的相對路徑）。
- `aos-jail` 靠工具池那顆 cpu 的 PATH 找（跟其他 aos 指令一樣在 `proto5/cli/`）。
- `_jail: false` 的工具照 §5.3 原樣（不包、`envs` 照舊）；`aos-agent check` 對它 warn。

## 3. `access` 指令

```
aos-agent access ls  [--target DIR] [--json]
aos-agent access set NAME PATH [--ro | --rw] [--cwd] [--target DIR]
aos-agent access rm  NAME [--target DIR]
aos-agent access cwd NAME [--target DIR]
aos-agent access net on|off [--target DIR]
```

改的是 `info.json` 的 `access` 欄指的檔（沒寫＝`<家>/access.json`）。

- **`ls`**：一行一個 mount：名字、`ro`／`rw`、存在否、解好的路徑；再印 `cwd: /work/<名>`（沒設＝`/work`）、`net`、`bwrap: ok|沒有…`、`檔：<路徑>`。檔壞了多一行 `壞了：<代號>: <白話>`、退 1（路徑不在時表照印，那一列「不在」）。沒 access 檔印「沒有 access.json：工具不關牢…」並教一行 `aos-agent access set ws workspace --cwd`、退 0。`--json` 印 `{"file", "exists", "mounts": {名: {"path", "ro", "exists"}}, "cwd", "net", "bwrap", "error"}`。
- **`set NAME PATH`**：PATH 照**殼的目前資料夾**轉成絕對路徑寫進檔（`~` 會展開）；要是存在的資料夾，否則 `NotFound` 退 1。檔不在就新建（帶 `_metainfo`、`net: false`）。
  - 已有的名字沒給 `--ro／--rw`＝保留原模式；原本可寫、新路徑又碰到信任資料＝`AccessUnsafe` 退 1、不寫。
  - 新名字預設可寫；碰到信任資料就自動唯讀並印一句「…所以設成唯讀（ro）」。
  - 明給 `--rw` 又碰到信任資料＝`AccessUnsafe` 退 1、不寫。
  - 原值是指示詞＝換成字面路徑，印一句「原本是指示詞 …，換成字面路徑」。
  - `--cwd`：同時把起點設成它。
  - 寫法：可寫＝路徑字串；唯讀＝`{"$opt": "ro", "$val": 路徑}`。
- **`rm NAME`**：拿掉；是目前的 `cwd` 就拒絕（`AccessInvalid` 退 1：先 `access cwd 別的`）。沒這個名字＝`NotFound` 退 1。
- **`cwd NAME`**：起點改成它（要在 mounts 裡）。**`net on|off`**：改 `net`。
- 寫入指令共同：持 `info.json` 的 flock（跟 `tools add` 同一把）；`.tmp`＋rename；JSON 縮排 2、不跳脫中文；保留檔裡原有的其他格。
  **access 檔解不開**（JSON 壞、格式錯）＝拒絕、退 1，印哪裡壞，不蓋掉手寫的東西；只有「路徑不在」或「重疊」的檔仍然可以改（好讓人用指令修）。
  寫完印改完的表（同 `ls`），**最後一行「下一批工具生效，不用重 start」**。
- 用法錯（參數個數、`net` 不是 on/off、名字不合 `[a-z0-9_-]+`、`--ro` 與 `--rw` 同給、選項給錯子命令）＝退 2，在看家之前就驗。

## 4. `check` 與 `status`

- `check`（[cli-check.md](cli-check.md)）多查 `access`、`access/<名>`、`access/bwrap`、`access/aos-jail` 與每支工具在牢裡的兩條 warn。
- `status`（[cli-status.md](cli-status.md)）：access 檔壞了多一行 `access bad：<代號>: <白話>`，`--json` 的 `access_error`。

## 5. 錯誤代號

`AccessInvalid`、`AccessUnsafe`、`NoBwrap`（[agent errors.md](../agent/errors.md)）；指令本身另有 `NotFound`、`Usage`。
