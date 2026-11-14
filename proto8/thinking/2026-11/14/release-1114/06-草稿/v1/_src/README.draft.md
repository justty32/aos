<!-- DRAFT v1, local review only. Marketing sentences are tagged copy:ID (source: release-1114 copy table). docs/ does not exist yet; links are planned targets. -->
# Folders are functions. <!-- copy:H1 -->

[license: TBD] [status: prototype] [docs](docs/zh/get-started.md)  ·  English | [繁體中文](README.zh-TW.draft.md)

aos runs AI agents as ordinary Linux processes inside folders. Every tool, every agent, every message is a folder or file you can ls, read, and set permissions on. <!-- copy:P1 -->

## Quickstart

Try it without any model. <!-- copy:TRY --> Needs: Linux (WSL2 works), git, bash, Python 3.11+, CMake 3.21+, a C++20 compiler, nlohmann-json (via vcpkg or a system package; the vcpkg route is the tested one).

```sh
git clone <REPO_URL> ~/aos            # large: about 150 MB even with --depth 1 (mostly archive/)
cd ~/aos/proto8/impls && cmake -B build && cmake --build build -j
export AOS_HOME=~/aos/proto8
export PATH=$(ls -d "$AOS_HOME"/impls/*/bin "$AOS_HOME"/cmd/*/bin | tr '\n' ':')$PATH
export PYTHONPATH=$AOS_HOME/py:$AOS_HOME/lib

mkdir -p ~/aos-demo/llms ~/aos-demo/tree
cd ~/aos-demo/llms
cp -r "$AOS_HOME/kernel/llm-kernel" def
nohup aos-exec --stack stacks/llm def > llm.log 2>&1 &
cd ~/aos-demo/tree
cp -r "$AOS_HOME/templates/daemon-root" defs
cp -r "$AOS_HOME/templates/agent-fsm" defs/ann
nohup aos-exec --stack stacks/root defs > root.log 2>&1 &
sleep 2

aos-agent -d stacks/root ctl add -w . defs/ann
aos-agent -d stacks/root -t ann say "hello, who are you?"
timeout 60 aos-agent -d stacks/root -t ann listen
tail -n 3 stacks/root/procs/ann/history.jsonl | cut -c1-200

aos-daemon-ctl -d ~/aos-demo/tree/stacks/root shutdown
aos-daemon-ctl -d ~/aos-demo/llms/stacks/llm shutdown
```

Expected: `listen` prints the fake brain's answer, and the last line of `history.jsonl` is the same answer:

```
FAKE ANSWER to: hello, who are you? (tool said: 2026-11-14T04:06:55Z)
{"role": "assistant", "content": "FAKE ANSWER to: hello, who are you? (tool said: 2026-11-14T04:06:55Z)"}
```

(The timestamp will differ. The fake brain first calls the tool `peek_now_time`, then answers.) aos writes nothing in your home folder except `~/aos` and `~/aos-demo` (the build lets vcpkg keep a download cache in `~/.cache/vcpkg`). If it sticks, see [troubleshooting](docs/zh/manual/troubleshooting.md).

<details><summary>Large clone? What is big, honestly</summary>

A full clone is large: `git clone --depth 1` still came to about 150 MB, mostly the `archive/` folder (old prototypes). The product folders themselves are small (about 6 MB, measured in batch 0). A smaller sparse-clone recipe is not measured yet, so none is given here.
</details>

## What you just ran

- `llms/` is the kernel for the brain: the one door every "ask the model" request goes through.
- `tree/` is your tree: a root daemon and the agents under it.
- `stacks/root/procs/ann/` is the agent's home: its state, its queue, its stage.
- `history.jsonl` is the conversation, as a plain file.

## Next steps

<!-- v1: English docs come after the Chinese pages are approved; these links open the Chinese drafts. -->
1. [Install](docs/zh/install/index.md): full build notes (vcpkg or system packages, `install.sh`).
2. [Get started](docs/zh/get-started.md): the same steps, explained.
3. [Tutorial 01](docs/zh/tutorials/01-first-tree.md): folders as functions.

Connecting a real model and using your own Claude Code as an agent: coming in the next batch.

## Why folders

- Folder = function. Put an _entry in a folder and it can be called; its notes and data sit right next to it. <!-- copy:C1 -->
- Native to LLMs. Models already know how to read and write files and folders; there is no framework to learn. <!-- copy:C2 -->
- Rides on Linux. Permissions are file permissions; write tools in any language. <!-- copy:C3 -->
- Small parts, Unix style. A few small programs that each do one thing: exec, loop, daemon. <!-- copy:C4 -->
- Bring your own brain and body. A fake brain for trying, any OpenAI-compatible endpoint, or your own Claude Code as an agent in the tree. <!-- copy:C5 -->

## How small

- 12 C++ projects under `proto8/impls/` (aos-daemon, aos-exec, aos-loop, aos-fsm, aos-llm, ...). <!-- count: `ls -d proto8/impls/aos-*/ | wc -l` = 12, same as the number of aos-*/CMakeLists.txt -->
- The Python parts import only the standard library plus aos's own modules. <!-- count: grep of every import/from line under proto8/py, proto8/lib, proto8/cmd; no third-party names found. Grep-based, not a dependency audit -->

## Status

aos is a prototype. File formats and commands still change. Linux only (WSL2 works). One tree lives on one machine; trees do not talk to each other yet. <!-- copy:S1 -->

## Repository layout

| Folder | What it is |
|---|---|
| `proto8/` | the product: code, templates, knowledge, concepts |
| `docs/` | the documentation site (planned) |
| `wf/`, `archive/`, `impl_cpp/`, and `thinking/`, `user-advice/`, `notes/` inside `proto8/` | development history and working notes, not part of the product |

`AGENTS.md` and `CLAUDE.md` at the root are entry points for agents.

## Security

Agents run programs under your user account. Try aos in a throwaway account, container, or folder you do not mind losing. Sandboxing is experimental. <!-- copy:SEC -->

## License

TBD.
