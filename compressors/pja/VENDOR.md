# PJA 0.0.8: the zpaq-std plugin, vendored

PJA (https://github.com/YadeWira/PJA), tag `v0.0.8`, commit `11ec86e`:
only the sources the zpaq-std plugin is built from. MIT (`LICENSE`);
`NOTICE` has the third-party notes (IJG for the arithmetic-coded JPEG,
CharLS's BSD 3-Clause for JPEG-LS).

One file, five codecs (`zpaqstd_codecs_v1`), on zpaq-std's plugin ABI 1,
with `zpaqstd_detect_v1`:

| index | codec | takes |
|---|---|---|
| 0 | `pja` | Huffman and arithmetic JPEG, 8-bit, as 0.0.1 |
| 1 | `pjals` | JPEG-LS, as 0.0.1 |
| 2 | `pjax` | Huffman JPEG that needs stream version 6: 12-bit, a height in a DNL, a DRI the encoder did not follow, or 256 KiB or more of JPEGs after the EOI (an MPO's or Ultra HDR's next images); photos with only EXIF thumbnails stay with pja |
| 3 | `pjall` | lossless JPEG (SOF3, Huffman): 2 to 16 bits, predictors 1 to 7, point transform, restarts, DNL; no other codec takes it |
| 4 | `pjalsx` | JPEG-LS whose components are subsampled (T.87's sampling factors), no interleave or line interleave; no other codec takes it |

Suggested `-sat` order: `pjax`, `pja`, `pjall`, `pjals`, `pjalsx`
(pjax's detect takes only what pja cannot take or what gains enough to
pay pjax's ZPAQL; the rest falls to pja; pjall, pjals and pjalsx take
what no other codec does). 0.0.6 adds pjalsx: pja, pjals, pjax and
pjall, their streams and their ZPAQL are 0.0.5's.
0.0.7 changes only the `pja` command (wildcards on Windows): the plugin
is 0.0.6's but for the version its info card shows.
0.0.8 changes only the `pja` command (the progressive JPEGs of
Photoshop, which end their refinement scans' EOB runs at another number
of correction bits than libjpeg, a quirk that needs stream version 6,
and threads on Linux and macOS): before, these files did not come back
and every detect said no; they still do, now because pja's and pjax's
detects ask for the quirk. The streams, the ZPAQL and what each codec
takes are 0.0.6's.

| | |
|---|---|
| stream | `pja`, `pjals`: PJA codec stream version 5, unchanged (library fields `pja stream v5 full`, `pja stream v5 jpeg-ls`); `pjax`: version 5 or 6 (`pja stream v6 pjax`); `pjall`: version 5 (`pja stream v5 lossless jpeg`); `pjalsx`: version 5 (`pja stream v5 jpeg-ls subsampled`) |
| ZPAQL | `pas/plugin/pjazpaql.inc` (pja, 62,294 bytes of PCOMP) and `pjalszpaql.inc` (pjals, 55,989), byte for byte 0.0.1's; `pjaxzpaql.inc` (pjax, 57,709), 0.0.3's; `pjallzpaql.inc` (pjall, 30,508), 0.0.5's; `pjalsxzpaql.inc` (pjalsx, 60,776); handed out as `ZS_DATA_ZPAQL_ARGS`; H sized per block by `query(ZS_QUERY_ZPAQL_ARGS)`; several segments a block (`query(ZS_QUERY_SEGMENTS)` = 1) |
| frozen | these five ZPAQL programs and the streams they read do not change under these codec names: a new format is a new codec or a new ZPAQL with another name |

## Building

FreePascal 3.2.2. From this directory, with the commit the info card
(`ZS_DATA_INFO`, `codecinfoex`) shows:

```sh
export PJA_COMMIT=11ec86e
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

pjalsx, with these sources: libzpaq (zpaq 7.15's engine) on 67
subsampled JPEG-LS files (CharLS's, subsampled 2x4/2x1/1x2, 4:2:0, 4:2:2
and 4:1:1, some with restarts, and T.87's T8SSE0 and T8SSE3), every file
back, each with either model forced (136 of 136), blocks of 6 and 4
segments, 300 damaged segments (299 errors, 1 decoded to other bytes of
the same size, which zpaq's SHA-1 catches; no hang); zpaq-std -sat in
the family's order on those with zpaq-std's 79 files: 49,375,481 bytes
against 0.0.5's 49,953,561 (-1.16%), every block ZPAQL OK, plain zpaq
7.15 giving every file back; Windows 10, 64 and 32 bits, the same
archive, every file back without the plugin. PJA's CI builds the plugin
on Linux x86-64, x86 and AArch64, macOS arm64 and Windows x64 and x86.

pjall as in 0.0.5: libzpaq (zpaq 7.15's engine) on 36 synthetic
lossless JPEGs and 60 photos as lossless JPEG, every file back, blocks of
several segments, 300 damaged segments (299 errors, 1 decoded the same,
no hang); zpaq-std 1.7.0 -sat (`-sat:pja:pjax+2:pja+2:pjall+2:pjals+2`)
on those with zpaq-std's 79 files: 128,835,877 bytes against 0.0.4's
151,373,263 (-14.9%), every block ZPAQL OK, plain zpaq 7.15 giving every
file back; Windows 10, 64 and 32 bits, the same archive, every file back
without the plugin.

pja, pjals and pjax as in 0.0.4: zpaq-std's 79 files 19,451,097 bytes
with the family, as without pjax; 116 JPEG, MPO and JPEG-LS files 3.92%
smaller than without pjax; pjax's ZPAQL through libzpaq on 69 corpus
JPEGs and 6 MPOs, and on Windows 10, 64 and 32 bits.
