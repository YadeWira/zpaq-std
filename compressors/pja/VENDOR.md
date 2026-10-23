# PJA 0.0.1: the zpaq-std plugin, vendored

PJA (https://github.com/YadeWira/PJA), tag `v0.0.1`, commit `0776d32`:
only the sources the zpaq-std plugin is built from. MIT (`LICENSE`);
`NOTICE` has the third-party notes (IJG for the arithmetic-coded JPEG,
CharLS's BSD 3-Clause for JPEG-LS).

One file, two codecs (`zpaqstd_codecs_v1`): `pja` for JPEG and `pjals` for
JPEG-LS, on zpaq-std's plugin ABI 1, with `zpaqstd_detect_v1`.

| | |
|---|---|
| stream | PJA codec stream version 5, full model (library field `pja stream v5 full`, `pja stream v5 jpeg-ls`) |
| ZPAQL | `pas/plugin/pjazpaql.inc` (pja, 62,294 bytes of PCOMP) and `pjalszpaql.inc` (pjals, 55,989), handed out as `ZS_DATA_ZPAQL_ARGS`; H sized per block by `query(ZS_QUERY_ZPAQL_ARGS)`; several segments a block (`query(ZS_QUERY_SEGMENTS)` = 1) |
| frozen | these two ZPAQL programs and the stream they read do not change under these codec names: a new format is a new codec or a new ZPAQL with another name |

## Building

FreePascal 3.2.2. From this directory, with the commit the info card
(`ZS_DATA_INFO`, `codecinfoex`) shows:

```sh
export PJA_COMMIT=0776d32
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

zpaq-std -sat with these sources (both codecs, JPEG and JPEG-LS files
mixed, one file a block and several): every block decoded by the ZPAQL as
by the plugin, every file back without the plugin, plain zpaq 7.15
included; Windows 10, 64 and 32 bits.
