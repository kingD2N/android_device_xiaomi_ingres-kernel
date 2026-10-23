#!/usr/bin/env python3
"""Check whether vendor .ko modules can load on a GKI 5.10 Image (CONFIG_MODVERSIONS).
usage: crccheck.py Image kallsyms.txt moddir [moddir...]
Exports are read from __ksymtab{,_gpl} (PREL32) + __kcrctab{,_gpl}; module demands from __versions.
Symbols exported by other modules in the given dirs are resolved too.
"""
import os, struct, sys


def load_syms(path):
    s = {}
    for line in open(path):
        p = line.split()
        if len(p) >= 3:
            s[p[2]] = int(p[0], 16)
    return s


def kernel_exports(img, syms):
    d = open(img, "rb").read()
    base = syms["_text"]
    exp = {}
    for tab, crc in (("__ksymtab", "__kcrctab"), ("__ksymtab_gpl", "__kcrctab_gpl")):
        a, b = syms["__start_" + tab], syms["__stop_" + tab]
        c = syms["__start_" + crc]
        n = (b - a) // 12
        for i in range(n):
            ea = a + i * 12
            vo, no, _ = struct.unpack_from("<iii", d, ea - base)
            na = ea + 4 + no
            off = na - base
            name = d[off:d.index(b"\0", off)].decode()
            exp[name] = struct.unpack_from("<I", d, c + i * 4 - base)[0]
    return exp


def elf_sections(b):
    shoff, = struct.unpack_from("<Q", b, 0x28)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", b, 0x3A)
    secs = []
    for i in range(shnum):
        o = shoff + i * shentsize
        nm, ty, fl, ad, of, sz = struct.unpack_from("<IIQQQQ", b, o)
        secs.append([nm, ty, of, sz])
    so = secs[shstrndx][2]
    out = {}
    for nm, ty, of, sz in secs:
        name = b[so + nm:b.index(b"\0", so + nm)].decode()
        out[name] = (ty, of, sz)
    return out, secs


def ko_info(path):
    b = open(path, "rb").read()
    secs, raw = elf_sections(b)
    want = {}
    if "__versions" in secs:
        _, of, sz = secs["__versions"]
        for i in range(0, sz, 64):
            crc, = struct.unpack_from("<Q", b, of + i)
            nm = b[of + i + 8: of + i + 64].split(b"\0")[0].decode()
            want[nm] = crc & 0xffffffff
    # exported symbols of the module itself: __ksymtab_<name> symbols in symtab
    provides = set()
    if ".symtab" in secs and ".strtab" in secs:
        _, so, ssz = secs[".symtab"]
        _, to, _ = secs[".strtab"]
        for i in range(0, ssz, 24):
            nm, = struct.unpack_from("<I", b, so + i)
            n = b[to + nm:b.index(b"\0", to + nm)].decode()
            if n.startswith("__ksymtab_") and not n.startswith("__ksymtab_gpl"):
                provides.add(n[len("__ksymtab_"):])
    return want, provides


def main():
    img, ks, dirs = sys.argv[1], sys.argv[2], sys.argv[3:]
    exp = kernel_exports(img, load_syms(ks))
    mods = {}
    for d in dirs:
        for f in sorted(os.listdir(d)):
            if f.endswith(".ko"):
                mods[os.path.join(d, f)] = ko_info(os.path.join(d, f))
    modprov = set()
    for w, p in mods.values():
        modprov |= p
    bad = {}
    for path, (want, _) in mods.items():
        for sym, crc in want.items():
            if sym in exp:
                if exp[sym] != crc:
                    bad.setdefault(path, []).append("%s (ko %08x != kernel %08x)" % (sym, crc, exp[sym]))
            elif sym not in modprov:
                bad.setdefault(path, []).append("%s (not exported)" % sym)
    print("kernel exports:", len(exp), "modules:", len(mods))
    if not bad:
        print("RESULT: OK - semua modul cocok CRC dengan kernel")
        return 0
    print("RESULT: GAGAL - %d modul tidak cocok" % len(bad))
    for p, l in sorted(bad.items()):
        print(" ", os.path.basename(p), ":", "; ".join(l[:4]), "..." if len(l) > 4 else "")
    return 3


if __name__ == "__main__":
    sys.exit(main())
