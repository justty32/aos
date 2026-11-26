// trees.cpp：aos-procfs-demo 測試用的 trees/——掛上之後隨時加一整棵夾（模擬 daemon 的 procs/<名>/）、用 remove_tree 拿掉。
#include "trees.hpp"

#include <atomic>
#include <memory>
#include <string>

namespace pf = aos::procfs;

void demo_trees_setup(pf::Fs& fs, pf::Ctl& ctl) {
    fs.add_dir("trees");
    // tree NAME：trees/NAME/{info, count, sub/deep, link -> info}；count 每開一次加 1（看得出讀的是不是開檔那刻那份）
    ctl.on("tree", [&fs](const pf::Command& c) {
        std::string d = "trees/" + c.words[1];
        auto n = std::make_shared<std::atomic<long>>(0);
        bool made = false;
        try {
            fs.add_dir(d);
            made = true;
            fs.add_text(d + "/info", [name = c.words[1]] { return "tree: " + name + "\n"; });
            fs.add_text(d + "/count", [n] { return std::to_string(++*n) + "\n"; });
            fs.add_dir(d + "/sub");
            fs.add_text(d + "/sub/deep", [] { return std::string("deep\n"); });
            fs.add_symlink(d + "/link", "info");
        } catch (const std::exception& e) {
            if (made) fs.remove_tree(d);   // 加到一半失敗就不留半棵；add_dir 就失敗（同名已經在）的那棵不是這次加的，不動
            return pf::Result::failed(std::string("TreeFailed ") + e.what());
        }
        return pf::Result::done();
    }, [](const pf::Command& c) -> std::string {
        return c.words.size() == 2 && c.words[1].find('/') == std::string::npos ? "" : "ArgumentsBad tree NAME";
    });
    // rmtree PATH：相對於掛載點根的任何路徑
    ctl.on("rmtree", [&fs](const pf::Command& c) {
        try {
            if (fs.remove_tree(c.words[1])) return pf::Result::done();
        } catch (const std::exception& e) {
            return pf::Result::failed(std::string("RemoveRefused ") + e.what());
        }
        return pf::Result::failed("RemoveRefused " + c.words[1] + " (missing, the root, or holds a ctl or mailbox)");
    }, [](const pf::Command& c) -> std::string {
        return c.words.size() == 2 ? "" : "ArgumentsBad rmtree PATH";
    });
}
