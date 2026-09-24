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

- 要關，但快照是 `error`（代號取 `error` 冒號前那段）、aos-agent 自己的 PATH 找不到 `bwrap`（`NoBwrap`）、或 `_meta` 讀了敏感環境變數（`EnvUnsafe`，下面）→ 這件記 `done`、`acked: true`，不送、不寫 inst。
- **這種 `done.content` 是寫給模型看的**，不放細節（路徑、欄位、變數名），免得模型以為要自己修；細節留給人在 `check`／`status` 看：

  ```
  工具 <名> 沒有執行：<原因>，被 aos 擋下（<代號>）。這不是你能修的，也不要改用別的工具繞過；
  請告訴使用者：「工具 <名> 被 aos 權限牆擋下（<代號>），請跑 aos-agent check --target <家> 看細節」。
  ```

  `<原因>`：`EnvUnsafe`＝`這支工具的設定有安全問題（會把金鑰類環境變數帶進牢裡）`；`NoBwrap`＝`這台機器沒有裝關牢要用的 bwrap`；其他（`AccessInvalid`、`AccessUnsafe`、`JsonSyntax`…）＝`這個 agent 的權限設定（access.json）有問題`。
  （`_meta` 本身解不過照舊是 `工具 <名> 跑不起來：<代號>: <白話>`，跟權限牆無關。）
- 要關、都好 → `_meta` 照 §5.3 解完，外層 inst 改成：

```json
{"argv": ["/…/proto5/cli/aos-jail", "--mount", "ws=/home/u/amy/workspace", "--mount-ro", "ref=/home/u/docs",
          "--chdir", "ws", "--net", "off", "--setenv", "FOO=bar",
          "--", "/home/u/amy/tools/base/bash", "…_meta.argv 其餘參數…"],
 "cwd": "/home/u/amy", "stdin": "…/work/N.in", "stdout": {"$opt": "mkdir", "$val": "…/work/N.out"}}
```

- `argv[0]` 是**跟 aos-agent 同一份 proto5 的 `cli/aos-jail` 絕對路徑**，不靠 PATH（PATH 可能指到可寫位置的替身；那份 `cli/`、`lib/` 也在信任資料裡）。
- mounts 照快照順序：可寫 `--mount`、唯讀 `--mount-ro`；`cwd` 有才 `--chdir`；`--net on|off` 一定寫。
- `_meta.argv[0]` 含 `/` 時先照 `_meta` 解出的 cwd 轉成絕對路徑（aos-jail 會把它的資料夾唯讀掛到 `/opt/tool`）；不含 `/` 就照牢裡的 PATH 找（牢裡只有 `/usr`）。
- `_meta.envs` 的每一對改成 `--setenv K=V`，**外層 inst 不帶 `envs`**。
- **敏感環境變數在寫 inst 之前就擋**（值一寫進 inst 就落盤了）。敏感名字＝`AOS_*`、含 `KEY`／`TOKEN`／`SECRET`／`PASSWORD`／`CREDENTIAL`（不分大小寫）、`SSH_AUTH_SOCK`：
  - `_meta` **任何一格**（envs、argv、`$fmt` 變數…）用 `$env` 讀了敏感名字＝這件照上面記成沒執行（`EnvUnsafe`）、不送、不寫 inst——不論值被換成什麼名字或放進 argv。`check` 用同一個判定（`secret_env_reads`）把這種工具標 bad，講哪支、哪一格、讀了哪個名字。
  - `envs` 的**輸出名字**是敏感名字（例如字面寫 `"GITHUB_TOKEN": "…"`）＝那一對直接丟掉，不寫進 inst。
  - aos-jail 端照樣再過濾一次 `--setenv`（第二層）。不關牢（`_jail: false`、沒 access 檔）的工具不受這條管。
- 外層 `cwd`＝原本解出的（agent 家或 `_meta.cwd`）；`stdin`／`stdout`／`stderr`／`exit` 照 §5.3 不變——這幾個是 aos-exec 在牢外開好、fd 帶進牢裡的。
- **牢裡的起點只看 access 的 `cwd`**；`_meta.cwd` 只影響牢外（串流的相對路徑、`argv[0]` 的相對路徑）。
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

- **`ls`**：一行一個 mount：名字、`ro`／`rw`、存在否、解好的路徑；再印 `cwd: /work/<名>`（沒設＝`/work`）、`net`、`bwrap: ok|沒有…`、`檔：<路徑>`。檔壞了多一行 `壞了：<代號>: <白話>`、退 1（路徑不在時表照印，那一列「不在」）。`info.json` 明寫的 access 檔不在＝`壞了：AccessInvalid: …檔不在`、退 1（不說「不關牢」）；這時除了 `set`（會在那個位置建檔）其他寫入指令都拒絕。沒 access 檔印「沒有 access.json：工具不關牢…」並教一行 `aos-agent access set ws workspace --cwd`、退 0。`--json` 印 `{"file", "exists", "mounts": {名: {"path", "ro", "exists"}}, "cwd", "net", "bwrap", "error"}`。
- **`set NAME PATH`**：PATH 照**殼的目前資料夾**轉成絕對路徑寫進檔（`~` 會展開）；要是存在的資料夾，否則 `NotFound` 退 1。檔不在就新建（帶 `_metainfo`、`net: false`）。
  - 已有的名字沒給 `--ro／--rw`＝保留原模式；原本可寫、新路徑又碰到信任資料＝`AccessUnsafe` 退 1、不寫。
  - 新名字預設可寫；碰到信任資料就自動唯讀並印一句「…所以設成唯讀（ro）」。
  - 明給 `--rw` 又碰到信任資料＝`AccessUnsafe` 退 1、不寫。
  - 原值是指示詞＝換成字面路徑並印一句；`--cwd`＝同時把起點設成它；寫法：可寫＝路徑字串、唯讀＝`{"$opt": "ro", "$val": 路徑}`。
- **`rm NAME`**：拿掉；是目前的 `cwd` 就拒絕（`AccessInvalid` 退 1：先 `access cwd 別的`）。沒這個名字＝`NotFound` 退 1。
- **`cwd NAME`**：起點改成它（要在 mounts 裡）。**`net on|off`**：改 `net`。
- 寫入指令共同：讀、驗、寫、印整段持著跟 `tools` 指令共用的鎖（`aos_agent_tools_edit.info_lock`，鎖一個不會被 rename 的專用鎖檔）；`.tmp`（檔名帶 pid＋時間，不互撞）＋rename；
  重疊判斷用**跟送件同一套信任集合**（含 access 檔自己 `$ref` 到的檔）；**落盤前把改好的候選內容整份再驗一次**：格式錯（例如 `rm` 之後 `cwd` 解出來的名字不在了）或多出新的「可寫又重疊」＝不寫、退 1（原本就重疊的那幾格不擋，好讓人一步步修）；`rm` 比的是**解好的** `cwd`；JSON 縮排 2、不跳脫中文；保留檔裡原有的其他格。
  access 檔 JSON 壞或格式錯＝拒絕、退 1、印哪裡壞、不蓋掉手寫的東西（只有「路徑不在」「重疊」的檔還能用指令修）。
  寫完印改完的表（同 `ls`），**最後一行「下一批工具生效，不用重 start」**。
- 用法錯（參數個數、`net` 值、名字不合 `[a-z0-9_-]+`、`--ro` 與 `--rw` 同給、選項給錯子命令）＝退 2，看家之前就驗。

## 4. check、status、錯誤代號

[`check`](cli-check.md) 多查 access 檔、bwrap、aos-jail、每支關牢工具（`EnvUnsafe`＝bad，其餘 warn）；[`status`](cli-status.md) 在 access 檔壞了時多一行 `access bad：…`（`--json` 的 `access_error`）。
代號：`AccessInvalid`、`AccessUnsafe`、`NoBwrap`、`EnvUnsafe`（[agent errors.md](../agent/errors.md)）；指令另有 `NotFound`、`Usage`。
