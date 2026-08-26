# 場地與指令形態

← [hackathon README](README.md)｜[結構索引](INDEX.md)

> **本檔＝怎麼把參賽者跑起來。** 場地開在哪、整包複製的指令、為什麼在 WSL、
> 以及 `codex exec` 這邊跟 workshop 不一樣的地方。撞到的坑見 [gotchas.md](gotchas.md)。

## 場地（整包複製，不碰 repo 工作區）

**2026-08-26 使用者指定：整包複製。** 參賽者要真的寫檔，不能讓幾個人在 repo 工作區互相蓋。
**場地開在 WSL 的 `$HOME/aos-hack/<題目-kebab>/p<N>/`**，一人一份，做完丟掉、不進 repo。
**不要用 `/tmp`**——實測會被清掉，賠掉過一整輪，理由見 [gotchas.md](gotchas.md)。

```bash
# 整場在 WSL 內跑（codex 在 WSL 就有：~/.local/bin/codex）
export PATH="$HOME/.local/bin:$PATH"          # bash foo.sh 不載 profile，沒這行 codex 會 127
SRC=/mnt/c/code/mine/simple_tools/aos
ARENA=$HOME/aos-hack/<題目-kebab>/p1        # 不要用 /tmp，會被清掉
mkdir -p "$ARENA/build/bin" "$ARENA/build/lib"
rsync -a --exclude build/ --exclude .git/ "$SRC/" "$ARENA/"
cp -a "$SRC/build/bin/aos" "$ARENA/build/bin/"
cp -a "$SRC"/build/lib/*.so*  "$ARENA/build/lib/"   # RUNPATH 是 $ORIGIN/../lib，少了跑不起來
```

**建場地、放任務書、冒煙、開跑要合併成同一支腳本、同一次 `wsl.exe` 呼叫**——理由與其他六個坑見 [gotchas.md](gotchas.md)。

**為什麼在 WSL 而不是 Windows 側的 scratchpad**：`build/bin/aos` 是 **Linux ELF**
（實測 `file`：`for GNU/Linux 3.2.0`），**Windows 這側執行不了，要把 aos 跑起來就只能從
WSL 跑**；而且 `/mnt/c` 是 9p 掛載，小檔 I/O 慢又會噴 clock skew。Windows 側的 session
scratchpad 照 workshop 慣例放**任務書與原始回報**（不進 repo）。

**預設不 build，用複製過去的那顆 `aos`。** 理由是實測的：codex 沙盒下 `$HOME` 唯讀，
vcpkg 拿不到 `~/dev/vcpkg/buildtrees/` 的 write lock，configure 一定失敗
（[T5 現場](../experiments/t5-agent-loop.md)）。題目真的要改 C++ 才給
`--add-dir ~/dev/vcpkg`，並預期第一次 configure 很久。

**可以讀 `../` 的兄弟專案**（2026-08-26 使用者指定）：`agent-machine`、`freepy`、`dcap`、
`arc_agi_tweets` 等，在 WSL 是 `/mnt/c/code/mine/simple_tools/`。沙盒只擋寫不擋讀，但
**場地不在 repo 旁邊，所以要在任務書裡把這個絕對路徑明講**，否則他們的 `../` 是空的。

## 指令形態

`codex exec` 的旗標、reasoning effort、`--json` 抓 session id、`-o`＋stdin、MCP
`AuthRequired` 噪音等**大致沿用 [workshop README 的〈指令形態〉](../workshop/README.md)**。
黑客松不同的地方：

- **參賽者沙盒是 `-s workspace-write`**（`-C` 指向他自己的場地複製品），加 `--skip-git-repo-check`。
- **逾時拉長到至少 1800 秒**（workshop 是 600）。
- **整場在 WSL 內跑**，不是 Windows 的 `codex.exe`——所以 workshop 那句
  「任務書放 Windows scratchpad」在這裡不適用。細節見 [gotchas.md](gotchas.md)。
