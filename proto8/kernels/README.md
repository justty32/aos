照名字找的 kernel 設定：`mini.py --kernels aos/base-low,aos/llm/fake -- 指令` 裡的每個名字，就是這個夾底下的一份 `<名字>.json`（使用者 11-27 晚定第 1 題：放 `$AOS_HOME/kernels/<名字>.json`）。

# kernels

← [proto8](../README.md)｜用它的程式：[proto9/mini-sandbox](../../proto9/mini-sandbox/README.md)（說明、驗收都在那邊）

- **怎麼找**：`mini.py` 先找 `$MINI_KERNELS_PATH`（冒號分隔的夾，可不設），再找 `$AOS_HOME/kernels/`；第一個找到的算。兩個都沒設就報錯、什麼都不跑。
- **一份長這樣**：`{"description": "一行英文", "program": "cg_kernel.py", "config": {…}}`。`program` 只寫檔名＝mini 自己的程式（跟 `mini.py` 同一夾）；寫了 `/` 才當路徑（`$變數`、`~` 會展開，相對路徑從這份 json 的夾算）【擬】。`config` 各 kernel 自己的欄位，見 mini-sandbox 的 README。
- **寫在前面的是外層**：`--kernels a,b,c` 的 `a` 最外面，pi 住在最裡面；裝了資源上限、網路或 llm kernel 時，mini 自動在最裡面加 `aos/mask/run-user`（`--no-auto-mask` 關掉）。
- **pi 在裡面會怎樣**：這些檔 pi 讀得到也改得到（檔案沒遮），改了要到下一次起的時候才生效。

| 名字 | 是什麼 |
|---|---|
| `aos/base-low` | 資源上限：CPU 一顆核的 20%、記憶體 512M（不用 swap）、行程＋執行緒 64 |
| `aos/base-high` | 資源上限：200%、4G、1024 |
| `aos/net/base-litellm-proxy` | 網路：只放行這台的 `127.0.0.1:4000`（LiteLLM），頻寬與總量有上限；跟 llm kernel 一起用時要寫在 llm kernel 前面（外層）；寫在後面（`aos/llm/…,aos/net/base-litellm-proxy`）會讓 pi 繞過 llm kernel 直連 LiteLLM，mini 會印警告 |
| `aos/mask/run-user` | 檔案遮蔽：`/run/user/<你的 uid>` 蓋成空夾（關住經 D-Bus 跳出沙箱那條路） |
| `aos/mask/ssh` | 檔案遮蔽：`~/.ssh` 蓋成空夾 |
| `aos/uid/1` | 切成 uid 1（外面是你第一個 subuid）；一定放最後 |
| `aos/llm/fake` | llm kernel，劇本腦（不叫模型）：`fake-model`、一次 50 次 |
| `aos/llm/litellm-luna` | llm kernel，上游是這台的 LiteLLM：只准 `chatgpt-gpt-6-luna-nothink`、一次 10 次；放在網路 kernel 外面 |
