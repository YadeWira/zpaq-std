# packPNG (vendored prebuilt SDK)

Lossless, byte-exact recompressor for PNG/APNG via WebP-lossless (backend TCIP:
preflate + WebP-lossless, ~45% ratio vs ~75% for a generic deflate-recompressor).
Upstream: https://github.com/YadeWira/packPNG (MIT, same author as this fork).

## Why prebuilt, not source-vendored

Unlike every other `compressors/*` codec in this tree, packPNG is vendored as
**prebuilt static libraries**, not source compiled in-tree. Reasons:

- packPNG's own build depends on `kanzi-cpp` (C++, its own `.a` built via a
  private/undocumented recipe in this checkout) and `preflate-rs` (Rust,
  `source/vendor/preflate-rs`, static libs built with `cargo build --release`
  and gitignored — not reproducible from the packPNG repo checkout alone).
- packPNG publishes an **SDK release** specifically for archiver embedding
  (`packPNG-2.0a-{linux-x64,win64}-lib.{tar.gz,zip}`, GitHub release `v2.0a`):
  a fat static archive with packPNG + packJPG + kanzi + preflate-rs already
  merged, plus the public C header (`packpng.h`). That is what is vendored here.

## Files

| File | From | Notes |
|---|---|---|
| `packpng.h` | SDK release `v2.0a`, both bundles (identical) | Public C API |
| `libpackpng-linux-x64.a` | `packPNG-2.0a-linux-x64-lib.tar.gz` | Linux x86-64 static |
| `libpackpng-windows-x64.a` | `packPNG-2.0a-win64-lib.zip` | Windows x86-64 static (137 MB: kanzi+preflate-rs+packjpg fat-merged) |
| `liblzma-windows-x64.a` | packPNG repo, `source/vendor/mingw-deps/lib/liblzma.a` | needed to satisfy `libpackpng-windows-x64.a`'s `lzma_*` symbols when cross-linking (mingw has no system liblzma) |

SHA-256 (2026-07-02, from `v2.0a`):
```
fff8597a511fc9e8b07e934ee0e5c195945e414ffc9cfa090d73d9c9e2e1b357  libpackpng-linux-x64.a
f28de7aa37404aef93fb5bce789622e5ab8175b8febb36078ed076b6e95276d5  libpackpng-windows-x64.a
9c6ea0987511717422761d09af67869a8fa8e524262dad74b31166e50698b99b  liblzma-windows-x64.a
2dcbf79edc5d178e243a811cd8641fb5c6e336ee7a585bf97c5f9e8826a97c0d  packpng.h
```

## Link requirements (verified by an actual test link, not just the SDK's README)

- **Linux**: `libpackpng-linux-x64.a` + static `-llzma -lz` (from `zlib1g-dev` /
  `liblzma-dev`) + `-lpthread -ldl -lm -lstdc++`. `-lzstd` (mentioned in the
  SDK's own README) is NOT actually needed — `ldd` on a real test binary shows
  no zstd dependency, so it's dropped here. No `libz.so`/`liblzma.so` runtime
  dependency: link the `.a` (static) forms with `-Wl,-Bstatic ... -Wl,-Bdynamic`,
  matching zpaq-std's zero-runtime-dependency policy (a naive `-llzma -lz` picks
  the `.so` and makes the WHOLE zpaq-std binary fail to start on any system
  missing those shared libs — verified, then avoided).
- **Windows (mingw x86_64-w64-mingw32)**: `libpackpng-windows-x64.a` +
  `liblzma-windows-x64.a` + system `libz.a` (from the `libz-mingw-w64-dev`
  apt package, `/usr/x86_64-w64-mingw32/lib/libz.a`) + `-lws2_32 -luserenv
  -lbcrypt -lntdll -lstdc++`, fully `-static`. Verified with a real cross-link
  + `wine` smoke run (`rc=0 version=2.0a`).
- **No i686/32-bit build exists.** packPNG's own `Targets:` are "Linux x86-64,
  Windows 10/11 x86-64" only; the Makefile only builds Rust for
  `x86_64-pc-windows-gnu`. zpaq-std's 32-bit (Win7 x86) build never links
  packPNG at all — see the `PACKPNG_AVAILABLE` gate in the main `Makefile`.

## Hard runtime requirement: AVX2

The vendored SDK requires **AVX2** (`-march=native` build; confirmed in the
SDK's own `README.txt`: "Requires x86-64 with AVX2"). This is not just a
performance note — code compiled for AVX2 executes illegal-instruction (SIGILL)
on a CPU without it. zpaq-std guards every call into packPNG with a runtime
CPUID + OSXSAVE + XGETBV check (`compressors/preflate/pcf_wrapper.cpp`,
mirroring the existing `ihavehw()` SHA-NI check in `zpaq-std.cpp`) so:

- **Encode**: on a non-AVX2 CPU, PNG/APNG files are simply not recompressed
  (same as if `-sa` didn't cover them) — no crash, no behavior change beyond
  no ratio gain for those files.
- **Decode**: a PCF_SEG_PACKPNG segment created on an AVX2 machine CANNOT be
  reversed on a non-AVX2 machine — this is an inherent limitation of the
  vendored library, not a bug. The extraction code degrades safely (the file
  is left as its still-compressed container, never garbage; `-test`/`-verify`
  catches the mismatch) and prints a clear diagnostic identifying the cause.

**Practical impact**: any x86-64 CPU from roughly 2013 onward (Haswell+/
Excavator+) has AVX2. This is documented in the top-level README next to the
`-pc` experimental notice.

## DO NOT update the vendored SDK without a migration plan

Extraction authenticates every PCF container by **re-encoding the decoded
original and requiring byte-identical output** to what was stored
(`pcf_authentic_reverse2`, `compressors/preflate/pcf_wrapper.cpp`). For
`PCF_SEG_PACKPNG` that means: the packPNG encoder available at *extract* time
must reproduce, bit-for-bit, the `.ppg` bytes produced at *add* time.

The current vendored `v2.0a` encoder was **empirically verified deterministic**
(bit-identical across `packpng_set_threads(1/2/8/auto)` and across reruns, on
real PNGs), so same-SDK add/extract always authenticates. But **swapping the
vendored `.a` for a newer packPNG release whose encoder output differs — even
by one byte, even though the wire format is "frozen 2.0x-decodable" — would
silently orphan every existing `-sa` PNG archive**: decode still works, the
authenticity re-encode mismatches, and the file is left as its compressed
container (extraction now warns per-file, `00566!`, instead of staying silent —
but the data is still not restored as a PNG).

If an SDK update is ever needed: either (a) keep the old `.a` alongside and try
old-then-new in the authenticity re-encode, or (b) migrate the PCF format to
authenticate by a stored hash of the original bytes instead of re-encode
equality (decode-side only, no encoder-identity requirement). Until then: the
vendored `.a` is part of the archive format surface — treat it as frozen.
