/*
  zs_codec.h - the interface between zpaq-std and a -ma codec.

  Every -ma codec is an adapter that fills one zs_codec. The full build links
  every adapter into the binary; the plugin build (make plugins) compiles each
  one, with its library, into codecs/<name>.dll (Windows) or codecs/<name>.so,
  which zpaq-std loads from the folder next to the executable when the codec
  is first used. Without its plugin a codec cannot compress, but its blocks
  still extract: every -ma block carries its own ZPAQL decoder.

  The adapter only calls the library, buffer to buffer, as zpaq-std called it
  before. Everything around the call (the block header, the ZPAQL method, the
  tag in the segment comment) stays in zpaq-std, so a block is the same byte
  for byte whichever build wrote it.

  The interface is plain C, so an adapter can be written in any language that
  exports C functions (C, C++, Rust, Free Pascal). A plugin exports one
  function:

      const zs_codec* zpaqstd_codec_v1(void);

  and zpaq-std refuses a plugin whose abi or name do not match.

  Codecs that are not part of zpaq-std (-mae and -mat, see compressors/plug/
  README.md) use the same interface, with two optional additions:
  - several codecs in one file: the plugin also exports
        const zs_codec* zpaqstd_codecs_v1(int i);
    which returns its i-th codec (from 0), or NULL past the last one;
  - the codec's own ZPAQL decoder: data(ZS_DATA_ZPAQL, &size) returns its text,
    a whole configuration ("comp ... hcomp ... pcomp ... end"). zpaq-std writes
    it into every block, so that any zpaq opens the archive without the plugin.
    The segment it decodes is the original size (u32 little endian) followed by
    what compress() wrote; it must output exactly the original bytes. $1 in the
    text is log2 of the segment size and $2 log2 of the original size, both
    rounded up, for sizing H and M (for instance "comp 0 0 0 $1+1 0").

  Codecs for specific formats (-sae and -sat) add one more export:
        int zpaqstd_detect_v1(const char* codec, const void* src, size_t n);
  zpaq-std calls it with each whole file (n bytes) and the name of one of the
  plugin's codecs; it returns 1 if that codec takes the file, else 0. The
  answer must depend only on the bytes (never on a name, the time or the
  machine), and it must never read outside src: it runs on whatever the user
  archives, damaged or hostile files included. A file the codec takes goes
  alone in a block, and compress() then gets that block: the file followed by
  zpaq-std's list of fragments (8 + 4 x fragments bytes), which it must give
  back too, so a codec has to keep bytes that follow the end of its format.
  zpaq-std decodes every block back and compares before writing it; one that
  does not come back identical is compressed as usual.

  zpaq-std, 2026. MIT licence.
*/
#ifndef ZS_CODEC_H
#define ZS_CODEC_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ZS_CODEC_ABI 1

#define ZS_ERR_DATA   (-1)  /* damaged stream, or the compressor failed */
#define ZS_ERR_MEMORY (-2)  /* out of memory: zpaq-std tries again later */

typedef struct zs_codec {
	int abi;                  /* ZS_CODEC_ABI */
	const char* name;         /* the -ma name, "zstd" */
	const char* library;      /* what is inside, "zstd 1.5.7" */
	int min_level, max_level; /* the levels the library accepts */

	/* Worst-case size of compress()'s output for n bytes at this level,
	   0 when n is too large for the library. */
	size_t (*bound)(size_t n, int level);

	/* Compress n bytes of src into dst (cap bytes) at level. Returns the size
	   written, or a negative number on error. Never writes past cap. */
	long long (*compress)(const void* src, size_t n, void* dst, size_t cap, int level);

	/* Decompress n bytes of src into dst. cap is the original size, which
	   zpaq-std always knows; param is what the codec needs from the block
	   header, if anything (kanzi: its level; ppmd: the order, and the memory in
	   MB from bit 8 on), else 0. Returns the size written, ZS_ERR_MEMORY if
	   memory ran out (zpaq-std tries the block again later), or another
	   negative number if the stream is damaged. Never reads or writes outside
	   the buffers. */
	long long (*decompress)(const void* src, size_t n, void* dst, size_t cap, int param);

	/* Optional, NULL if the codec needs none: a question about a compressed
	   stream that zpaq-std needs to size the ZPAQL decoder's memory
	   (kanzi: the length of its first pre-transform). */
	long long (*query)(int what, const void* src, size_t n);

	/* Optional, NULL if the codec needs none: fixed data that zpaq-std writes
	   into a block, built from the library's own tables (brotli: the data
	   prefix ZPAQBROTLI reads, ZS_DATA_PREFIX). Returns a pointer that stays
	   valid while the plugin is loaded, and its size in *size. */
	const void* (*data)(int what, size_t* size);
} zs_codec;

#define ZS_QUERY_FIRST_PRE 1  /* kanzi: the length of the first pre-transform */
#define ZS_DATA_PREFIX     1  /* brotli: ZPAQBROTLI's data prefix */
#define ZS_DATA_ZPAQL      2  /* -mae/-mat: the codec's ZPAQL decoder, as text */

typedef const zs_codec* (*zs_codec_entry)(void);

#define ZS_CODEC_ENTRY "zpaqstd_codec_v1"
typedef const zs_codec* (*zs_codec_list_entry)(int i);
#define ZS_CODEC_LIST_ENTRY "zpaqstd_codecs_v1"
typedef int (*zs_detect_entry)(const char* codec, const void* src, size_t n);
#define ZS_DETECT_ENTRY "zpaqstd_detect_v1"

#ifdef _WIN32
#define ZS_CODEC_EXPORT __declspec(dllexport)
#else
#define ZS_CODEC_EXPORT __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
}
#endif

#endif
