#!/usr/bin/env python3
"""校準用：從 golden/ 做 3 份故意弄壞的版本到 calib/broken/<批號>/。

每人：刪兩個事實、編一個假事實、改一個行號（指到錯的段落，不超界）。
用法：python make_broken.py
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

BREAKS = {
    ("100", "伊萬"): {
        "entry": [
            ("當烏薩斯取消當年所有冰原考察許可時，他從麥哲倫口中取得失蹤科考隊坐標，卻立刻以烏薩斯方言向神秘同僚報告，並奉命盯梢她、等待調查其背景與價值", "（刪 1）"),
            ("他表面友善、甚至答應日後教她故鄉方言，實際則持續與同僚以方言通訊，要把她交給邊防軍和調查隊，作為熟悉冰原的向導", "（刪 2）"),
            ("他的正式官署、軍階、族裔", "伊萬曾在烏薩斯第四集團軍服役十年，以中尉軍銜退役。（假）他的正式官署、軍階、族裔"),
        ],
        "evidence": ("lore/evidence/characters/伊萬.md", "act15mini_眠于树影之中.md` L73-L103", "act15mini_眠于树影之中.md` L300-L330"),
    },
    ("143", "羅索"): {
        "entry": [
            ("，又因證據遭銷毀、恩佐背後的家族關係而宣告其無罪", "（刪 1）"),
            ("恩佐承認傷害茱莉亞與走私後，羅索偽裝成殺手準備處決他，卻被跟蹤而來的萊昂圖索阻止；", "（刪 2）"),
            ("羅索其實已從法律守護者", "羅索年輕時曾任薩盧佐家族的首席律師，後因良心不安辭職。（假）羅索其實已從法律守護者"),
        ],
        "evidence": ("lore/evidence/characters/羅索/庭審、私刑與死亡邊界.md", "`story_vigil_2_1.txt` L23-L111", "`story_vigil_2_1.txt` L600-L688"),
    },
    ("79", "奧克里·珀森斯"): {
        "entry": [
            ("高登識破費爾南後，為掩蓋自身安保失誤，先以補償為名將本尊帶走，實際把他囚禁在貴賓室。", "（刪 1）"),
            ("娜斯提的巨型裝置樹升空，使三人連同貨物一起暴露，他與費爾南第二次回到同一間牢房。", "（刪 2）"),
            ("浮空層遭引爆時，", "事故後他被梅蘭德追究洩密責任，判入獄三年。（假）浮空層遭引爆時，"),
        ],
        "evidence": ("lore/evidence/characters/奧克里·珀森斯/經歷與結局.md", "`act47side_未许之地.md` L453-L459", "`act47side_未许之地.md` L1453-L1459"),
    },
}


def main() -> int:
    for (batch, name), spec in BREAKS.items():
        src = HERE / "golden" / batch
        dst = HERE / "calib" / "broken" / batch
        entry = f"lore/characters/{name}.md"
        paths = [entry] + [str(p.relative_to(src)) for p in (src / "lore/evidence/characters").glob(f"{name}*") if p.is_file()]
        paths += [str(p.relative_to(src)) for p in (src / "lore/evidence/characters" / name).rglob("*.md")] if (src / "lore/evidence/characters" / name).is_dir() else []
        for rel in paths:
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / rel, dst / rel)
        text = (dst / entry).read_text(encoding="utf-8")
        for old, new in spec["entry"]:
            assert old in text, (name, old[:20])
            new = "" if new.startswith("（刪") else new.replace("（假）", "")
            text = text.replace(old, new, 1)
        (dst / entry).write_text(text, encoding="utf-8")
        ef, old, new = spec["evidence"]
        et = (dst / ef).read_text(encoding="utf-8")
        assert old in et, (name, old)
        (dst / ef).write_text(et.replace(old, new, 1), encoding="utf-8")
        print(f"{batch}/{name}：刪 2、編 1、改行號 {old.split()[-1]}→{new.split()[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
