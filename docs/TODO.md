### This is the todo list @ 2023-10-03 in no particular order

- [X] *Hard* Debian package. Ready, but I get an "overloaded" DD
- [X] *Hard* Fedora package. Almost ready, lost contact with Fedora maintainer
- [ ] *Mid* Update FreeBSD package. Not really a priority
- [X] *Hard* Implement the zpaq-over-TCP. Not easy, but all "pieces" already done => now SFTP support
- [ ] *Low* Complete and fix the wiki. I do not like very much english :)
- [ ] *Mid* XOR-ing SHA-1 to VFILE. Requires a lot of work to fix SHA-1 collisions
- [ ] *Hard* New file format without SHA-1. Backward compatibility will be broken. Not sure => not worth
- [X] *Low* "Automagically" define. In the source, but need more tests
- [X] *Low* Better low-memory extractor. For ESXi servers
- [X] *Low* Better proxmox backup. "Smarter hunter" of image's dataset
- [X] *???* Inspect -stdin with -fragment

### Multi-algo & Windows cross-compile integration @ 2026-06-07 (delegated, in progress)

Branch: `main` — 10 commits ahead of `origin/main` (unpushed).
Goal: 5+ external compressors via `-ma:algo:N` switch + 32-bit Linux + Windows 7+ cross-compile.

**Done (10 commits, unpushed):**
- LZAV (avaneev, MIT)
- heatshrink (atomicobject, ISC)
- LZFSE (Apple, BSD-3)
- zopfli (MrKrzYch00, Apache-2.0) — REMOVED later, see below
- bsc (IlyaGrebnov, Apache-2.0)
- LZHAM (richgel999, Public Domain)
- 32-bit Linux support (`make m32` with g++-multilib, requires `-D_GLIBCXX_USE_CXX11_ABI=0`)
- README/CHANGELOG/CONTRIBUTORS docs
- Partial Windows 7+ support doc
- Remove zopfli (-ma:zop) due to incompatible deflate output

**Final algo count: 17 (16 active):** lz4, zstd, flzma2, lz5, lizard, bzip2, bzip3, brotli, snappy, deflate, lz, lzav, hs, lzfse, bsc, lzh. ~~igzip~~ (x86_64 only) and ~~zopfli~~ (deflate incompatibility) excluded.

**Linux 64-bit: 14/14 algos verified.** Linux 32-bit: 5/5 working algos verified in wine.

**Windows full cross-compile (commit 11) — DONE locally, verified on a real Windows 10 LTSC VM. NOT pushed yet (pending review).**

Modified files:
- `Makefile`
- `zpaq-std.cpp`
- `compressors/snappy/snappy-stubs-public.h`
- (`compressors/bzip2/bzlib_private.h` was reverted to pristine upstream; the
  earlier VPrintf hack is replaced by `-DBZ_NO_STDIO` in the Makefile)

**What was fixed to make Windows actually build, load and run:**

1. **printf format bug (real, not just a warning):** 16 `sscanf(p+1,"%d:%ld",...,&X_orig)`
   read an `int64_t` with `%ld`, which is 32-bit on Windows → only half the value
   read, garbage high word. Fixed to `"%d:%" SCNd64` + an unconditional
   `#include <cinttypes>` (the POSIX include block is `#ifdef unix`, so the include
   had to live before the platform conditionals).

2. **Hard compile error:** the `__ctype_b_loc` ctype table used C99 designated
   array initializers (`[0x30]=...`) that g++ rejects. Rewritten with a loop.

3. **Binary would not load** ("bad EXE format" on wine/clean Windows): it depended
   on `libstdc++-6.dll`, `libgcc_s_seh-1.dll`, `libwinpthread-1.dll` and mixed the
   UCRT (`api-ms-win-crt-*`) with `msvcrt`. Fixed: `-static -static-libgcc
   -static-libstdc++` and link ONLY `msvcrt` (present on every Win7+). Now imports
   just KERNEL32/msvcrt/ADVAPI32/SHELL32/urlmon/USER32.

4. **`.comment` section** with a bogus VA far past SizeOfImage made the loader
   reject the image. Fixed with a post-link `strip --remove-section=.comment`
   (only on the mingw target).

5. **bzip2 link errors + the old stderr hack:** the WIP defined `stderr/stdout/stdin`
   as a dummy `FILE` to dodge UCRT, which **silently swallowed all error output AND
   broke the archiver's file I/O on real Windows** (archive scanned then never wrote).
   Root cause: only bzip2 referenced those symbols. Fixed by compiling bzip2 with
   `-DBZ_NO_STDIO` (zpaq-std only uses `BZ2_bzBuffToBuff*`, not the FILE* API) and
   providing `bz_internal_error()`. The stderr/stdout/stdin stubs are gone; msvcrt
   provides the real streams.

**Verified on real Windows 10 LTSC (10.0.19044, x64) via the SSH VM — round-trip
SHA-1 confirmed:** `lz4` ✓ `lzav` ✓ `bsc` ✓ `lzh` ✓ (plus the binary loads and the
help/`a`/`x` verbs work). Native Linux 64-bit build + 6-algo round-trip still green.

**KNOWN ISSUE — `-ma:hs` and `-ma:lzfse` crash on the Windows build:**
- `hs` → ACCESS_VIOLATION (0xC0000005); `lzfse` → HEAP_CORRUPTION (0xC0000374).
  Both produce a 0-byte archive and abort after the "Add" line.
- The crash is a `memset` invoked with a garbage huge size (≈ a stack pointer),
  i.e. a build-/ABI-specific bug. **valgrind on Linux is clean** and both work
  natively, and a 16 MB `-Wl,--stack` did NOT help — so it is not a simple stack
  overflow. Root cause still open (suspect an x64-ABI prototype mismatch in the
  hs/lzfse dispatch path).
- **Mitigation shipped:** `-ma:hs`/`-ma:lzfse` are rejected up front on `_WIN32`
  with a clear message, so a crash can never truncate/corrupt an archive mid-write.
  They remain fully supported on Linux/macOS.

**Remaining work:**
- Decide hs/lzfse on Windows: root-cause the memset/ABI bug, or keep them gated.
- `git push origin main` (11 commits) once reviewed.

**Key technical decisions (history):**
- zopfli: MrKrzYch00 fork's `ZopfliDeflate()` output not parseable by libdeflate — excluded.
- igzip: Intel ISA-L needs nasm + x86_64 only — excluded
- Windows LZ4: use the inline LZ4 in zpaq-std.cpp; stubs for `LZ4_compress_fast`
  (fresh-stream `LZ4_compress_fast_continue`) and `LZ4_compress_HC` (falls back).
- Windows LZHAM: `LZHAM_THREADING=win32`
- Windows FL2/Bzip2: `-U_FORTIFY_SOURCE`; FL2 also `-DNDEBUG`; `util.c` excluded
  (POSIX), with a `UTIL_countPhysicalCores` stub.
- bsc wrapper: `bsc_decompress` returns 0 (LIBBSC_NO_ERROR) on success, not size
- LZHAM wrapper: `lzham_compress_memory` one-shot, `m_dict_size_log2=20` (1MB)
- 32-bit: `-D_GLIBCXX_USE_CXX11_ABI=0` to link against old ABI libstdc++-32
- heatshrink: first byte = params header (low=window_sz2, high=lookahead_sz2)

**Build / test environment:**
- x86_64-w64-mingw32 cross-compile chain on Linux; wine for smoke tests.
- Real Windows 10 LTSC VM over SSH (see CONEXION-IA.md) for authoritative testing.
- All compressors in `compressors/` (no system deps).
