#!/usr/bin/env python3
"""Minimal full-OTA payload.bin extractor (REPLACE / REPLACE_BZ / REPLACE_XZ / ZSTD / ZERO).
usage: payload_extract.py payload.bin outdir part1,part2,...
"""
import bz2, lzma, struct, sys, os, subprocess


def varint(b, i):
    r = s = 0
    while True:
        c = b[i]; i += 1
        r |= (c & 0x7f) << s; s += 7
        if c < 0x80:
            return r, i


def fields(b):
    i, n = 0, len(b)
    while i < n:
        key, i = varint(b, i)
        fn, wt = key >> 3, key & 7
        if wt == 0:
            v, i = varint(b, i)
        elif wt == 2:
            l, i = varint(b, i); v = b[i:i + l]; i += l
        elif wt == 1:
            v = b[i:i + 8]; i += 8
        elif wt == 5:
            v = b[i:i + 4]; i += 4
        else:
            raise ValueError("wire type %d" % wt)
        yield fn, v


def main():
    path, out, want = sys.argv[1], sys.argv[2], set(sys.argv[3].split(","))
    os.makedirs(out, exist_ok=True)
    f = open(path, "rb")
    hdr = f.read(24)
    assert hdr[:4] == b"CrAU", "not a payload"
    ver, msize = struct.unpack(">QQ", hdr[4:20])
    sigsize = struct.unpack(">I", hdr[20:24])[0] if ver >= 2 else 0
    if ver < 2:
        f.seek(20)
    man = f.read(msize)
    data_off = f.tell() + sigsize
    bs = 4096
    parts = []
    for fn, v in fields(man):
        if fn == 3:
            bs = v
        elif fn == 13:
            parts.append(v)
    for p in parts:
        name, ops = None, []
        for fn, v in fields(p):
            if fn == 1:
                name = v.decode()
            elif fn == 8:
                ops.append(v)
        if name not in want:
            continue
        dst = open(os.path.join(out, name + ".img"), "wb")
        for o in ops:
            t, doff, dlen, ext = 0, 0, 0, []
            for fn, v in fields(o):
                if fn == 1: t = v
                elif fn == 2: doff = v
                elif fn == 3: dlen = v
                elif fn == 6:
                    e = dict(fields(v)); ext.append((e.get(1, 0), e.get(2, 0)))
            f.seek(data_off + doff)
            raw = f.read(dlen) if dlen else b""
            if t == 0: blob = raw
            elif t == 1: blob = bz2.decompress(raw)
            elif t == 8: blob = lzma.decompress(raw)
            elif t == 14: blob = subprocess.run(["zstd", "-dc"], input=raw, capture_output=True, check=True).stdout
            elif t in (6, 7): blob = None
            else: raise SystemExit("%s: op type %d not supported (incremental OTA?)" % (name, t))
            pos = 0
            for start, num in ext:
                dst.seek(start * bs)
                size = num * bs
                if blob is None:
                    dst.write(b"\0" * size)
                else:
                    dst.write(blob[pos:pos + size]); pos += size
        dst.close()
        print("extracted", name, os.path.getsize(os.path.join(out, name + ".img")))


if __name__ == "__main__":
    main()
