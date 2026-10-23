#!/usr/bin/env bash
#
# SPDX-FileCopyrightText: kingD2N
# SPDX-License-Identifier: Apache-2.0
#
# Refresh prebuilt kernel ingres (format AOSPA / KERNEL_PREBUILT_DIR).
#
#   ./update-prebuilt.sh <rom.zip|payload.bin> [boot.img]
#
#   rom.zip   : ROM LineageOS/AOSP ingres (full OTA, payload.bin) -> sumber
#               DTB (vendor_boot), dtbo.img, modul vendor_ramdisk + vendor_dlkm
#   boot.img  : kernel custom (mis. TES/boot.img D2N). Kosong = kernel dari ROM.
#
# Kernel custom HANYA dipasang kalau CRC simbolnya cocok dengan semua modul
# (CONFIG_MODVERSIONS). Kalau tidak cocok -> script berhenti (exit 3).
#
# Butuh: python3, lz4, zstd, cpio, debugfs (e2fsprogs), fsck.erofs (erofs-utils),
#        kallsyms-finder (pip: git+https://github.com/marin-m/vmlinux-to-elf)

set -euo pipefail

MY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${1:?pakai: $0 <rom.zip|payload.bin> [boot.img]}"
BOOT="${2:-}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

log() { echo "[ingres-kernel] $*"; }

# 1) payload
if [[ "$SRC" == *.zip ]]; then
    log "unzip payload.bin"
    unzip -q -o "$SRC" payload.bin -d "$TMP"
    PAYLOAD="$TMP/payload.bin"
else
    PAYLOAD="$SRC"
fi
python3 -I "$MY_DIR/tools/payload_extract.py" "$PAYLOAD" "$TMP/img" boot,vendor_boot,dtbo,vendor_dlkm

# 2) kernel
KIMG="$TMP/Image"
if [ -n "$BOOT" ]; then
    python3 -I - "$BOOT" "$KIMG" <<'EOF'
import struct, sys
d = open(sys.argv[1], "rb").read()
assert d[:8] == b"ANDROID!", "bukan boot.img"
ks, ver = struct.unpack_from("<I", d, 8)[0], struct.unpack_from("<I", d, 40)[0]
page = 4096 if ver >= 3 else struct.unpack_from("<I", d, 36)[0]
open(sys.argv[2], "wb").write(d[page:page + ks])
EOF
else
    python3 -I - "$TMP/img/boot.img" "$KIMG" <<'EOF'
import struct, sys
d = open(sys.argv[1], "rb").read()
ks = struct.unpack_from("<I", d, 8)[0]
open(sys.argv[2], "wb").write(d[4096:4096 + ks])
EOF
fi
log "kernel: $(strings "$KIMG" | grep -m1 '^Linux version 5' | cut -d' ' -f1-3)"

# 3) vendor_boot -> dtb + ramdisk modules
python3 -I "$MY_DIR/tools/vboot.py" "$TMP/img/vendor_boot.img" "$TMP/vb" >/dev/null
mkdir -p "$TMP/vbr"
for f in "$TMP"/vb/vendor_ramdisk*; do
    (cd "$TMP/vbr" && { lz4 -dc "$f" 2>/dev/null || zstd -dc "$f" 2>/dev/null || cat "$f"; } | cpio -idm --quiet 2>/dev/null) || true
done

# 4) vendor_dlkm (ext4 atau erofs)
mkdir -p "$TMP/dlkm"
if file "$TMP/img/vendor_dlkm.img" | grep -qi erofs; then
    fsck.erofs --extract="$TMP/dlkm" "$TMP/img/vendor_dlkm.img" >/dev/null
else
    debugfs -R "rdump / $TMP/dlkm" "$TMP/img/vendor_dlkm.img" >/dev/null 2>&1
fi

# 5) CRC check
kallsyms-finder "$KIMG" > "$TMP/kallsyms.txt" 2>/dev/null
python3 -I "$MY_DIR/tools/crccheck.py" "$KIMG" "$TMP/kallsyms.txt" \
    "$TMP/vbr/lib/modules" "$TMP/dlkm/lib/modules" | tee "$TMP/crc.log"
grep -q "RESULT: OK" "$TMP/crc.log" || { log "CRC tidak cocok -> dibatalkan"; exit 3; }

# 6) install
rm -rf "$MY_DIR/vendor_ramdisk" "$MY_DIR/vendor_dlkm" "$MY_DIR/dtbs"
mkdir -p "$MY_DIR/vendor_ramdisk" "$MY_DIR/vendor_dlkm" "$MY_DIR/dtbs"
cp "$KIMG" "$MY_DIR/Image"
grep -E " [tTdDrRbBwW] " "$TMP/kallsyms.txt" | sort > "$MY_DIR/System.map"
cp "$TMP/vb/dtb" "$MY_DIR/dtbs/waipio.dtb"
python3 -I - "$TMP/img/dtbo.img" "$MY_DIR/dtbs/dtbo.img" <<'EOF'
import struct, sys
d = open(sys.argv[1], "rb").read()
total = struct.unpack_from(">I", d, 4)[0]
open(sys.argv[2], "wb").write(d[:total])
EOF
cp "$TMP"/vbr/lib/modules/* "$MY_DIR/vendor_ramdisk/"
cp "$TMP"/dlkm/lib/modules/* "$MY_DIR/vendor_dlkm/"
# AOSPA kernel-platform.mk butuh nama file lengkap (.ko) di modules.load*
for f in "$MY_DIR"/vendor_ramdisk/modules.load "$MY_DIR"/vendor_ramdisk/modules.load.recovery "$MY_DIR"/vendor_dlkm/modules.load; do
    [ -f "$f" ] && sed -i -E '/\.ko$/! s/$/.ko/' "$f"
done
log "selesai: $(ls "$MY_DIR"/vendor_ramdisk/*.ko | wc -l) modul ramdisk, $(ls "$MY_DIR"/vendor_dlkm/*.ko | wc -l) modul dlkm"
