// fs.cpp：Fs 的節點表（加夾、加檔、加連結、拿掉）與掛上／卸下的流程。
#include "internal.hpp"

#include <cerrno>
#include <chrono>
#include <climits>
#include <cstring>
#include <stdexcept>
#include <sys/stat.h>
#include <unistd.h>

namespace aos::procfs {

Fs::Fs(Options opt) : impl_(std::make_unique<Impl>()) {
    impl_->opt = std::move(opt);
    if (impl_->opt.threads < 1) impl_->opt.threads = 1;
    impl_->uid = getuid();
    impl_->gid = getgid();
    impl_->t0 = static_cast<long long>(time(nullptr));
    Node root;
    root.kind = Kind::Dir;
    root.mode = impl_->opt.root_sockets ? 0755 : 0555;
    root.sockets = impl_->opt.root_sockets;
    impl_->nodes[1] = std::move(root);
}

Fs::~Fs() {
    try {
        unmount();
    } catch (...) {
    }
}

uint64_t Fs::Impl::lookup_path(const std::string& path, std::string* leaf, bool want_parent) const {
    std::vector<std::string> parts;
    size_t i = 0;
    while (i <= path.size()) {
        size_t j = path.find('/', i);
        if (j == std::string::npos) j = path.size();
        if (j > i) parts.push_back(path.substr(i, j - i));
        i = j + 1;
    }
    if (parts.empty()) throw std::runtime_error("empty path");
    size_t stop = want_parent ? parts.size() - 1 : parts.size();
    uint64_t cur = 1;
    for (size_t k = 0; k < stop; ++k) {
        const Node& n = nodes.at(cur);
        uint64_t next = 0;
        for (uint64_t c : n.kids)
            if (nodes.at(c).name == parts[k]) next = c;
        if (!next) return 0;
        cur = next;
    }
    if (leaf) *leaf = parts.back();
    return cur;
}

uint64_t Fs::Impl::add_node(const std::string& path, Node n) {
    std::lock_guard<std::mutex> g(mu);
    std::string leaf;
    uint64_t parent = lookup_path(path, &leaf, true);
    if (!parent || nodes.at(parent).kind != Kind::Dir) throw std::runtime_error("no parent dir for " + path);
    if (leaf == "." || leaf == "..") throw std::runtime_error("bad name " + path);
    for (uint64_t c : nodes.at(parent).kids)
        if (nodes.at(c).name == leaf) throw std::runtime_error("already exists: " + path);
    n.parent = parent;
    n.name = leaf;
    uint64_t nid = next_nid++;
    nodes[nid] = std::move(n);
    nodes.at(parent).kids.push_back(nid);
    return nid;
}

void Fs::add_dir(const std::string& path, bool sockets) {
    Node n;
    n.kind = Kind::Dir;
    // 能放 socket 的夾要有寫的權限，default_permissions 才放 bind 過去
    n.mode = sockets ? 0755 : 0555;
    n.sockets = sockets;
    impl_->add_node(path, std::move(n));
}

void Fs::add_text(const std::string& path, Producer produce) {
    Node n;
    n.kind = Kind::Text;
    n.mode = 0444;
    n.produce = std::move(produce);
    impl_->add_node(path, std::move(n));
}

void Fs::add_json(const std::string& path, std::string content) {
    Node n;
    n.kind = Kind::Json;
    n.mode = 0444;
    n.data = std::make_shared<const std::string>(std::move(content));
    impl_->add_node(path, std::move(n));
}

Ctl& Fs::add_ctl(const std::string& path, std::string prefix) {
    if (impl_->is_mounted) throw std::runtime_error("add_ctl after mount");
    auto ctl = std::make_unique<Ctl>(std::move(prefix));
    Node n;
    n.kind = Kind::Ctl;
    n.mode = 0200;
    n.ctl = ctl.get();
    impl_->add_node(path, std::move(n));
    impl_->ctls.push_back(std::move(ctl));
    return *impl_->ctls.back();
}

void Fs::add_symlink(const std::string& path, std::string target) {
    Node n;
    n.kind = Kind::Link;
    n.mode = 0777;
    n.data = std::make_shared<const std::string>(std::move(target));
    impl_->add_node(path, std::move(n));
}

bool Fs::remove(const std::string& path) {
    std::lock_guard<std::mutex> g(impl_->mu);
    uint64_t nid = impl_->lookup_path(path, nullptr, false);
    if (!nid || nid == 1) return false;
    Node& n = impl_->nodes.at(nid);
    if (n.kind != Kind::Link && n.kind != Kind::Sock) return false;
    auto& kids = impl_->nodes.at(n.parent).kids;
    std::erase(kids, nid);
    impl_->nodes.erase(nid);
    return true;
}

void Fs::mount(const std::string& mountpoint) {
    forbid_on_answer_thread("Fs::mount");
    Impl& m = *impl_;
    if (m.is_mounted) throw std::runtime_error("already mounted");
    struct stat st;
    if (stat(mountpoint.c_str(), &st) != 0) {
        if (mkdir(mountpoint.c_str(), 0700) != 0)
            throw std::runtime_error("mkdir " + mountpoint + ": " + std::strerror(errno));
        m.created_dir = true;
    }
    char buf[PATH_MAX];
    if (!realpath(mountpoint.c_str(), buf)) throw std::runtime_error("realpath " + mountpoint + ": " + std::strerror(errno));
    m.mnt = buf;
    std::string opts = "fsname=" + m.opt.fsname + ":" + std::to_string(getpid()) + ",subtype=aosproc,default_permissions";
    try {
        m.fd = fuse_mount(m.mnt, opts);
    } catch (...) {
        if (m.created_dir) rmdir(m.mnt.c_str());
        m.created_dir = false;
        throw;
    }
    m.is_mounted = true;
    for (auto& c : m.ctls) c->impl()->start();
    m.live_threads = m.opt.threads;
    for (int i = 0; i < m.opt.threads; ++i) m.threads.emplace_back([&m] { m.loop(); });
}

void Fs::unmount() {
    forbid_on_answer_thread("Fs::unmount");
    Impl& m = *impl_;
    if (!m.is_mounted) return;
    m.is_mounted = false;
    // 自己站在掛載點裡 umount 會 EBUSY，先離開
    char cwd[PATH_MAX];
    if (getcwd(cwd, sizeof cwd)) {
        std::string c = cwd;
        if (c == m.mnt || c.rfind(m.mnt + "/", 0) == 0) {
            if (chdir("/") != 0) {}
        }
    }
    if (run_fusermount({"-u", m.mnt}, true) != 0) {
        // 別人還站在裡面：lazy 卸，再 abort 連線，不然回答的線要等到那人離開才醒
        long id = connection_id(m.mnt);
        run_fusermount({"-u", "-z", m.mnt}, false);
        if (id >= 0) {
            FILE* f = fopen(("/sys/fs/fuse/connections/" + std::to_string(id) + "/abort").c_str(), "w");
            if (f) {
                fputs("1", f);
                fclose(f);
            }
        }
    }
    bool all_gone;
    {
        std::unique_lock<std::mutex> lk(m.tmu);
        all_gone = m.tcv.wait_for(lk, std::chrono::seconds(2), [&] { return m.live_threads == 0; });
    }
    for (auto& t : m.threads) {
        if (all_gone) t.join();
        else t.detach();   // 醒不來就不等，行程結束時一起收；fd 也不關，免得它讀到別人的 fd
    }
    m.threads.clear();
    if (all_gone) close(m.fd);
    m.fd = -1;
    for (auto& c : m.ctls) c->impl()->stop();
    if (m.created_dir) rmdir(m.mnt.c_str());
    m.created_dir = false;
}

bool Fs::mounted() const { return impl_->is_mounted; }

const std::string& Fs::mountpoint() const { return impl_->mnt; }

}  // namespace aos::procfs
