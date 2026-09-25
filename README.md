# zpaq-std

**A fork by [YadeWira](https://github.com/YadeWira), based on `fcorbelli/zpaqfranz` 65.4.**

A deduplicated, multi-version archiver (originally a fork of [zpaq](http://mattmahoney.net/zpaq.html) by Matt Mahoney, with the bulk of the code coming via Franco Corbelli's `zpaqfranz` fork), with **17 bundled, swappable external compression libraries** plus the LZ4 and LZAV that zpaqfranz itself embeds (23 `-ma` switches) and **zero system dependencies**.

Think of it as a single-file "Time Machine": every run only adds the deltas, so 5 daily backups of the same data cost roughly **the same space as 1**, not 5×. The archive is **append-only**, so `rsync --append` over a slow link only transfers what was actually added since the last sync.

This is **YadeWira's personal fork**. The new work here is the bundled-compressors architecture: pick the algorithm at archive time, no host setup needed. The base code (the deduplication engine, the journaling archiver) is Franco Corbelli's, derived in turn from Matt Mahoney's public-domain zpaq 7.15. See [CONTRIBUTORS](CONTRIBUTORS) for the full attribution chain.

The application lives in one ~130,000-line `zpaq-std.cpp`, plus `libdivsufsort/`,
the bundled `compressors/` and the `test/testlab/` harness. More documentation is in
the **[wiki](https://github.com/YadeWira/zpaq-std/wiki)**.

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

The killer feature of this fork. You can pick **which external algorithm compresses
each block**, without installing anything — everything is bundled under `compressors/`.

| Switch | Library | Levels | Default | Opens in any zpaq |
|---|---|---|---|---|
| `-ma:lz4:N` / `lz4hc` / `lz4f` | LZ4 1.10 (zpaqfranz's) | 1–12 | 9 | **yes** — it *is* `-m6` |
| `-ma:lzav:N` | LZAV 5.17 (zpaqfranz's) | 0–1 | 1 | **yes** — it *is* `-m7` |
| `-ma:zstd:N` | zstd 1.5.7 | 1–22 | 3 | **yes** (ZPAQZSTD) |
| `-ma:brotli:N` | brotli 1.2.0 | 0–11 | 11 | **yes** (ZPAQBROTLI) |
| `-ma:lzma:N` | LZMA SDK 26.03 | 0–9 | 6 | **yes** (ZPAQLZMA, decoder by kaitz) |
| `-ma:flzma2:N` | fast-lzma2 1.0.1 | 1–10 | 5 | **yes** (ZPAQFLZMA2) |
| `-ma:lz:N` | lzlib 1.16 | 0–9 | 6 | **yes** (ZPAQLZIP) |
| `-ma:bzip2:N` | bzip2 1.0.8 | 1–9 | 9 | **yes** (ZPAQBZIP2) |
| `-ma:deflate:N` | libdeflate 1.26 | 0–12 | 6 | **yes** (ZPAQDEFLATE) |
| `-ma:lizard:N` | Lizard 2.1 | 10–49 | 17 | **yes** (ZPAQLIZARD, ZPAQLIZARDH) |
| `-ma:lz5:N` / `lz5hc` / `lz5f` | LZ5 1.5 | 1–15 | 9 | **yes** (ZPAQLZ5) |
| `-ma:lz6:N` | lz6, **experimental** | 0–15 | 0 | **yes** (ZPAQLZ5) |
| `-ma:snappy:N` | Snappy 1.2.1 | 1–2 | 1 | **yes** (ZPAQSNAPPY) |
| `-ma:lzfse` | LZFSE (Apple) | 0–1 | 1 | **yes** (ZPAQLZFSE) |
| `-ma:hs:N` | heatshrink 0.4.1 | 0–2 | 1 | **yes** (ZPAQHS) |
| `-ma:bzip3:N` | bzip3 1.5.4 | 1–9 | 9 | **yes** (ZPAQBZIP3) |
| `-ma:bsc:N` | libbsc 3.3.12 | 1–9 | 3 | **yes** (ZPAQBSC) |
| `-ma:lzh:N` | LZHAM 1.0 | 1–4 | 4 | **yes** (ZPAQLZHAM) |
| `-ma:ppmd:N` | PPMd var.H (7-Zip SDK) | 2–32 (order) | 6 | no |

If the external pass does not beat the original by more than 16 bytes, the block
stays native (no regression).

### Portability

**22 of the 23 `-ma` switches write archives that any zpaq extracts** — zpaq 7.15,
zpaqfranz, and every zpaq-std from pre20 on. Their blocks carry their own decoder,
written in ZPAQL, the bytecode every zpaq implementation runs (the way zpaq's own
`-m1` works); zpaq-std recognises its decoders and decodes natively, at full speed.
Details, sizes and speeds of each decoder: **[wiki: Portable codecs](https://github.com/YadeWira/zpaq-std/wiki/Portable-codecs)**.

The other one (`ppmd`) only extracts in zpaq-std. zpaq-std
warns when it writes it (`00596!`), and other tools reject those blocks cleanly
(`unknown post processing type`) instead of writing wrong data; they still list
the archive and extract its native files.

**Upgrading:** new versions read every older archive. Old versions read the
portable codecs and native blocks, but not the newer non-portable ones — so
**upgrade the machine that RESTORES before the one that compresses.**

### Example

```bash
zpaq-std a backup.zpaq /data -ma:zstd:3          # nightly backups: fast, balanced
zpaq-std a docs.zpaq ~/Documents -ma:brotli:11   # best ratio on text
zpaq-std a media.zpaq /photos -ma:flzma2:9       # strong LZMA2
zpaq-std a mixed.zpaq *.txt -ma:brotli:11        # one algo per run, in one archive
```

The codec and the original size are recorded in each block's comment, so one
archive can mix codecs freely.

`-ytool` and `-pc` were removed (v64.8j-pre19 and pre14); see the
[wiki](https://github.com/YadeWira/zpaq-std/wiki/ytool-Precompressor) if you have
archives written with them.

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

All 17 bundled libraries live inside `compressors/` (LZ4 and LZAV come with
zpaqfranz), together with the ZPAQL decoders and the scripts that generate them.
No `apt install`, no `brew install`, no `-lz`, no `-lbrotli`: just `make`, and **no
flag needs anything installed on the host**. The tree, and the optional `mount`
command (off by default: it needs FUSE/WinFsp), are in the
[wiki: Building](https://github.com/YadeWira/zpaq-std/wiki/Building).

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

The Windows build is a self-contained `zpaq-std.exe` that runs on a clean Windows
7+ box. **32-bit builds are extract-only** (they extract, list and test; create
archives with a 64-bit build). More in the
[wiki: Building](https://github.com/YadeWira/zpaq-std/wiki/Building).

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

`suite_*.sh` add round-trip sweeps over all 23 `-ma` codecs, every command, and
corruption/robustness cases; the corpus, golden archives and reference binaries
live outside the repo, with their sha256 manifests committed.

---

## Why a fork

The original zpaq 7.15 (Matt Mahoney, 2009–2016) is unmaintained. This fork keeps the archive format and the dependency-free build of its upstream lineage and adds the **bundled-compressor** philosophy: pick the algorithm at archive time, no host setup needed.

See [CONTRIBUTORS](CONTRIBUTORS) for full attributions.

---

## License

MIT (see `LICENSE` and `COPYING`). Third-party libraries in `compressors/` keep their original licenses (BSD, Apache 2.0, etc.).
