# 哪些交給 `.aos`、哪些永遠留在 markdown

← [本場索引](../README.md)｜[workshop](../../../README.md)

本場的職責切線原本是一份 9 KB 的單檔，照 [DEV-GUIDE](../../../../../DEV-GUIDE.md) 的「膨脹即拆」再拆成三份：切線的兩邊各一份，加上三軸各自長成什麼的那一段。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [該變成 `.aos` 的](to-aos.md) | 〈該變成 `.aos` 的〉：共同長出的動作、磁碟版面有兩個尚未合併的版本、一個候選的動作順序、安裝與升級也可以機械化但不應覆蓋客製 | 要設計 `wf` 命令、決定活狀態放哪裡，或要做安裝升級時 |
| [該永遠留在 markdown 的](stay-in-markdown.md) | 〈該永遠留在 markdown 的〉：四位共同畫出的邊界、薄 front matter 的例外、為什麼提早編成 schema 會凍死還在生長的政策 | 要決定什麼**不該**被編成 JSON，或要引用那條分工鐵律時 |
| [三軸分別長成什麼](three-axes.md) | 〈三軸分別長成什麼〉：SESSION-LOG／WAIT_USER／inbox 各自的候選形狀、進出動作、不能失去的原意，以及 schedule／tick | 要動 SESSION-LOG、WAIT_USER 或 inbox 任何一軸時 |
