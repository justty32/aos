# 主輪：分層與各入口怎麼接

← [本場索引](../README.md)｜[workshop](../../../README.md)

主輪的整體分層原本是一份 10 KB 的單檔，照 [DEV-GUIDE](../../../../../STRUCTURE.md) 的「膨脹即拆」再拆成三份：先是層次與前提，再是三個入口各自的接法，最後是把本場 workshop 自己搬上 aos 的版面與卡點。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [分層與已知前提](layering.md) | 〈主輪：aos 怎麼跟現有工具協作〉：pi 與本場的已知前提、誰在上面誰在下面、stdout→stdin 能成立但不能拿 raw stdout 當協定、coding agent 的 session 只可當快取 | 要先搞清楚 aos 與 coding agent 誰管什麼、界線畫在哪時 |
| [skill／MCP／權限三個接法](skill-mcp-permission.md) | 〈skills 怎麼接〉、〈MCP 怎麼接，或為什麼 pi 不接〉、〈權限這塊〉 | 要動手寫 SKILL.md、MCP 薄殼，或決定哪幾支預設暴露時 |
| [把這場研討會搬到 aos 上](workshop-on-aos.md) | 〈把這場研討會搬到 aos 上〉：topic-world 版面、四個回合、Deliver 尚未實作等四個卡點 | 想看一個具體例子，或要知道現在做不到的是哪一段時 |
