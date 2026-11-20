"""links_check - defs check 的「斷掉的連結」：定義夾最上層有連結（symlink）指到不在的東西＝一條 problem（編譯程式庫第 4 刀，線 aos-pylib-k4-1120）。

defs.extern 編成連結之後（使用者 11-20「創建一個symlink…編譯的時候就是只生成symlink」，設計稿 thinking/2026-11/20/aos-pylib-plan-1120/05），
定義夾被搬、被抄、目標被刪，連結就斷；斷掉的 system.txt 執行時是靜靜地沒有 system 文字，只有 check 會說。
catalog.check 先叫這支：有斷鏈就只報斷鏈（一個一條），其餘會順著它去讀的檢查等修好再查（Argon A9：不然同一個斷鏈會被當缺檔再報一次）。
只看最上層（宣告的檔都在那裡），不往子夾走；只讀。"""
import os


def broken(path):
    """[(名字, 連結裡存的字)]：path 最上層斷掉的連結，照名字排。"""
    out = []
    for name in sorted(os.listdir(path)):
        p = os.path.join(path, name)
        if os.path.islink(p) and not os.path.exists(p):
            out.append((name, os.readlink(p)))
    return out


def check(path, problem):
    """每個斷鏈報一條；回有沒有斷鏈（有＝呼叫方不再往下查）。"""
    found = broken(path)
    for name, target in found:
        problem('%s is a link to %s, which is not there (a defs.extern target moved or deleted?); the other checks of this '
                'definition wait until it is fixed' % (name, target))
    return bool(found)
