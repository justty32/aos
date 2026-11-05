## 前綴是aos-inst

要評估一下方不方便做，是否會牽扯到其他模塊的修改，牽扯多少

用法是aos-inst ./inst.json envs
順序不能錯，第一個一定是inst檔案路徑
或是aos-inst ./ envs
這樣的話會依序搜尋./inst.json, ./.aos/inst.json

args
    吐出的是組裝且解析後的。比如ls -la這樣。
    如果解析的時候，遇到$env找不到，這類解析失敗的，會輸出東西到stderr。
args --raw
    吐出的是未經組裝和解析的。
args --json
args --raw --json

envs
    吐出的是一行一行xxx=yyy這樣的。
    吐出的是完整env，也就是解析後的
envs --json
    改成吐出json object
envs --raw
    吐出的是未經組裝和解析的。
envs --json --raw
    順序隨意。吐出的是未經組裝和解析的json object。

stdin
    吐出檔案路徑，還有檔案狀態，關於是否是pipe。
stdout
stderr
stexit
    這是exit status。同上

