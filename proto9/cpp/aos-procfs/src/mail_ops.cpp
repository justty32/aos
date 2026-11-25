// mail_ops.cpp：回答的線上信箱資料夾的操作——分派、讀、刪，搬進 new/（不覆蓋、可拒收）；寫的那一半在 mail_write.cpp。只碰記憶體。
#include "internal.hpp"

#include <cerrno>
#include <fcntl.h>
#include <linux/fs.h>
#include <sys/stat.h>
#include <unistd.h>

namespace aos::procfs {

bool Fs::Impl::mail_op(const Req& r, Lock& lk, uint64_t nid, Node& node) {
    auto fail = [&](int e) {
        lk.unlock();
        reply(r.h.unique, e);
        return true;
    };
    switch (r.h.opcode) {
    case FUSE_CREATE: {
        fuse_create_in ci;
        r.in(ci);
        mail_make(r, lk, nid, r.name_at(sizeof ci), false, ci.mode & ~ci.umask, true);
        return true;
    }
    case FUSE_MKNOD: {
        fuse_mknod_in mi;
        r.in(mi);
        if ((mi.mode & S_IFMT) != S_IFREG) return fail(EPERM);
        mail_make(r, lk, nid, r.name_at(sizeof mi), false, mi.mode & ~mi.umask, false);
        return true;
    }
    case FUSE_MKDIR: {
        fuse_mkdir_in di;
        r.in(di);
        mail_make(r, lk, nid, r.name_at(sizeof di), true, di.mode & ~di.umask, false);
        return true;
    }
    case FUSE_SETATTR: mail_setattr(r, lk, nid, node); return true;
    case FUSE_OPEN: {
        fuse_open_in oi;
        r.in(oi);
        if (node.kind != Kind::MailFile) return fail(EISDIR);
        if ((oi.flags & O_ACCMODE) != O_RDONLY && !open_in_tmp(nodes, node)) return fail(EACCES);
        lk.unlock();
        fuse_open_out o{};
        o.open_flags = FOPEN_DIRECT_IO;   // 長度隨時在變：不走頁快取，讀寫都直接到這裡
        reply(r.h.unique, 0, &o, sizeof o);
        return true;
    }
    case FUSE_READ: {
        fuse_read_in ri;
        r.in(ri);
        if (node.kind != Kind::MailFile) return fail(EISDIR);
        const std::string& b = *node.body;
        size_t off = ri.offset < b.size() ? static_cast<size_t>(ri.offset) : b.size();
        std::string out = b.substr(off, std::min<size_t>(ri.size, b.size() - off));   // 拿著鎖抄：tmp/ 裡的還在被寫
        lk.unlock();
        reply(r.h.unique, 0, out.data(), out.size());
        return true;
    }
    case FUSE_WRITE: mail_write(r, lk, node); return true;
    case FUSE_UNLINK: mail_remove(r, lk, node, false); return true;
    case FUSE_RMDIR: mail_remove(r, lk, node, true); return true;
    case FUSE_RENAME:
    case FUSE_RENAME2: mail_rename(r, lk, nid, node); return true;
    case FUSE_LINK:
    case FUSE_SYMLINK: return fail(EPERM);   // 照 aos-post：只用 rename 投遞
    default: return false;
    }
}

void Fs::Impl::mail_remove(const Req& r, Lock& lk, Node& node, bool dir) {
    uint64_t c = kid(node, r.name_at(0));
    int err = 0;
    if (!c) err = ENOENT;
    else if (!open_in_tmp(nodes, nodes.at(c))) err = EPERM;   // new/ 裡的歸 proc（take 拿走）
    else if (dir && nodes.at(c).kind != Kind::MailDir) err = ENOTDIR;
    else if (dir && !nodes.at(c).kids.empty()) err = ENOTEMPTY;
    else if (!dir && nodes.at(c).kind != Kind::MailFile) err = EISDIR;
    if (!err) {
        uint64_t top = nodes.at(c).top;
        node.mb->drop(c);
        if (top != c) nodes.at(top).touched = wall_now();
    }
    lk.unlock();
    reply(r.h.unique, err);
}

void Fs::Impl::mail_rename(const Req& r, Lock& lk, uint64_t nid, Node& node) {
    uint64_t newdir;
    uint32_t flags = 0;
    size_t off;
    if (r.h.opcode == FUSE_RENAME2) {
        fuse_rename2_in ri;
        r.in(ri);
        newdir = ri.newdir;
        flags = ri.flags;
        off = sizeof ri;
    } else {
        fuse_rename_in ri;
        r.in(ri);
        newdir = ri.newdir;
        off = sizeof ri;
    }
    std::string from = r.name_at(off), to = r.name_at(off + from.size() + 1);
    auto done = [&](int e) {
        lk.unlock();
        reply(r.h.unique, e);
    };
    Mailbox::Impl& mb = *node.mb;
    auto dit = nodes.find(newdir);
    uint64_t src = kid(node, from);
    if (flags & ~static_cast<uint32_t>(RENAME_NOREPLACE)) return done(EINVAL);   // EXCHANGE、WHITEOUT 不給
    if (dit == nodes.end() || dit->second.mb != &mb) return done(EPERM);
    if (!src) return done(ENOENT);
    Node& d = dit->second;
    if (!open_in_tmp(nodes, nodes.at(src))) return done(nodes.at(src).sealed && node.role == Role::Tmp ? EBUSY : EPERM);
    if (!mail_name_ok(to)) return done(EINVAL);
    if (newdir == nid) {
        // 同一夾裡改名（tmp/ 裡、或信夾裡 write_json 的 .letter.json.<pid>.tmp → letter.json）；一樣不覆蓋
        if (to != from && kid(node, to)) return done(EEXIST);
        nodes.at(src).name = to;
        nodes.at(nodes.at(src).top).touched = wall_now();
        return done(0);
    }
    if (node.role != Role::Tmp || d.role != Role::New) return done(EPERM);   // 只有 tmp/ → new/ 這一條路
    if (to[0] == '.') return done(EINVAL);                                  // . 開頭的不算信（Maildir、aos-post）
    if (kid(d, to)) return done(EEXIST);                                    // 不覆蓋已經寄到的
    // 投遞：先封住（不能再寫、刪、搬、也不會被當過期丟掉），再問 accept
    Node& s = nodes.at(src);
    s.sealed = true;
    s.from_uid = r.h.uid;
    s.from_pid = r.h.pid;
    s.arrived = wall_now();
    Refusal no;
    if (mb.accept) {
        Letter l = mb.letter(src);
        l.name = to;
        Accept acc = mb.accept;
        lk.unlock();   // 不拿著表鎖叫使用者的回呼；src 封住了，放開的這段時間沒人動得了它
        try {
            no = acc(l);
        } catch (...) {
            no = {EIO, "Internal accept threw"};
        }
        lk.lock();
        if (!no.err && kid(d, to)) no = {EEXIST, ""};   // 放開的那段時間有人先寄了同名的
    }
    Node& s2 = nodes.at(src);   // 封住的不會被拿掉；重新拿參考，表在放開時可能長大過
    if (no.err) {
        s2.sealed = false;
        if (no.err != EEXIST) {
            ++mb.refused;
            mb.last_refusal = no.reason.empty() ? "Refused " + std::string(strerrorname_np(no.err) ? strerrorname_np(no.err) : "error") : no.reason;
        }
        return done(no.err == EXDEV ? EPERM : no.err);
    }
    std::erase(node.kids, src);
    d.kids.push_back(src);
    s2.parent = mb.nw;
    s2.name = to;
    s2.mode &= ~0222u;
    for (uint64_t c : s2.kids) nodes.at(c).mode &= ~0222u;
    node.mtime = d.mtime = s2.arrived;
    ++mb.delivered;
    uint64_t one = 1;
    if (write(mb.efd, &one, sizeof one) < 0) {}   // eventfd、非阻塞：只會在計數滿到 2^64 時失敗
    done(0);
}

}  // namespace aos::procfs
