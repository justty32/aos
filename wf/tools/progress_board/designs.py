"""Merge hand-written fable design cards with auto-discovered fable design files for the designs page."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
DEFAULT_GLOBS = ["proto8/thinking/**/*fable*.md"]


def first_line(path):
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                text = re.sub(r"<!--|-->|^#+\s*", "", line).strip()
                if text:
                    return text[:160]
    except OSError:
        pass
    return ""


def designs_state(cfg):
    options = cfg.get("designs", {})
    repo = Path(cfg.get("aos_repo", "~/repo/simple_tools/aos")).expanduser()
    source = ROOT / options.get("file", "designs.json")
    warnings, cards = [], []
    try:
        table = json.loads(source.read_text(encoding="utf-8"))
        cards = [row for row in table.get("rows", []) if isinstance(row, dict) and row.get("doc")]
    except (OSError, ValueError, AttributeError) as error:
        warnings.append(f"Design cards unreadable: {error}")
    known = {card["doc"] for card in cards}
    found = set()
    for pattern in options.get("globs", DEFAULT_GLOBS):
        for path in repo.glob(pattern):
            if path.is_file():
                found.add(path.relative_to(repo).as_posix())
    for card in cards:
        card["exists"] = card["doc"] in found or (repo / card["doc"]).is_file()
        card["pending"] = False
    for doc in sorted(found - known):
        date = re.search(r"(\d{4})-(\d{2})/(\d{2})/", doc)
        cards.append({"id": doc, "doc": doc, "order": 1000, "pending": True, "exists": True,
                      "title": f"{Path(doc).parent.name}／{Path(doc).stem}", "topic": Path(doc).parent.name,
                      "date": f"{date[1]}-{date[2]}-{date[3]}" if date else "",
                      "conclusion": first_line(repo / doc)})
    written = sorted((card for card in cards if not card["pending"]),
                     key=lambda card: (int(card.get("order") or 1000), card["doc"]))
    pending = sorted((card for card in cards if card["pending"]),
                     key=lambda card: card.get("date", ""), reverse=True)
    cards = written + pending
    return {"repo": str(repo), "cards": cards, "pending": len(pending), "warnings": warnings}


def write_designs(board_dir, cfg, atomic_write):
    encoded = json.dumps(designs_state(cfg), ensure_ascii=False)
    data = Path(board_dir) / "data"
    atomic_write(data / "designs.json", encoded + "\n")
    atomic_write(data / "designs.js", "window.AOS_DESIGNS = " + encoded + ";\n")
