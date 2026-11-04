← [教程索引](README.md)｜接在 [03 第一個 agent](03-first-agent.md) 之後讀

# 06 附錄：不用 init，手寫一個 agent 家（和 kernel 家）

**目標**：看清楚 agent 家其實就是一個資料夾加四份檔；`init` 只是替你寫好它們。kernel 家也一樣，只是一份池表（第 4 節）。

**前提**：開著機（[01](01-daemon-kernel.md) 的 `aos up`）。新終端先 `. $HOME/aos-try/env.sh`。

## 1. 寫四份檔

```sh
mkdir -p $W/amy/prompts $W/amy/tools $W/amy/workspace
cat > $W/amy/info.json <<'EOF'
{"_metainfo": {"_type": "llm_agent", "_version": 1},
 "llm": {"model": "default", "timeout_ms": 190000},
 "tools": ["tools/base.json"],
 "tick": {"interval_ms": 500}}
EOF
cat > $W/amy/prompts/system.json <<'EOF'
{"content": "你是繁體中文助理。要知道現在時間就呼叫 date 工具，拿到結果後用一句話回答。"}
EOF
cat > $W/amy/tools/base.json <<'EOF'
[{"type": "function",
  "function": {"name": "date", "description": "取得現在的本機日期與時間",
               "parameters": {"type": "object", "properties": {}}},
  "_meta": {"argv": ["date", "+%Y-%m-%d %H:%M:%S"]}}]
EOF
cat > $W/amy/access.json <<'EOF'
{"_metainfo": {"_type": "agent_access", "_version": 1},
 "mounts": {"ws": "workspace"}, "cwd": "ws", "net": false}
EOF
aos-agent check --target $W/amy
```

最後一行 `設定檢查通過；未測模型連線（--probe 會測）` 就對了（中間各行跟 [03 第 2 步](03-first-agent.md#2-檢查)一樣）。
第四份 `access.json` 是工具的牢：工具只看得到 `workspace/`、不能上網（[04b](04b-access-and-tool-admin.md)）。**沒有它，工具一支都不會跑**（`check` 報 `bad access`，agent 會回你「沒有 access.json 不能跑」）。
`info.json` 沒寫的都有預設：人格 `prompts/system.json`、記憶 `prompts/history.json`、問模型派 `llm` 池、工具與走格派 `default` 池。

## 2. 登記、投話、看回話

手寫的家沒有 `input/` 資料夾，輸入投到 `input.json`。要**原子地**投：先寫暫存檔再 `mv`，免得它讀到寫一半的檔。

```sh
aos-agent start --target $W/amy
echo '"現在幾點？請用工具查。"' > $W/amy/input.tmp && mv $W/amy/input.tmp $W/amy/input.json
sleep 20
aos-agent listen --target $W/amy --last
```

`start` 印 `started agent-amy`；`listen` 印一句報時。收過的輸入搬進 `amy/done/`（`init` 的家是 `input/done/`）。
`aos-agent say` 在這種家也能用，一樣投到 `input.json`。

## 3. 收工

```sh
aos-agent stop --target $W/amy
```

## 4. 手寫一個 kernel 家：一份池表

kernel 家的 `info.json`（第 2 版）只列池：每池要幾顆、交給哪個 daemon、在 daemon 那邊叫什麼、帶什麼環境。最小的樣子：

```sh
mkdir -p $W/K4/requests $W/K4/responses $W/K4/pools
cat > $W/K4/info.json <<EOF
{"_metainfo": {"_type": "kernel", "_version": 2},
 "daemon": "$AOS_DAEMON_HOME",
 "pools": {"default": {"count": 1, "dpool": "k4-default"}}}
EOF
aos-kernel check --target $W/K4
aos up --target $W/K4
```

`check` 全 `ok` 再 `aos up`，印 `up K=/home/you/aos-try/K4  daemon /home/you/aos-try/D（本來就在）  1 個池、1 顆 cpu` 和 `health ok`
（daemon 是 01 開的那個，所以「本來就在」）。要注意的四件事：

- **`requests/`、`responses/`、`pools/` 要自己建**（`init` 會建）。`check` 的 `dirs` 會說缺哪個（報 `bad`）。
- **`daemon` 要寫**：手寫的家不會自動填 `AOS_DAEMON_HOME`，沒寫 `aos up` 報 `NoDaemon`。這個 daemon 同時替 kernel 走格。
- **`dpool` 是池在 daemon 那邊的名字**，省略＝池名。這裡跟 01 的 `K` 共用同一個 daemon，`K` 已經有 `default` 這個池，所以要換個名字。
  撞名的話 `check` 就會報 `bad pools/default: 池 default 在 daemon … 那邊叫 default，已經是 …/K 的（aos up 會報 NameTaken）…`。
  沒看 `check` 直接 `aos up` 的話，第二行印 `health 池 default：NameTaken（池 default 已是 …/K 的）`、退 1；`aos down --target $W/K4` 收掉，補 `dpool` 再 `aos up`。
- **池名 `kernel` 不能用**（保留名）。舊的教程會寫一個 `kernel` 池給 kernel 自己用，現在不用了：kernel 走格改由 daemon 負責。

開機之後家長這樣（kernel 自己補齊，你不用寫）：

```text
K4/info.json                   你寫的池表；aos-kernel cpu add／rm 也是改它
K4/ledger.sqlite               帳本（sqlite；用 aos-kernel ls、aos-kernel proc 看，別手改）
K4/kernel.log                  每格做了什麼
K4/pools/default/envs.json     這池的環境（照 info 的 envs 寫）
K4/pools/default/inst.json     這池每顆 cpu 的模板：跑 aos-cpu、環境取 ../../envs.json
K4/pools/default/cpus/0/       第 0 號 cpu 的家：info.json、inst.json、requests/、responses/、cpu.log
```

其他欄位（`tick_ms`、`interval_ms`、`skip`、每池各自的 `daemon`…）都有預設，見 [池表 info.json](../spec/kernel/info.md)、[家的長相](../spec/kernel/home.md)。
收工：`aos down --target $W/K4`。它印 `stopped`，再印一行 `daemon … 沒停：還有 別的 kernel：…/K；池：default、llm（要停就 aos-daemon halt --target …）`——daemon 還要給 01 的 `K` 用，所以留著，這是對的。

## 底下在幹嘛

`info.json` 各格、`input` 可以指到哪、記憶的格式，見 [agent 家的「使用者只需要懂的」](../spec/agent/essentials.md) 與 [info.json](../spec/agent/info.md)、[state.json 的 input](../spec/agent/state.md)。
