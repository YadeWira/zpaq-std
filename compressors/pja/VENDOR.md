# PJA 0.0.4: the zpaq-std plugin, vendored

PJA (https://github.com/YadeWira/PJA), tag `v0.0.4`, commit `ceae7c7`:
only the sources the zpaq-std plugin is built from. MIT (`LICENSE`);
`NOTICE` has the third-party notes (IJG for the arithmetic-coded JPEG,
CharLS's BSD 3-Clause for JPEG-LS).

One file, three codecs (`zpaqstd_codecs_v1`), on zpaq-std's plugin ABI 1,
with `zpaqstd_detect_v1`:

| index | codec | takes |
|---|---|---|
| 0 | `pja` | Huffman and arithmetic JPEG, 8-bit, as 0.0.1 |
| 1 | `pjals` | JPEG-LS, as 0.0.1 |
| 2 | `pjax` | Huffman JPEG that needs stream version 6: 12-bit, a height in a DNL, a DRI the encoder did not follow, or 256 KiB or more of JPEGs after the EOI (an MPO's or Ultra HDR's next images); photos with only EXIF thumbnails stay with pja |

Suggested `-sat` order: `pjax`, `pja`, `pjals` (pjax's detect takes only
what pja cannot take or what gains enough to pay pjax's ZPAQL; the rest
falls to pja). 0.0.4 changes only which files pjax's detect takes: the
streams and the three ZPAQL programs are 0.0.3's.

| | |
|---|---|
| stream | `pja`, `pjals`: PJA codec stream version 5, unchanged (library fields `pja stream v5 full`, `pja stream v5 jpeg-ls`); `pjax`: version 5 or 6 (`pja stream v6 pjax`) |
| ZPAQL | `pas/plugin/pjazpaql.inc` (pja, 62,294 bytes of PCOMP) and `pjalszpaql.inc` (pjals, 55,989), byte for byte 0.0.1's; `pjaxzpaql.inc` (pjax, 57,709); handed out as `ZS_DATA_ZPAQL_ARGS`; H sized per block by `query(ZS_QUERY_ZPAQL_ARGS)`; several segments a block (`query(ZS_QUERY_SEGMENTS)` = 1) |
| frozen | these three ZPAQL programs and the streams they read do not change under these codec names: a new format is a new codec or a new ZPAQL with another name |

## Building

FreePascal 3.2.2. From this directory, with the commit the info card
(`ZS_DATA_INFO`, `codecinfoex`) shows:

```sh
export PJA_COMMIT=ceae7c7
mkdir -p build/lin build/win64 build/win32
```

Linux x86_64 (`-Cg`: position-independent code, for a shared library):

```sh
fpc -O3 -dPJA_FAST -Cg -Fupas -Fipas -Fupas/plugin -Fipas/plugin \
    -FUbuild/lin -obuild/lin/pja.so pas/plugin/pja_zpaqstd.pas
```

Windows x64 (FPC's own cross target, no extra tools):

```sh
fpc -Twin64 -Px86_64 -O3 -dPJA_FAST -Fupas -Fipas -Fupas/plugin -Fipas/plugin \
    -FUbuild/win64 -obuild/win64/pja.dll pas/plugin/pja_zpaqstd.pas
```

Windows x86 (i386-win32, Windows 7 and later), with a `ppc386` cross
compiler and its i386-win32 RTL units in `$RTL386`; `-n` keeps the host's
fpc.cfg out:

```sh
ppc386 -n -Twin32 -O3 -dPJA_FAST -Fu"$RTL386" -Fupas -Fipas -Fupas/plugin -Fipas/plugin \
    -FUbuild/win32 -obuild/win32/pja.dll pas/plugin/pja_zpaqstd.pas
```

Each goes into zpaq-std's `codecs/` folder as `pja.so` or `pja.dll`.
`-dPJA_FAST` turns off range and overflow checks in the models and the
encoders, where they cost 2.3x; the JPEG and JPEG-LS parsers keep theirs
in every build. x86-64 builds use PJA's assembly routines; the 32-bit
build uses their Pascal versions (the same results, checked in PJA's
suite).

## Checked

zpaq-std 1.7.0 -sat with these sources (`-sat:pja:pjax+2:pja+2:pjals+2`),
plain zpaq 7.15 giving every file back: zpaq-std's 79 files 19,451,097
bytes, as without pjax (0.0.3: +0.40%); our 116 JPEG, MPO and JPEG-LS
files 32,047,857, -3.92% against without pjax (0.0.3: -1.84%). pjax's
ZPAQL (0.0.3's) also through libzpaq on 69 corpus JPEGs and 6 MPOs, in
blocks of several segments, 300 damaged segments (299 errors, 1 decoded
the same, no hang), and on Windows 10, 64 and 32 bits.
