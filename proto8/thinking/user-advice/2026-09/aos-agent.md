## aos-agent

init
    用默認設定啟用一個agent。(默認設定來自於哪，我還沒想好。應該會是環境變數吧)
    所謂啟用，就是準備好相關資料夾(.aos/agent)
init --config xxx.json
    從指定json讀取設定，啟用。

start
    跟aos kernel說，要register這個資料夾。
    這個指令後面可以跟著一堆flag，繼承於aos kernel register的。
    之後可能還有一些其他的flag，之後再說。
stop
    跟aos kernel說，unregister這個資料夾。
    跟pause不一樣，pause那個，是仍registering，但狀態機不動。

pause
    daemon的cpu仍然會持續執行，但是agent的狀態機不會前進。
    交給外部cpu跑的東西，回來的結果也是會存，但agent不會反應
    shell跑的東西，會跑完，但agent不會反應
continue
    繼續

tools
    顯示當前資料夾agent的可用工具，的id(這一輪)
tools ls
    同上
tools add ./xxx.json
    指定的json檔案必須是符合工具描述格式的(可以是陣列(多個工具))
tools remove xxx
    透過id移除指定工具
tools enable xxx
tools disable xxx

llms
    顯示當前資料夾agent可使用的llm設置集的id(這一輪)
    也包括當前正在使用的
llms ls
    同上
llms add ./xxx.json
llms remove xxx
llms enable xxx
llms disable xxx

state
    顯示當前agent的狀態機狀態

