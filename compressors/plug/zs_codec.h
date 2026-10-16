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

  zpaq-std, 2026. MIT licence.
*/
#ifndef ZS_CODEC_H
#define ZS_CODEC_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ZS_CODEC_ABI 1

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
	   zpaq-std always knows. Returns the size written, or a negative number
	   if the stream is damaged. Never reads or writes outside the buffers. */
	long long (*decompress)(const void* src, size_t n, void* dst, size_t cap);

	/* Optional, NULL if the codec needs none: a question about a compressed
	   stream that zpaq-std needs to size the ZPAQL decoder's memory
	   (kanzi: the length of its first pre-transform). */
	long long (*query)(int what, const void* src, size_t n);
} zs_codec;

typedef const zs_codec* (*zs_codec_entry)(void);

#define ZS_CODEC_ENTRY "zpaqstd_codec_v1"

#ifdef _WIN32
#define ZS_CODEC_EXPORT __declspec(dllexport)
#else
#define ZS_CODEC_EXPORT __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
}
#endif

#endif
