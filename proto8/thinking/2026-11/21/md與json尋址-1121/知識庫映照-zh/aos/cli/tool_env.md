# `knowledge/aos/cli/tool_env.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/tool_env.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# 工具登記裡的 hub 變數

在登記時就存下 hub 的位置，讓每次工具呼叫都用到想要的服務。

這樣登記 hub：

```sh
aos-tools --file tools.json add --name read --env-file hubs.env --envs LANG=C.UTF-8 ../lib/tools/base/read
```

`aos-agent tools --target bob add` 收一樣的旗標（`--name`、`--replace`、`--envs`、`--env-file`、`--path-json`、`--no-cache`），並把它們寫進那個 agent 在自己 stack 裡的登記表（registry）。

`--envs K=V` 需要幾次就重複幾次。同一個鍵以最後一個值為準。值是照打的樣子存進登記表的字面字串，所以不要把機密放在那裡。`--env-file FILE` 只存那個檔在哪裡（像工具路徑一樣：絕對路徑維持絕對，相對路徑存成相對於登記表）；每次呼叫都會讀這個檔，而且絕不會複製進登記表，所以機密要用它放。呼叫時，後面的蓋過前面的：工具自己的 `.env`（只補空缺）、呼叫的人的環境、env 檔、`--envs`。env 檔不存在時，add 時是警告，呼叫時是錯誤。

之後改 hubs.env，下一次呼叫就生效。要改 `--envs` 的值，用 `--replace` 再登記一次；取代會重寫整個項目。登記表裡的值不能蓋過工具的暫存 `AOS_STACK`。

工具宣告了但找不到的 hub 會產生警告，登記仍然成功。ls/get 不會印出存下的登記環境值。工具的輸入仍然放在 stdin 的 JSON 裡；hub 變數不是工具的參數。
