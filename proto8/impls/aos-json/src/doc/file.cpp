// file.cpp：【doc】讀一份 JSON 檔、照原樣寫回去。
//
// 「照原樣」做得到的只有這幾件（nlohmann 不記原文的位置，做不到逐字保留，取捨寫在 README「排版」）：
//   - 第一行 #!（aos 的設定檔可以當入口，第一行 #! 跳過，同 aos-util 的 read_json_at）整行留著
//   - key 的順序（ordered_json）
//   - 一行寫完的檔寫回一行；多行的看第一個有縮排的行，猜每層幾個空白（或 tab），整份照這個縮排重排
//   - 結尾有沒有換行、檔的權限（入口要 +x）
//   - 捷徑：寫到捷徑指的那份檔，捷徑本身不動
#include "doc/doc.hpp"

#include "aos/files.hpp"

#include <cerrno>
#include <cstdlib>
#include <cstring>

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace aos::json {

static std::string real_path(const std::string& p) {
    char* r = ::realpath(p.c_str(), nullptr);
    if (r == nullptr) {
        return p;
    }
    std::string s = r;
    std::free(r);
    return s;
}

// 多行的檔：第一個「換行後接空白再接字」的行，那段空白就是一層。
static void guess_layout(const std::string& text, File& f) {
    size_t end = text.find_last_not_of(" \t\r\n");
    std::string body = end == std::string::npos ? "" : text.substr(0, end + 1);
    f.final_newline = !text.empty() && text.back() == '\n';
    if (body.find('\n') == std::string::npos) {
        f.one_line = true;
        return;
    }
    f.one_line = false;
    size_t i = 0;
    while ((i = body.find('\n', i)) != std::string::npos) {
        i += 1;
        size_t j = i;
        while (j < body.size() && (body[j] == ' ' || body[j] == '\t')) {
            j += 1;
        }
        if (j > i && j < body.size() && body[j] != '\n' && body[j] != '\r') {
            f.indent_char = body[i];
            f.indent = 0;
            for (size_t k = i; k < j && body[k] == f.indent_char; ++k) {
                f.indent += 1;
            }
            return;
        }
    }
}

File load_file(const std::string& path, bool allow_missing) {
    File f;
    f.given = aos::abspath(path);
    f.real = real_path(f.given);
    struct stat st;
    if (::stat(f.real.c_str(), &st) != 0) {
        if (errno == ENOENT && allow_missing) {
            return f;
        }
        if (errno == ENOENT) {
            throw Error{code::FileMissing, "檔不在：" + path};
        }
        throw Error{code::FileBad, "讀不了 " + path + "：" + std::strerror(errno)};
    }
    if (S_ISDIR(st.st_mode)) {
        throw Error{code::FileBad, path + " 是資料夾"};
    }
    int err = 0;
    std::optional<std::string> text = aos::read_file(f.real, err);
    if (!text) {
        throw Error{code::FileBad, "讀不了 " + path + "：" + std::strerror(err)};
    }
    std::string body = *text;
    if (body.starts_with("#!")) {
        size_t nl = body.find('\n');
        f.shebang = nl == std::string::npos ? body + "\n" : body.substr(0, nl + 1);
        body = nl == std::string::npos ? "" : body.substr(nl + 1);
    }
    f.doc = Json::parse(body, nullptr, false);
    if (f.doc.is_discarded()) {
        throw Error{code::FileBad, path + " 不是 JSON"};
    }
    guess_layout(body, f);
    f.body = body;
    f.exists = true;
    f.mode = st.st_mode & 07777;
    return f;
}

std::string render_body(const File& f, const Json& before) {
    if (!f.body.empty()) {
        std::optional<std::string> s = splice(f, before, f.doc);
        if (s) {
            return *s;
        }
    }
    std::string out;
    if (f.one_line) {
        out += aos::dumps(f.doc);
    } else {
        out += f.doc.dump(f.indent, f.indent_char);
    }
    if (f.final_newline) {
        out += "\n";
    }
    return out;
}

static mode_t new_file_mode() {
    mode_t mask = ::umask(0);
    ::umask(mask);
    return 0666 & ~mask;
}

void save_file(const File& f) {
    std::string text = f.shebang + f.body;
    std::string dir = aos::dirname(f.real);
    std::string name = f.real.substr(f.real.rfind('/') + 1);
    std::string tmp = aos::join(dir, "." + name + "." + std::to_string(::getpid()) + ".tmp");
    int fd = ::open(tmp.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (fd < 0) {
        throw Error{code::WriteFailed, "寫不了 " + tmp + "：" + std::strerror(errno)};
    }
    std::string why;
    if (::fchmod(fd, f.exists ? f.mode : new_file_mode()) != 0) {
        why = std::string("設權限：") + std::strerror(errno);
    }
    size_t done = 0;
    while (why.empty() && done < text.size()) {
        ssize_t n = ::write(fd, text.data() + done, text.size() - done);
        if (n < 0 && errno == EINTR) {
            continue;
        }
        if (n < 0) {
            why = std::strerror(errno);
            break;
        }
        done += (size_t)n;
    }
    if (why.empty() && ::fsync(fd) != 0) {
        why = std::strerror(errno);
    }
    if (::close(fd) != 0 && why.empty()) {
        why = std::strerror(errno);
    }
    if (why.empty() && ::rename(tmp.c_str(), f.real.c_str()) != 0) {
        why = std::strerror(errno);
    }
    if (!why.empty()) {
        ::unlink(tmp.c_str());
        throw Error{code::WriteFailed, "寫不了 " + f.real + "：" + why};
    }
}

File& Docs::open(const std::string& path, bool allow_missing) {
    std::string real = real_path(aos::abspath(path));
    auto it = files.find(real);
    if (it != files.end()) {
        return it->second;
    }
    File f = load_file(path, allow_missing);
    return files.emplace(f.real, std::move(f)).first->second;
}

}  // namespace aos::json
