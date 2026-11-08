"""Copy board pages and the current reference style with a bundled offline fallback."""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent


def copy_assets(board_dir):
    board = Path(board_dir)
    board.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "app.js", "asks.js", "eli5.js", "md.js", "detail.html", "detail.js", "style.css"):
        shutil.copyfile(ROOT / "web" / name, board / name)
    for name in ("rounds.html", "rounds.js", "rounds.css", "designs.html", "designs.js", "designs.css",
                 "forum.html", "forum.js", "forum.css",
                 "guide.html", "guide-detail.html", "guide-play.html", "guide.css", "guide.js"):
        if (ROOT / "web" / name).is_file():
            shutil.copyfile(ROOT / "web" / name, board / name)
    (board / "assets").mkdir(exist_ok=True)
    reference = Path("~/Desktop/aos-arknights/assets/style.css").expanduser()
    source = reference if reference.is_file() else ROOT / "web/ak-style.fallback.css"
    try:
        shutil.copyfile(source, board / "assets/ak-style.css")
    except OSError:
        if source != reference:
            raise
        shutil.copyfile(ROOT / "web/ak-style.fallback.css", board / "assets/ak-style.css")
    shutil.copyfile(ROOT / "README.md", board / "README.md")

