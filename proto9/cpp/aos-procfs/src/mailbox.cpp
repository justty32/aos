// mailbox.cpp：信箱資料夾的收信這一邊——add_mailbox 擺出 tmp/ new/ cur/、take() 拿走最早的一封、stats()、丟掉過期的 tmp/。
#include "internal.hpp"

#include <stdexcept>
#include <sys/eventfd.h>
#include <time.h>
#include <unistd.h>

namespace aos::procfs {

double wall_now() {
    timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);   // vDSO：不碰檔案系統，回答的線上叫得
    return static_cast<double>(ts.tv_sec) + ts.tv_nsec / 1e9;
}

void Mailbox::Impl::sweep(double now) {
    // 最多一秒掃一次（過期時間設得很短時再密一點）；只掃 tmp/，new/ 裡等多少封都不影響
    if (now - last_sweep < std::min(1.0, lim.stale_tmp_seconds / 4)) return;
    last_sweep = now;
    std::vector<uint64_t> old;
    for (uint64_t c : fs->nodes.at(tmp).kids) {
        const Node& n = fs->nodes.at(c);
        if (!n.sealed && now - n.touched > lim.stale_tmp_seconds) old.push_back(c);
    }
    for (uint64_t c : old) {
        drop(c);
        ++dropped_stale;
    }
}

void Mailbox::Impl::drop(uint64_t nid) {
    auto& nodes = fs->nodes;
    Node& n = nodes.at(nid);
    if (n.top == nid) {
        bytes -= n.lbytes;
        --entries;
    } else if (n.kind == Kind::MailFile) {
        size_t sz = n.body->size();
        nodes.at(n.top).lbytes -= sz;
        bytes -= sz;
    }
    std::erase(nodes.at(n.parent).kids, nid);
    std::vector<uint64_t> kids = n.kids;   // 信夾裡只有一層檔
    nodes.erase(nid);
    for (uint64_t k : kids) nodes.erase(k);
}

Letter Mailbox::Impl::letter(uint64_t nid) const {
    const Node& n = fs->nodes.at(nid);
    Letter l;
    l.name = n.name;
    l.size = n.lbytes;
    l.uid = n.from_uid;
    l.pid = n.from_pid;
    l.arrived_at = n.arrived;
    if (n.kind == Kind::MailFile) {
        l.bytes = n.body;
    } else {
        l.folder = true;
        for (uint64_t c : n.kids) {
            const Node& f = fs->nodes.at(c);
            l.files.emplace_back(f.name, f.body);
            if (f.name == "letter.json") l.bytes = f.body;
        }
    }
    if (!l.bytes) l.bytes = std::make_shared<const std::string>();
    return l;
}

Mailbox::Mailbox(std::unique_ptr<Impl> impl) : impl_(std::move(impl)) {}

Mailbox::~Mailbox() {
    if (impl_->efd >= 0) close(impl_->efd);
}

std::optional<Letter> Mailbox::take() {
    std::lock_guard<std::mutex> g(impl_->fs->mu);
    const auto& waiting = impl_->fs->nodes.at(impl_->nw).kids;   // 照搬進來的先後
    if (waiting.empty()) return std::nullopt;
    uint64_t id = waiting.front();
    Letter l = impl_->letter(id);
    impl_->drop(id);
    ++impl_->taken;
    return l;
}

int Mailbox::fd() const { return impl_->efd; }

MailStats Mailbox::stats() const {
    std::lock_guard<std::mutex> g(impl_->fs->mu);
    Impl& m = *impl_;
    m.sweep(wall_now());
    MailStats s;
    s.waiting = m.fs->nodes.at(m.nw).kids.size();
    s.writing = m.fs->nodes.at(m.tmp).kids.size();
    s.bytes = m.bytes;
    s.delivered = m.delivered;
    s.taken = m.taken;
    s.refused = m.refused;
    s.dropped_stale = m.dropped_stale;
    s.last_refusal = m.last_refusal;
    return s;
}

Mailbox& Fs::add_mailbox(const std::string& path, MailLimits limits, Accept accept) {
    if (impl_->is_mounted) throw std::runtime_error("add_mailbox after mount");
    auto mi = std::make_unique<Mailbox::Impl>();
    mi->fs = impl_.get();
    mi->lim = limits;
    mi->accept = std::move(accept);
    mi->efd = eventfd(0, EFD_NONBLOCK | EFD_CLOEXEC);
    if (mi->efd < 0) throw std::runtime_error("eventfd failed");
    Mailbox::Impl* m = mi.get();
    auto box = std::make_unique<Mailbox>(std::move(mi));   // 先交給 Mailbox：下面丟例外時 eventfd 也會關
    auto dir = [&](const std::string& p, Role role, uint32_t mode) {
        Node n;
        n.kind = Kind::MailDir;
        n.role = role;
        n.mode = mode;
        n.mb = m;
        n.mtime = wall_now();
        return impl_->add_node(p, std::move(n));
    };
    // 根與 cur/ 不給寫；tmp/、new/ 要有寫的權限（default_permissions 照權限位擋，aos-post 也先 access(W_OK|X_OK)）
    m->root = dir(path, Role::Root, 0555);
    m->tmp = dir(path + "/tmp", Role::Tmp, 0755);
    m->nw = dir(path + "/new", Role::New, 0755);
    m->cur = dir(path + "/cur", Role::Cur, 0555);
    impl_->mailboxes.push_back(std::move(box));
    return *impl_->mailboxes.back();
}

}  // namespace aos::procfs
