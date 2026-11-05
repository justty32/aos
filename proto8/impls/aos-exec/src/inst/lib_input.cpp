// lib_input.cpp：【inst】Inst → libaos 的單子（aos_inst_input_t）。
//
// libaos 只收絕對路徑、環境要給完整一份，所以這裡先做好：
//   1. cwd：從 base_dir 算；沒寫＝base_dir。cwd_mkdir＝先 mkdir -p；存不存在由 libaos 檢查（CwdMissing）
//   2. stdin／stdout／stderr：有寫＝從解出來的 cwd 算的絕對路徑；沒寫＝inherits（接呼叫者的 fd 0／1／2）；
//      stdout_mkdir／stderr_mkdir＝先 mkdir -p 那個檔的上層資料夾。建不了＝MkdirFailed
//   3. 環境：envs 有東西＝現有環境（被 envs 蓋掉的名字跳過）＋envs；沒有＝傳 NULL 沿用；
//      envs_clear＝現有環境只留 aos-exec 的六個 AOS_*（有設的）＋envs（PATH 也不留）
//   4. 填單子：appends、stderr_merge→merge（又寫 stderr＝libaos 報 PathConflict）、timeout_ms（0＝不限）、grace_ms、
//      new_session＝true（自成行程群組，逾時整群收）
// 路徑的接法用 aos-util 的 aos::join（照 Python 的 os.path.join）。
// 從 impls/aos-inst 的 src/libaos/lib_input.cpp 抄來改（串流沒寫改成 inherits；*_mkdir、envs_clear、stderr_merge 11-04 補回）。
#include "inst/inst.hpp"

#include "aos/files.hpp"

#include <filesystem>
#include <set>

extern char** environ;

namespace aos::exec {

// envs_clear 之後還留著的：aos-exec 的六個（N-57）。
static const std::set<std::string> kept_on_clear = {"AOS_ENTRY", "AOS_WS", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO"};

// 子程式的完整環境 "K=V"：現有的（被 envs 蓋掉的跳過；envs_clear＝只留那六個）＋envs。
static std::vector<std::string> build_env(const Inst& inst) {
    std::vector<std::string> out;
    for (char** e = environ; *e != nullptr; ++e) {
        std::string kv = *e;
        std::string name = kv.substr(0, kv.find('='));
        if (inst.envs_clear && !kept_on_clear.contains(name)) {
            continue;
        }
        if (!inst.envs.contains(name)) {
            out.push_back(kv);
        }
    }
    for (auto& [k, v] : inst.envs) {
        out.push_back(k + "=" + v);
    }
    return out;
}

// mkdir -p dir；建不了 MkdirFailed（key＝哪個 *_mkdir）。
static void mkdir_p(const std::string& dir, const char* key) {
    std::error_code ec;
    std::filesystem::create_directories(dir, ec);
    if (ec || !std::filesystem::is_directory(dir)) {
        throw Error{code::MkdirFailed, std::string("inst ") + key + ": cannot create " + dir + " (" + ec.message() + ")"};
    }
}

void build_lib_input(const Inst& inst, const std::string& base_dir, LibInput& out) {
    // 1. cwd
    out.cwd = base_dir;
    if (inst.cwd) {
        out.cwd = join(base_dir, *inst.cwd);
    }
    if (inst.mkdirs[0]) {
        mkdir_p(out.cwd, "cwd_mkdir");
    }

    // 2. 三個串流
    const char* mkdir_keys[3] = {nullptr, "stdout_mkdir", "stderr_mkdir"};
    for (int i = 0; i < 3; ++i) {
        if (inst.paths[i]) {
            out.paths[i] = join(out.cwd, *inst.paths[i]);
            if (i > 0 && inst.mkdirs[i]) {
                mkdir_p(dirname(*out.paths[i]), mkdir_keys[i]);
            }
        }
    }

    // 3. argv、環境
    for (auto& a : inst.argv) {
        out.argv.push_back(a.c_str());
    }
    out.argv.push_back(nullptr);
    bool own_env = !inst.envs.empty() || inst.envs_clear;
    if (own_env) {
        out.env_strings = build_env(inst);
        for (auto& e : out.env_strings) {
            out.envp.push_back(e.c_str());
        }
        out.envp.push_back(nullptr);
    }

    // 4. 填單子（指標都指到 out 自己的欄位，所以 out 不能搬）
    out.in.argv = out.argv.data();
    out.in.cwd = out.cwd.c_str();
    out.in.envs = nullptr;
    if (own_env) {
        out.in.envs = out.envp.data();
    }
    for (int i = 0; i < 3; ++i) {
        out.in.paths[i] = nullptr;
        out.in.inherits[i] = !out.paths[i] && !(i == 2 && inst.merge);   // 併進 stdout 就不接呼叫者的 fd 2
        if (out.paths[i]) {
            out.in.paths[i] = out.paths[i]->c_str();
        }
        out.in.appends[i] = inst.appends[i];
    }
    out.in.merge = inst.merge;
    out.in.timeout_ms = inst.timeout_ms;
    out.in.grace_ms = inst.grace_ms;
    out.in.new_session = true;
}

}  // namespace aos::exec
