← [教程索引](README.md)｜上一篇 [04 給 agent 加工具、暫停它、救回它](04-tools-and-pause.md)｜下一篇 [05 管一大堆 agent](05-many-agents.md)

# 04b 權限牆與工具管理

**目標**：搞懂 `access.json`（工具被關進的牢）怎麼看、怎麼改，也學會用文字編輯器直接改它；再學會 `tools ls／add／rm／alias／unalias` 這組管理指令。

**前提**：做完 [04](04-tools-and-pause.md)，bob 已經裝了 `base` 工具包（`aos-agent tools add base --target $W/bob`），家裡因此有一份 `access.json`。這篇繼續用同一個 bob。

## 1. 限制 agent 能碰什麼

`access.json` 放在 `<家>/access.json`，決定這個家的工具被關進的沙盒（`bwrap`）看得到哪些資料夾、能不能連網、起點在哪。
**這個檔不存在＝不關牢**——工具照舊在 agent 家跑，碰得到跑它的人碰得到的所有檔（跟以前一樣）。**有這個檔＝這個家的工具一律關牢**（除了那支自己說 `_jail: false` 的，下面會講）。

`tools add base` 第一次裝的時候，如果家裡還沒有這個檔，會順手建一份、只准工具寫 workspace，裝的時候你會看到多印這幾行：

```text
寫了 /home/you/aos-try/bob/access.json：工具會關在牢裡，只看得到 /work/ws（＝workspace，可寫）、起點 /work/ws、不能上網。
要改：aos-agent access set NAME PATH [--ro]、access net on、access ls 看全表
```

這份預設的 `access.json` 長這樣：

```json
{"_metainfo": {"_type": "agent_access", "_version": 1},
 "mounts": {"ws": "workspace"},
 "cwd": "ws",
 "net": false}
```

用 `access ls` 看目前的表：

```sh
aos-agent access ls --target $W/bob
```

```text
名字  權限  存在  路徑
ws    rw    在    /home/you/aos-try/bob/workspace
cwd: /work/ws
net: off
bwrap: ok
檔：/home/you/aos-try/bob/access.json
```

`access set NAME PATH` 加一個 mount（`PATH` 照你殼目前的資料夾轉成絕對路徑寫進檔）：

```sh
aos-agent access set ref ~/docs --target $W/bob
```

```text
名字  權限  存在  路徑
ws    rw    在    /home/you/aos-try/bob/workspace
ref   rw    在    /home/you/docs
cwd: /work/ws
net: off
bwrap: ok
檔：/home/you/aos-try/bob/access.json
下一批工具生效，不用重 start
```

想讓工具連網（連得到 localhost、區網服務）：`access net on`。換工具的起點（牢裡的目前資料夾）：`access cwd ref`。拿掉一個 mount：`access rm NAME`——但**正被當 `cwd` 用的那個不能 rm**，要先 `access cwd 換別的`：

```sh
aos-agent access rm ws --target $W/bob
```

```text
aos-agent: AccessInvalid: ws 是目前的起點（cwd），先 aos-agent access cwd 別的名字 再 rm
```

### `self`（整個家）只能唯讀

想讓工具看得到 agent 自己的家（例如讀人格檔），掛的時候會自動被壓成唯讀，因為家裡有 `info.json`、記憶檔這些「工具永遠寫不到」的東西：

```sh
aos-agent access set self . --target $W/bob
```

```text
self 可寫、但包含 /home/you/aos-try/bob/info.json（家裡的 info.json），所以設成唯讀（ro）
名字  權限  存在  路徑
ws    rw    在    /home/you/aos-try/bob/workspace
ref   rw    在    /home/you/docs
self  ro    在    /home/you/aos-try/bob
```

硬要它可寫（`--rw`）會直接拒絕，什麼都不寫：

```text
aos-agent: AccessUnsafe: selfbad 可寫、但包含 /home/you/aos-try/bob/info.json（家裡的 info.json）；改 --ro 或換資料夾（沒寫）
```

（哪些檔算「工具永遠寫不到」的信任資料，細節在規範 [agent access.md](../spec/agent/access.md#信任資料工具永遠寫不到)。）

### 下一批才生效

跟工具本身一樣，改完 `access.json`（不管是用指令還是手改）**下一批工具呼叫才吃得到新表，不用重 `start`**；正在跑的那支不會被臨時收回權限。要馬上擋：先 `aos-agent pause`。

### 沒 bwrap 會怎樣

權限牆需要系統裝了 `bubblewrap`。沒裝的話 `access ls`、`check` 都會提醒；工具會直接跑不起來（不是悄悄變成「不關牢」，是整批拒絕，逼你先裝好）：

```text
bwrap: 沒有（工具會跑不起來；Arch/Manjaro: sudo pacman -S bubblewrap）
```

### `_jail: false`：讓某一支工具跳過牢

工具檔裡某個元素頂層加一格 `"_jail": false`，那一支就不關牢（照舊在 agent 家跑，碰得到你碰得到的所有檔）。`tools ls` 那一支的「關牢」欄會印 `no`，`check` 也會多一行警告：

```text
warn agent/tool/bash: _jail: false：這支不關牢，碰得到你碰得到的所有檔
```

平常不建議這樣用（等於幫那一支工具開後門），只在你確定知道自己在幹嘛的時候用。

## 2. 用文字編輯器改 access.json

指令背後改的就是這份 JSON，直接用編輯器開也完全可以。完整例子：

```json
{"_metainfo": {"_type": "agent_access", "_version": 1},
 "mounts": {"ws": "workspace", "ref": {"$opt": "ro", "$val": "~/docs"}},
 "cwd": "ws",
 "net": false}
```

每個鍵一句：

| 鍵 | 意思 |
|---|---|
| `_metainfo` | 可省；有寫就要 `_type: agent_access`、`_version: 1`，抓貼錯版本 |
| `mounts` | 物件，key 是牢裡看到的名字（會掛在 `/work/<名>`），值是路徑；可省＝空（工具在牢裡什麼資料夾都碰不到） |
| `cwd` | `mounts` 裡的一個名字，工具在牢裡的起點；可省＝`/work` |
| `net` | `true`／`false`；`true`＝共用主機網路（連得到 localhost、區網），可省＝`false` |

`mounts` 底下每個值可以是純路徑字串（可寫），也可以是 `{"$opt": "ro", "$val": 路徑}`（唯讀）。路徑可以寫 `~` 開頭或相對 agent 家，存檔時指令會自動展開成絕對路徑；手改也可以直接這樣寫，下一批生效時會照樣展開。

**改壞了會怎樣**：`access.json` 只認 `_metainfo`／`mounts`／`cwd`／`net` 這四個頂層鍵，打錯字（例如把 `net` 手滑打成 `network`）**不會被默默忽略**，而是直接判定整份壞掉。用 `aos-agent check` 就會指出哪裡壞：

```text
bad  access: AccessInvalid: access 檔 /home/you/aos-try/bob/access.json 的 network：不認得的鍵（只認 mounts／cwd／net／_metainfo）
```

`access ls` 也一樣會老實印出來，不會假裝沒事：

```text
壞了：AccessInvalid: access 檔 /home/you/aos-try/bob/access.json 的 network：不認得的鍵（只認 mounts／cwd／net／_metainfo）
bwrap: ok
檔：/home/you/aos-try/bob/access.json
```

**檔壞的時候，`access` 系列指令的寫入動作（`set`／`rm`／`cwd`／`net`）一律拒絕**，逼你先手動修好（或刪掉重來），不會自動蓋掉你手寫的東西：

```text
aos-agent: AccessInvalid: access 檔 /home/you/aos-try/bob/access.json 的 network：不認得的鍵（只認 mounts／cwd／net／_metainfo）；access 檔壞了，先手修好（或刪掉重來）再用 access 指令
```

改回對的內容（拿掉多打的那格），`check`、`access ls` 就都恢復乾淨。

## 3. 管理工具

`tools add base` 裝的是一整包；`tools ls`／`rm`／`alias`／`unalias` 用來看現況、拿掉某支、幫某支改名——**都只改 `info.json` 的 `tools` 欄，不動任何工具檔**。

### `tools ls`

```text
名字   原名  來源檔           關牢  池
read   -     tools/base.json  jail  default
write  -     tools/base.json  jail  default
edit   -     tools/base.json  jail  default
bash   -     tools/base.json  jail  default
grep   -     tools/base.json  jail  default
find   -     tools/base.json  jail  default
ls     -     tools/base.json  jail  default
date   -     tools/date.json  jail  default
8 個工具；關牢照 /home/you/aos-try/bob/access.json
```

「原名」欄沒改名印 `-`；「關牢」欄 `jail`＝會關、`no`＝那支 `_jail: false`、`-`＝家裡沒有 access 檔。

### `tools add` 引用一個現成的檔或資料夾（不裝包）

`tools add NAME` 裝的是內建包（複製進 `tools/`）；給一個**含 `/` 的資料夾或 `.json` 檔**會**原地引用**，不複製：

```sh
aos-agent tools add ../util-tools --only ping --as hello --target $W/bob
```

```text
referenced /home/you/aos-try/util-tools（原地引用、不複製；1 個工具：hello）
info.json 的 tools 補了 {"$opt": {"as": {"ping": "hello"}, "only": ["ping"]}, "$val": "/home/you/aos-try/util-tools"}
下一批工具生效，不用重 start
```

`--only a,b` 先從那個檔（或資料夾裡全部 `*.json`）挑幾支、`--as OLD=NEW` 再改名（只挑到一支時可以簡寫 `--as 新名`）。原名不在裡面、改名後撞名都會直接拒絕（`ToolInvalid`）。

### `tools rm NAME`：拿掉，不刪檔

```sh
aos-agent tools rm date --target $W/bob
```

```text
拿掉 date：info.tools 第 0 條改成只挑（原名）read、write、edit、bash、grep、find、ls
注意：這條是整個資料夾，之後放進去的新工具要加進 only（或 tools add）才會出現
檔還在 /home/you/aos-try/bob/tools/date.json（第 0 個，原名 date）；沒刪任何檔
下一批工具生效，不用重 start
```

工具檔（`tools/date.json` 那個檔）還在原地，只是模型看不到它了；真的要刪就自己刪那個檔。

### `tools alias`／`unalias`：換模型看到的名字

```sh
aos-agent tools alias bash exec --target $W/bob
```

```text
bash 改叫 exec（原名 bash；info.tools 第 0 條）
下一批工具生效，不用重 start
```

```sh
aos-agent tools unalias exec --target $W/bob
```

```text
exec 改回原名 bash（info.tools 第 0 條）
第 0 條沒有選項了，收回成 "tools"
下一批工具生效，不用重 start
```

`NAME` 可以是現在的名字，也可以是原名；改回跟原名一樣就等於 `unalias`。

### 在 `info.json` 手寫 `$opt`

上面這些指令背後改的就是 `info.tools` 陣列裡的元素，直接手改也可以：

```json
"tools": ["tools/base.json",
          {"$opt": {"as": {"ping": "hello"}, "only": ["ping"]}, "$val": "../util-tools"}]
```

`$val` 是那個工具檔或資料夾的路徑；`$opt` 是字面物件，只認 `as`（`{原名: 新名}`）與 `only`（原名陣列），兩個都可省但至少給一個，順序是**先 `only` 篩、再 `as` 改名**。每種寫法錯了會回什麼代號，在規範 [agent tools-opt.md](../spec/agent/tools-opt.md) 有完整表。

## 底下在幹嘛

- act 批在建批那一刻把 `access.json` 解一次存成快照，同一批每件、崩了重送都用它——所以「下一批生效」不是比喻，是真的照批次算。
- 送件時工具被包成 `aos-jail --mount … --chdir … --net … -- 原本的程式`；`aos-jail` 本身不讀 `access.json`、不解指示詞，只照參數組沙盒（[aos-agent access.md](../spec/aos-agent/access.md)、[aos-jail.md](../spec/aos-exec/aos-jail.md)）。
- 「信任資料」（access 檔本身、`info.json`、人格檔、記憶檔、工具檔與工具程式所在資料夾、`state.json` 等）永遠查不到可寫，就算你手動 `access set` 也會被自動改成唯讀或直接拒絕。

## 常見錯誤

| 看到 | 原因與怎麼辦 |
|---|---|
| `access set NAME PATH` 說 `AccessUnsafe` | PATH 跟信任資料重疊，且你明給了 `--rw`；改 `--ro` 或換一個資料夾 |
| `access rm NAME` 說「是目前的起點」 | 那個名字正被 `cwd` 用；先 `access cwd 換別的` 再 rm |
| `check`／`access ls` 印 `bad`／「壞了：AccessInvalid」 | `access.json` 有格式錯（多餘的鍵、型別不對）；照訊息裡的位置手動修好 |
| `access` 系列指令一直說「access 檔壞了，先手修好」 | 同上，寫入指令全被擋住，直到你把檔修對 |
| `access ls` 說 `bwrap: 沒有` | 系統沒裝 `bubblewrap`；照提示裝（Arch/Manjaro：`sudo pacman -S bubblewrap`） |
| `tools rm`／`alias` 說 `FieldTypeMismatch` | `info.tools` 用了 `$ref` 這類指示詞，這幾個指令只改「字面陣列」；請自己手改 `info.json` |

## 收工

跟 [04](04-tools-and-pause.md) 共用同一個 bob，收工方式一樣：`aos-agent stop --target $W/bob`；今天到此為止就照 [01 第 7 步](01-daemon-kernel.md#7-關機順序kernel--daemon)關機；接著做 [05](05-many-agents.md) 就先留著。
