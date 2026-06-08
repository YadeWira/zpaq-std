# Vendored: preflate

- **Upstream:** https://github.com/deus-libri/preflate
- **Commit:** `609eefaa96ac6c51d7b1a3fb29e0ed94d0f3623e`
- **Copyright:** 2018 Dirk Steinke
- **License:** Apache License 2.0 (see `LICENSE`). Permissive; compatible with this
  project's MIT licensing. Apache-2.0 §4 requires retaining the license and stating
  changes — this file does so.

## What is vendored

Only the **library** sources (the `add_library(preflate ...)` set from upstream
`CMakeLists.txt`): 18 `preflate_*.cpp` + 12 `support/*.cpp`, plus all needed
headers, `LICENSE`, and upstream `README.md`. The demo/tooling
(`main.cpp`, `main2.cpp`, `preflate_checker.*`, `preflate_statistical_debug.cpp`,
`support/support_tests.cpp`), the `CMakeLists.txt`/`Makefile`, and the demo-only
`packARI/` and bundled `zlib` are **not** vendored — they are not needed for the
`preflate_decode` / `preflate_reencode` vector APIs we use.

## Modifications from upstream (Apache-2.0 §4)

Minimal portability fixes for modern GCC and the MinGW cross build:

1. `preflate_seq_chain.h` — added `#include <cstdint>` (uses `uint16_t`; upstream
   relied on transitive includes that newer GCC no longer provides).
2. `support/outputcachestream.h` — added `#include <cstddef>` and `#include <cstdint>`
   (uses `ptrdiff_t`).
3. `support/filestream.cpp` — guarded the MSVC-only `_ftelli64` / `_fseeki64` behind
   `#ifdef _MSC_VER`, falling back to `ftello` / `fseeko` elsewhere (Linux + MinGW).

No algorithmic changes. The reconstruction format and behaviour are upstream's.

## Phase-0 self-test (reproducible)

`selftest.cpp` (this project's file, **not** upstream) proves the core guarantee:
a raw DEFLATE stream → `preflate_decode` → `preflate_reencode` is **byte-identical**.

Build & run (Linux):

```sh
cd compressors/preflate
mkdir -p /tmp/pfobj
for f in *.cpp support/*.cpp; do [ "$(basename $f)" = selftest.cpp ] && continue; \
  g++ -std=c++11 -O2 -I. -Isupport -DZ_SOLO -DNO_GZIP -c "$f" -o "/tmp/pfobj/$(basename ${f%.cpp}).o"; done
g++ -std=c++11 -O2 -I. -Isupport -DZ_SOLO -DNO_GZIP -pthread selftest.cpp /tmp/pfobj/*.o -o /tmp/pf_selftest
# make raw-deflate samples:
python3 - <<'PY'
import zlib, os
d=(b"hi "*5000)+bytes(range(256))*200+os.urandom(40000)
for l in (1,6,9):
    c=zlib.compressobj(l,zlib.DEFLATED,-15); open(f"/tmp/t{l}.deflate","wb").write(c.compress(d)+c.flush())
PY
/tmp/pf_selftest /tmp/t1.deflate /tmp/t6.deflate /tmp/t9.deflate
```

Verified result (Linux native **and** Windows MinGW cross, run on a real Win10 VM):
all streams report `BIT-EXACT OK` → `SELFTEST: ALL BIT-EXACT`. Reconstruction diff
was 13 bytes for a 242 KB / ~51 KB-deflate sample.
