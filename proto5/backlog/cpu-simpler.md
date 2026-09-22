# cpu 佇列實作再精簡

**問題**：cpu 佇列現在是 requests／running／done 三個資料夾＋一把 `.queue.lock` flock 短鎖＋認領前 utime＋收屍＋發布前核對 inode。每一項都有理由（findings #1、#8～10、#19），但加起來不算薄。

**使用者意見（2026-09-22）**：接受現在這套；但實作上「可以不加複雜度就不加」，再評估看看，可能在 proto5-2 試。

**以後從哪下手**：`lib/aos_cpu.py` 的 `tick`；候選是拿掉 running 資料夾（認領＝改名加前綴）、收屍改成只看 mtime。
