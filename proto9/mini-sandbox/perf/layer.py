"""One synthetic file layer for the flat bench, kept as lean as a small kernel: cover tree/m/d<i> with a tmpfs, then start the next layer in a new user+mount namespace (layer mode) or cover all n here at once (flat mode); the last step is the agent's own extra namespace, which tries to undo a cover."""
# usage (inside unshare -Urm): python3 -I layer.py layer TREE I N | python3 -I layer.py flat TREE N
import ctypes
import os
import sys

libc = ctypes.CDLL(None, use_errno=True)
MS_NOSUID, MS_NODEV = 2, 4
LEAF = ("umount {tree}/m/d0 2>/dev/null && echo umount-worked; "
        "test -z \"$(ls -A {tree}/m/d{last})\" && echo leaf-ok")


def cover(tree, i):
    if libc.mount(b"tmpfs", ("%s/m/d%d" % (tree, i)).encode(), b"tmpfs", ctypes.c_ulong(MS_NOSUID | MS_NODEV),
                  b"size=1m") != 0:
        e = ctypes.get_errno()
        sys.exit("layer: mount d%d: %s" % (i, os.strerror(e)))


def leaf(tree, n):
    os.execvp("unshare", ["unshare", "-Urm", "sh", "-c", LEAF.format(tree=tree, last=n - 1)])


mode, tree = sys.argv[1], sys.argv[2]
if mode == "layer":
    i, n = int(sys.argv[3]), int(sys.argv[4])
    cover(tree, i)
    if i + 1 < n:
        os.execvp("unshare", ["unshare", "-Urm", sys.executable, "-I", "-B", os.path.abspath(__file__), "layer",
                              tree, str(i + 1), str(n)])
    leaf(tree, n)
else:
    n = int(sys.argv[3])
    for i in range(n):
        cover(tree, i)
    leaf(tree, n)
