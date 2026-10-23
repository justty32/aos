// files.cpp：【aos-util】路徑、讀檔、原子寫入（說明見 include/aos/files.hpp）。
//
// 為什麼要「原子寫入」：ctl 窗、state 窗是兩個行程透過檔案講話。如果直接打開舊檔、清空、再寫，
// 讀的人剛好在中間讀到，就會讀到半份（壞 JSON）或空的。改成「寫到旁邊的暫存檔 → rename 蓋過去」：
// rename 在同一個檔案系統裡是原子的，讀的人只會看到「整份舊的」或「整份新的」，不會看到一半。
// 暫存檔放在同一個資料夾（.名字.tmp），才保證在同一個檔案系統上（跨檔案系統的 rename 會失敗）。
#include "aos/files.hpp"

#include <cerrno>
#include <cstring>
#include <filesystem>
#include <sstream>

#include <fcntl.h>
#include <unistd.h>

namespace aos {

std::string abspath(const std::string& path) {
    std::string full = path;
    if (!path.starts_with('/')) {
        full = std::filesystem::current_path().string() + "/" + path;
    }
    std::vector<std::string> parts;
    std::istringstream in(full);
    std::string seg;
    while (std::getline(in, seg, '/')) {
        if (seg.empty() || seg == ".") {
            continue;
        }
        if (seg == "..") {
            if (!parts.empty()) {
                parts.pop_back();
            }
            continue;
        }
        parts.push_back(seg);
    }
    std::string out;
    for (const std::string& p : parts) {
        out += "/" + p;
    }
    if (out.empty()) {
        return "/";
    }
    return out;
}

std::string dirname(const std::string& path) {
    size_t slash = path.rfind('/');
    if (slash == std::string::npos) {
        return "";
    }
    std::string d = path.substr(0, slash + 1);
    while (d.size() > 1 && d.ends_with('/')) {
        d.pop_back();
    }
    return d;
}

std::string join(const std::string& a, const std::string& b) {
    if (b.starts_with('/') || a.empty()) {
        return b;
    }
    if (a.ends_with('/')) {
        return a + b;
    }
    return a + "/" + b;
}

std::optional<std::string> read_file(const std::string& path, int& errno_out) {
    int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        errno_out = errno;
        return std::nullopt;
    }
    std::string text;
    char buf[65536];
    while (true) {
        ssize_t n = read(fd, buf, sizeof buf);
        if (n < 0 && errno == EINTR) {
            continue;
        }
        if (n < 0) {
            errno_out = errno;   // 例如它是個資料夾（EISDIR）
            close(fd);
            return std::nullopt;
        }
        if (n == 0) {
            break;
        }
        text.append(buf, (size_t)n);
    }
    close(fd);
    errno_out = 0;
    return text;
}

std::optional<Json> read_json(const std::string& path) {
    int err = 0;
    std::optional<std::string> text = read_file(path, err);
    if (!text) {
        return std::nullopt;
    }
    Json doc = Json::parse(*text, nullptr, false);   // false＝不丟例外，壞的回 discarded
    if (doc.is_discarded()) {
        return std::nullopt;
    }
    return doc;
}

Spec split_hash(const std::string& spec) {
    size_t hash = spec.find('#');
    if (hash == std::string::npos) {
        return Spec{spec, ""};
    }
    std::string pointer = spec.substr(hash + 1);
    if (!pointer.starts_with('/')) {
        throw Error{code::CfgBad, "尋址要寫成 檔#/位置（# 後面要接 /）：" + spec};
    }
    return Spec{spec.substr(0, hash), pointer};
}

Json read_json_at(const std::string& path, const std::string& pointer) {
    int err = 0;
    std::optional<std::string> text = read_file(path, err);
    if (!text) {
        // 原因的寫法同 Python 的 OSError（`[Errno 2] No such file or directory: 'x'`），load_cfg 的一行跟 bin 版一樣
        throw Error{err == ENOENT ? code::CfgMissing : code::CfgBad,
                    "[Errno " + std::to_string(err) + "] " + std::strerror(err) + ": '" + path + "'"};
    }
    // 第一行 #!：換成空行（留著換行，JSON 錯誤訊息的行號才對得上）
    if (text->starts_with("#!")) {
        size_t nl = text->find('\n');
        if (nl == std::string::npos) {
            text->clear();
        } else {
            text->erase(0, nl);
        }
    }
    Json doc = Json::parse(*text, nullptr, false);
    if (doc.is_discarded()) {
        throw Error{code::CfgBad, "不是 JSON：" + path};
    }
    if (pointer.empty()) {
        return doc;
    }
    try {
        return doc.at(Json::json_pointer(pointer));
    } catch (const nlohmann::json::exception& e) {
        throw Error{code::CfgMissing, "指不到 " + path + "#" + pointer + "：" + e.what()};
    }
}

// 把 text 整份寫進 fd；失敗回 false（errno 留著）。
static bool write_all(int fd, const std::string& text) {
    size_t done = 0;
    while (done < text.size()) {
        ssize_t n = write(fd, text.data() + done, text.size() - done);
        if (n < 0 && errno == EINTR) {
            continue;
        }
        if (n < 0) {
            return false;
        }
        done += (size_t)n;
    }
    return true;
}

std::optional<std::string> write_json(const std::string& path, const Json& doc) {
    std::string dir = dirname(path);
    std::string name = path.substr(path.rfind('/') + 1);
    std::string tmp = join(dir, "." + name + ".tmp");

    // 1. 所在的資料夾沒有就建
    if (!dir.empty()) {
        std::error_code ec;
        std::filesystem::create_directories(dir, ec);
        if (ec) {
            return "建不了資料夾 " + dir + "：" + ec.message();
        }
    }
    // 2. 寫暫存檔
    std::string text = doc.dump(2, ' ', false, Json::error_handler_t::replace);
    int fd = open(tmp.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0666);
    if (fd < 0) {
        return "開不了 " + tmp + "：" + std::strerror(errno);
    }
    bool ok = write_all(fd, text);
    int saved = errno;
    if (close(fd) != 0 && ok) {
        ok = false;
        saved = errno;
    }
    // 3. 改名蓋過去（原子）
    if (ok && rename(tmp.c_str(), path.c_str()) == 0) {
        return std::nullopt;
    }
    if (ok) {
        saved = errno;
    }
    unlink(tmp.c_str());
    return "寫不了 " + path + "：" + std::strerror(saved);
}

}  // namespace aos
