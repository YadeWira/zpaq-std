# zpaq-std

**A fork by [YadeWira](https://github.com/YadeWira), based on `fcorbelli/zpaqfranz`.**

A deduplicated, multi-version archiver (originally a fork of [zpaq](http://mattmahoney.net/zpaq.html) by Matt Mahoney, with the bulk of the code coming via Franco Corbelli's `zpaqfranz` fork), maintained as a **single-file C++ program** with **17 bundled, swappable external compression algorithms** and **zero system dependencies**.

Think of it as a single-file "Time Machine": every run only adds the deltas, so 5 daily backups of the same data cost roughly **the same space as 1**, not 5×. The archive is **append-only**, so `rsync --append` over a slow link only transfers what was actually added since the last sync.

This is **YadeWira's personal fork**. The new work here is the bundled-compressors architecture: pick the algorithm at archive time, no host setup needed. The base code (the deduplication engine, the journaling archiver, the single-file C++ layout) is Franco Corbelli's, derived in turn from Matt Mahoney's public-domain zpaq 7.15. See [CONTRIBUTORS](CONTRIBUTORS) for the full attribution chain.

---

## What it does

- **Deduplicated** — identical blocks across files and versions are stored once
- **Versioned** — each run is a new "snapshot" inside the same `.zpaq` file
- **Compressed** — every block goes through zpaq's internal DCE + CM codec, then optionally through a **second-pass external compressor** chosen per-archive
- **Append-only** — never modifies existing data; ideal for incremental cloud sync
- **Self-verifying** — triple-checksums (CRC-32, XXHASH64, SHA-1) per block, with optional SHA-2/SHA-3/Whirlpool/BLAKE3
- **Single file** — no repositories, no databases, no temp files; one `.zpaq` is the whole backup

---

## External compression: `-ma:algo:N`

The killer feature of this fork. You can pick **which external algorithm compresses each block**, without installing anything — everything is bundled under `compressors/`.

| Switch | Algorithm | Range | Default | Best for |
|---|---|---|---|---|
| `-ma:lz4:N` / `lz4hc` / `lz4f` | LZ4 v1.10.0 | 1–12 | 9 | speed (fastest) |
| `-ma:zstd:N` | zstd v1.5.7 | 1–22 | 3 | balanced (general purpose) |
| `-ma:flzma2:N` | fast-lzma2 v1.0.1 | 1–10 | 5 | LZMA2 fast, 2–8× faster than ref |
| `-ma:lz5:N` / `lz5hc` / `lz5f` | LZ5 v1.5 | 1–15 | 9 | LZ4-compatible, denser |
| `-ma:lizard:N` | Lizard v2.1 | 10–49 | 17 | LZ4-class with better ratio |
| `-ma:bzip2:N` | bzip2 v1.0.8 | 1–9 | 9 | BWT+HF, classic |
| `-ma:bzip3:N` | bzip3 v1.5.3 | 1–9 | 5 | BWT+ANS, modern bzip2 successor |
| `-ma:brotli:N` | brotli v1.2.0 | 0–11 | 11 | Google's compressor (text) |
| `-ma:snappy:N` | Snappy v1.2.1 | 1–2 | 1 | Google's, like lz4 but tighter |
| `-ma:deflate:N` | libdeflate v1.24 | 0–12 | 6 | fast deflate/inflate (ebiggers) |
| `-ma:lz:N` | lzlib v1.16 | 0–9 | 6 | LZMA, BSD-2 lzip stream API |
| `-ma:lzav:N` | LZAV v5.8 (avaneev) | 0–1 | 0 | LZ77, header-only, very fast |
| `-ma:hs:N` | heatshrink v0.4.1 (atomicobject) | 0–2 | 0 | tiny, embedded-grade (2KB/8KB/32KB window) |
| `-ma:lzfse` | LZFSE (Apple, BSD-3) | 0–1 | 0 | high ratio on text/structured data |
| `-ma:bsc:N` | libbsc v3.3.12 (IlyaGrebnov, Apache-2.0) | 1–9 | 3 | BWT/ST + LZP + QLFC, very slow |
| `-ma:lzh:N` | LZHAM (richgel999, Public Domain) | 1–4 | 1 | LZMA-class, very slow |

If the external pass produces output larger than `orig - 16` bytes, the original is kept (no regression).

### Example

```bash
# Speed: zstd level 3 (good for nightly backups)
zpaq-std a backup.zpaq /data -ma:zstd:3

# Best ratio for text: brotli 11
zpaq-std a docs.zpaq ~/Documents -ma:brotli:11

# Old-school bzip2
zpaq-std a legacy.zpaq archive.tar -ma:bzip2:9

# Mixed (one algo per file)
zpaq-std a mixed.zpaq bigfile.bin -ma:flzma2:5
zpaq-std a mixed.zpaq *.txt  -ma:brotli:11
```

The chosen algo and original size are recorded in each block's metadata as `zpaqstd-ma:<algo>:<level>:<origSize>`, so a single archive can mix algos freely and decompress correctly even if the embedded bitstream changes.

---

## No system dependencies

All 17 libraries live inside `compressors/`:

```
compressors/
├── lz4/         2 .c  + 2 .h
├── zstd/        1 .c  + 2 .h   (amalgamated)
├── fl2/        13 .c + 22 .h   (fast-lzma2)
├── lz5/         2 .c  + 4 .h
├── lizard/     10 .c + 26 .h
├── bzip2/       7 .c  +  2 .h
├── bzip3/       1 .c  +  4 .h
├── brotli/     35 .c + 71 .h   (enc+dec+common)
├── snappy/      7 .cpp + 6 .h  (Google, BSD-3)
├── libdeflate/ 39 .c  +  4 .h  (ebiggers, MIT; core+lib/x86+lib/arm)
├── lzlib/      13 .c  +  1 .h  (lzip, BSD-2; single-TU wrapper)
├── lzav/        1 .h            (header-only)
├── hs/          2 .c  + 1 .h   (+ hs_wrapper.c glue)
├── lzfse/       7 .c           (+lzvn helpers)
├── bsc/        12 .cpp + libsais.c
└── lzham/      19 .cpp
```

Total: **~145 source files, ~10.7 MB**. No `apt install`, no `brew install`, no `-lz`, no `-lbrotli`. Just `make`.

---

## Build

Requires only a C++ compiler (g++, clang++) and GNU make. pthread for multithreading.

```bash
make              # optimized build
make debug        # with -O0 -g
make static       # static binary (NAS, containers, rescue)
make m32          # 32-bit i386 ELF (requires g++-multilib)
make test         # run zpaq-std's built-in autotest
make check        # show configuration
```

Cross-compile:
```bash
make CROSS_COMPILE=aarch64-linux-gnu-     # ARM64 Linux
make CROSS_COMPILE=x86_64-w64-mingw32-    # 64-bit Windows (MinGW-w64)
make CROSS_COMPILE=i686-w64-mingw32-      # 32-bit Windows (MinGW-w64)
```

The 32-bit Linux build (`make m32`) uses `g++-multilib` and forces the older C++ ABI (`-D_GLIBCXX_USE_CXX11_ABI=0`) so it links against `libstdc++-32`. Useful for i386 distros and wine testing.

The Windows cross-compile via `make CROSS_COMPILE=x86_64-w64-mingw32-` produces a
self-contained `zpaq-std.exe` (static MinGW runtime, links only `msvcrt` + core
system DLLs) that runs on a clean Windows 7+ box. Verified on Windows 10: the binary
loads and **all bundled `-ma` external compressors round-trip correctly** (full parity
with the native Linux build, SHA-1 verified). The `i686-w64-mingw32-` (32-bit)
variant uses the same flags.

On non-x86 the JIT is auto-disabled; on x86_64 you get HW SHA-1/SHA-2 acceleration (`-DHWSHA2`).

The output is a single `zpaq-std` binary, ~6.5 MB native / ~8.5 MB Windows.

---

## Install

```bash
make install            # to /usr/local/bin (or PREFIX=/opt)
make install-clean      # install and remove local build
make install-nointel    # disable JIT explicitly
```

On FreeBSD/OpenBSD/NetBSD use `gmake`.

---

## Usage

The classic 7z-style verbs:
- `a` archive files into the .zpaq
- `x` extract (optionally `-until N` to pick a version, `-to dir/`)
- `l` list contents of a version
- `i` show all versions and their stats
- `c` compare / verify

See `zpaq-std h <command>` for full help, or `zpaq-std h voodoo` for the full list of switches (the new `-ma:*` family is documented there).

---

## Why a fork

The original zpaq 7.15 (Matt Mahoney, 2009–2016) is unmaintained. This fork preserves the single-file C++ codebase of its upstream lineage and adds the **bundled-compressor** philosophy: pick the algorithm at archive time, no host setup needed.

See [CONTRIBUTORS](CONTRIBUTORS) for full attributions.

---

## License

MIT (see `LICENSE` and `COPYING`). Third-party libraries in `compressors/` keep their original licenses (BSD, Apache 2.0, etc.).
