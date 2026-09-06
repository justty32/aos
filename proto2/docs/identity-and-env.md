# 身份與環境

一個時鐘就是 kernel 開的一個 `aos-loop`。

目前所有時鐘預設都跟 kernel 用同一個 Linux user。
`user` 欄位仍可用。只有 root 跑的 kernel 才能換 user。

## 工具清單

- `aos-daemon register 世界 --config clock.json`：用設定檔開鐘。
- `aos-daemon register 世界 --env K=V`：直接加一個環境變數。可以重複。
- `aos-daemon register 世界 --env-from llm.env`：從檔案讀環境變數。
- `<daemon 目錄>/config.json`：放 kernel 共用設定。
- `chmod 600 llm.env`：把金鑰檔鎖成只有自己能讀寫。

## 什麼時候用

一般設定用 `env`。

要沿用 kernel 現有的一個變數，用 `env_keep`。

金鑰只用 `env_from`。只有 LLM 世界的鐘可以指向金鑰檔。
agent 世界的鐘不要指。

## 關掉舊相容模式

在 daemon 目錄寫 `config.json`：

```json
{
  "legacy_env": false
}
```

目前沒寫時，預設是 `true`。
這是為了不弄壞已經在跑的共用環境。

`true` 會把 kernel 的整包環境交給每顆鐘。
kernel 的 shell 若有金鑰，agent 也看得到。

下一步要把預設改成 `false`。
在那之前，要隔開金鑰的 daemon 必須明寫 `false`。

## 時鐘設定

```json
{
  "interval": 1,
  "user": null,
  "env": {
    "MY_MODE": "work"
  },
  "env_keep": ["TERM"],
  "env_from": "/絕對路徑/llm.env"
}
```

乾淨環境先放這些：

- `PATH`：`proto2` 工具目錄在最前面，後面是基本系統路徑。
- `HOME`、`USER`、`LANG`。
- `AOS_DAEMON_DIR`：目前 daemon 目錄。
- `AOS_LLM_DIR`：kernel 啟動時拿到的值。沒有就是空字串。

套用順序是：乾淨環境 → `env_keep` → `env` → `env_from`。
後面的同名值會蓋掉前面的。
`PATH` 最後仍會把 `proto2` 工具目錄放回最前面。

`--env` 會併進設定檔的 `env`：

```sh
aos-daemon register ./worker \
  --config worker-clock.json \
  --env MY_MODE=work \
  --env DEBUG=0
```

`--env-from` 會蓋掉設定檔裡的 `env_from`。
命令列給的路徑會先轉成絕對路徑。

## 金鑰只給 LLM 鐘

`llm.env` 一行一個 `KEY=VALUE`：

```text
DEEPSEEK_API_KEY=你的金鑰
```

先鎖權限：

```sh
chmod 600 /絕對路徑/llm.env
```

LLM 鐘的設定才寫：

```json
{
  "interval": 1,
  "env_from": "/絕對路徑/llm.env"
}
```

agent 鐘不要寫 `env_from`。
kernel 啟動前也不要把金鑰 export 進 shell。

`env_from` 權限不是正好 600，register 會失敗。
錯誤會留在 `requests/done/` 的請求結果，也會進 kernel log。

## 主人的檔

目前不改程式，只寫做法。

`system-prompt.json` 和 `llm.json` 可以由主人手動鎖：

```sh
sudo chattr +i system-prompt.json llm.json
```

要修改時先解鎖：

```sh
sudo chattr -i system-prompt.json llm.json
```

不要鎖 `.aos/inst`。
shared 小孩與暫停功能還會改它。

## 坑

- 安全模式目前不是預設。要自己寫 `legacy_env: false`。
- `env_from` 請寫絕對路徑。設定檔裡的相對路徑由 kernel 的工作目錄解讀。
- 改了 `llm.env`，已經在跑的鐘不會立刻換環境。要重開那顆鐘。
- `env_from` 只檢查檔案模式是 600。沒有處理 ACL、符號連結或檔案被同時換掉。
- 不同 agent 仍是同一個 user。它們還是可能直接讀別的世界或 home。
- 時鐘很密時，`aos-loop` 的 log 會長很快。這輪不處理。
