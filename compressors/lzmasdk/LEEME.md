# LZMA SDK 26.03

Origin: https://github.com/ip7z/7zip, tag `26.03` (2026-09-03), directory `C/`.
Igor Pavlov, **public domain**. Files copied unmodified.

Used by `-ma:lzma`: `LzmaCompress` writes each block, and `LzmaUncompress`
decodes it natively when zpaq-std reads it. Other zpaq tools do not need this
library: every `-ma:lzma` block carries its own decoder in ZPAQL (see
`compressors/zpaqlzma/`).

Built with `-DZ7_ST`, which compiles out the multi-threaded match finder
(`LzFindMt.c`, `Threads.c` are not here; their headers are, because
`LzFind.c` includes them). zpaq-std already parallelises across blocks.

This is unrelated to `compressors/fl2` (fast-lzma2, LZMA**2**) and to
`compressors/lzlib` (lzip format): neither has a raw LZMA1 entry point with
the 5-byte property header the ZPAQL decoder reads.

To update: re-copy the files from upstream `C/`. Nothing here is patched.
