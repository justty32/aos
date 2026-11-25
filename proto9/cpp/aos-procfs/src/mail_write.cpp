// mail_write.cpp：回答的線上信箱資料夾的「寫」——在 tmp/ 開檔或信夾、寫入、截短與改屬性；照上限擋（EFBIG／ENOSPC），只碰記憶體。
#include "internal.hpp"

#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>

namespace aos::procfs {

void Fs::Impl::mail_make(const Req& r, Lock& lk, uint64_t pid, const std::string& name, bool dir, uint32_t mode, bool open) {
    Node& p = nodes.at(pid);
    Mailbox::Impl& mb = *p.mb;
    double now = wall_now();
    bool top_level = p.role == Role::Tmp;
    if (top_level) mb.sweep(now);
    int err = 0;
    if (!top_level && !(p.role == Role::Letter && open_in_tmp(nodes, p))) err = EPERM;   // 只能在 tmp/ 寫，再搬進 new/
    else if (dir && !top_level) err = EPERM;                                               // 信夾裡不能再開夾
    else if (!mail_name_ok(name)) err = EINVAL;
    else if (kid(p, name)) err = EEXIST;
    else if (top_level && mb.entries >= mb.lim.max_letters) err = ENOSPC;
    else if (!top_level && p.kids.size() >= mb.lim.max_files) err = ENOSPC;
    if (err == ENOSPC) {
        ++mb.refused;
        mb.last_refusal = top_level ? "MailboxFull " + std::to_string(mb.entries) + " letters (max_letters)"
                                    : "LetterTooManyFiles " + std::to_string(p.kids.size()) + " files (max_files)";
    }
    if (err) {
        lk.unlock();
        reply(r.h.unique, err);
        return;
    }
    Node n;
    n.kind = dir ? Kind::MailDir : Kind::MailFile;
    n.role = dir ? Role::Letter : Role::None;
    n.mb = &mb;
    n.mode = mode & 07777;
    n.parent = pid;
    n.name = name;
    n.mtime = n.touched = now;
    if (!dir) n.body = std::make_shared<std::string>();
    uint64_t id = next_nid++;
    n.top = top_level ? id : p.top;
    nodes[id] = std::move(n);
    p.kids.push_back(id);   // unordered_map 加新項不會讓別項的參考失效
    p.mtime = now;
    if (top_level) ++mb.entries;
    Node& t = nodes.at(nodes.at(id).top);
    t.touched = t.mtime = now;
    fuse_entry_out e = entry_of(id, nodes.at(id));
    lk.unlock();
    if (!open) {
        reply(r.h.unique, 0, &e, sizeof e);
        return;
    }
    fuse_open_out o{};
    o.open_flags = FOPEN_DIRECT_IO;
    char out[sizeof e + sizeof o];
    std::memcpy(out, &e, sizeof e);
    std::memcpy(out + sizeof e, &o, sizeof o);
    reply(r.h.unique, 0, out, sizeof out);
}

int Fs::Impl::mail_resize(Node& f, size_t size) {
    Mailbox::Impl& mb = *f.mb;
    Node& t = nodes.at(f.top);
    size_t old = f.body->size();
    if (size > old) {
        size_t d = size - old;
        if (size > mb.lim.max_letter_bytes || t.lbytes + d > mb.lim.max_letter_bytes) {
            ++mb.refused;
            mb.last_refusal = "LetterTooBig " + t.name + " over " + std::to_string(mb.lim.max_letter_bytes) + " bytes (max_letter_bytes)";
            return EFBIG;
        }
        if (mb.bytes + d > mb.lim.max_total_bytes) {
            ++mb.refused;
            mb.last_refusal = "MailboxFull " + std::to_string(mb.bytes) + " bytes held (max_total_bytes)";
            return ENOSPC;
        }
        t.lbytes += d;
        mb.bytes += d;
    } else {
        t.lbytes -= old - size;
        mb.bytes -= old - size;
    }
    f.body->resize(size);
    double now = wall_now();
    f.mtime = t.touched = t.mtime = now;
    return 0;
}

void Fs::Impl::mail_write(const Req& r, Lock& lk, Node& node) {
    fuse_write_in wi;
    r.in(wi);
    int err = 0;
    size_t off = sizeof wi;
    size_t n = off < r.blen ? std::min<size_t>(wi.size, r.blen - off) : 0;
    if (node.kind != Kind::MailFile || !open_in_tmp(nodes, node)) err = EPERM;   // 已經搬進 new/：封住了
    else if (wi.offset > node.mb->lim.max_letter_bytes) err = mail_resize(node, node.mb->lim.max_letter_bytes + 1);
    else if (wi.offset + n > node.body->size()) err = mail_resize(node, static_cast<size_t>(wi.offset + n));
    if (!err) {
        std::memcpy(node.body->data() + wi.offset, r.body + off, n);
        Node& t = nodes.at(node.top);
        node.mtime = t.touched = t.mtime = wall_now();
    }
    lk.unlock();
    if (err) {
        reply(r.h.unique, err);
        return;
    }
    fuse_write_out o{};
    o.size = static_cast<uint32_t>(n);
    reply(r.h.unique, 0, &o, sizeof o);
}

void Fs::Impl::mail_setattr(const Req& r, Lock& lk, uint64_t nid, Node& node) {
    fuse_setattr_in si;
    r.in(si);
    bool mine = open_in_tmp(nodes, node);   // 還在 tmp/ 的才改得動；new/ 裡的與四個固定的夾只當沒事（時間）或拒（其餘）
    int err = 0;
    if (si.valid & (FATTR_UID | FATTR_GID)) err = EPERM;
    else if ((si.valid & FATTR_SIZE) && node.kind != Kind::MailFile) err = EISDIR;
    else if ((si.valid & (FATTR_SIZE | FATTR_MODE)) && !mine) err = EPERM;
    else if (si.valid & FATTR_SIZE) err = si.size > node.mb->lim.max_letter_bytes ? mail_resize(node, node.mb->lim.max_letter_bytes + 1)
                                                                                : mail_resize(node, static_cast<size_t>(si.size));
    if (!err && mine) {
        if (si.valid & FATTR_MODE) node.mode = si.mode & 07777;
        if (si.valid & FATTR_MTIME_NOW) node.mtime = wall_now();
        else if (si.valid & FATTR_MTIME) node.mtime = static_cast<double>(si.mtime) + si.mtimensec / 1e9;
    }
    if (err) {
        lk.unlock();
        reply(r.h.unique, err);
        return;
    }
    fuse_attr_out o{};
    fill_attr(nid, node, o.attr);
    lk.unlock();
    reply(r.h.unique, 0, &o, sizeof o);
}

}  // namespace aos::procfs
