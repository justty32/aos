# 身份、權限、PATH 與環境

← [proto2/README](../../README.md)｜[抒發原文](../2026-09-06-world-clock-agent.md)

一句話：**一個鐘（或一個新生的 agent）要跑在哪個 Linux user 底下、看得到哪些環境變數、
哪些檔它不准改**——這三件事現在全靠「反正都是我自己」在撐，這篇寫最土的做法跟建議走到哪。

底下是建議稿，不是已落地的東西。

## 一、身份：一個鐘跑在誰底下

階梯就三階，愈下面愈麻煩。

**(a) 全部同一個 user（現在這樣）。** kernel 是你開的，時鐘是 kernel 開的，
所以每個時鐘都是你。agent 能碰的東西＝你能碰的東西，包含 `~/.ssh`、整個 repo、`sudo`（如果你沒密碼）。
要改的地方：沒有。`--config` 的 `user` 不填就是這一階。

**(b) 一個 `aos` 群組，每個 agent 一個 user。** 只在「要跑一個我不敢看著它跑的 agent」時才走到這階。

```sh
sudo groupadd aos
sudo useradd -m -g aos -s /usr/sbin/nologin aos-helper     # 一個 agent 一個
sudo chown -R aos-helper:aos /srv/worlds/helper            # 它的世界給它
```

要改的地方三處：①kernel 得用 root 跑（`sudo aos-daemon-kernel start`），因為切身份靠 `runuser`，
非 root 現在會直接回「要切換身份得用 root 跑 kernel」。②register 時給
`--config '{"user": "aos-helper"}'`。③`useradd` 只有你（sudo）能做——
**agent 自己 spawn 出來的小孩沒辦法自己要一個新 user**，只能沿用父的身份，或你事先開好一批空的 user 給它挑。

**(c) container／namespace。** 先不做。等到「這個 agent 會連外網、會裝東西、我不想讓它看到 home」才值得。

**建議：停在 (a)。** 現在只有你一個人一台機器，(b) 換來的隔離抵不上「每個世界都要 chown、log 讀不到、
agent 之間互相寄信要調權限」的麻煩。把 (b) 的路留著就好——`user` 欄位已經在了，能動就行。

## 二、別讓 agent 弄壞自己的家

先把家裡的檔分兩區。分完再談用什麼手段鎖。

| 檔 | 誰的 | 為什麼 |
|---|---|---|
| `.aos/inst` | **主人** | 心跳。改掉它，agent 就不會動了，或每格跑錯的東西 |
| `system-prompt.json` | **主人** | 人格。自己改人格＝可以把自己改成別人 |
| `llm.json` | **主人** | 決定打哪台、花誰的錢 |
| `tools.json` | agent | toolsmith 那包就是要它自己加工具 |
| `prompts.json`、`state.json` | agent | 記憶跟進度，每格都在寫，鎖了就死 |
| `inbox/`、`outbox/`、`kids/`、`jobs/`、`packs/` | agent | 它幹活的地方 |

**最土可行的一招：`sudo chattr +i <檔>`。** 檔案系統層級的「不准改」，連同一個 user 都寫不動、
連 root 自己也要先 `-i` 才能改。一個檔一次，不用分 user、不用改任何程式碼。

代價三個，都不小：①你自己要改人格也得先 `sudo chattr -i`，忘了就會看到看不懂的 `Operation not permitted`；
②`git checkout`、`rm -rf 那個世界`、備份還原全都會失敗；③只有 ext4／xfs 這種檔案系統有，`/tmp` 上的
tmpfs 沒有。

**建議：只鎖 `system-prompt.json` 跟 `llm.json` 兩個檔。**
`.aos/inst` 先不要鎖——因為 spawn 一個 shared 小孩就是往父的 `.aos/inst` 尾巴加一行
`aos-exec kids/<名字>`，`kids_pause` 也是去那行前面加 `#`。鎖了它，生小孩跟暫停小孩當場壞掉。
真要鎖，得先把小孩那幾行搬進另一個檔（例如 `.aos/kids`，`inst` 裡加一句去跑它），
這是設計改動，見拍板第 3 條。

走到階梯 (b) 之後就不用 `chattr` 了，改用最正常的那招：主人的檔 `chown 你:aos` 加 `chmod 644`，
其他的 `chown aos-helper`。agent 讀得到、寫不動，訊息也正常。**唯讀 bind mount 不建議**——
一個 agent 一個 mount，重開機要重掛，跟「檔案就是介面」打架太多。

## 三、PATH 與環境變數

**aos 工具目錄一定要在 agent 的 PATH 裡。** 現在已經是了：`aos-exec`／`aos-loop` 開頭就把自己所在的
資料夾插到 PATH 最前面，往下一路傳給 `aos-agent`、傳給 `sh` 工具。所以 agent 的 `sh` 直接打
`aos-daemon register ...`、`aos-user say ...` 都叫得到。這是**要的**，不然它連生小孩、開長工都做不到。

**一個現成的坑**：走 `runuser` 換身份時，PATH 可能被系統的 `login.defs` 蓋掉。
修法就一句——`runuser -u bob -w PATH,AOS_DAEMON_DIR,AOS_LLM_DIR -- ...`（`-w` 是保留這幾個變數）。

`AOS_DAEMON_DIR`／`AOS_LLM_DIR` 現在是「kernel 從你的 shell 撿到什麼，時鐘就拿到什麼」——
`start_loop()` 那句 `env = dict(os.environ)` 把 kernel 的整包環境原封不動抄給每個時鐘。
能動，但也表示 **kernel 啟動時 shell 裡有的任何東西，每個 agent 都看得到**。

**建議：kernel 給一個乾淨底，其他寫在 config 裡。** daemon config 加三個欄位：

```json
{
  "interval": 1,
  "user": null,
  "env":      { "AOS_LLM_DIR": "/home/me/worlds/llm" },
  "env_keep": ["PATH", "HOME", "LANG", "TERM"],
  "env_from": "/home/me/.aosd/llm.env"
}
```

- 乾淨底：`PATH`（proto2 目錄＋`/usr/bin:/bin`）、`HOME`、`USER`、`LANG`。
- `env_keep`：從 kernel 自己的環境「額外多帶這幾個名字」。不寫就只有乾淨底。
- `env`：直接寫死的鍵值，最常用，`AOS_DAEMON_DIR`／`AOS_LLM_DIR` 就寫這裡。
- `env_from`：一個 `KEY=VALUE` 檔的路徑，一行一個。**密鑰只走這條**。
- 疊加順序：乾淨底 → `env_keep` → `env` → `env_from`（後面蓋前面）。

**密鑰絕不進 agent 的環境。** 理由很直白：agent 有 `sh`，`sh` 打一句 `env` 就全看到了，
它想寄給誰都可以。所以 `DEEPSEEK_API_KEY` 只能出現在**LLM 世界那個鐘**的環境裡——
那個世界沒有 agent、沒有模型、只有 `aos-llm exec` 在派工。
做法：金鑰寫進 `~/.aosd/llm.env`（`chmod 600`），只有 LLM 那個鐘的 config 有 `env_from` 指過去。
你自己的 shell 也別再 `export` 它，不然 kernel 一啟動又全場都有了。
`engines.json` 的 `api_key_env` 本來就只是個變數名字，這樣接完全不用改。

## 四、資源上限：先不做

Linux 的輪子現成的有兩個。**`ulimit`**——在 `.aos/inst` 最前面加一句 `ulimit -v 2000000;` 就有，
最土，但只擋記憶體、而且 agent 自己改得掉那個檔。**`systemd-run`**——
`systemd-run --user --scope -p MemoryMax=2G -p CPUQuota=50% aos-loop <世界> --keep-inst`，
kernel 開時鐘那句話前面加這一段就是了，CPU／記憶體／IO 都能限。

**何時值得**：等到有一個 agent 自己去 `pip install`、自己編東西、或寫了個無窮迴圈，
把你的機器卡到你連終端機都打不動的那天。在那之前，`sh` 的 60 秒逾時就夠。

## 五、跟現有東西怎麼接

- `aos-daemon-kernel` 的 `start_loop()`：`env = dict(os.environ)` 換成一個 `build_env(cfg)`；
  `runuser` 那行加 `-w PATH,AOS_DAEMON_DIR,AOS_LLM_DIR`。
- `aos-daemon`：說明裡把 `env`／`env_keep`／`env_from` 三個欄位寫上（它本來就把 config 原樣轉給 kernel，不用改邏輯）。
- `aos_agent.spawn()`：`own` 那條路的 `aos-daemon register` 加一個 `--config`，
  預設抄父鐘的 `interval`／`user`／`env`（父的鐘檔在 `$AOS_DAEMON_DIR/clocks/`）。
  `kids` 包的 `spawn` 工具**不開放**這幾個參數給模型填，只有主人從命令列給。
- 新檔：`~/.aosd/llm.env`（600，放金鑰）。`.gitignore` 記得別讓 `*.env` 進 repo。
- README 的 daemon 一節加兩行講 `env`，「放進 PATH」那節加一句「時鐘的 PATH 是 kernel 給的」。

## 六、現在故意不做的邊緣狀況

- 一個 agent 讀／寫別的 agent 的世界資料夾（同一個 user 就是全開）。
- `sudo`、`curl`、`pip install`、`rm -rf ~` 都不擋。
- kernel 是 root 跑的時候，log 檔跟 clocks/ 的權限沒特別處理。
- `chattr +i` 的鎖沒有人幫你上、也沒有人幫你解，全手動。
- `env_from` 的檔權限沒檢查（放成 644 也照讀）。
- agent 從 `/proc/self/environ`、或去讀 `engines.json` 旁邊的檔挖金鑰。
- 換身份後世界資料夾的檔案權限對不對，kernel 不檢查，開不起來只會標 dead。
- 環境變數的大小、非 UTF-8、`env_from` 裡有引號的值。

## 七、要使用者拍板

1. 身份就停在階梯 (a)「全部同一個 user」？**建議是**，(b) 留著欄位就好，需要時再開。
2. `system-prompt.json` 跟 `llm.json` 用 `sudo chattr +i` 鎖起來？**建議鎖**，一次 sudo，換一個「agent 改不掉自己人格」。
3. `.aos/inst` 要不要一起鎖（要的話得先把 shared 小孩那幾行搬去 `.aos/kids`）？**建議先不鎖**，別為了鎖它動 spawn。
4. daemon config 加 `env`／`env_keep`／`env_from` 三欄，kernel 改成給乾淨底？**建議採用**，不然 kernel 的整包環境每個 agent 都看得到。
5. `DEEPSEEK_API_KEY` 改放 `~/.aosd/llm.env`（600），只有 LLM 鐘的 config 指過去，你的 shell 不再 export？**建議是**，這是密鑰不外流唯一有效的一招。
