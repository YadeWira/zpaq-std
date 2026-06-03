# zpaq-std — Development Workflow

> Detailed guide for continuing the work. Assumes you have a Linux/macOS/BSD dev box, g++ or clang++, GNU make, and git.

---

## 0. TL;DR for someone in a hurry

```bash
git clone https://github.com/YadeWira/zpaq-std
cd zpaq-std
make                       # builds ./zpaq-std
./zpaq-std version         # smoke test
make check                 # show compiler, flags, JIT status
./zpaq-std h voodoo        # see the -ma:algo:N switches
```

If `make` succeeds and `./zpaq-std version` prints something with `v64.7g` (or similar), you're good. If it fails, jump to **§5 Troubleshooting**.

---

## 1. Repo layout

```
zpaq-std/
├── zpaq-std.cpp           ← THE single-file source. All C++ lives here.
├── Makefile               ← GNU make; no cmake, no autoconf
├── README.md              ← User-facing docs
├── WORKFLOW.md            ← This file
├── CHANGELOG.md           ← Version history
├── LICENSE / COPYING
├── compressors/           ← Bundled 3rd-party compression libs (C source)
│   ├── lz4/               ← LZ4 v1.10.0       (2 .c)
│   ├── zstd/              ← zstd v1.5.7        (1 .c amalgamated)
│   ├── fl2/               ← fast-lzma2 v1.0.1  (13 .c)
│   ├── lz5/               ← LZ5 v1.5           (2 .c)
│   ├── lizard/            ← Lizard v2.1        (10 .c)
│   ├── bzip2/             ← bzip2 v1.0.8       (7 .c)
│   ├── bzip3/             ← bzip3 v1.5.3       (1 .c)
│   └── brotli/            ← brotli v1.2.0      (35 .c)
├── man/                   ← man pages (zpaq-std.1, zpaq-std.pod)
├── docker/                ← Dockerfile for CI
└── .github/workflows/     ← CI build matrix
```

**The single C++ source `zpaq-std.cpp` is the whole program.** The `compressors/` directory is plain C source code from the upstream libraries, copied verbatim. We do **not** modify it (except for adding `-Wno-unused-function` to bzip3 via Makefile).

Total bundled source: **~71 .c files, 8.5 MB**. Total `zpaq-std.cpp`: ~100k lines, ~3.5 MB.

---

## 2. The `-ma:algo:N` switch (the whole point of this fork)

The `zpaq-std` block pipeline is roughly:

```
file bytes  →  DCE+CM (zpaq internal)  →  StringBuffer sb
                                          ↓
                                if -ma:algo:N is set:
                                external compress sb → sb'
                                (only if sb'.size() < sb.size() - 16)
                                          ↓
                                      segment
```

The external pass is **per-segment**, and the algorithm is chosen by the user at archive time. The choice is recorded in the segment header as:

```
zpaqstd-ma:<algo>:<level>:<origSize>
```

so extraction knows what to call, even if `compressors/kanzi` is later replaced by `compressors/lz4` (this fork doesn't ship kanzi yet — see §3 for how to add one).

### Where the code lives in `zpaq-std.cpp`

| Concern | Approx line | What it does |
|---|---|---|
| Includes | ~8500 | `#include` of compressor headers (with `extern "C"`) |
| Parser | ~55000 | Validates `-ma:algo:N`, sets default level, clamps to range |
| Compress dispatch | ~100800 | `if (g_ma_algorithm=="lz4") {...} else if (...=="brotli") {...}` |
| Decompress detection | ~58700 | `cs.find("zpaqstd-ma:<algo>")` + sscanf for level/origSize |
| Decompress execution | ~58800 | Mirror of compress: `if (lz4_orig>0) LZ4_decompress(...)` |
| Help text | ~52580 | `h voodoo` lines for each algo |

Use grep to find them: `rg "g_ma_algorithm" zpaq-std.cpp`.

### Adding a new algorithm (5-step recipe)

Let's say you want to add `-ma:zlib:N` (just as an example). Steps:

#### 1. Bundle the source

```bash
mkdir compressors/zlib
cp <upstream>/zlib/*.c compressors/zlib/
cp <upstream>/zlib/*.h compressors/zlib/
```

#### 2. Makefile

Add the include flag and object list:

```make
ZLIBSRC := compressors/zlib/deflate.c compressors/zlib/inflate.c \
           compressors/zlib/adler32.c compressors/zlib/crc32.c \
           compressors/zlib/zutil.c compressors/zlib/trees.c \
           compressors/zlib/inffast.c compressors/zlib/inftrees.c
ZLIBINC := -Icompressors/zlib
ZLIBOBJ := $(ZLIBSRC:.c=.o)

# Pattern rule (note: path on BOTH target and prereq!)
compressors/zlib/%.o: compressors/zlib/%.c
	$(CC) $(ZPAQ_CFLAGS) $(ZLIBINC) -c $< -o $@

# Add to $(PROG) deps and link line
$(PROG): $(SOURCE) ... $(ZLIBOBJ)
	$(CXX) ... $(ZLIBOBJ) ... -o $@
```

> **Pitfall:** if the lib has multiple subdirs (like brotli has `enc/`, `dec/`, `common/`), split into separate `BZIP3OBJ` / `BROTLI_COMMON_OBJ` / `BROTLI_ENC_OBJ` / `BROTLI_DEC_OBJ` lists, one per subdir, with one static pattern rule each. See the brotli section of the Makefile for the working pattern.

#### 3. `zpaq-std.cpp` includes

Around line 8500:

```cpp
extern "C" {
    #include "zlib.h"
}
```

#### 4. Parser (~line 55000)

```cpp
if (g_ma_algorithm=="zstd") g_ma_level=3;
else if (g_ma_algorithm=="flzma2") g_ma_level=5;
else if (g_ma_algorithm=="lizard") g_ma_level=17;
else if (g_ma_algorithm=="brotli") g_ma_level=11;
else if (g_ma_algorithm=="bzip2"||g_ma_algorithm=="bzip3") g_ma_level=9;
else if (g_ma_algorithm=="zlib") g_ma_level=6;       // ← add
```

Then in the clamp section:

```cpp
else if (g_ma_algorithm=="bzip2"||g_ma_algorithm=="bzip3")
{
    if (g_ma_level<1) g_ma_level=1;
    if (g_ma_level>9) g_ma_level=9;
}
else if (g_ma_algorithm=="zlib")                       // ← add
{
    if (g_ma_level<1) g_ma_level=1;
    if (g_ma_level>9) g_ma_level=9;
}
```

And the validation list:

```cpp
if (g_ma_algorithm!="lz4"&&...&&g_ma_algorithm!="brotli")
    g_ma_algorithm="";
```

(extend this with `&&g_ma_algorithm!="zlib"`).

#### 5. Compress dispatch (~line 100800)

After the brotli `else if`, add:

```cpp
else if (g_ma_algorithm=="zlib" && sb.size()>16)
{
    uLongf dstCap = orig_size + 1024;
    Bytef* zlibbuf = new(std::nothrow) Bytef[dstCap];
    if (zlibbuf)
    {
        uLongf zs = dstCap;
        if (compress2(zlibbuf, &zs, (const Bytef*)sb.data(), orig_size, g_ma_level) == Z_OK
            && zs < (uLongf)(orig_size - 16))
        {
            sb.write((const char*)zlibbuf, zs);
            ma_comment="zpaqstd-ma:zlib:"+itos(g_ma_level)+":"+itos(orig_size);
        }
        delete[] zlibbuf;
    }
}
```

#### 6. Decompress detection (~line 58700)

```cpp
int64_t zlib_orig= 0;
// ...
auto mz = cs.find("zpaqstd-ma:zlib");
if (mz != string::npos) {
    int lvl; sscanf(cs.c_str()+mz, "zpaqstd-ma:zlib:%d:%ld", &lvl, &zlib_orig);
}
```

#### 7. Decompress execution (~line 58800)

```cpp
else if (zlib_orig > 0)
{
    decomp2.resize(zlib_orig);
    uLongf r2 = (uLongf)zlib_orig;
    if (uncompress(&decomp2[0], &r2, (const Bytef*)out.data(), out.size()) != Z_OK
        || (int64_t)r2 != zlib_orig)
        error("31319 zlib decompression failed");
    output_size = zlib_orig;
}
```

#### 8. Help text (~line 52580)

```cpp
scrivi_riga(" ", "  zlib: deflate (1=fast, 6=default, 9=best)");
```

#### 9. Test

```bash
make clean && make
# round-trip test
mkdir /tmp/zlibtest && cd /tmp/zlibtest
head -c 4194304 /dev/zero > z.bin
zpaq-std a t.zpaq z.bin -ma:zlib:6
zpaq-std x t.zpaq -to out/ -force
cmp z.bin out/z.bin && echo MATCH
```

#### 10. Update README.md and CHANGELOG.md

Add a row to the compression table in `README.md`, and a one-liner under `CHANGELOG.md`.

---

## 3. Algorithms deliberately not integrated (and why)

| Lib | Why not |
|---|---|
| **kanzi-cpp 2.5.3** | C++ OOP framework (`namespace kanzi`, `class BlockCompressor`); no clean one-shot `compress(buf, len)` API. Has a C ABI but it uses `FILE*` (not memory buffers). Would need a `std::stringstream` wrapper and 50 .cpp files of C++ dependencies. Tried; deferred. |
| **lrzip 0.651** | File-level archiver; API is `rzip_fd(fd_in, fd_out)`, not memory buffers. Not a block compression library. |
| **xz / liblzma** | Already covered by `flzma2` (fast-lzma2). xz is too slow at high levels for our use. |

If you want to revisit one of these, see the API references in:
- https://github.com/flanglet/kanzi-cpp/blob/master/API_REFERENCE.md
- https://github.com/colordot/lrzip (archived)

---

## 4. Build matrix (where it works)

Tested personally (in previous sessions) on:
- Linux x86_64 (g++ 13, clang++ 17) ← main dev environment
- FreeBSD 14 (clang++)
- macOS Sonoma (Apple clang)

The Makefile is structured to work on:
- x86_64 / amd64 (JIT + HWSHA2 auto-enabled)
- aarch64 / arm64 (JIT auto-disabled)
- ppc / ppc64 / ppc64le (JIT disabled, `-DANCIENT -DBIG`)
- sparc / sparc64 (JIT disabled, `-DALIGNMALLOC`)
- mips / mips64 (JIT disabled, `-DBIG`)
- RISC-V (JIT disabled, default)

Use `make check` to see what's enabled on the current machine.

---

## 5. Troubleshooting

### "xxhash.h: No such file"

`compressors/fl2/` uses xxhash. We disable it via `-DNO_XXHASH` (set in `FL2INC` in the Makefile). If you see this error, the pattern rule for fl2 isn't being used — make fell back to the default `cc -c` rule. **Check the pattern rule has the path on both sides** (see Makefile line 157–160):
```make
compressors/fl2/%.o: compressors/fl2/%.c        # ← both sides
```

### "undefined reference to BrotliEncoderCompress" at link time

A brotli .c file didn't compile. Run:
```bash
make CC=cc -d compressors/brotli/enc/encode.o 2>&1 | grep -E "atención|warning|error"
```

### "warning: overriding recipe for target 'compressors/brotli/dec/static_init.o'"

Three static pattern rules share the same `$(BROTLIOBJ)` list. The fix is in place: split into `BROTLI_COMMON_OBJ`, `BROTLI_ENC_OBJ`, `BROTLI_DEC_OBJ` with one static pattern rule per subdir. See Makefile lines 152–180.

### "warning: 'libsais_create_ctx' defined but not used"

bzip3's `libsais.h` has many `static inline` functions that gcc flags as unused. Suppressed by `-Wno-unused-function` in `BZIP3INC` (line 80). Don't remove that flag unless you patch libsais.h.

### "make: *** No rule to make target compressors/bzip3/libbz3.o"

The static pattern rule for bzip3 isn't matching. Verify line 170:
```make
$(BZIP3OBJ): compressors/bzip3/%.o: compressors/bzip3/%.c
```
is intact. The bzip3 file count must be ≥1; check `ls compressors/bzip3/*.c`.

### Build succeeds but `./zpaq-std` says "command not found"

The binary is in the current dir. Use `./zpaq-std` not `zpaq-std` (or `make install`).

### Compressed output is LARGER than the original

That's not a bug — if `cstr.size() < (orig - 16)` fails, the segment is stored uncompressed. Add a `-nochecksum` and a level to see real compression: `zpaq-std a test.zpaq big.bin -ma:zstd:19 -nochecksum`.

### All segfaults / corrupt archives

99% of the time this is a `bzip3` API misuse (the `bz3_compress` block_size arg is finicky). Run with a single algo in isolation:
```bash
zpaq-std a test.zpaq big.bin -ma:bzip3:5 -nochecksum
zpaq-std x test.zpaq -to out/ -force
cmp big.bin out/big.bin
```

---

## 6. Round-trip test script (canonical)

Save as `runtest.sh` and run after any change:

```bash
#!/bin/bash
set -e
ZS="./zpaq-std"
WD=$(mktemp -d)
cd "$WD"

# 4 MiB of zeros (very compressible)
head -c 4194304 /dev/zero > zeros.bin
for i in 1 2 3; do cp zeros.bin "f$i.bin"; done

declare -A ALGOS=(
    [lz4]=1 [lz4hc]=9 [zstd]=3 [flzma2]=5 [lz5]=9
    [lizard]=17 [bzip2]=9 [bzip3]=5 [brotli]=6
)

for algo in "${!ALGOS[@]}"; do
    level="${ALGOS[$algo]}"
    rm -rf out/
    "$ZS" a test.zpaq f*.bin "-ma:$algo:$level" -nochecksum >/dev/null
    "$ZS" x test.zpaq -to out/ -force >/dev/null
    if cmp -s f1.bin out/f1.bin && cmp -s f2.bin out/f2.bin && cmp -s f3.bin out/f3.bin; then
        echo "$algo:$level  MATCH"
    else
        echo "$algo:$level  *** MISMATCH ***" >&2
        exit 1
    fi
done

# Mixed archive (all 9 in one)
rm -rf out/ mixed.zpaq
for i in $(seq 1 9); do cp zeros.bin "f$i.bin"; done
"$ZS" a mixed.zpaq f1.bin -ma:zstd:3   -nochecksum >/dev/null
"$ZS" a mixed.zpaq f2.bin -ma:lz4:9    -nochecksum >/dev/null
"$ZS" a mixed.zpaq f3.bin -ma:flzma2:5 -nochecksum >/dev/null
"$ZS" a mixed.zpaq f4.bin -ma:lz5:9    -nochecksum >/dev/null
"$ZS" a mixed.zpaq f5.bin -ma:lizard:17 -nochecksum >/dev/null
"$ZS" a mixed.zpaq f6.bin -ma:bzip2:9  -nochecksum >/dev/null
"$ZS" a mixed.zpaq f7.bin -ma:bzip3:5  -nochecksum >/dev/null
"$ZS" a mixed.zpaq f8.bin -ma:brotli:6 -nochecksum >/dev/null
"$ZS" a mixed.zpaq f9.bin -ma:brotli:11 -nochecksum >/dev/null
"$ZS" x mixed.zpaq -to out/ -force >/dev/null
for i in $(seq 1 9); do
    cmp -s "f$i.bin" "out/f$i.bin" || { echo "MIXED f$i MISMATCH" >&2; exit 1; }
done
echo "MIXED 9-algo archive  MATCH"
```

Run it after every code change. It catches the most common integration bugs (offset bugs in decompress, marker-prefix mismatches, level-clamp errors, etc.) in ~5 seconds.

---

## 7. Commit / push workflow

```bash
# After making changes:
make clean && make
./runtest.sh                                    # if you created it
git status
git diff                                         # eyeball the changes
git add -A
git commit -m "Add -ma:zlib:N support"           # or whatever
git push origin main
```

The repo lives at `https://github.com/YadeWira/zpaq-std`. The local remote is:
```bash
git remote -v
# origin  https://github.com/YadeWira/zpaq-std (fetch)
# origin  https://github.com/YadeWira/zpaq-std (push)
```

If the remote ever points back to one of Franco Corbelli's forks (`fcorbelli/zpaqfranz` or `fcorbelli/zpaq-std`), fix it with:
```bash
git remote set-url origin https://github.com/YadeWira/zpaq-std
```

---

## 8. Quick code reference for the integrators

When working on `zpaq-std.cpp`, these are the symbols / line ranges you need:

| Symbol | Type | Where |
|---|---|---|
| `g_ma_algorithm` | `std::string` | line ~2191 (global) |
| `g_ma_level` | int | near `g_ma_algorithm` |
| `ma_comment` | `std::string` (local) | inside the compress segment loop |
| `zstd_orig`, `lz4_orig`, `brotli_orig` etc. | `int64_t` | inside the decompress path |
| `cs.find("zpaqstd-ma:...")` | detection | decompress path |
| `sb.write(...)` | append to segment buffer | compress path |
| `decomp2` | `std::vector<unsigned char>` | decompress output |

To find the exact lines: `rg -n "g_ma_algorithm" zpaq-std.cpp`.

---

## 9. Versioning

`zpaq-std` follows the upstream version number (`v64.7g` in current build). When adding a feature, bump the local `CHANGELOG.md` only; don't touch the version string in `zpaq-std.cpp` — that comes from the upstream sync.

If you do an upstream sync (rare), re-test with `./runtest.sh` and verify that the `-ma:algo:N` markers in the new code still match the dispatch in this fork.
