# zpaq-std

**A fork by [YadeWira](https://github.com/YadeWira), based on `fcorbelli/zpaqfranz` 65.4.**

A deduplicated, multi-version archiver (originally [zpaq](http://mattmahoney.net/dc/zpaq.html) by Matt Mahoney, with most of the code coming via Franco Corbelli's `zpaqfranz`), with **21 bundled, swappable compression libraries** (29 `-ma` switches, every one of them opening in any zpaq), lossless **JPEG and JPEG-LS** recompression with `-sa` (experimental), and **zero system dependencies**.

Think of it as a single-file "Time Machine": every run only adds the deltas, so 5 daily backups of the same data cost roughly **the same space as 1**. The archive is **append-only**, so `rsync --append` over a slow link only transfers what was added.

More documentation: the **[wiki](https://github.com/YadeWira/zpaq-std/wiki)**. Releases: **[Releases](https://github.com/YadeWira/zpaq-std/releases)**.

| Component | Status |
|---|---|
| CI | [![CI][ciBadge]][ciLink] |
| Latest release | [![Release][relBadge]][relLink] |

## Platforms

| OS | Architectures | State |
|---|---|---|
| Windows (7 and later) | x86-64 | release binary; built and tested in CI, and on Windows 7 before each release |
| Windows (7 and later) | x86 | release binary; built and tested in CI, and on Windows 7 before each release |
| Linux | x86-64 | release binary; built and tested in CI and on the host (full test battery) |
| Linux | x86 (32-bit) | built and tested in CI |
| Linux | AArch64 | built and tested in CI; archives byte-identical to x86-64 |
| macOS | AArch64 | built and tested in CI; archives byte-identical to Linux x86-64 |

In CI every built-in method (`-m1`..`-m5` and every `-ma` switch that is not
plugin-only) compresses, extracts and tests on each platform, and the archives are
compared byte for byte: Linux and macOS with Linux x86-64, Windows x86 with Windows
x86-64 (on Windows the archive also stores each file's creation and access dates). The
32-bit builds write other, equally valid, bytes for four methods: `-ma:brotli`,
`-ma:lz6:0`, `-ma:lz4f` and `-ma:lz5f`. Every platform reads what any other writes.

---

## What it does

- **Deduplicated** — identical blocks across files and versions are stored once
- **Versioned** — each run is a new "snapshot" inside the same `.zpaq` file
- **Compressed** — zpaq's internal codecs, or an external compressor chosen per archive (`-ma`)
- **Append-only** — never modifies existing data; ideal for incremental cloud sync
- **Self-verifying** — CRC-32, XXHASH64 and SHA-1 per block, optionally SHA-2/SHA-3/Whirlpool/BLAKE3
- **One archive file** — no repositories, no databases, no temp files

---

## External compression: `-ma:algo:N`

Pick **which algorithm compresses each block**, with nothing to install: everything
is bundled under `compressors/`. Every block carries its own decoder written in
ZPAQL, so **any zpaq extracts the archive** (zpaq 7.15, zpaqfranz); zpaq-std decodes
natively, at full speed. Details: [wiki: Portable codecs](https://github.com/YadeWira/zpaq-std/wiki/Portable-codecs).

```bash
zpaq-std a backup.zpaq /data -ma:zstd:3          # fast, balanced
zpaq-std a docs.zpaq ~/Documents -ma:brotli:11   # best ratio on text
zpaq-std a media.zpaq /photos -ma:flzma2:9       # strong LZMA2
```

| Switch | Library | Levels | Default |
|---|---|---|---|
| `-ma:zstd:N` | [zstd](https://github.com/facebook/zstd) 1.5.7 | 1–22 | 3 |
| `-ma:brotli:N` | [brotli](https://github.com/google/brotli) 1.2.1 | 0–11 | 11 |
| `-ma:lzma:N` | [LZMA SDK](https://www.7-zip.org/sdk.html) 26.05 | 0–9 | 6 |
| `-ma:flzma2:N` | [fast-lzma2](https://github.com/YadeWira/ultra-fast-lzma2/tree/master/fast-lzma2) 1.1.2 | 1–10 | 5 |
| `-ma:uflzma2:N` | [ultra-fast-lzma2](https://github.com/YadeWira/ultra-fast-lzma2) 1.6.4 | 1–11 | 5 |
| `-ma:lz:N` | [lzlib](https://www.nongnu.org/lzip/lzlib.html) 1.16 | 0–9 | 6 |
| `-ma:bzip2:N` | [bzip2](https://sourceware.org/bzip2/) 1.0.8 | 1–9 | 9 |
| `-ma:deflate:N` | [libdeflate](https://github.com/ebiggers/libdeflate) 1.26 | 0–12 | 6 |
| `-ma:lizard:N` | [lizard-ex](https://github.com/YadeWira/lizard-ex) 2.3.2 (Lizard 2.1's format) | 10–49 | 17 |
| `-ma:lz5:N` / `lz5hc` / `lz5f` | [lz5-ex](https://github.com/YadeWira/lz5-ex) 1.5.3 | 1–15 | 9 |
| `-ma:snappy:N` | [Snappy](https://github.com/google/snappy) 1.3.1 | 1–2 | 2 |
| `-ma:lzfse` | [lzfse-ex](https://github.com/YadeWira/lzfse-ex) 1.0.3 | 0–1 | 1 |
| `-ma:hs:N` | [heatshrink-ex](https://github.com/YadeWira/heatshrink-ex) 0.7.0 | 0–2 | 1 |
| `-ma:bzip3:N` | [bzip3](https://github.com/iczelia/bzip3) 1.5.5 | 1–9 | 9 |
| `-ma:bsc:N` | [libbsc](https://github.com/IlyaGrebnov/libbsc) 3.4.0 | 1–9 | 3 |
| `-ma:lzh:N` | [lzham-ex](https://github.com/YadeWira/lzham-ex) 1.0.2 (LZHAM 1.0) | 1–4 | 4 |
| `-ma:ppmd:N` | PPMd var.H ([7-Zip SDK](https://www.7-zip.org/sdk.html)) | 2–32 | 6 |
| `-ma:kanzi:N` | [kanzi](https://github.com/flanglet/kanzi-cpp) 2.6.0 | 1–9 | 2 |
| `-ma:zxc:N` | [zxc](https://github.com/hellobertrand/zxc) 0.15.0 | 1–7 | 3 |
| `-ma:lz6:N` | [lz6](https://github.com/YadeWira/lz6) 1.7.1 | 0–15 | 0 |

#### Experimental

Their **encoder** may still change between releases; what is already written stays
readable. See [issue #3](https://github.com/YadeWira/zpaq-std/issues/3).

| Switch | Library | Levels | Default |
|---|---|---|---|
| `-ma:bz2:N` | [bz2-ng](https://github.com/tfenne/bz2-ng) 517948e | 1–9 | 9 |
| `-ma:sylz:N` | [sylz](https://github.com/YadeWira/syc) (syc v0.5.1), plugin only | 0–10 | 1 |
| `-ma:sylzec:N` | sylz with Huffman-coded literals (syc v0.5.1, format v3), plugin only (in sylz.dll) | 0–10 | 1 |
| `-ma:lz4:N` / `lz4hc` / `lz4f` | [LZ4](https://github.com/lz4/lz4) 1.10 (zpaqfranz's `-m6`) | 1–12 | 9 |
| `-ma:lzav:N` | [LZAV](https://github.com/avaneev/lzav) 5.17 (zpaqfranz's `-m7`) | 0–1 | 1 |

What each codec's levels mean, and notes on some of them (kanzi, lzh, bz2):
[wiki: Usage](https://github.com/YadeWira/zpaq-std/wiki/Usage#codec-notes). `codecinfo` lists them all; `codecinfo <codec>`
shows its card (author, repository, version, hashes).

---

## JPEG, lossless JPEG and JPEG-LS: `-sa` (experimental)

> **Experimental: not recommended yet.** PJA is new. Its archives open in any zpaq, but keep another copy of what you archive with `-sa`.

```bash
zpaq-std a photos.zpaq /photos -sa                   # PJA's family: pjax, pja, pjall, pjals, pjalsx
zpaq-std a photos.zpaq /photos -sa:pjals -ma:zstd    # only JPEG-LS; the rest with zstd
```

#### Stable

None yet.

#### Experimental

| Switch | Library | Takes | Levels | Default |
|---|---|---|---|---|
| `-sa:pja` | [PJA](https://github.com/YadeWira/PJA) 0.0.8, plugin only (`pja.dll` or `.so`): the family, its five codecs in this order | | 2 | 2 |
| `-sa:pjax+N` | the same plugin | JPEG that needs PJA's format v6: MPO and Ultra HDR (big JPEGs after the EOI), 12 bits, DNL, DRI without RST | 2 | 2 |
| (pja) | the same plugin, only through the family | JPEG: baseline, progressive, arithmetic-coded | 2 | 2 |
| `-sa:pjall+N` | the same plugin | lossless JPEG (SOF3): 2 to 16 bits, predictors 1–7 | 2 | 2 |
| `-sa:pjals+N` | the same plugin | JPEG-LS | 2 | 2 |
| `-sa:pjalsx+N` | the same plugin | JPEG-LS with subsampled components | 2 | 2 |

Files are chosen by their contents, never by name; the rest is compressed as
`-m`/`-ma` say. The plugin comes in the `extra-codecs` download. More:
[wiki: Usage](https://github.com/YadeWira/zpaq-std/wiki/Usage#jpeg-and-jpeg-ls--sa).

---

## Build

Only a C++ compiler (g++, clang++) and GNU make; no library to install. On macOS,
also `llvm-objcopy` (`brew install llvm`).

```bash
make                                      # optimized build
make CROSS_COMPILE=x86_64-w64-mingw32-    # 64-bit Windows
make CROSS_COMPILE=i686-w64-mingw32-      # 32-bit Windows (Windows 7 and later)
make m32                                  # 32-bit Linux (needs g++-multilib)
make CROSS_COMPILE=aarch64-linux-gnu-     # Linux AArch64
make plugins                              # program + every codec as a plugin (make clean first)
make install                              # to /usr/local/bin (or PREFIX=/opt)
```

Each release has, per platform, the full program, `extra-codecs.zip` (the codecs that
are only plugins: sylz, sylzec and pja, to put in `codecs/` next to the program) and
`plugins.zip` (a small program and every codec as a plugin). Targets, plugins and
cross-compiling: [wiki: Building](https://github.com/YadeWira/zpaq-std/wiki/Building).

---

## Usage

- `a` archive files into the .zpaq
- `x` extract (`-until N` picks a version, `-to dir/` renames)
- `l` list contents of a version
- `i` show all versions and their stats
- `t` test the archive
- `codecinfo` the codecs at a glance; `codecinfo <codec>` its card

The built-in help documents **59** commands (`zpaq-std h <command>`), and
`zpaq-std h voodoo` lists every switch. `-popgui` shows a native progress window on
Windows (for installers); `pakka` and `-catpaqmode` are for GUIs. More:
[wiki: Usage](https://github.com/YadeWira/zpaq-std/wiki/Usage).

---

## Verification

The test harness is in **`test/testlab/`**: round trips over every codec and
command, damaged archives, archives of published releases (golden), comparisons
between versions, Windows 7. On every push, CI (`.github/workflows/ci.yml`, with
`test/ci/`) builds the six platforms above and runs every built-in method on each.
See [wiki: Verification](https://github.com/YadeWira/zpaq-std/wiki/Verification).

---

## Why a fork

The original zpaq 7.15 (Matt Mahoney, 2009–2016) is unmaintained. This fork keeps the archive format and the dependency-free build of its upstream lineage and adds the **bundled-compressor** philosophy: pick the algorithm at archive time, no host setup needed. See [CONTRIBUTORS](CONTRIBUTORS) for full attributions.

**Version numbers** are `MAJOR.MINOR.PATCH` (details on the [wiki](https://github.com/YadeWira/zpaq-std/wiki)).

---

## License

MIT (see `LICENSE` and `COPYING`). Third-party libraries in `compressors/` keep their original licenses (BSD, MIT, Apache 2.0, LGPL-3.0 for bzip3, public domain), each in its folder.

[`THIRD-PARTY-LICENSES.txt`](THIRD-PARTY-LICENSES.txt) lists everything from other authors that the release binaries contain, with the full text of each license. It is attached to every release; redistribute it with the binaries. `python3 tools/third_party_licenses.py > THIRD-PARTY-LICENSES.txt` rebuilds it.

[ciBadge]: https://github.com/YadeWira/zpaq-std/actions/workflows/ci.yml/badge.svg "Continuous Integration"
[ciLink]: https://github.com/YadeWira/zpaq-std/actions/workflows/ci.yml
[relBadge]: https://img.shields.io/github/v/release/YadeWira/zpaq-std "Latest release"
[relLink]: https://github.com/YadeWira/zpaq-std/releases/latest
