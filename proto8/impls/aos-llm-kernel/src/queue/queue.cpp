// queue.cpp：【queue】queue.json 與排隊（說明見 queue.hpp）。
#include "queue/queue.hpp"

#include "aos/files.hpp"

#include <algorithm>
#include <cerrno>
#include <cstring>

namespace aos::llm_kernel {

Queue read_queue(const std::string& stack) {
    Queue q;
    std::string path = aos::join(stack, "queue.json");
    int err = 0;
    std::optional<std::string> text = aos::read_file(path, err);
    if (!text) {
        if (err == ENOENT) {
            return q;
        }
        throw Error{code::QueueBad, "讀不了 " + path + "：" + std::strerror(err)};
    }
    std::optional<Json> doc = aos::read_json(path);
    if (!doc || !doc->is_object() || !aos::is_count(doc->value("counter_runs", Json())) ||
        !doc->value("seen_at_runs", Json()).is_object()) {
        throw Error{code::QueueBad, path + " 要是 {\"counter_runs\": 非負整數, \"seen_at_runs\": {…}}（刪掉它就從頭算）"};
    }
    q.runs = (*doc)["counter_runs"].get<long long>();
    q.seen_at_runs = (*doc)["seen_at_runs"];
    return q;
}

void write_queue(const std::string& stack, const Queue& q) {
    Json doc = Json::object();
    doc["counter_runs"] = q.runs;
    doc["seen_at_runs"] = q.seen_at_runs;
    std::optional<std::string> err = aos::write_json(aos::join(stack, "queue.json"), doc);
    if (err) {
        throw Error{code::WriteFailed, *err};
    }
}

long long waited_runs(const Waiting& w, long long runs) {
    long long n = runs - w.seen_at_runs;
    if (n < 0) {
        return 0;
    }
    return n;
}

long long effective(const Waiting& w, long long runs) {
    return w.priority.level + waited_runs(w, runs) / 10;
}

void order(std::vector<Waiting>& ws, long long runs) {
    std::stable_sort(ws.begin(), ws.end(), [runs](const Waiting& a, const Waiting& b) {
        long long ea = effective(a, runs);
        long long eb = effective(b, runs);
        if (ea != eb) {
            return ea > eb;
        }
        if (a.priority.deadline.has_value() != b.priority.deadline.has_value()) {
            return a.priority.deadline.has_value();
        }
        if (a.priority.deadline && *a.priority.deadline != *b.priority.deadline) {
            return *a.priority.deadline < *b.priority.deadline;
        }
        // 10-24 `_metainfo`：同級同時限，宣告短的先、有寫的在沒寫的前面（不蓋過 level 與 deadline；aging 照舊，插隊有上限）
        if (a.priority.time_ms.has_value() != b.priority.time_ms.has_value()) {
            return a.priority.time_ms.has_value();
        }
        if (a.priority.time_ms && *a.priority.time_ms != *b.priority.time_ms) {
            return *a.priority.time_ms < *b.priority.time_ms;
        }
        long long wa = waited_runs(a, runs);
        long long wb = waited_runs(b, runs);
        if (wa != wb) {
            return wa > wb;
        }
        return a.id < b.id;
    });
}

}  // namespace aos::llm_kernel
