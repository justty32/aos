// lib_input.cpp：【inst】Inst → libaos 的單子（aos_inst_input_t）。
//
// libaos 只收絕對路徑、環境要給完整一份，所以這裡先做好：
//   1. cwd：從 base_dir 算；沒寫＝base_dir。存不存在由 libaos 檢查（CwdMissing）
//   2. stdin／stdout／stderr：有寫＝從解出來的 cwd 算的絕對路徑；沒寫＝inherits（接呼叫者的 fd 0／1／2）
//   3. 環境：envs 有東西＝現有環境（被 envs 蓋掉的名字跳過）＋envs；沒有＝傳 NULL 沿用
//   4. 填單子：appends、timeout_ms（0＝不限）、grace_ms、new_session＝true（自成行程群組，逾時整群收）
// 路徑的接法用 aos-util 的 aos::join（照 Python 的 os.path.join）。
// 從 impls/aos-inst 的 src/libaos/lib_input.cpp 抄來改（拿掉 *_mkdir、envs_clear、stderr_merge，串流沒寫改成 inherits）。
#include "inst/inst.hpp"

#include "aos/files.hpp"

extern char** environ;

namespace aos::exec {

// 子程式的完整環境 "K=V"：現有的（被 envs 蓋掉的跳過）＋envs。
static std::vector<std::string> build_env(const Inst& inst) {
    std::vector<std::string> out;
    for (char** e = environ; *e != nullptr; ++e) {
        std::string kv = *e;
        if (!inst.envs.contains(kv.substr(0, kv.find('=')))) {
            out.push_back(kv);
        }
    }
    for (auto& [k, v] : inst.envs) {
        out.push_back(k + "=" + v);
    }
    return out;
}

void build_lib_input(const Inst& inst, const std::string& base_dir, LibInput& out) {
    // 1. cwd
    out.cwd = base_dir;
    if (inst.cwd) {
        out.cwd = join(base_dir, *inst.cwd);
    }

    // 2. 三個串流
    for (int i = 0; i < 3; ++i) {
        if (inst.paths[i]) {
            out.paths[i] = join(out.cwd, *inst.paths[i]);
        }
    }

    // 3. argv、環境
    for (auto& a : inst.argv) {
        out.argv.push_back(a.c_str());
    }
    out.argv.push_back(nullptr);
    if (!inst.envs.empty()) {
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
    if (!inst.envs.empty()) {
        out.in.envs = out.envp.data();
    }
    for (int i = 0; i < 3; ++i) {
        out.in.paths[i] = nullptr;
        out.in.inherits[i] = !out.paths[i];
        if (out.paths[i]) {
            out.in.paths[i] = out.paths[i]->c_str();
        }
        out.in.appends[i] = inst.appends[i];
    }
    out.in.merge = false;
    out.in.timeout_ms = inst.timeout_ms;
    out.in.grace_ms = inst.grace_ms;
    out.in.new_session = true;
}

}  // namespace aos::exec
