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

## A codec that is not part of zpaq-std: -mae and -mat

A codec can be used in real archives without rebuilding zpaq-std. Put its plugin in
`codecs/` and name it on the command line, without the extension:

```
zpaq-std a test.zpaq files -mat:<file>:<codec>[:<level>]     test (for its developer)
zpaq-std a data.zpaq files -mae:<file>:<codec>[:<level>]     external (a finished codec)
```

`<file>` is `codecs/<file>.dll` or `.so`, `<codec>` one of the codecs in it, and
`<level>` one of its levels (by default 1, or its lowest). The names may hold only
letters, digits, `_`, `-` and `.`: a codec is loaded from `codecs/` and nowhere else.

The plugin uses the interface above, with two optional additions (`zs_codec.h`):

- **Several codecs in one file**: export `zpaqstd_codecs_v1(int i)`, returning the
  i-th codec or NULL past the last one. A file with only `zpaqstd_codec_v1()` holds
  one codec.
- **Its ZPAQL decoder**: `data(ZS_DATA_ZPAQL, &size)` returns a whole ZPAQL
  configuration as text. Every block carries it, so any zpaq opens the archive
  without the plugin. It decodes a segment made of the original size (u32 little
  endian) followed by what `compress()` wrote, and must output exactly the original
  bytes. In the text, `$1` is log2 of the segment size and `$2` log2 of the original
  size, both rounded up, for sizing H and M (`comp 0 0 0 $1+1 0`).

| | `-mae` (external) | `-mat` (test) |
|---|---|---|
| for | finished codecs from third parties | developing a codec |
| ZPAQL decoder | **required**: the archive opens in any zpaq, whatever happens to the plugin | optional |
| message | `00606!`: not an official zpaq-std codec, its support is not guaranteed | the plugin's details, then every block |
| block tag | `zpaqstd-mae:` | `zpaqstd-mat:` |

**What `-mat` shows**: the plugin (path, the codecs in the file, library, interface,
levels, whether it gives a ZPAQL decoder and its size), and for every block its sizes,
ratio and compression time, decoded back by the plugin and by the ZPAQL decoder and
compared (`OK`, `WRONG`, or the ZPAQL's error). Extracting a `-mat` archive says, for
every block, whether the plugin or the ZPAQL decoded it.

**A `-mat` codec without a ZPAQL decoder**: allowed, so that a compressor can be tried
before its decoder is written. For safety, its blocks carry a decoder that writes
nothing (ZPAQEXTNONE): any other zpaq reports them as damaged, instead of handing back
the compressed bytes as if they were the file. Only zpaq-std with that plugin extracts
them; without it, `31321` names the plugin it needs.

**Extraction**: zpaq-std decodes a block with the plugin only if the block's ZPAQL
program is, byte for byte, the one the plugin gives now. If a later version of the
plugin changed its format (and so its decoder), the block's own decoder runs instead,
which is always right.

[`tools/plugin_example/zs_example.c`](../../tools/plugin_example/zs_example.c) is a
complete plugin with two codecs: `rle`, with its ZPAQL decoder, and `rlenz`, without.

## Codecs for specific formats: -sae and -sat

Some codecs only make sense for one kind of file (a JPEG recompressor, for instance).
`-sae` and `-sat` are `-mae` and `-mat` for them: the codec compresses only the files
it takes, each one alone in its block, and the rest of the archive is compressed as
`-m`/`-ma` say.

```
zpaq-std a test.zpaq files -sat:<file>:<codec>[+<level>][:<codec>[+<level>]...]
zpaq-std a data.zpaq files -sae:<file>:<codec>[+<level>][:<codec>[+<level>]...]
```

- **Which files**: the plugin exports one more function,
  `int zpaqstd_detect_v1(const char* codec, const void* src, size_t n)`, which gets a
  whole file and returns 1 if that codec takes it. It looks **only at the bytes**:
  never at the name or the extension, which can lie. It must give the same answer on
  every machine, never read outside `src`, and be safe on damaged or hostile files
  and when several threads call it at once (it runs in the threads that read the files
  ahead of the main one). Each file goes to the first codec, in the order written,
  that takes it. Files up to 64 MB are shown to the codecs.
- **What compress() gets**: the file's block, that is the file followed by zpaq-std's
  list of fragments (8 + 4 × fragments bytes). The codec must give those bytes back
  too, so it has to keep whatever follows the end of its format, and so must its ZPAQL
  decoder. The segment is, as for `-mae`, the size (u32 little endian) and the codec's
  output.
- **Decoded back before writing**: zpaq-std decodes every such block with the plugin
  (and, with `-sat`, with its ZPAQL) and compares; a block that does not come back
  identical (`00735!`), or that the codec cannot make smaller, is compressed as `-m`
  says (not by a `-ma` codec). A file already partly in the archive (deduplicated) is
  compressed as usual, since the codec needs it whole.
- **Threads**: the codec runs in the compressing threads, several files at once. The
  archive is byte for byte the same with any number of threads.
- `-sae` requires the ZPAQL decoder and says (`00732!`) that the codecs are not
  official; `-sat` allows a codec without one (its blocks then fail cleanly in any
  other zpaq, as with `-mat`) and shows which codec took each file, its sizes and
  times, and how it decoded back. Tags: `zpaqstd-sae:` and `zpaqstd-sat:`.

**A codec's card**: `data(ZS_DATA_INFO, &size)` may return `key=value` lines (`author`,
`repo`, `license`, `version`, `commit`, `format`, `notes`, or any other key), which
`zpaq-std codecinfoex <file>:<codec>` shows next to what zpaq-std works out itself:
the SHA-256 of the plugin file and of the ZPAQL decoder's text, and which of
`-mae`/`-mat`/`-sae`/`-sat` can use the codec. A card is only shown, never acted on.

`zs_example.c` also has a `zpaqstd_detect_v1`: its two codecs take a file where at
least half of the bytes are in runs of three or more.

## Plugin-only codecs: Rust and Free Pascal

A codec written in Rust or Free Pascal is, by rule, **never linked into zpaq-std**:
it is always a plugin, in both builds. The full program loads these codecs
(`ZS_PLUGIN_ONLY` in zpaq-std.cpp, today sylz) from `codecs/` as well, and
`make fpc-plugins` builds the Free Pascal ones with `fpc` (for Windows x86, a cross
`ppc386` and its RTL: `FPC=.../ppc386 FPCUNITS=-Fu.../units/i386-win32`). Their
adapter is written in their own language and exports `zpaqstd_codec_v1` (sylz's is
`compressors/sylz/sylz_zpaqstd.pas`). Like every `-ma` codec, their blocks carry a
ZPAQL decoder inside zpaq-std, so any zpaq reads them without the plugin.

## A plugin from somewhere else

The interface is plain C, so an adapter can be written in any language that exports
C functions: C, C++, Rust, Free Pascal. A plugin can replace one of the codecs above
with another build of the same library, as long as it writes the same format: its
blocks travel with zpaq-std's frozen ZPAQL decoder for that codec, and any zpaq has to
be able to read them. A new codec, though, also needs its ZPAQL decoder and its
`-ma` name inside zpaq-std: see the wiki page
[Adding a compressor](https://github.com/YadeWira/zpaq-std/wiki/Adding-a-compressor).
`tools/codec_check` checks the same three calls a plugin provides.
