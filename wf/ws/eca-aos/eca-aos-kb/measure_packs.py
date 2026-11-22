# measure_packs.py - characters per tool pack as sent to the brain, for the table in proto8/knowledge/aos/packs.md
# Usage: python3 -I measure_packs.py /home/lorkhan/repo/aos/proto8
# Per tool: len(json.dumps({"type": "function", "function": {name, description, parameters}}, ensure_ascii=False)), summed per pack.
# 2026-11-22: this formula reproduced the old table exactly for the six optional packs (events, subagent, def, jsonx, comm, ws-write).
import json, os, sys

PACKS = ["look", "change", "delete", "shell", "gadgets", "todo", "self", "mailbox", "goal", "json", "index",
         "events", "subagent", "def", "jsonx", "comm", "ws-write", "kernel_gate"]


def main():
    home = sys.argv[1]
    for pack in PACKS:
        with open(os.path.join(home, "lib/packs", pack + ".json")) as f:
            tools = json.load(f)["tools"]
        total = 0
        for name, entry in tools.items():
            path = entry["path"]
            path = home + path["$path"] if isinstance(path, dict) else path
            with open(os.path.join(path, "_tooldef.json")) as f:
                tooldef = json.load(f)
            sent = {"type": "function", "function": {"name": name, "description": tooldef.get("description", ""),
                                                     "parameters": tooldef.get("parameters", {})}}
            total += len(json.dumps(sent, ensure_ascii=False))
        print("%s\t%d\t%s" % (pack, len(tools), format(total, ",")))


if __name__ == "__main__":
    main()
