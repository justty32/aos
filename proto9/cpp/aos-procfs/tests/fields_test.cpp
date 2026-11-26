// fields_test.cpp：欄位表（aos/fields.hpp）的測試——同一個 struct 生出的純文字與 json 逐 byte 對照；印 ok／FAIL 與總數。
#include "aos/procfs.hpp"

#include <cstdio>
#include <map>
#include <optional>
#include <string>

namespace pf = aos::procfs;

#define ROW_FIELDS(F)                            \
    F(std::string, phase, Always)                \
    F(std::optional<long long>, pid, Always)     \
    F(std::string, reason, Always)               \
    F(std::string, external, OmitEmpty)          \
    F(std::optional<std::string>, obey, OmitEmpty)
AOS_RECORD(Row, ROW_FIELDS)
using Rows = std::map<std::string, Row>;

#define INNER_FIELDS(F) F(long long, n, Always) F(std::string, s, Always)
AOS_RECORD(Inner, INNER_FIELDS)

#define TOP_FIELDS(F)                            \
    F(std::string, aos_name, Always)             \
    F(long long, aos_pid, Always)                \
    F(pf::Feedback, aos_ctl_, Embed)             \
    F(Inner, inner, Always)                      \
    F(Rows, rows, Always)
AOS_RECORD(Top, TOP_FIELDS)

namespace {

int passed = 0, total = 0;

void check(const char* name, const std::string& got, const std::string& want) {
    ++total;
    if (got == want) {
        ++passed;
        std::printf("ok    %s\n", name);
    } else {
        std::printf("FAIL  %s\n  got:  [%s]\n  want: [%s]\n", name, got.c_str(), want.c_str());
    }
}

}  // namespace

int main() {
    Rows rows;
    rows["b"] = Row{"stopped", std::nullopt, "", "", std::nullopt};
    rows["a"] = Row{"running", 42, "two\nlines", "yes", std::string()};
    Top t{"d1/kid", 7, pf::Feedback{"add x \"q\"", "done", "", 3}, Inner{5, ""}, rows};

    check("text: flat, Embed joins without a dot, nested and map keys with a dot, empty is -, OmitEmpty drops",
          pf::to_text(t),
          "aos_name: d1/kid\naos_pid: 7\naos_ctl_cmd: add x \"q\"\naos_ctl_state: done\naos_ctl_error: -\naos_ctl_count: 3\n"
          "inner.n: 5\ninner.s: -\n"
          "rows.a.phase: running\nrows.a.pid: 42\nrows.a.reason: two lines\nrows.a.external: yes\nrows.a.obey: -\n"
          "rows.b.phase: stopped\nrows.b.pid: -\nrows.b.reason: -\n");
    check("json: same fields; Embed flattened, empty is null, OmitEmpty drops, strings escaped",
          pf::to_json(t),
          "{\"aos_name\": \"d1/kid\", \"aos_pid\": 7, \"aos_ctl_cmd\": \"add x \\\"q\\\"\", \"aos_ctl_state\": \"done\", "
          "\"aos_ctl_error\": null, \"aos_ctl_count\": 3, \"inner\": {\"n\": 5, \"s\": null}, "
          "\"rows\": {\"a\": {\"phase\": \"running\", \"pid\": 42, \"reason\": \"two\\nlines\", \"external\": \"yes\", \"obey\": null}, "
          "\"b\": {\"phase\": \"stopped\", \"pid\": null, \"reason\": null}}}\n");
    check("a map at the top (procs_status): keys are <name>.<field>", pf::to_text(rows),
          "a.phase: running\na.pid: 42\na.reason: two lines\na.external: yes\na.obey: -\nb.phase: stopped\nb.pid: -\nb.reason: -\n");
    check("empty map: empty text, {} json", pf::to_text(Rows{}) + pf::to_json(Rows{}), "{}\n");
    check("control characters in json strings", pf::json_quote(std::string("a\x01" "b\t", 4)), "\"a\\u0001b\\t\"");
    std::printf("%d/%d passed\n", passed, total);
    return passed == total ? 0 : 1;
}
