# kids 工具包

這包讓 agent 生小孩，也管小孩。

小孩住在 `<home>/kids/<名字>/`。
它有自己的人格、記憶和信箱。
它跟父共用同一個 LLM 資料夾。

## 工具

### `spawn`

生一個小孩。

- `name`：名字。只能用英數字、底線、減號。
- `persona`：它的人格和工作方式。
- `packs`：它可用的工具包。明講時優先；沒講就用模板的，沒有模板才抄父的。
- `clock`：`shared` 或 `own`。預設是 `shared`。
- `task`：可省略。生完立刻寄給它的第一件事。
- `template`：可省略。出廠模板名字。

使用者說要 coder、manager 或 chat 小孩時，應把同名值放進 `template`。只把「coder」寫在人格裡，不會自動換工具包。

回 `ok`、`name`、`path`、`clock`、`message`。

父是第 0 層。小孩是第 1 層。孫是第 2 層。
第 2 層不能再生。

### `kids_list`

看所有名冊裡的小孩。

不用參數。

每列有：

- `name`、`clock`。
- `state`、`busy`、`step`。
- `unread`：小孩還沒讀的信有幾封。
- `last`：小孩 outbox 最後一句。太長會切短。
- `paused`：有沒有暫停。

派完活後可用它看進度。

### `kids_pause`、`kids_resume`

參數只有 `name`。

`own` 小孩會走 daemon 的 pause／continue。
`shared` 小孩沒有自己的鐘。
暫停時會註解父 `.aos/inst` 裡推它的那一行。
續跑時會拿掉註解。

### `kids_kill`

收掉一個小孩。

- `name`：小孩名字。
- `keep_files`：預設 `true`。

預設只停鐘和改名冊。
資料夾與記憶會留下。

`keep_files=false` 才會刪資料夾。
刪了不能救回來。

### `kids_tell`

寄工作給小孩。

- `name`：小孩名字。
- `text`：要它做的事。

信會進 `kids/<名字>/inbox/parent/`。
小孩下一格會看到。

## 小孩怎麼回報

小孩只要正常回答。
不用找父的路徑，也不用自己寫信件檔。

回答會保留在小孩的 outbox。這是 agent 共用行為，不要求小孩自己也載入 `kids` 包。
同一句也會進父的 `inbox/kid-<小孩名>/`。
父下一格用信箱工具讀。

## 名冊

名冊在 `<home>/kids.json`。

每個小孩會記：`name`、`clock`、`created`、`depth`、`parent`、`alive`、`task`。
實作也保留 `dir`，用來找到小孩資料夾。

kill 後名冊還在。
`alive` 會變成 `false`。

## 設定與坑

- `own` 需要 `AOS_DAEMON_DIR`。沒設時只會建資料夾，不會自己走。
- `shared` 會改父世界的 `.aos/inst`。父停，它也停。
- 名冊是準的那份。這版不修名冊與資料夾對不上的情況。
- kill 掉的名字這版不能重用。
- `kids_list` 每次會掃信箱與 outbox。檔案很多時會變慢。
