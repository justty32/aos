# 這是 snippet，複製後改名（例如 todo.py），不要直接在這裡改。
"""一支 CLI 小程式的骨架：add／list／delete 三個子命令，資料存一個 JSON 檔。

測試可以直接 import：main(["--file", "/tmp/x.json", "add", "買牛奶"]) 回退出碼，
不必開子行程，也不會動到真正的資料檔。
"""
import argparse
import sys

from json_store import load, save  # SNIPPET-MERGE: json_store

DEFAULT_FILE = "items.json"


def _items(path):
    data = load(path, {"items": []})
    items = data.get("items") if isinstance(data, dict) else None
    return items if isinstance(items, list) else []


def cmd_add(args):
    items = _items(args.file)
    new_id = max([int(row.get("id") or 0) for row in items], default=0) + 1
    items.append({"id": new_id, "text": args.text})
    save(args.file, {"items": items})
    print("added %d %s" % (new_id, args.text))
    return 0


def cmd_list(args):
    items = _items(args.file)
    if not items:
        print("(empty)")
        return 0
    for row in items:
        print("%s\t%s" % (row.get("id"), row.get("text") or ""))
    return 0


def cmd_delete(args):
    items = _items(args.file)
    kept = [row for row in items if str(row.get("id")) != str(args.id)]
    if len(kept) == len(items):
        print("no such id: %s" % args.id, file=sys.stderr)
        return 1
    save(args.file, {"items": kept})
    print("deleted %s" % args.id)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="一支小 CLI：加一筆、列出來、刪掉一筆。")
    parser.add_argument("--file", default=DEFAULT_FILE, help="資料檔路徑，預設 items.json")
    sub = parser.add_subparsers(dest="command")
    add = sub.add_parser("add", help="加一筆")
    add.add_argument("text", help="內容")
    add.set_defaults(fn=cmd_add)
    listing = sub.add_parser("list", help="列出全部")
    listing.set_defaults(fn=cmd_list)
    delete = sub.add_parser("delete", help="刪掉一筆")
    delete.add_argument("id", help="要刪的編號")
    delete.set_defaults(fn=cmd_delete)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "fn", None):
        parser.print_help()
        return 2
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
