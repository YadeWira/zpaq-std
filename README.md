# zpaq-std

**A fork by [YadeWira](https://github.com/YadeWira), based on `fcorbelli/zpaqfranz`.**

A deduplicated, multi-version archiver (originally a fork of [zpaq](http://mattmahoney.net/zpaq.html) by Matt Mahoney, with the bulk of the code coming via Franco Corbelli's `zpaqfranz` fork), with **17 bundled, swappable external compression libraries** (21 `-ma` switches) and **zero system dependencies**.

Think of it as a single-file "Time Machine": every run only adds the deltas, so 5 daily backups of the same data cost roughly **the same space as 1**, not 5×. The archive is **append-only**, so `rsync --append` over a slow link only transfers what was actually added since the last sync.

This is **YadeWira's personal fork**. The new work here is the bundled-compressors architecture: pick the algorithm at archive time, no host setup needed. The base code (the deduplication engine, the journaling archiver) is Franco Corbelli's, derived in turn from Matt Mahoney's public-domain zpaq 7.15. See [CONTRIBUTORS](CONTRIBUTORS) for the full attribution chain.

The application still lives in one ~104,000-line `zpaq-std.cpp`, but it is no longer
strictly single-file: `libdivsufsort/` was lifted out into its own module, and
`test/testlab/` holds the verification harness.

---

## What it does

- **Deduplicated** — identical blocks across files and versions are stored once
- **Versioned** — each run is a new "snapshot" inside the same `.zpaq` file
- **Compressed** — every block goes through zpaq's internal DCE + CM codec, then optionally through a **second-pass external compressor** chosen per-archive, and optionally through the `-ytool` precompressor first
- **Append-only** — never modifies existing data; ideal for incremental cloud sync
- **Self-verifying** — triple-checksums (CRC-32, XXHASH64, SHA-1) per block, with optional SHA-2/SHA-3/Whirlpool/BLAKE3
- **One archive file** — no repositories, no databases, no temp files; a single `.zpaq` is the whole backup

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
| `-ma:ppmd:N` | PPMd var.H (7-Zip SDK, Public Domain) | 2–32 (order) | 6 | context modeling, strong on natural-language text |

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

## Precompressor: `-ytool`

A **reversible, bit-exact** precompressor applied *before* compression, so the
second stage sees the real data instead of an already-compressed blob.

Hands each candidate file to [ytool](https://github.com/YadeWira/ytool) (an
open-source FPC recreation of xtool) and stores the result as a self-describing
container. ytool detects gzip / zlib / ZIP / PDF DEFLATE **plus** JPEG, PNG, MP3,
raw WAV/PCM and LZO. The binary is found via `ytool_set_binary()`, the
`ZPAQ_YTOOL` environment variable, or `ytool` on `PATH` — in that order.

```bash
zpaq-std a backup.zpaq /data -ytool -ma:flzma2
zpaq-std a backup.zpaq /data -ytool:<codecs|params>   # override ytool's arguments
```

- **Safe by construction**: a file is stored as a ytool container only if
  `decode(encode(x)) == x` was proven byte-for-byte at encode time. The container
  carries the original's size and CRC-32, so extraction re-checks the reversed
  bytes. Anything that fails is stored verbatim.
- **Deterministic**: ytool's `precomp` is only deterministic at `-t1` (there is a
  real race above that), so zpaq-std always passes `-t1` and recovers throughput
  by running many ytool processes in parallel — one per file, from its own
  prefetch pool. Each file is deterministic *and* the batch is parallel, which
  keeps the output dedup-friendly.
- Deliberately no `-dd`: deduplication is left to zpaq's own content-defined
  chunking.
- **It is the one thing that needs something installed on the host**: an external
  `ytool` binary. Everything else in zpaq-std is self-contained.

### `-pc` was removed

The older `-pc` (preflate/PCF DEFLATE recompression) is **gone entirely** —
encoder and decoder — and `compressors/preflate/` and `compressors/zlib/` went
with it: 87 source files, 2.3 MB, and about 410 KB off the binary. It only ever
handled DEFLATE, which `-ytool` handles and more.

Passing `-pc` (or `-pcc`) prints what to use instead:

```
00563! -pc was removed: use -ytool instead (it detects more formats)
       archives already made with -pc still extract normally
```

**A `.zpaq` written with `-pc` by v64.8j-pre13 or earlier can no longer be
reversed.** Extraction leaves the PCF container on disk and warns per file
(`00566!`); use pre13 to reverse one. This was accepted deliberately: the
project has no production deployment, and keeping the decoder meant keeping
preflate's encoder and a vendored stock zlib compiled forever, because reversing
a PCF container re-encodes it to prove it is authentic.

## Installer progress: `-innosetup`

Pass **`-innosetup`** and zpaq-std shows its **own native progress window** while it
works — modelled on 7-Zip's **7zG.exe** and styled like an Inno Setup wizard page: a
comctl32 v6 progress bar, the operation and percentage in the **title bar**
(`Compressing... NN%` / `Extracting... NN%`), two columns of stat rows (**Elapsed time,
Remaining time, Total size, Speed, Processed, Compressed size, Compression ratio**), and
**Background** (minimise and keep working) / **Cancel** (confirm, then abort) buttons. It
**auto-detects the OS dark/light theme** — on Windows 10+ it follows `AppsUseLightTheme`
(dark background + dark title bar + dark progress trough); on Windows 8.1 and older it
stays light. It runs on a separate thread so the operation
is never blocked; the window updates as it goes and closes when finished (or on exit).
Normal console output is silenced.

```bash
# e.g. an installer extracting a bundled archive, with a progress window:
zpaq-std x "data.zpaq" -to "C:\Program Files\MyApp\" -innosetup
```

- **Windows only.** On any other OS the flag is **ignored** — zpaq-std runs exactly as
  if it had not been passed (normal output, nothing silenced).
- Works for any long operation (`a` compress, `x`/`t` extract, …). No installer
  scripting, output redirection or progress files needed — the window is self-contained.

---

## No system dependencies

All 17 `-ma` libraries live inside `compressors/`:

```
compressors/
├── lz4/          2 src +  2 h
├── zstd/         1 src +  2 h   (amalgamated)
├── fl2/         13 src + 22 h   (fast-lzma2)
├── lz5/          2 src +  4 h
├── lizard/      10 src + 26 h
├── bzip2/        7 src +  2 h
├── bzip3/        1 src +  4 h
├── brotli/      35 src + 71 h   (enc+dec+common)
├── snappy/       4 src +  6 h   (Google, BSD-3; .cc)
├── libdeflate/  11 src + 28 h   (ebiggers, MIT)
├── lzlib/        7 src +  7 h   (lzip, BSD-2)
├── lzav/         0 src +  1 h   (header-only)
├── hs/           3 src +  5 h   (+ hs_wrapper.c glue)
├── lzfse/        7 src +  7 h   (+lzvn helpers)
├── bsc/         12 src + 15 h   (+libsais)
├── lzham/       20 src + 29 h   (richgel999)
└── ppmd/         4 src +  7 h   (7-Zip SDK, + ppmd_wrapper.c glue)
```

Plus `ytool/`, which is not an `-ma` codec but a subprocess bridge (see above).

Total: **379 source files, 8.7 MB of source**. No `apt install`, no `brew install`,
no `-lz`, no `-lbrotli`. Just `make`.

The one exception is **`-ytool`**, which shells out to an external `ytool`
binary — that flag, and only that flag, needs something installed on the host.

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

**32-bit builds are extract-only.** Heavy compression doesn't fit a ~2 GB address
space reliably, so on any 32-bit build (`make m32` or `i686-w64-mingw32-`) the `a`
command is disabled — these binaries **extract, list and test** (and run the
`-innosetup x` installer flow); create or modify archives with a 64-bit build.

On non-x86 the JIT is auto-disabled; on x86_64 you get HW SHA-1/SHA-2 acceleration (`-DHWSHA2`).

The output is a single `zpaq-std` binary, ~6.9 MB native / ~6.9 MB Windows.

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
- `t` test the archive (recomputes the stored hashes)

Those are the common ones; the built-in help documents **57** commands in total
(`backup`, `testbackup`, `trim`, `crop`, `find`, `redu`, `dirsize`, `sum`,
`collision`, `1on1`, `consolidate`, `versum`, `image`, `gui`, `tui`…).

See `zpaq-std h <command>` for full help, or `zpaq-std h voodoo` for the full list of switches (the `-ma:*` family is documented there).

---

## Verification

An archiver's only real promise is that what came out is what went in, so the
harness lives in the repo under **`test/testlab/`** (see its `LEEME.md`). Four
tools that measure different things:

| tool | what it checks |
|---|---|
| `difftest.sh A B` | two binaries agree: byte-identical archives, each reads the other's, same `l`/`t` verdict |
| `golden_gate.sh` | the current build still extracts `.zpaq` files written by **published** releases, with identical content and `t` == 0 |
| `os_msgs.sh A B` | destination shapes and the numbered messages — bare relative name, nonexistent chain, UTF-8, long paths, symlinks, unwritable directories, `-append` on an existing archive |
| `pin_corpus.sh` | pins the test corpus, so a comparison can't silently be run on different inputs |

`suite_*.sh` add round-trip sweeps over all 21 `-ma` codecs, every command, and
corruption/robustness cases.

The scripts are versioned here; the corpus, the golden archives and the reference
binaries live outside the repo, with their sha256 manifests committed alongside.

Bit-exactness deserves a caveat, because it is easy to misread: with `-ma` the
block is stored and the codec is identified by a comment, so two builds can write
**different bytes** and still be perfectly interoperable. It is a diagnostic, not
a requirement — the harness reports the columns separately for that reason.

---

## Why a fork

The original zpaq 7.15 (Matt Mahoney, 2009–2016) is unmaintained. This fork keeps the archive format and the dependency-free build of its upstream lineage and adds the **bundled-compressor** philosophy: pick the algorithm at archive time, no host setup needed.

See [CONTRIBUTORS](CONTRIBUTORS) for full attributions.

---

## License

MIT (see `LICENSE` and `COPYING`). Third-party libraries in `compressors/` keep their original licenses (BSD, Apache 2.0, etc.).
