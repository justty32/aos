// ops.cpp：回答的線上一般節點的幾個較長的操作——MKNOD／UNLINK（只給 socket）、OPEN／READ／WRITE、OPENDIR／READDIR。
#include "internal.hpp"

#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>

namespace aos::procfs {

void Fs::Impl::op_mknod(const Req& r, Lock& lk, uint64_t nid, Node& node) {
    fuse_mknod_in mi;
    r.in(mi);
    std::string name = r.name_at(sizeof mi);
    if (node.kind != Kind::Dir || !node.sockets || (mi.mode & S_IFMT) != S_IFSOCK || name.empty()) {
        lk.unlock();
        reply(r.h.unique, EPERM);
        return;
    }
    if (kid(node, name)) {
        lk.unlock();
        reply(r.h.unique, EEXIST);
        return;
    }
    Node s;
    s.kind = Kind::Sock;
    s.mode = mi.mode & ~mi.umask & 07777;
    s.parent = nid;
    s.name = name;
    uint64_t sid = next_nid++;
    nodes[sid] = std::move(s);
    nodes.at(nid).kids.push_back(sid);
    fuse_entry_out e = entry_of(sid, nodes.at(sid));
    lk.unlock();
    reply(r.h.unique, 0, &e, sizeof e);
}

void Fs::Impl::op_unlink(const Req& r, Lock& lk, Node& node) {
    // 只有 bind 出來的 socket 可以被 rm；其餘的節點歸程式管
    uint64_t c = kid(node, r.name_at(0));
    if (c && nodes.at(c).kind == Kind::Sock) {
        std::erase(node.kids, c);
        nodes.erase(c);
        lk.unlock();
        reply(r.h.unique, 0);
        return;
    }
    bool dir = node.kind == Kind::Dir;
    lk.unlock();
    reply(r.h.unique, dir ? EPERM : ENOTDIR);
}

void Fs::Impl::op_open(const Req& r, Lock& lk, Node& node) {
    fuse_open_in oi;
    r.in(oi);
    fuse_open_out o{};
    Kind k = node.kind;
    if (k == Kind::Text && (oi.flags & O_ACCMODE) == O_RDONLY) {
        Producer p = node.produce;
        lk.unlock();
        // 開檔那一刻產生一份，整次讀都讀這份（跟 /proc/<PID>/status 一樣），不在拿著表鎖時叫使用者的回呼
        std::shared_ptr<const std::string> snap;
        try {
            snap = std::make_shared<const std::string>(p ? p() : std::string());
        } catch (...) {
            reply(r.h.unique, EIO);   // 使用者的回呼丟例外不該弄死回答的線
            return;
        }
        lk.lock();
        o.fh = next_fh++;
        fhs[o.fh] = std::move(snap);
        lk.unlock();
        o.open_flags = FOPEN_DIRECT_IO;
        reply(r.h.unique, 0, &o, sizeof o);
        return;
    }
    if (k == Kind::Json) {
        o.fh = next_fh++;
        fhs[o.fh] = node.data;
        lk.unlock();
        o.open_flags = FOPEN_KEEP_CACHE;
        reply(r.h.unique, 0, &o, sizeof o);
        return;
    }
    if (k == Kind::Ctl) {
        Ctl* c = node.ctl;
        lk.unlock();
        // 開檔也擋：殼裡的錯誤字才是「ctl: Device or resource busy」；真正上鎖在 WRITE
        if (!c->impl()->open_ok()) {
            reply(r.h.unique, EBUSY);
            return;
        }
        o.open_flags = FOPEN_DIRECT_IO;
        reply(r.h.unique, 0, &o, sizeof o);
        return;
    }
    lk.unlock();
    reply(r.h.unique, EACCES);
}

void Fs::Impl::op_read(const Req& r, Lock& lk) {
    fuse_read_in ri;
    r.in(ri);
    auto f = fhs.find(ri.fh);
    std::shared_ptr<const std::string> d = f == fhs.end() ? nullptr : f->second;
    lk.unlock();
    if (!d) {
        reply(r.h.unique, EBADF);
        return;
    }
    size_t off = ri.offset < d->size() ? static_cast<size_t>(ri.offset) : d->size();
    size_t n = std::min<size_t>(ri.size, d->size() - off);
    reply(r.h.unique, 0, d->data() + off, n);
}

void Fs::Impl::op_write(const Req& r, Lock& lk, Node& node) {
    fuse_write_in wi;
    r.in(wi);
    if (node.kind != Kind::Ctl) {
        lk.unlock();
        reply(r.h.unique, EACCES);
        return;
    }
    Ctl* c = node.ctl;
    lk.unlock();
    size_t off = sizeof wi;
    size_t n = off < r.blen ? std::min<size_t>(wi.size, r.blen - off) : 0;
    int err = c->impl()->write(std::string_view(r.body + off, n));
    if (err) {
        reply(r.h.unique, err);
        return;
    }
    fuse_write_out o{};
    o.size = wi.size;
    reply(r.h.unique, 0, &o, sizeof o);
}

void Fs::Impl::op_opendir(const Req& r, Lock& lk, uint64_t nid, Node& node) {
    if (node.kind != Kind::Dir && node.kind != Kind::MailDir) {
        lk.unlock();
        reply(r.h.unique, ENOTDIR);
        return;
    }
    if (node.mb) node.mb->sweep(wall_now());   // ls tmp/ 時順手丟掉過期的
    // 開夾那刻拍一張名單：procs/ 的連結、信箱的信隨時會變，分段讀才不會漏或重複
    auto list = std::make_shared<std::vector<DirEnt>>();
    list->push_back({".", nid, S_IFDIR >> 12});
    list->push_back({"..", node.parent, S_IFDIR >> 12});
    for (uint64_t c : node.kids) {
        const Node& k = nodes.at(c);
        uint32_t t = k.kind == Kind::Dir || k.kind == Kind::MailDir ? S_IFDIR : k.kind == Kind::Link ? S_IFLNK
                     : k.kind == Kind::Sock ? S_IFSOCK : S_IFREG;
        list->push_back({k.name, c, t >> 12});
    }
    fuse_open_out o{};
    o.fh = next_fh++;
    dirs[o.fh] = std::move(list);
    lk.unlock();
    reply(r.h.unique, 0, &o, sizeof o);
}

void Fs::Impl::op_readdir(const Req& r, Lock& lk) {
    fuse_read_in ri;
    r.in(ri);
    auto d = dirs.find(ri.fh);
    auto list = d == dirs.end() ? nullptr : d->second;
    lk.unlock();
    if (!list) {
        reply(r.h.unique, EBADF);
        return;
    }
    std::string out;
    for (size_t i = ri.offset; i < list->size(); ++i) {
        const DirEnt& e = (*list)[i];
        size_t rec = FUSE_DIRENT_ALIGN(FUSE_NAME_OFFSET + e.name.size());
        if (out.size() + rec > ri.size) break;
        fuse_dirent de{};
        de.ino = e.nid;
        de.off = i + 1;   // 下一次從第幾項讀
        de.namelen = static_cast<uint32_t>(e.name.size());
        de.type = e.type;
        size_t start = out.size();
        out.resize(start + rec, '\0');
        std::memcpy(&out[start], &de, FUSE_NAME_OFFSET);
        std::memcpy(&out[start + FUSE_NAME_OFFSET], e.name.data(), e.name.size());
    }
    reply(r.h.unique, 0, out.data(), out.size());
}

}  // namespace aos::procfs
