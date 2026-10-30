# PJA 0.5.1: the zpaq-std plugin, vendored

PJA (https://github.com/YadeWira/PJA), tag `v0.5.1`, commit `b52504c`:
only the sources the zpaq-std plugin is built from. MIT (`LICENSE`);
`NOTICE` has the third-party notes (IJG for the arithmetic-coded JPEG,
CharLS's BSD 3-Clause for JPEG-LS).

One file, ten codecs (`zpaqstd_codecs_v1`), on zpaq-std's plugin ABI 1,
with `zpaqstd_detect_v1`. 0 to 4 are 0.3.0's, unchanged (streams, ZPAQL,
what each takes). 5 to 9 are new: each is the codec above it without the
z (the same functions for detect, compress, decompress and query; its
detect answers as that codec's) with another ZPAQL, for blocks whose
segments zpaq-std passes through zpaq's level 1 LZ77 (the `-m1` method,
`rb` = 0), matches reaching back into the segments before in the block.

| index | codec | takes |
|---|---|---|
| 0 | `pja` | Huffman and arithmetic JPEG, 8-bit, as 0.0.1 |
| 1 | `pjals` | JPEG-LS, as 0.0.1 |
| 2 | `pjax` | Huffman JPEG that needs stream version 6 (12-bit, DNL, a DRI not followed, 256 KiB or more of JPEGs after the EOI) |
| 3 | `pjall` | lossless JPEG (SOF3, Huffman) |
| 4 | `pjalsx` | JPEG-LS with subsampled components |
| 5 | `pjaz` | what `pja` takes; block: `pja` segments through the LZ77 |
| 6 | `pjalsz` | what `pjals` takes; likewise |
| 7 | `pjaxz` | what `pjax` takes; likewise |
| 8 | `pjallz` | what `pjall` takes; likewise |
| 9 | `pjalsxz` | what `pjalsx` takes; likewise |


Suggested `-sat` order: `pjax`, `pja`, `pjall`, `pjals`, `pjalsx`
(pjax's detect takes only what pja cannot take or what gains enough to
pay pjax's ZPAQL; the rest falls to pja; pjall, pjals and pjalsx take
what no other codec does). The z codecs are not in that order: zpaq-std
takes a group's files by their codec and uses its z codec for the block
when the LZ77 wins. 0.0.6 adds pjalsx: pja, pjals, pjax and
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
0.1.0 brings the `pja` command a new model (stream version 7, in C),
which the plugin does not use: the plugin has no C and these sources
build it as before. Its one change: on macOS (Darwin) the exported names
carry the leading underscore `dlsym` looks for there
(`_zpaqstd_codecs_v1`, `_zpaqstd_codec_v1`, `_zpaqstd_detect_v1`);
other platforms export the same names as before. The streams, the ZPAQL
and what each codec takes are 0.0.6's.
0.2.0 adds libpja (a C library and 7-Zip codec, not part of this
tarball): the plugin is 0.1.0's. The list of files here is the same as
since 0.0.6; pjacodec, pjajpeg and pjamodel have changed inside since
0.0.8 (stream version 7 for the command), with no effect on what the
plugin writes or reads.
0.3.0 makes libpja faster in 7-Zip (two streams, dedup, a thread
pool). In these sources, one change: each thread that codes frees the
model tables it kept for its next file (`ReleaseThreadModels` in
pjamodel, called at the end of pjacodec's band threads), which
FreePascal does not free when a thread ends. The streams, the ZPAQL and
what each codec takes are 0.0.6's.
0.4.0 adds the z codecs (5 to 9) and one file, `pas/plugin/lzzpaql.inc`,
with their ZPAQL; `pja_zpaqstd.pas` lists them. Codecs 0 to 4, their
streams, their ZPAQL and what each takes are 0.3.0's (0.0.6's). The same
sources as the preview of commit `4468f35` but for the version number.
0.5.0 changes the `pja` command and libpja (JPEGs without their tables
in libpja's filter; two encoder quirks repaired). In these sources:
pjamodel's CodeRaw can leave out tables a caller gives
(`SetGivenTables`), which the plugin never does, and pjacodec has a new
stream version 6 mode (PATCH) that only `Compress` with parts writes:
the plugin writes version 5 (and pjax its own), as before. The codecs,
their streams, their ZPAQL and what each takes are 0.4.0's.
0.5.1 changes the plugin only, and none of its streams or ZPAQL. pjax's
detection takes the MPO it refused by an estimate that counted the second
image twice (2^27 words of H where the stream asks for 2^25): more MPO go
to pjax. The detections of pja, pjax and pjall verify a JPEG once (a few
verdicts kept, by size and hash); pja's compress then only takes it apart
(`pjacodec.CompressVerified`). A new optional export,
`void zpaqstd_threads_v1(int n)` (cdecl; `_zpaqstd_threads_v1` on macOS):
zpaq-std's number of threads, of which each compress() and decompress()
takes n / (the calls running) for its file's bands. Without it, one
thread a call, as before; the streams are the same with any number.

| | |
|---|---|
| z ZPAQL | `pas/plugin/lzzpaql.inc`: `PJAZ_ZPAQL` 39,458 bytes of PCOMP, `PJALSZ_ZPAQL` 32,984, `PJAXZ_ZPAQL` 37,476, `PJALLZ_ZPAQL` 18,003, `PJALSXZ_ZPAQL` 36,110; handed out as `ZS_DATA_ZPAQL_ARGS`; config `comp 0 0 $3 $1 0` |
| `$3` | the codec's own `query(ZS_QUERY_ZPAQL_ARGS)` on each segment (the codec's stream, before the LZ77), the largest of the block: the z decoders take H to the word as their codec's |
| `$1` | the LZ77 window's bits: M is a ring of 2^$1 bytes; no match distance may reach 2^$1 and no segment come out larger than 2^$1 bytes |
| errors | a match before the block's first byte, more than 23 bits of distance, and whatever the codec's decoder refuses |
| native path | expand the LZ77 in C (the same ring), then the codec's `decompress()` on each segment, as today |
| library | the codec's field with `, lz77` (`pja stream v5 full, lz77`, ...) |
| frozen | these five z ZPAQL programs do not change under these names, nor 0 to 4's |

## Building

FreePascal 3.2.2. From this directory, with the commit the info card
(`ZS_DATA_INFO`, `codecinfoex`) shows:

```sh
export PJA_COMMIT=b52504c
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

## Checked (the z codecs)

libzpaq (zpaq 7.15's engine), each set as ONE block of its codec's
segments through a test LZ77 (PJA's `tools/zpaql/lz77.py`, and the same
in C): every file back, with $1 = 24 and with the smallest window that
holds the largest segment (M wraps several times); pjaz also at 12 and 10
bits. arithmetic 244 (17.70% of the JPEGs), generated 640 (16.77%), 73
JPEG-LS (79.24%), 66 JPEG + 6 MPO through pjaxz (71.73%), 36 lossless
JPEG (19.84%), 76 subsampled JPEG-LS (69.96%). 150 damaged segments per
codec in blocks of 12 to 15: no hang; 144 to 150 errors, the rest the same
file or other bytes with no error (as without the LZ77: zpaq's SHA-1
catches them). PJA's suite decodes each z on a block of two files and the
first again, in its ZPAQL interpreter.

## Checked (0.3.0, codecs 0 to 4)

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
