# LZMA SDK (encoder only)

Origin: https://github.com/ip7z/7zip, `C/` directory. Igor Pavlov, **public domain**.

Vendored for one reason: zpaqf's transform 14, reached by `-mf3`. The ZPAQL
postprocessor that `makeConfigF` emits decodes an LZMA1 stream, so producing
that block needs an LZMA1 *encoder* that matches it. The decoder side is the
ZPAQL bytecode carried inside the archive, which is why no decoder source is
here and why any zpaq can read an `-mf3` archive without this library.

Only the files `LzmaCompress` needs are kept:

    LzmaLib.c  LzmaEnc.c  LzmaDec.c  LzFind.c  Alloc.c  CpuArch.c
    LzmaLib.h  LzmaEnc.h  LzmaDec.h  LzFind.h  Alloc.h  LzHash.h
    7zTypes.h  7zWindows.h  CpuArch.h  Compiler.h  Precomp.h

`LzmaDec.c` is here only because `LzmaLib.c` defines `LzmaUncompress` next to
`LzmaCompress` in the same translation unit; nothing calls it. `CpuArch.c`
provides the `CPU_IsSupported_*` probes that `LzmaDec.c` needs on x86.

Built with `-DZ7_ST`: that compiles out the multi-threaded match finder
(`LzFindMt.c`, `Threads.c`), which is why neither file is here. zpaq-std already
parallelises across blocks, so a second thread pool inside one block would only
fight it for cores.

This is unrelated to `compressors/fl2` (fast-lzma2), which is LZMA**2** and has
no raw LZMA1 entry point with the 5-byte property header this needs.

To update: re-copy the files above from upstream `C/`. Nothing here is patched.
