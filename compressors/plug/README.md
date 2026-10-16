# `-ma` codecs behind one interface

Every `-ma` codec reaches its library through an adapter in this folder,
`zs_<name>.cpp`, which fills one `zs_codec` (see [`zs_codec.h`](zs_codec.h)):

| field | |
|---|---|
| `name`, `library` | the `-ma` name, and what is inside ("zstd 1.5.7") |
| `min_level`, `max_level` | the levels the library accepts |
| `bound(n, level)` | worst-case output size |
| `compress(src, n, dst, cap, level)` | size written, or negative; never writes past `cap` |
| `decompress(src, n, dst, cap, param)` | size written, `ZS_ERR_MEMORY`, or another negative number for a damaged stream; `param` is whatever the codec needs from the block header (kanzi: its level, ppmd: order and memory), else 0 |
| `query`, `data` | optional: kanzi's first pre-transform length, brotli's data prefix |

The adapter only calls the library, buffer to buffer. The block around it (its
header, the ZPAQL method, the `zpaqstd-ma2:` tag) stays in zpaq-std, so a block is
the same byte for byte whichever build wrote it.

## Two builds of the same adapters

- **`make`** links every adapter into the program, reached through
  `zs_codec_<name>()`.
- **`make plugins`** (after `make clean`) builds `plugins/zpaq-std` without the
  codecs' libraries, and each adapter with its library as
  `plugins/codecs/<name>.dll` (Windows) or `.so`, exporting one function,
  `zpaqstd_codec_v1()`. The program loads them from the `codecs` folder next to
  it, by absolute path, once at start-up, and refuses a plugin whose `abi` or
  `name` do not match. On Windows the DLLs link their runtime statically, like
  the program, and import only `KERNEL32` and `msvcrt`: they run on Windows 7.

Without a codec's plugin, compressing with it stops with `00605!`, and its blocks
extract through their ZPAQL decoder. lz5's plugin serves `-ma:lz5`, `lz5hc` and
`lz5f` (the level carries the mode); `-ma:lz` writes LZMA blocks that the `lzma`
plugin decodes.

## A plugin from somewhere else

The interface is plain C, so an adapter can be written in any language that exports
C functions: C, C++, Rust, Free Pascal. A plugin can replace one of the codecs above
with another build of the same library, as long as it writes the same format: its
blocks travel with zpaq-std's frozen ZPAQL decoder for that codec, and any zpaq has to
be able to read them. A new codec, though, also needs its ZPAQL decoder and its
`-ma` name inside zpaq-std: see the wiki page
[Adding a compressor](https://github.com/YadeWira/zpaq-std/wiki/Adding-a-compressor).
`tools/codec_check` checks the same three calls a plugin provides.
