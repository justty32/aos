// 逐步驅動 handoff 三個動作，用來手工佈置「崩在某個 syscall 之間」的狀態。
// 只連 build/lib 裡已經建好的 libaos_inst.so，完全不動 repo。
#include <aos/inst.hpp>

#include <cstdio>
#include <cstring>
#include <string>

int main(int argc, char **argv) {
    if (argc < 3) {
        std::fprintf(stderr, "usage: probe <aggregate|claim|release> <inst.json path>\n");
        return 2;
    }
    const std::string op = argv[1];
    const std::string path = argv[2];
    if (op == "aggregate") {
        aos::HandoffResult r;
        const aos::HandoffState s = aos::aggregate_instructions(path, r);
        std::printf("aggregate=%s published=%d path=%s errno=%d\n",
                    aos::to_string(s), r.published ? 1 : 0, r.path.c_str(), r.error);
        for (const aos::HandoffIssue &i : r.issues) {
            std::printf("  issue %s path=%s inst=%s errno=%d\n", aos::to_string(i.kind),
                        i.path.c_str(), aos::to_string(i.inst_state), i.error);
        }
        return s == aos::HandoffState::Ok ? 0 : 1;
    }
    if (op == "claim") {
        aos::HandoffResult r;
        std::string doc;
        const aos::HandoffState s = aos::claim_instruction(path, doc, r);
        std::printf("claim=%s bytes=%zu path=%s errno=%d\n", aos::to_string(s),
                    doc.size(), r.path.c_str(), r.error);
        return s == aos::HandoffState::Ok ? 0 : 1;
    }
    if (op == "release") {
        aos::HandoffResult r;
        const aos::HandoffState s = aos::release_instruction(path, r);
        std::printf("release=%s path=%s errno=%d\n", aos::to_string(s), r.path.c_str(),
                    r.error);
        return s == aos::HandoffState::Ok ? 0 : 1;
    }
    std::fprintf(stderr, "unknown op %s\n", op.c_str());
    return 2;
}
