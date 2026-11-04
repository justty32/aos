# bin — aos-tick、aos-tools、aos-daemon-ctl、aos-eca-turn（Python）

← [proto8](../README.md)｜慣例：[CONVENTION](../docs/CONVENTION.md)｜demo：[demo](../demo/README.md)｜C++ 實作：[impls](../impls/README.md)｜測試：`python3 -m unittest discover -s proto8/tests`（先建 impls，見 [testing](../../wf/workflows/testing.md)）

> **C++（[proto8/impls](../impls/README.md)）是唯一實作**（使用者 10-23：「python版本可以刪掉了。aos-exec/loop/daemon都用C++」；fsm 和 tick，使用者選「fsm 也改用 C++、tick 先留 Python」）：
> `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 的說明在各自的 README：[aos-exec](../impls/aos-exec/README.md)、[aos-loop](../impls/aos-loop/README.md)、[aos-fsm](../impls/aos-fsm/README.md)、[aos-daemon](../impls/aos-daemon/README.md)；inst 是 C lib [inst](../impls/inst/README.md)。
> 這裡是 Python 的 `aos-tick`、`aos-tools`、`aos-daemon-ctl`、`aos-eca-turn`（都用 `aos_flags.py` 的旗標解析 `parse`）；完整說明在各支的檔頭 docstring。

```
python3 -m unittest discover -s proto8/tests           # C++ 的在 impls/<名>/bin/、Python 的在這裡（tests/aos_bins.py 放 PATH）
```

aos 的程式都不動 PATH（ideas § 24）：自己跑時把 `proto8/impls/<名>/bin/` 與這個 `bin/`（aos-tick、aos-tools…）放進 PATH，`tests/aos_bins.py` 就是這樣做（11-04 前 `demo/run.sh` 也是）。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按標題（再按條號／頂層清單項）拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-逐支說明](docs/01-逐支說明.md) | 逐支說明：開頭、aos-tools - 一個 agent 資料夾一份工具註冊、aos-round 不在了、aos-eca-turn - 外部 coding agent |
| [02-aos-tick與已定值](docs/02-aos-tick與已定值.md) | 逐支說明（續）：aos-tick - 把時鐘檔的回合數往前走一格、aos_flags.py：命令列旗標解析 parse(；已定值 |
| [03-aos-daemon-ctl](docs/03-aos-daemon-ctl.md) | aos-daemon-ctl：開頭、哪個 daemon、add／rm＝投信、做完的同名再 add＝重新起、自動識別、-- 參數...、--ws WS、--stack S、不碰 /.stack、stop／start、pause／resume、exec 型只有跑和拔 |
| [04-aos-daemon-ctl續](docs/04-aos-daemon-ctl續.md) | aos-daemon-ctl（續）：where --stack 名字、ls、ls 另判 daemon 活著、錯 |

<a id="逐支說明"></a>
<a id="已定值"></a>
<a id="aos-daemon-ctl"></a>
