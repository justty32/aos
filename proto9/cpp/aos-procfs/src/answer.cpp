// answer.cpp：回答的線——讀 /dev/fuse 一次一個請求、照 linux/fuse.h 分派與回覆；只碰記憶體，不碰任何檔案系統路徑。
#include "internal.hpp"

#include <cerrno>
#include <fcntl.h>
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
    case Kind::Dir:
    case Kind::MailDir: return S_IFDIR;
    case Kind::Link: return S_IFLNK;
    case Kind::Sock: return S_IFSOCK;
    default: return S_IFREG;
    }
}

// 隨時會變的節點：名字與屬性都不快取（symlink、socket、信箱裡的一切）
bool volatile_node(const Node& n) { return n.kind == Kind::Link || n.kind == Kind::Sock || n.mb; }

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

void Fs::Impl::fill_attr(uint64_t nid, const Node& n, fuse_attr& a) const {
    std::memset(&a, 0, sizeof a);
    a.ino = nid;
    a.mode = type_bits(n.kind) | n.mode;
    a.nlink = (n.kind == Kind::Dir || n.kind == Kind::MailDir) ? 2 : 1;
    a.uid = uid;
    a.gid = gid;
    a.blksize = 4096;
    a.atime = a.mtime = a.ctime = static_cast<uint64_t>(t0);
    if (n.mb && n.mtime > 0) {
        a.atime = a.mtime = a.ctime = static_cast<uint64_t>(n.mtime);
        a.atimensec = a.mtimensec = a.ctimensec = static_cast<uint32_t>((n.mtime - static_cast<double>(a.mtime)) * 1e9);
    }
    // 純文字檔報 0、靠 direct_io 讀；報真長度就得每次 stat 都產生一次，而且 stat 與讀之間會對不上
    if (n.kind == Kind::Json || n.kind == Kind::Link) a.size = n.data->size();
    if (n.kind == Kind::MailFile) a.size = n.body->size();
    a.blocks = (a.size + 511) / 512;
}

fuse_entry_out Fs::Impl::entry_of(uint64_t nid, const Node& n) const {
    fuse_entry_out e{};
    e.nodeid = nid;
    // kid 死了、信被拿走之後才不會還看到舊的一秒
    bool vol = volatile_node(n);
    e.entry_valid = vol ? 0 : 1;
    e.attr_valid = vol ? 0 : 1;
    fill_attr(nid, n, e.attr);
    return e;
}

uint64_t Fs::Impl::kid(const Node& dir, const std::string& name) const {
    if (dir.kind != Kind::Dir && dir.kind != Kind::MailDir) return 0;
    for (uint64_t c : dir.kids)
        if (nodes.at(c).name == name) return c;
    return 0;
}

void Fs::Impl::dispatch(const char* buf, size_t len) {
    Req r;
    std::memcpy(&r.h, buf, sizeof r.h);
    if (r.h.len > len) r.h.len = static_cast<uint32_t>(len);
    r.body = buf + sizeof r.h;
    r.blen = r.h.len - sizeof r.h;
    const fuse_in_header& h = r.h;

    switch (h.opcode) {
    case FUSE_INIT: {
        fuse_init_in ii;
        r.in(ii);
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

    Lock lk(mu);
    auto it = nodes.find(h.nodeid);
    if (it == nodes.end()) {
        lk.unlock();
        reply(h.unique, ENOENT);
        return;
    }
    uint64_t nid = it->first;
    Node& node = it->second;
    if (node.mb && mail_op(r, lk, nid, node)) return;

    switch (h.opcode) {
    case FUSE_LOOKUP: {
        uint64_t c = kid(node, r.name_at(0));
        if (c) {
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
        o.attr_valid = volatile_node(node) ? 0 : 1;
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
    case FUSE_MKNOD: return op_mknod(r, lk, nid, node);
    case FUSE_UNLINK: return op_unlink(r, lk, node);
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
    case FUSE_OPEN: return op_open(r, lk, node);
    case FUSE_READ: return op_read(r, lk);
    case FUSE_WRITE: return op_write(r, lk, node);
    case FUSE_RELEASE: {
        fuse_release_in ri;
        r.in(ri);
        fhs.erase(ri.fh);
        lk.unlock();
        reply(h.unique, 0);
        return;
    }
    case FUSE_OPENDIR: return op_opendir(r, lk, nid, node);
    case FUSE_READDIR: return op_readdir(r, lk);
    case FUSE_RELEASEDIR: {
        fuse_release_in ri;
        r.in(ri);
        dirs.erase(ri.fh);
        lk.unlock();
        reply(h.unique, 0);
        return;
    }
    case FUSE_FLUSH:
    case FUSE_FSYNC:
    case FUSE_FSYNCDIR:
        // fsync 一律成功：內容都在記憶體裡，沒有東西可以再往下寫（信的寄件人照 Maildir 會 fsync）
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
