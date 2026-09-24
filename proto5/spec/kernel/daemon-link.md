← [kernel](README.md)｜[spec 總導航](../README.md)

# 5. 跟 daemon 講話

kernel 對 daemon 只做兩件事：`spawn`（每格第 7 步）、`kill`（只有 boot）。看孩子活不活是偷看 `D/state.json`
（唯讀）；看 daemon 本身活不活是對 `D/.daemon.lock` 試拿**非阻塞的共享 flock**——拿不到＝daemon 持著獨占鎖＝活著，
拿到了就馬上放掉＝沒有 daemon（[daemon §6.1](../daemon/lifecycle.md)）。不看 pid。
放單、等 `D/responses/` 同名回音（最多 5000 ms，逾時＝`-32000`／`ReadFailed`，**逾時不代表沒做**，
下格重送是安全的）、ack 進 `acks`。

| method | kernel 怎麼用 |
|---|---|
| `spawn {"name","target","restart":true}` → `{"pid"}` | `name`＝cpu 名；`target`＝`K/cpus/<c>/inst.json`（argv `aos-cpu K/cpus/<c>`、cwd 那個家、stderr 接 `cpu.log` append、`envs` 照 info）；`restart:true`＝非 0 退出 daemon 自己再拉。同名同 target 已活著＝回它的 pid、不重拉；同名**不同** target＝`NameTaken`——兩個 kernel 共用一個 daemon 又都叫 `k` 會在這裡大聲失敗，不會靜默搶到別人的孩子 |
| `kill {"name"}` | boot 用它收掉舊的 kernel cpu：取消重拉、走階梯、死透從孩子表消失（[daemon §3](../daemon/methods.md)） |
