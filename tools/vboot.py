#!/usr/bin/env python3
"""Unpack vendor_boot v3/v4: dtb, ramdisk fragments, cmdline, bootconfig.
usage: vboot.py vendor_boot.img outdir
"""
import os, struct, sys


def al(x, p):
    return (x + p - 1) // p * p


def main():
    img, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    d = open(img, "rb").read()
    assert d[:8] == b"VNDRBOOT", "not vendor_boot"
    ver, page, kaddr, raddr, rsize = struct.unpack_from("<5I", d, 8)
    cmdline = d[28:28 + 2048].split(b"\0")[0]
    o = 28 + 2048
    tags, = struct.unpack_from("<I", d, o); o += 4
    name = d[o:o + 16].split(b"\0")[0]; o += 16
    hsize, dtbsize = struct.unpack_from("<II", d, o); o += 8
    o += 8  # dtb addr
    tsize = tnum = tesize = bcsize = 0
    if ver >= 4:
        tsize, tnum, tesize, bcsize = struct.unpack_from("<4I", d, o)
    off_r = al(hsize, page)
    off_dtb = off_r + al(rsize, page)
    off_tab = off_dtb + al(dtbsize, page)
    off_bc = off_tab + al(tsize, page)
    open(os.path.join(out, "cmdline"), "wb").write(cmdline + b"\n")
    open(os.path.join(out, "dtb"), "wb").write(d[off_dtb:off_dtb + dtbsize])
    if bcsize:
        open(os.path.join(out, "bootconfig"), "wb").write(d[off_bc:off_bc + bcsize])
    frags = []
    if ver >= 4 and tnum:
        for i in range(tnum):
            e = d[off_tab + i * tesize: off_tab + (i + 1) * tesize]
            sz, of, ty = struct.unpack_from("<3I", e, 0)
            nm = e[12:12 + 32].split(b"\0")[0].decode() or "ramdisk%02d" % i
            frags.append((nm, ty, d[off_r + of: off_r + of + sz]))
    else:
        frags.append(("ramdisk00", 1, d[off_r:off_r + rsize]))
    for i, (nm, ty, blob) in enumerate(frags):
        fn = "vendor_ramdisk%02d" % i
        open(os.path.join(out, fn), "wb").write(blob)
        print("fragment", i, repr(nm), "type", ty, len(blob), "->", fn)
    print("header_version", ver, "page", page, "name", name, "dtb", dtbsize, "bootconfig", bcsize)
    print("cmdline:", cmdline.decode(errors="replace"))


if __name__ == "__main__":
    main()
