# aos-util

`libaos-util - aos 這一家命令列工具共用的小函式庫`（NAME，C-54 R1）

**一句話：aos 這一家命令列工具共用的小函式庫——錯誤型別與全家的錯誤代號、三扇門（stdin／stdout／stderr）、旗標（`aos/cli.hpp`；較早一代沒人叫的 `aos/flags.hpp` 11-04 刪了）、設定檔、路徑與原子寫入、子程序、訊號。** 沒有執行檔，只出 `lib/libaos-util.a`。全家慣例見 [impls/README.md](../README.md)。

像一家店的共用倉庫：每支工具自己只放自己獨有的東西，「好幾支都要」的一律放這裡，一份就好。

## 用法

```cpp
int main() {
    try {
        aos::Json in = aos::read_stdin();      // stdin 一份 JSON
        return aos::emit(做事(in));             // stdout 一行、退 0
    } catch (const aos::Error& e) {
        return aos::fail("aos-x", e);           // stderr 一行「aos-x: error: 代號 原因」、退 1
    }
}
```

## 元素（一個標頭一個元素）

逐檔「哪個檔負責什麼」從檔頭一句話生成，在 code map 的 [proto8 生成冊](../../../wf/workflows/common/code-map/proto8/README.md)（`impls` 冊的 `aos-util/` 段）；改說明去改檔頭。

標頭開頭都有白話說明（含「為什麼原子寫入」「為什麼不用訊號處理函數」「行程群組、收屍、memfd 是什麼」），從那裡讀。

## 建置與測試

```sh
cmake -B build && cmake --build build
```

- 別的專案怎麼連、vcpkg、產物：見 [impls/README.md「建置」](../docs/04-命令列-設定-旗標-三扇門-指示詞與新專案照這張清單.md#建置)。

## 已知限制

- 只支援 Linux（`posix_spawn` 的 `SETSID`、`memfd_create`、`signalfd`、`/proc`）。
