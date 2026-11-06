// queue.cpp：【queue】queue.json 與排隊（說明見 queue.hpp）。
#include "queue/queue.hpp"

#include "aos/util/files.hpp"

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <limits>

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
        throw Error{code::QueueBad, "cannot read " + path + ": " + std::strerror(err)};
    }
    std::optional<Json> doc = aos::read_json(path);
    if (!doc || !doc->is_object() || !aos::is_count(doc->value("counter_runs", Json())) ||
        (doc->contains("seen_at_ms") && !(*doc)["seen_at_ms"].is_object()) ||
        (doc->contains("seen_at_ticks") && !(*doc)["seen_at_ticks"].is_object())) {
        throw Error{code::QueueBad, path + " must contain counter_runs (non-negative integer) and optional seen_at_ms/seen_at_ticks objects (delete it to start over)"};
    }
    q.runs = (*doc)["counter_runs"].get<long long>();
    q.seen_at_ms = doc->value("seen_at_ms", Json::object());
    q.seen_at_ticks = doc->value("seen_at_ticks", Json::object());
    return q;
}

void write_queue(const std::string& stack, const Queue& q) {
    Json doc = Json::object();
    doc["counter_runs"] = q.runs;
    doc["seen_at_ms"] = q.seen_at_ms;
    if (q.on_tick) {
        doc["seen_at_ticks"] = q.seen_at_ticks;
    }
    std::optional<std::string> err = aos::write_json(aos::join(stack, "queue.json"), doc);
    if (err) {
        throw Error{code::WriteFailed, *err};
    }
}

long long effective(const Waiting& w, long long aging_ticks) {
    long long age = w.waited_ticks / aging_ticks;
    if (w.priority.level > 0 && age > std::numeric_limits<long long>::max() - w.priority.level) {
        return std::numeric_limits<long long>::max();
    }
    return w.priority.level + age;
}

void order(std::vector<Waiting>& ws, long long aging_ticks) {
    std::stable_sort(ws.begin(), ws.end(), [aging_ticks](const Waiting& a, const Waiting& b) {
        long long ea = effective(a, aging_ticks);
        long long eb = effective(b, aging_ticks);
        if (ea != eb) {
            return ea > eb;
        }
        if (a.priority.deadline.has_value() != b.priority.deadline.has_value()) {
            return a.priority.deadline.has_value();
        }
        if (a.priority.deadline && *a.priority.deadline != *b.priority.deadline) {
            return *a.priority.deadline < *b.priority.deadline;
        }
        if (a.pack.speed != b.pack.speed) {   // 11-05 feat-proto：同級、同 deadline 時快的包先（早放格；慢的靠 aging 不會餓死）
            return a.pack.speed < b.pack.speed;
        }
        long long wa = a.waited_ticks;
        long long wb = b.waited_ticks;
        if (wa != wb) {
            return wa > wb;
        }
        return a.id < b.id;
    });
}

}  // namespace aos::llm_kernel
