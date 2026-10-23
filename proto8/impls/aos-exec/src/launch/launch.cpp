// launch.cpp：【launch】開跑（說明見 launch.hpp）。cd 已經在 hop 做完（cwd＝入口檔所在的資料夾）。
//
// 可執行檔、argv 陣列都用 glibc 的 execvp：+x 但沒 #! 的檔 kernel 回 ENOEXEC，execvp 會改用
// `/bin/sh 那個檔 args...` 再跑（ideas § 22，使用者「乙」）。argv[0] 沒 '/' 時照 PATH 找（空的一段＝目前資料夾；
// 沒設 PATH＝/bin:/usr/bin；某段 EACCES 換下一段），可執行檔入口給的是絕對路徑、不找 PATH。
// argv 陣列：開跑前解指示詞（$env／$ref，$ref 從入口檔所在的資料夾算＝cwd），解完要全是字串（10-20 ideas D2、D8）；
// argv[0] 帶 / 又 exec 不了＝前面插 aos-exec（argv0，D3）。
// inst 單子（run_inst，src/inst/）的 argv[0] 由 libaos 的 execvp 跑，同樣會退回 sh。
#include "launch/launch.hpp"

#include "aos/directive.hpp"
#include "aos/files.hpp"

#include <cerrno>
#include <cstring>

#include <sys/stat.h>
#include <unistd.h>

namespace aos::exec {

static std::vector<char*> c_argv(const std::vector<std::string>& argv) {
    std::vector<char*> out;
    for (const std::string& a : argv) {
        out.push_back(const_cast<char*>(a.c_str()));
    }
    out.push_back(nullptr);
    return out;
}

static Error launch_failed(const std::string& what, int err) {
    std::string msg = "起不來：" + what + "（" + std::strerror(err) + "）";
    return Error{code::LaunchFailed, msg};
}

// execvp；成功不回來，失敗丟 LaunchFailed。
[[noreturn]] static void exec_vp(const std::string& prog, std::vector<char*>& cargv) {
    execvp(prog.c_str(), cargv.data());
    throw launch_failed(prog, errno);
}

std::vector<std::string> argv0(const std::vector<std::string>& argv, const std::string& cwd) {
    if (argv.empty() || argv[0].find('/') == std::string::npos) {
        return argv;
    }
    std::string p = argv[0];
    if (!p.starts_with('/')) {
        p = cwd + "/" + p;
    }
    struct stat st;
    bool runnable = stat(p.c_str(), &st) == 0 && S_ISREG(st.st_mode) && access(p.c_str(), X_OK) == 0;
    if (argv[0].find("#/") == std::string::npos && runnable) {
        return argv;
    }
    std::vector<std::string> out{"aos-exec"};
    out.insert(out.end(), argv.begin(), argv.end());
    return out;
}

// argv 陣列解指示詞、驗全是字串。錯＝EntryBad（入口壞）。指示詞在六個 AOS_* 設好、.env 讀完之後解；$ref 從入口檔所在的資料夾算。
static std::vector<std::string> argv_of(const Json& doc, const std::string& dir) {
    Json v;
    try {
        v = aos::resolve(doc, dir);
    } catch (const Error& e) {
        throw Error{code::EntryBad, "入口壞：argv 陣列的指示詞解不開：" + e.msg};
    }
    std::vector<std::string> out;
    for (const Json& a : v) {
        if (!a.is_string()) {
            throw Error{code::EntryBad, "入口壞：argv 陣列解完要全是字串：" + aos::dumps(v)};
        }
        out.push_back(a.get<std::string>());
    }
    return out;
}

int launch(const Found& found, const std::vector<std::string>& args) {
    std::string dir = aos::dirname(found.file);   // hop 已經 cd 到這裡
    if (found.kind == Kind::Inst) {
        try {
            return run_inst(found.doc, dir, args).code;
        } catch (const Error& e) {
            throw Error{e.code, "單子跑不起來：" + e.msg};   // 代號照舊分種類
        }
    }
    std::vector<std::string> argv;
    if (found.kind == Kind::Executable) {
        argv.push_back("./" + found.file.substr(found.file.rfind('/') + 1));
        argv.insert(argv.end(), args.begin(), args.end());
        std::vector<char*> cargv = c_argv(argv);
        exec_vp(found.file, cargv);
    }
    argv = argv_of(found.doc, dir);
    argv.insert(argv.end(), args.begin(), args.end());
    argv = argv0(argv, dir);
    std::vector<char*> cargv = c_argv(argv);
    exec_vp(argv[0], cargv);
}

}  // namespace aos::exec
