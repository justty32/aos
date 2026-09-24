← [教程索引](README.md)｜上一篇 [04 給 agent 加工具、暫停它、救回它](04-tools-and-pause.md)｜下一篇 [05 管一大堆 agent](05-many-agents.md)

# 04b 權限牆與工具管理

**目標**：搞懂 `access.json`（工具被關進的牢）怎麼看、怎麼改，包含用文字編輯器直接改；再學會 `tools ls／add／rm／alias／unalias` 這組管理指令。

**前提**：做完 [03](03-first-agent.md)，`aos-agent init` 就已經幫 bob 生了一份 `access.json`；做完 [04](04-tools-and-pause.md)，bob 又裝了 `base` 工具包。這篇繼續用同一個 bob。

## 1. 限制 agent 能碰什麼

`access.json` 放在 `<家>/access.json`，決定這個家的工具被關進的沙盒（`bwrap`）看得到哪些資料夾、能不能連網、起點在哪。**有這個檔＝這個家的工具一律關牢**（除了自己說 `_jail: false` 的那支，下面會講）；**沒有這個檔時，要關牢的工具一律不送**（`NoAccess`），不再像以前那樣退回「不關牢」。

`aos-agent init` 生家時就順手建好一份，只准工具寫 `workspace`：

```text
initialized /home/you/aos-try/bob
access.json：工具關在牢裡，只看得到 /work/ws（＝workspace，可寫）、不能上網；改：aos-agent access ls／set
llm.model 是代號 "default"：llm.json（…）要有 default 這個代號
```

`tools add base` 裝的時候看到家裡已經有這份表，就不會重印一次；只有給了 `--root X` 而表的起點沒對到 `X` 時，才多印一行教你 `access set` 改表（見 [tools add](../spec/aos-agent/tools.md)）。

用 `access ls` 看目前的表（JSON 長什麼樣見第 2 節）：

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

`access set NAME PATH` 加一個 mount（`PATH` 照你**殼目前的資料夾**轉成絕對路徑寫進檔，不是照 `--target`——要指 bob 家裡的資料夾，就寫絕對路徑或 `~` 開頭，別靠殼剛好在哪裡）：

```sh
aos-agent access set ref ~/docs --target $W/bob
```

表裡多一行 `ref   rw    在    /home/you/docs`，結尾多印一行 `下一批工具生效，不用重 start`；`../ref/x.txt` 或 `/work/ref/x.txt` 兩種寫法工具都讀得到——**碰得到的範圍是整個 `/work`，不只是起點那一個 mount**。想連網：`access net on`。換起點：`access cwd ref`。拿掉一個 mount：`access rm NAME`——但**正被當 `cwd` 用的那個不能 rm**。**換完起點或改完表，記得 `aos-agent say` 跟模型說一聲**，不然它會以為自己弄壞了。

### `self`（整個家）只能唯讀

想讓工具看得到 agent 自己的家，掛的時候會自動被壓成唯讀，因為家裡有「工具永遠寫不到」的東西：

```sh
aos-agent access set self "$W/bob" --target $W/bob
```

```text
self 可寫、但包含 /home/you/aos-try/bob/info.json（家裡的 info.json），所以設成唯讀（ro）
```

硬要 `--rw` 會直接拒絕、什麼都不寫（`AccessUnsafe`）。信任資料也含 `aos` 自己的指令與程式庫，見 [agent access.md](../spec/agent/access.md#信任資料工具永遠寫不到)。

### 掛兩個資料夾：一個可寫、一個唯讀

```sh
aos-agent access set ws $W/bob/workspace --cwd --target $W/bob   # 起點，可寫（家裡的寫絕對路徑）
aos-agent access set ref ~/docs --ro --target $W/bob        # 第二個，唯讀
```

工具起點在 `/work/ws`，照樣讀得到 `../ref/筆記.txt`；但寫 `../ref/新檔.txt` 會退：

```text
{"ok": false, "error": "ReadOnly",
 "message": "cannot write ../ref/新檔.txt: that folder is read-only … Writable folders: /work/ws."}
```

直接寫在 `/work` 底下（不在任何掛進去的資料夾裡）也是同一個代號。

改完 `access.json`，**下一批工具呼叫才吃得到新表，不用重 `start`**；要馬上擋先 `aos-agent pause`。需要系統裝了 `bubblewrap`，沒裝工具直接跑不起來，`access ls`、`check` 會提醒照 `sudo pacman -S bubblewrap` 裝。

### 工具跑不起來的幾種情形

- **沒有 `access.json`**：家裡要關牢的工具卻沒表，送件時整批不送（`NoAccess`），`tools ls` 關牢欄印 `-`、`check` 印 `bad`，都教同一行指令：`mkdir -p <家>/workspace && aos-agent access set ws <家>/workspace --cwd --target <家>`。
- **`_jail: false`**：工具檔某元素頂層加這格，那支就不關牢，`tools ls` 印 `no`，`check` 多印一行警告。平常不建議這樣用（等於開後門）。
- **`$env` 讀到金鑰**：`_meta` 若用 `$env` 讀名字像金鑰或 `AOS_*` 的變數，關牢的工具整支不給跑，退 `EnvUnsafe`；拿掉那一格才會恢復正常。
- **`info.json` 明寫的 access 檔不在**：跟「沒寫 `access` 欄」不同，算設定錯：`access ls` 印「壞了：AccessInvalid…」退 1。先 `access set` 建一份，或改對 `access` 欄。

### 舊家升級（09-24 以前 `init` 的家）

以前 `init` 的家沒有 `access.json`，現在會被 `NoAccess` 擋下：

```sh
mkdir -p $W/bob/workspace && aos-agent access set ws $W/bob/workspace --cwd --target $W/bob
aos-agent check --target $W/bob   # 確認 access 那行 ok
```

舊家裝過的 `base` 是程式副本，更新 aos 不會跟著換；要讓 read 等工具也看得到整個 `/work`，重裝一次：`aos-agent tools add base --force --target $W/bob`。
不想關牢的某一支工具，才在它的元素頂層寫 `"_jail": false`（不建議）。

## 2. 用文字編輯器改 access.json

指令背後改的就是這份 JSON，直接用編輯器開也完全可以——存檔一律縮排 2 格，方便手改後用 diff 看差異。完整例子：

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
| `mounts` | 物件，key 是牢裡看到的名字（掛在 `/work/<名>`），值是路徑；可省＝空 |
| `cwd` | `mounts` 裡的一個名字，工具在牢裡的起點；可省＝`/work` |
| `net` | `true`／`false`；`true`＝共用主機網路，可省＝`false` |

`mounts` 底下每個值可以是純路徑字串（可寫），也可以是 `{"$opt": "ro", "$val": 路徑}`（唯讀）。路徑可寫 `~` 開頭或相對 agent 家，存檔時會自動展開成絕對路徑；手改也可以直接這樣寫，下一批生效時照樣展開。

**改壞了會怎樣**：只認上面四個頂層鍵，打錯字（如把 `net` 打成 `network`）**不會被默默忽略**，`check`、`access ls` 都會老實指出哪裡壞：

```text
bad  access: AccessInvalid: access 檔 /home/you/aos-try/bob/access.json 的 network：不認得的鍵（只認 mounts／cwd／net／_metainfo）
```

檔壞的時候，`access` 系列寫入動作（`set`／`rm`／`cwd`／`net`）一律拒絕，不會蓋掉你手寫的東西；改回對的內容，`check`、`access ls` 就都恢復乾淨。

## 3. 管理工具

`tools ls`／`rm`／`alias`／`unalias` 看現況、拿掉某支、改名——**都只改 `info.json` 的 `tools` 欄，不動工具檔**。（`access set` 的 PATH 一樣照打指令那一刻殼的目前資料夾算，跟第 1 節同一條規矩。）

### `tools ls`

```text
名字   原名  來源檔           關牢  池
read   -     tools/base.json  jail  default
write  -     tools/base.json  jail  default
…（edit／bash／grep／find／ls 同一批）
date   -     tools/date.json  jail  default
8 個工具；關牢照 /home/you/aos-try/bob/access.json
```

「原名」欄沒改名印 `-`；「關牢」欄 `jail`＝會關、`no`＝那支 `_jail: false`、`-`＝**沒有 access.json，要關牢的都不會送**（`NoAccess`）、`錯`＝access 設定壞了（見上）。

### `tools add` 引用一個現成的檔或資料夾（不裝包）

`tools add NAME` 裝內建包（複製進 `tools/`）；給一個**含 `/` 的資料夾或 `.json` 檔**會**原地引用**，不複製：

```sh
aos-agent tools add ../util-tools --only ping --as hello --target $W/bob
```

```text
referenced /home/you/aos-try/util-tools（原地引用、不複製；1 個工具：hello）
info.json 的 tools 補了 {"$opt": {"as": {"ping": "hello"}, "only": ["ping"]}, "$val": "…/util-tools"}
下一批工具生效，不用重 start
```

`--only a,b` 先挑幾支、`--as OLD=NEW` 再改名；撞名或原名不在裡面都拒絕（`ToolInvalid`）。

### `tools rm NAME`：拿掉，不刪檔

```sh
aos-agent tools rm date --target $W/bob
```

```text
拿掉 date：info.tools 第 0 條改成只挑（原名）read、write、edit、bash、grep、find、ls
注意：這條是整個資料夾，之後放進去的新工具要加進 only（或 tools add）才會出現
檔還在 …/tools/date.json（第 0 個，原名 date）；沒刪任何檔
下一批工具生效，不用重 start
```

### `tools alias`／`unalias`：換模型看到的名字

`aos-agent tools alias bash exec --target $W/bob` 印 `bash 改叫 exec（原名 bash；info.tools 第 0 條）`；`unalias exec` 改回原名。`NAME` 可以是現在的名字，也可以是原名。兩者都會再印一行 `下一批工具生效，不用重 start`。

這些指令背後改的是 `info.tools` 陣列裡的元素，一樣可直接手改（`{"$opt": {"as": {...}, "only": [...]}, "$val": "路徑"}`），完整寫法見 [agent tools-opt.md](../spec/agent/tools-opt.md)。

## 底下在幹嘛

- act 批在建批那一刻把 `access.json` 解一次存成快照，同一批每件、崩了重送都用它——「下一批生效」是真的照批次算。
- 送件時工具被包成 `aos-jail --mount … --chdir … --net … -- 原本的程式`，掛完之後整個牢的根（含 `/work` 本身）再轉唯讀；`aos-agent` 一律用絕對路徑呼叫自己這份 `aos-jail`，不查 `PATH`（[aos-agent access.md](../spec/aos-agent/access.md)、[aos-jail.md](../spec/aos-exec/aos-jail.md)）。
- `tools`／`access` 的寫入指令共用同一把鎖 `<家>/.admin.lock`，兩邊不會同時改半份。
- 「信任資料」永遠查不到可寫，手動 `access set` 也會被自動改唯讀或直接拒絕。

## 常見錯誤

| 看到 | 原因與怎麼辦 |
|---|---|
| 工具沒執行，代號 `NoAccess` | 家裡沒有 `access.json`；`mkdir -p <家>/workspace && aos-agent access set ws <家>/workspace --cwd --target <家>` |
| write／edit 說 `ReadOnly` | 寫到唯讀掛點，或直接寫在 `/work` 底下；訊息列出目前哪些資料夾可寫 |
| `access set` 說 `AccessUnsafe` | PATH 跟信任資料重疊、又給了 `--rw`；改 `--ro` 或換資料夾 |
| `access rm NAME` 說「是目前的起點」 | 那名字正被 `cwd` 用；先 `access cwd 換別的` 再 rm |
| `check`／`access ls` 印 `bad`／「壞了：AccessInvalid」 | 格式錯，或明寫的 access 檔不在（見第 1 節） |
| 工具失敗、代號 `EnvUnsafe` | `_meta` 用 `$env` 讀了金鑰或 `AOS_*` 變數；拿掉那一格 |
| `tools rm`／`alias` 說 `FieldTypeMismatch` | `info.tools` 用了 `$ref`，這些指令只改字面陣列；自己手改 |

## 收工

跟 [04](04-tools-and-pause.md) 共用同一個 bob：`aos-agent stop --target $W/bob`；今天到此為止就照 [01 第 7 步](01-daemon-kernel.md#7-關機順序kernel--daemon)關機；接著做 [05](05-many-agents.md) 就先留著。
