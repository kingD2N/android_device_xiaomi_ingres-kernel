# Prebuilt kernel — POCO F4 GT / Redmi K50 Gaming (ingres)

Format **AOSPA** (`KERNEL_PREBUILT_DIR`, dipakai `device/qcom/common/dlkm/kernel-platform.mk`), branch `calcite` (Android 17).

| Isi | Sumber |
|---|---|
| `Image` | `ALL-PROJECT-D2N` rilis `TES/boot.img` — 5.10.272-gki-MIX™-KERNEL-kingD2N |
| `dtbs/waipio.dtb`, `dtbs/dtbo.img` | LineageOS 23.2 ingres (Ingres-Centre, 20260209) |
| `vendor_ramdisk/*.ko` (338), `vendor_dlkm/*.ko` (393) | LineageOS 23.2 ingres (20260209) |
| `kernel-headers/` | UAPI header AOSPA marble-kernel (calcite) — wajib untuk `LOCAL_HBM_UI_READY` dll. di udfps/sensor-notifier |

Kernel `Image` sudah dicek CRC (`CONFIG_MODVERSIONS`) terhadap **semua 731 modul**: cocok.
Modul prebuilt lama (branch `lineage-22.2`, RushKernel) **tidak** cocok dengan kernel MIX (301 modul gagal) — jangan dicampur.

## Update

```bash
./update-prebuilt.sh lineage-23.2-XXXX-ingres.zip TES-boot.img   # kernel custom + modul ROM
./update-prebuilt.sh rom.zip                                      # kernel + modul dari ROM yang sama
./gencommit.sh
```

Script menolak (exit 3) kalau ada modul yang tidak bisa dimuat kernel.
