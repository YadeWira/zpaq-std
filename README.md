# zpaq-std

**A fork by [YadeWira](https://github.com/YadeWira), based on `fcorbelli/zpaqfranz`.**

A deduplicated, multi-version archiver (originally a fork of [zpaq](http://mattmahoney.net/zpaq.html) by Matt Mahoney, with the bulk of the code coming via Franco Corbelli's `zpaqfranz` fork), with **18 bundled, swappable external compression libraries** (22 `-ma` switches) and **zero system dependencies**.

Think of it as a single-file "Time Machine": every run only adds the deltas, so 5 daily backups of the same data cost roughly **the same space as 1**, not 5×. The archive is **append-only**, so `rsync --append` over a slow link only transfers what was actually added since the last sync.

This is **YadeWira's personal fork**. The new work here is the bundled-compressors architecture: pick the algorithm at archive time, no host setup needed. The base code (the deduplication engine, the journaling archiver) is Franco Corbelli's, derived in turn from Matt Mahoney's public-domain zpaq 7.15. See [CONTRIBUTORS](CONTRIBUTORS) for the full attribution chain.

The application still lives in one ~113,000-line `zpaq-std.cpp`, but it is no longer
strictly single-file: `libdivsufsort/` was lifted out into its own module, and
`test/testlab/` holds the verification harness.

---

## What it does

- **Deduplicated** — identical blocks across files and versions are stored once
- **Versioned** — each run is a new "snapshot" inside the same `.zpaq` file
- **Compressed** — every block goes through zpaq's internal DCE + CM codec, then optionally through a **second-pass external compressor** chosen per-archive
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
| `-ma:lz5:N` / `lz5hc` / `lz5f` | LZ5 v1.5 | 1–15 | 9 | LZ4-compatible, denser; **opens in any zpaq** |
| `-ma:lz6:N` | lz6 (YadeWira, BSD-2), **experimental** | 0–15 | 0 | 0 = fast, low CPU; 1–15 = HC; **opens in any zpaq** |
| `-ma:lizard:N` | Lizard v2.1 | 10–49 | 17 | LZ4-class with better ratio |
| `-ma:bzip2:N` | bzip2 v1.0.8 | 1–9 | 9 | BWT+HF, classic |
| `-ma:bzip3:N` | bzip3 v1.5.4 | 1–9 | 9 | BWT+ANS, modern bzip2 successor |
| `-ma:brotli:N` | brotli v1.2.0 | 0–11 | 11 | Google's compressor (text) |
| `-ma:snappy:N` | Snappy v1.2.1 | 1–2 | 1 | Google's, like lz4 but tighter |
| `-ma:deflate:N` | libdeflate v1.26 | 0–12 | 6 | fast deflate/inflate (ebiggers) |
| `-ma:lz:N` | lzlib v1.16 | 0–9 | 6 | LZMA, BSD-2 lzip stream API |
| `-ma:lzav:N` | LZAV v5.17 (avaneev) | 0–1 | 1 | LZ77, header-only, very fast |
| `-ma:hs:N` | heatshrink v0.4.1 (atomicobject) | 0–2 | 1 | tiny, embedded-grade (2KB/8KB/32KB window) |
| `-ma:lzfse` | LZFSE (Apple, BSD-3) | 0–1 | 1 | high ratio on text/structured data (one internal level: 0 and 1 give the same output) |
| `-ma:bsc:N` | libbsc v3.3.12 (IlyaGrebnov, Apache-2.0) | 1–9 | 3 | BWT/ST + LZP + QLFC, very slow |
| `-ma:lzh:N` | LZHAM (richgel999, Public Domain) | 1–4 | 4 | LZMA-class, very slow |
| `-ma:ppmd:N` | PPMd var.H (7-Zip SDK, Public Domain) | 2–32 (order) | 6 | context modeling, strong on natural-language text |

If the external pass produces output larger than `orig - 16` bytes, the original is kept (no regression).

### Portability: which `-ma` archives open in other zpaq tools

**`-ma:lz5`, `-ma:lz5hc`, `-ma:lz5f` and `-ma:lz6` are portable.** Their blocks carry their
own decoder, written in ZPAQL — the bytecode language every zpaq implementation
runs (see [ZPAQLZ5](#zpaqlz5-an--ma-codec-any-zpaq-can-extract) below). **Every
other `-ma` codec is not**: its payload is compressed by a codec no other
implementation has, and the codec is named only in a block comment
(`zpaqstd-ma:<algo>:<level>:<original>`).

Measured against the two reference implementations:

| method | zpaq 7.15 | zpaqfranz 64.8j |
|---|---|---|
| `-m0` … `-m5` (native) | extracts correctly | extracts correctly |
| `-ma:lz5` / `lz5hc` / `lz5f` / `lz6` | **extracts correctly** | **extracts correctly** |
| any other `-ma:algo` | skips the block, `rc=1` | skips the block, `rc≠0` |

Those `-ma` blocks are deliberately tagged with a **post-processing type that no
zpaq knows**, so other tools reject them by name:

```
Job 4: skipping [2..2] at 1319: unknown post processing type
Extracted 1 of 2 files OK (1 errors)
```

That is a great deal better than what the format would do otherwise — read the
compressed bytes as if they were raw and die on a fragment hash that does not add
up, which looks exactly like a corrupt archive. Three things follow:

- **Other tools still list the archive correctly** and, in a mixed archive, they
  still recover the native files. Only the `-ma` blocks are lost to them.
- **Nothing bad is ever written.** Measured in every case: non-zero exit status
  and no file on disk. It never hands back wrong data as if it were good.
- **A block is tagged only if it really carries external-codec payload.** When
  the external pass does not beat the original, the data stays native and the
  archive remains universally readable — verified: incompressible input with
  `-ma:zstd` produces zero tags and zpaq 7.15 extracts it.

#### ZPAQLZ5: an `-ma` codec any zpaq can extract

A zpaq block can carry its own decompressor as a ZPAQL program (the
post-processor), and any zpaq that follows the specification runs it without
knowing what algorithm it is — that is how zpaq's own `-m1`/`-m2` work. ZPAQLZ5 is
an LZ5 block decoder written in ZPAQL, and every `-ma:lz5` block carries it:

| | |
|---|---|
| decoder size | about **430 bytes** per block |
| decode speed in other tools | **62–103 MB/s** with the ZPAQL JIT, **11 MB/s** without |
| zpaq-std itself | recognises its own decoder byte for byte and decodes LZ5 **natively** |
| older zpaq-std versions (pre20 on) | run the ZPAQL, so they extract these archives too |

One decoder serves all four switches, because `lz5`, `lz5hc`, `lz5f` and `lz6`
write the same block format: lz6's block format is LZ5 v1.5's, frozen by lz6 as its
portable profile. `-ma:lz6` caps its window at 4 MB, so a foreign zpaq needs 4 MB
per thread, not 16.

> **lz6 is experimental and subject to major changes.** What can change is lz6's
> *encoder*: its ratio, speed and levels, so `-ma:lz6` may compress differently
> from one zpaq-std release to the next, and its levels may be renumbered. What
> cannot change is the *block format* `-ma:lz6` writes, which lz6 froze as its
> portable profile: every archive already written carries its own decoder and
> stays readable, by zpaq-std and by any other zpaq. Any future lz6 format would
> get a new name, never this one.

Measured on 19.9 MB (text, binary, 3 MB of random data), one thread:

| method | archive | CPU | opens in zpaq 7.15 |
|---|---|---|---|
| `-m1` | 8.47 MB | 1.11 s | yes |
| `-ma:lz4f` | 13.96 MB | 0.26 s | no |
| `-ma:lz5f` | 10.52 MB | 0.31 s | yes |
| **`-ma:lz6`** (0, fast) | **10.22 MB** | **0.31 s** | **yes** |
| `-ma:lz6:9` | 9.09 MB | 1.09 s | yes |
| `-ma:lz6:15` | 8.34 MB | 5.70 s | yes | It only works because LZ5 has no entropy coding: a brotli
decoder in ZPAQL was measured at about 63 KB of bytecode and 1.6 MB/s, which is
why the other codecs stay non-portable. The decoder is frozen: every archive
already written carries its own copy, and zpaq-std recognises it byte for byte.

#### Upgrading

The tag is not understood by **older zpaq-std versions either**. For the
non-portable codecs the compatibility is one-way, and it is the useful direction:

| | |
|---|---|
| new version reading old archives | **yes** — verified over pre9…pre20 × 7 codecs, plus native |
| old version reading new `-ma` blocks | no — **except `-ma:lz5`/`lz5hc`/`lz5f`/`lz6`**, which every version from pre20 on extracts by running their ZPAQL decoder |
| old version reading new **native** archives | **yes** — those bytes are unchanged |

In a mixed or appended archive an old version still recovers everything it could
recover before, file by file; it fails only on the new `-ma` blocks. Still, the
rule when upgrading is simple: **upgrade the machine that RESTORES before the one
that compresses.**

**Use `-m0`…`-m5`, `-ma:lz5` or `-ma:lz6`, if the archive has to be readable
anywhere else.** Raised as
issue #1 by kaitz, and the report is correct on the substance (the header,
however, is unchanged — it is byte-for-byte a standard zpaq header).

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

## `-ytool` was removed

`-ytool` handed files to the external [ytool](https://github.com/YadeWira/ytool)
binary to precompress recompressible streams before fragmentation. It never left
the experimental stage and was dropped in v64.8j-pre19, along with the last
external dependency: **every flag now works with nothing installed on the host.**

If you have an archive written with `-ytool`, extraction leaves the `zYTL`
container on disk and says so per file (`00568!`) rather than pretending it
succeeded. Use v64.8j-pre18 or earlier to get those files back. The same applies
to `-pc`, removed in pre14 — use pre13 for those.

---

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
- **Progress is real.** When compressing, the bar follows what has been
  compressed, not what has been read: at `-m5` those are minutes apart.
- **A failure is shown as one.** On a non-zero exit the title says "Extraction
  failed" (or Compression / Test), the bar and the taskbar button turn red, the
  first error is shown (e.g. `bad checksum`, `Archive not found: …`), and the
  window closes on **Close** or by itself after **10 s**, so an unattended
  (`/VERYSILENT`) install never hangs. The exit code is unchanged: the
  installer should still check it.

---

## No system dependencies

All 18 `-ma` libraries live inside `compressors/`:

```
compressors/
├── lz4/          2 src +  2 h
├── zstd/         1 src +  2 h   (amalgamated)
├── fl2/         13 src + 22 h   (fast-lzma2)
├── lz5/          2 src +  4 h
├── lz6/          2 src +  4 h   (YadeWira, BSD-2; frozen, see VERSION)
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



Total: **377 source files, 8.6 MB of source**. No `apt install`, no `brew install`,
no `-lz`, no `-lbrotli`. Just `make`.

There is no longer any exception: with `-ytool` gone, **no flag needs anything
installed on the host.**

---

## Optional: `mount` (off by default)

`zpaqfranz` 65.x added a `mount` command that exposes an archive as a read-only
drive. **zpaq-std does not ship it**, because it would break the one promise this
project keeps: that no flag needs anything installed. It needs FUSE on Linux or
WinFsp on Windows — at build time *and* at run time.

The code is carried, inert, behind `ZPAQMOUNT`, and there is a build switch for
anyone who wants it:

```sh
make MOUNT=1                                   # Linux, needs libfuse3-dev
make MOUNT=1 CROSS_COMPILE=x86_64-w64-mingw32- \
     WINFSP_INC=/path/to/WinFsp/inc            # Windows, needs WinFsp "Developer"
```

Without `MOUNT=1` nothing changes: the default binary carries **no mount symbol
at all**, and `zpaq-std mount` answers `00590!` explaining it is disabled rather
than falling through to the help screen.

**On licensing**: neither library is bundled or statically linked. On Linux the
build links dynamically against the system `libfuse3`, which is the use LGPL-2.1
contemplates; on Windows nothing is linked at all — WinFsp is resolved with
`LoadLibrary` at run time. Bundling them *would* be a licensing problem (libfuse
is LGPL-2.1, WinFsp is GPLv3, this project is MIT), which is exactly why the
switch uses the system's copies instead.

**Untested by us.** There is no FUSE on the development machine and no WinFsp in
the test VM, and upstream says of its own feature *"not really tested on \*nix"*.
Verify it yourself before relying on it.

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

`suite_*.sh` add round-trip sweeps over all 22 `-ma` codecs, every command, and
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
