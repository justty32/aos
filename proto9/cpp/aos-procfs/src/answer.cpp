// answer.cpp：回答的線——讀 /dev/fuse 一次一個請求、照 linux/fuse.h 回覆；只碰記憶體，不碰任何檔案系統路徑。
#include "internal.hpp"

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <linux/fuse.h>
#include <sys/stat.h>
#include <sys/uio.h>
#include <unistd.h>

namespace aos::procfs {

namespace {

constexpr uint32_t MAX_WRITE = 128 * 1024;
// 核心要求讀的緩衝至少放得下 header＋write_in＋max_write
constexpr size_t BUF_SIZE = MAX_WRITE + 64 * 1024;

uint32_t type_bits(Kind k) {
    switch (k) {
    case Kind::Dir: return S_IFDIR;
    case Kind::Link: return S_IFLNK;
    case Kind::Sock: return S_IFSOCK;
    default: return S_IFREG;
    }
}

uint32_t dirent_type(Kind k) { return type_bits(k) >> 12; }

}  // namespace

void Fs::Impl::reply(uint64_t unique, int err, const void* data, size_t len) {
    fuse_out_header h{};
    h.len = static_cast<uint32_t>(sizeof h + (err ? 0 : len));
    h.error = -err;
    h.unique = unique;
    iovec iov[2] = {{&h, sizeof h}, {const_cast<void*>(data), err ? 0 : len}};
    // ENOENT＝那個請求已被中斷（INTERRUPT），照協議忽略
    while (writev(fd, iov, (err || !len) ? 1 : 2) < 0 && errno == EINTR) {}
}

void Fs::Impl::loop() {
    mark_answer_thread();
    std::vector<char> buf(BUF_SIZE);
    for (;;) {
        ssize_t n = read(fd, buf.data(), buf.size());
        if (n < 0) {
            if (errno == EINTR || errno == EAGAIN || errno == ENOENT) continue;
            break;   // ENODEV＝被卸或被 abort；其他錯也沒辦法再答
        }
        if (n < static_cast<ssize_t>(sizeof(fuse_in_header))) continue;
        dispatch(buf.data(), static_cast<size_t>(n));
    }
    bool last;
    {
        std::lock_guard<std::mutex> g(tmu);
        last = --live_threads == 0;
    }
    tcv.notify_all();
    if (last && opt.on_gone) opt.on_gone();
}

void Fs::Impl::dispatch(const char* buf, size_t len) {
    fuse_in_header h;
    std::memcpy(&h, buf, sizeof h);
    if (h.len > len) h.len = static_cast<uint32_t>(len);
    const char* body = buf + sizeof h;
    size_t blen = h.len - sizeof h;
    // 依結構大小把請求的本體抄出來；短了補 0，不越界
    auto in = [&](auto& s) {
        std::memset(&s, 0, sizeof s);
        std::memcpy(&s, body, std::min(sizeof s, blen));
    };
    auto fill_attr = [&](uint64_t nid, const Node& n, fuse_attr& a) {
        std::memset(&a, 0, sizeof a);
        a.ino = nid;
        a.mode = type_bits(n.kind) | n.mode;
        a.nlink = n.kind == Kind::Dir ? 2 : 1;
        a.uid = uid;
        a.gid = gid;
        a.blksize = 4096;
        a.atime = a.mtime = a.ctime = static_cast<uint64_t>(t0);
        // 純文字檔報 0、靠 direct_io 讀；報真長度就得每次 stat 都產生一次，而且 stat 與讀之間會對不上
        if (n.kind == Kind::Json || n.kind == Kind::Link) a.size = n.data->size();
    };
    auto entry_of = [&](uint64_t nid, const Node& n) {
        fuse_entry_out e{};
        e.nodeid = nid;
        // symlink／socket 隨時會被加、拿掉：名字與屬性都不快取，kid 死了才不會還看到舊的一秒
        bool vol = n.kind == Kind::Link || n.kind == Kind::Sock;
        e.entry_valid = vol ? 0 : 1;
        e.attr_valid = vol ? 0 : 1;
        fill_attr(nid, n, e.attr);
        return e;
    };

    switch (h.opcode) {
    case FUSE_INIT: {
        fuse_init_in ii;
        in(ii);
        fuse_init_out o{};
        o.major = FUSE_KERNEL_VERSION;
        o.minor = std::min<uint32_t>(ii.minor, FUSE_KERNEL_MINOR_VERSION);
        if (ii.major != FUSE_KERNEL_VERSION) {
            // 核心比我們新的大版號：照協議回我們的版號，它會重送
            reply(h.unique, 0, &o, FUSE_COMPAT_INIT_OUT_SIZE);
            return;
        }
        o.max_readahead = ii.max_readahead;
        o.flags = 0;   // 不談任何選用功能：O_TRUNC 改走 SETATTR、沒有 writeback cache
        o.max_background = 16;
        o.congestion_threshold = 12;
        o.max_write = MAX_WRITE;
        o.time_gran = 1;
        reply(h.unique, 0, &o, o.minor < 23 ? FUSE_COMPAT_22_INIT_OUT_SIZE : sizeof o);
        return;
    }
    case FUSE_FORGET:
    case FUSE_BATCH_FORGET:
    case FUSE_INTERRUPT:
        return;   // 協議規定這三種不回；nodeid 不回收，所以不必記 lookup 次數
    case FUSE_DESTROY:
        reply(h.unique, 0);
        return;
    default:
        break;
    }

    std::unique_lock<std::mutex> lk(mu);
    auto it = nodes.find(h.nodeid);
    if (it == nodes.end()) {
        lk.unlock();
        reply(h.unique, ENOENT);
        return;
    }
    uint64_t nid = it->first;
    Node& node = it->second;

    switch (h.opcode) {
    case FUSE_LOOKUP: {
        std::string name(body, strnlen(body, blen));
        if (node.kind == Kind::Dir)
            for (uint64_t c : node.kids)
                if (nodes.at(c).name == name) {
                    fuse_entry_out e = entry_of(c, nodes.at(c));
                    lk.unlock();
                    reply(h.unique, 0, &e, sizeof e);
                    return;
                }
        lk.unlock();
        reply(h.unique, ENOENT);
        return;
    }
    case FUSE_GETATTR:
    case FUSE_SETATTR: {
        // SETATTR：`echo x > ctl` 的 O_TRUNC 會變成 SETATTR size=0；回個屬性當成功，什麼都不動（鎖著時也一樣）
        fuse_attr_out o{};
        o.attr_valid = (node.kind == Kind::Link || node.kind == Kind::Sock) ? 0 : 1;
        fill_attr(nid, node, o.attr);
        lk.unlock();
        reply(h.unique, 0, &o, sizeof o);
        return;
    }
    case FUSE_READLINK: {
        if (node.kind != Kind::Link) break;
        auto target = node.data;
        lk.unlock();
        reply(h.unique, 0, target->data(), target->size());
        return;
    }
    case FUSE_MKNOD: {
        fuse_mknod_in mi;
        in(mi);
        size_t off = sizeof mi;
        std::string name(off < blen ? body + off : "", off < blen ? strnlen(body + off, blen - off) : 0);
        if (node.kind != Kind::Dir || !node.sockets || (mi.mode & S_IFMT) != S_IFSOCK || name.empty()) {
            lk.unlock();
            reply(h.unique, EPERM);
            return;
        }
        for (uint64_t c : node.kids)
            if (nodes.at(c).name == name) {
                lk.unlock();
                reply(h.unique, EEXIST);
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
        reply(h.unique, 0, &e, sizeof e);
        return;
    }
    case FUSE_UNLINK: {
        // 只有 bind 出來的 socket 可以被 rm；其餘的節點歸程式管
        std::string name(body, strnlen(body, blen));
        for (uint64_t c : node.kids)
            if (nodes.at(c).name == name) {
                if (nodes.at(c).kind != Kind::Sock) break;
                std::erase(node.kids, c);
                nodes.erase(c);
                lk.unlock();
                reply(h.unique, 0);
                return;
            }
        lk.unlock();
        reply(h.unique, node.kind == Kind::Dir ? EPERM : ENOTDIR);
        return;
    }
    case FUSE_MKDIR:
    case FUSE_SYMLINK:
    case FUSE_LINK:
    case FUSE_RENAME:
    case FUSE_RENAME2:
    case FUSE_RMDIR:
    case FUSE_CREATE:
        lk.unlock();
        reply(h.unique, EPERM);
        return;
    case FUSE_OPEN: {
        fuse_open_in oi;
        in(oi);
        fuse_open_out o{};
        Kind k = node.kind;
        if (k == Kind::Text) {
            if ((oi.flags & O_ACCMODE) != O_RDONLY) break;
            Producer p = node.produce;
            lk.unlock();
            // 開檔那一刻產生一份，整次讀都讀這份（跟 /proc/<PID>/status 一樣），不在拿著表鎖時叫使用者的回呼
            std::shared_ptr<const std::string> snap;
            try {
                snap = std::make_shared<const std::string>(p ? p() : std::string());
            } catch (...) {
                reply(h.unique, EIO);   // 使用者的回呼丟例外不該弄死回答的線
                return;
            }
            lk.lock();
            o.fh = next_fh++;
            fhs[o.fh] = std::move(snap);
            lk.unlock();
            o.open_flags = FOPEN_DIRECT_IO;
            reply(h.unique, 0, &o, sizeof o);
            return;
        }
        if (k == Kind::Json) {
            o.fh = next_fh++;
            fhs[o.fh] = node.data;
            lk.unlock();
            o.open_flags = FOPEN_KEEP_CACHE;
            reply(h.unique, 0, &o, sizeof o);
            return;
        }
        if (k == Kind::Ctl) {
            Ctl* c = node.ctl;
            lk.unlock();
            // 開檔也擋：殼裡的錯誤字才是「ctl: Device or resource busy」；真正上鎖在 WRITE
            if (!c->impl()->open_ok()) {
                reply(h.unique, EBUSY);
                return;
            }
            o.open_flags = FOPEN_DIRECT_IO;
            reply(h.unique, 0, &o, sizeof o);
            return;
        }
        lk.unlock();
        reply(h.unique, EACCES);
        return;
    }
    case FUSE_READ: {
        fuse_read_in ri;
        in(ri);
        auto f = fhs.find(ri.fh);
        std::shared_ptr<const std::string> d = f == fhs.end() ? nullptr : f->second;
        lk.unlock();
        if (!d) {
            reply(h.unique, EBADF);
            return;
        }
        size_t off = ri.offset < d->size() ? static_cast<size_t>(ri.offset) : d->size();
        size_t n = std::min<size_t>(ri.size, d->size() - off);
        reply(h.unique, 0, d->data() + off, n);
        return;
    }
    case FUSE_WRITE: {
        fuse_write_in wi;
        in(wi);
        if (node.kind != Kind::Ctl) break;
        Ctl* c = node.ctl;
        lk.unlock();
        size_t off = sizeof wi;
        size_t n = off < blen ? std::min<size_t>(wi.size, blen - off) : 0;
        int err = c->impl()->write(std::string_view(body + off, n));
        if (err) {
            reply(h.unique, err);
            return;
        }
        fuse_write_out o{};
        o.size = wi.size;
        reply(h.unique, 0, &o, sizeof o);
        return;
    }
    case FUSE_RELEASE: {
        fuse_release_in ri;
        in(ri);
        fhs.erase(ri.fh);
        lk.unlock();
        reply(h.unique, 0);
        return;
    }
    case FUSE_OPENDIR: {
        if (node.kind != Kind::Dir) break;
        // 開夾那刻拍一張名單：procs/ 的連結隨時會變，分段讀才不會漏或重複
        auto list = std::make_shared<std::vector<DirEnt>>();
        list->push_back({".", nid, S_IFDIR >> 12});
        list->push_back({"..", node.parent, S_IFDIR >> 12});
        for (uint64_t c : node.kids) list->push_back({nodes.at(c).name, c, dirent_type(nodes.at(c).kind)});
        fuse_open_out o{};
        o.fh = next_fh++;
        dirs[o.fh] = std::move(list);
        lk.unlock();
        reply(h.unique, 0, &o, sizeof o);
        return;
    }
    case FUSE_READDIR: {
        fuse_read_in ri;
        in(ri);
        auto d = dirs.find(ri.fh);
        auto list = d == dirs.end() ? nullptr : d->second;
        lk.unlock();
        if (!list) {
            reply(h.unique, EBADF);
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
        reply(h.unique, 0, out.data(), out.size());
        return;
    }
    case FUSE_RELEASEDIR: {
        fuse_release_in ri;
        in(ri);
        dirs.erase(ri.fh);
        lk.unlock();
        reply(h.unique, 0);
        return;
    }
    case FUSE_FLUSH:
    case FUSE_FSYNC:
    case FUSE_FSYNCDIR:
        lk.unlock();
        reply(h.unique, 0);
        return;
    case FUSE_STATFS: {
        lk.unlock();
        fuse_statfs_out o{};
        o.st.bsize = o.st.frsize = 4096;
        o.st.namelen = 255;
        reply(h.unique, 0, &o, sizeof o);
        return;
    }
    default:
        // 其餘（ACCESS、GETXATTR、LISTXATTR…）回 ENOSYS，核心多半就記住不再問
        lk.unlock();
        reply(h.unique, ENOSYS);
        return;
    }
    lk.unlock();
    reply(h.unique, EACCES);
}

}  // namespace aos::procfs
