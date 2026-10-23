// find.cpp：【find】一跳（hop）——說明見 find.hpp。對應 proto8/bin/aos-exec 的 locate、hop（10-21 ideas § 4～§ 7）。
// 這裡會 chdir、setenv（.env 要在挑入口之前讀，挑入口又要看讀完之後的 $AOS_ENTRY，拆不成純計算）。
#include "find/find.hpp"

#include "env/env.hpp"
#include "aos/files.hpp"

#include <cerrno>
#include <climits>
#include <cstdlib>
#include <cstring>

#include <sys/stat.h>
#include <unistd.h>

namespace aos::exec {

std::string entry_name() {
    const char* v = std::getenv("AOS_ENTRY");
    if (v == nullptr || v[0] == '\0') {
        return "_entry";
    }
    return v;
}

void Layer::apply() const {
    if (flag_ws) {
        setenv("AOS_WS", ws.c_str(), 1);
    }
}

namespace {

bool is_dir(const std::string& path) {
    struct stat st;
    return stat(path.c_str(), &st) == 0 && S_ISDIR(st.st_mode);
}

bool is_file(const std::string& path) {
    struct stat st;
    return stat(path.c_str(), &st) == 0 && S_ISREG(st.st_mode);
}

bool lexists(const std::string& path) {
    struct stat st;
    return lstat(path.c_str(), &st) == 0;
}

// 解開捷徑的絕對路徑；解不開（不在）＝空字串。
std::string real(const std::string& path) {
    char buf[PATH_MAX];
    if (realpath(path.c_str(), buf) == nullptr) {
        return "";
    }
    return buf;
}

// 最後一段（basename）裡有沒有 `.`
bool has_extension(const std::string& path) {
    size_t slash = path.rfind('/');
    std::string base = path;
    if (slash != std::string::npos) {
        base = path.substr(slash + 1);
    }
    return base.find('.') != std::string::npos;
}

// XXX → 資料夾（dir 非空）或 實際的檔＋指標（file 非空）。資料夾裡的入口檔這時還不挑（讀完 .env 才挑）。
struct Located {
    std::string dir;
    std::string file;
    std::string pointer;
};

Located locate(const std::string& spec, const std::string& base) {
    Spec s;
    try {
        s = split_hash(spec);
    } catch (const Error&) {
        throw Error{code::EntryBad, "入口壞：" + spec + " 的 # 後面要接 /"};
    }
    std::string p = join(base, s.path);
    Located out;
    if (is_dir(p)) {
        if (!s.pointer.empty()) {
            throw Error{code::EntryBad, "入口壞：資料夾不能帶 #/：" + spec};
        }
        out.dir = real(p);
        return out;
    }
    std::string f;
    if (is_file(p)) {
        f = p;
    } else if (!lexists(p) && !has_extension(s.path) && is_file(p + ".json")) {
        f = p + ".json";
    } else {
        throw Error{code::EntryMissing, "入口不存在：" + spec};
    }
    out.file = real(f);
    out.pointer = s.pointer;
    return out;
}

// 走進一層：設 AOS_CF／AOS_CD／AOS_CO、cd、讀 .env（什麼都能設、含 AOS_*；已經 cd 過，改 AOS_CD 不會再 cd）、旗標蓋回。
// 走進那一刻 $AOS_ENTRY 是 `.env`＝那份 .env 是入口、不讀成環境。回 .env 設過的名字。
std::set<std::string> enter(const std::string& dir, const std::string& cf, const Layer& layer) {
    setenv("AOS_CF", cf.c_str(), 1);
    setenv("AOS_CD", dir.c_str(), 1);
    setenv("AOS_CO", "", 1);
    if (chdir(dir.c_str()) != 0) {
        throw Error{code::Internal, "cd 不進 " + dir + "：" + std::strerror(errno)};
    }
    std::set<std::string> names;
    if (entry_name() != ".env") {
        names = load_env(dir, layer.dotenv_override);
    }
    layer.apply();
    return names;
}

void mark(std::set<std::string>& visited, const std::string& dir) {
    if (visited.count(dir) > 0) {
        throw Error{code::EntryBad, "入口壞：資料夾繞圈：" + dir};
    }
    visited.insert(dir);
}

}  // namespace

Found hop(const std::string& spec, const std::string& base, const std::string& ws_flag, bool dotenv_override,
          Chain& chain) {
    Layer layer;
    layer.dotenv_override = dotenv_override;
    layer.flag_ws = !(ws_flag == "-" || ws_flag.empty());
    std::string ws = check_ws(ws_flag);
    layer.ws = ws;
    Located loc = locate(spec, base);
    setup_stack(ws);

    std::string f = loc.file;
    std::set<std::string> names;
    if (f.empty()) {
        std::string d = loc.dir;
        names = enter(d, d, layer);
        std::set<std::string> visited{d};
        while (f.empty()) {
            std::string name = entry_name();
            std::vector<std::string> parts;   // 空的段不算（尾巴的 /、//）；全是 /＝.
            size_t i = 0;
            while (i <= name.size()) {
                size_t j = name.find('/', i);
                if (j == std::string::npos) {
                    j = name.size();
                }
                if (j > i) {
                    parts.push_back(name.substr(i, j - i));
                }
                i = j + 1;
            }
            if (parts.empty()) {
                parts.push_back(".");
            }
            for (size_t k = 0; k + 1 < parts.size(); ++k) {   // 多段的 $AOS_ENTRY（例 sub/run）：沿路的資料夾都走進去（由外到內）
                std::string nxt = real(join(d, parts[k]));
                if (nxt.empty() || !is_dir(nxt)) {
                    throw Error{code::EntryMissing, "入口不存在：" + join(d, name) + "（" + join(d, parts[k]) + " 不是資料夾）"};
                }
                if (nxt != d) {   // . 不算走進新資料夾；走回走過的（例 sub/../sub/run）＝繞圈
                    mark(visited, nxt);
                    d = nxt;
                    names = enter(nxt, nxt, layer);
                }
            }
            std::string last = join(d, parts.back());
            if (is_dir(last)) {   // 挑到資料夾＝走進去，照當下的 $AOS_ENTRY 再挑
                std::string nxt = real(last);
                mark(visited, nxt);
                d = nxt;
                names = enter(nxt, nxt, layer);
                continue;
            }
            if (!lexists(last)) {
                last += ".json";
            }
            if (!is_file(last)) {
                throw Error{code::EntryMissing,
                            "入口不存在：" + join(d, parts.back()) + "（也沒有 " + parts.back() + ".json）"};
            }
            f = real(last);
        }
        if (names.count("AOS_CF") == 0) {
            setenv("AOS_CF", f.c_str(), 1);
        }
        std::string fd = dirname(f);
        if (fd != d) {   // 入口檔是指到別處的捷徑：cd 到實際的資料夾，那邊的 .env 不讀
            if (chdir(fd.c_str()) != 0) {
                throw Error{code::Internal, "cd 不進 " + fd + "：" + std::strerror(errno)};
            }
            if (names.count("AOS_CD") == 0) {
                setenv("AOS_CD", fd.c_str(), 1);
            }
        }
    } else {
        names = enter(dirname(f), f, layer);
    }

    Classified c = classify(f, loc.pointer, chain, layer);
    const std::set<std::string>& last = c.read_env ? c.names : names;   // 只看最後讀的那一份自己設了沒（10-21 ideas § 7）
    if (last.count("AOS_CF") == 0) {
        setenv("AOS_CF", f.c_str(), 1);
    }
    if (last.count("AOS_CD") == 0) {
        setenv("AOS_CD", dirname(f).c_str(), 1);
    }
    if (last.count("AOS_CO") == 0) {
        setenv("AOS_CO", c.at.c_str(), 1);
    }
    Found out;
    out.kind = c.kind;
    out.file = f;
    out.doc = c.doc;
    return out;
}

}  // namespace aos::exec
