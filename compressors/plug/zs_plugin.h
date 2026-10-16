/*
  zs_plugin.h - for the adapters in compressors/plug/ (C++).

  ZS_DEFINE_CODEC(id, library, min, max, bound, compress, decompress, query)
  defines the adapter's zs_codec. In the full build it is reached through
  zs_codec_<id>(), which zpaq-std's registry calls; built with -DZS_PLUGIN it
  is exported as zpaqstd_codec_v1(), the entry point of codecs/<id>.dll/.so.
*/
#ifndef ZS_PLUGIN_H
#define ZS_PLUGIN_H

#include "zs_codec.h"

#define ZS_CODEC_OBJECT(id, library, mn, mx, b, c, d, q) \
	static const zs_codec zs_codec_obj = { ZS_CODEC_ABI, #id, library, mn, mx, b, c, d, q };

#ifdef ZS_PLUGIN
#define ZS_DEFINE_CODEC(id, library, mn, mx, b, c, d, q) \
	ZS_CODEC_OBJECT(id, library, mn, mx, b, c, d, q) \
	extern "C" ZS_CODEC_EXPORT const zs_codec* zpaqstd_codec_v1(void) { return &zs_codec_obj; }
#else
#define ZS_DEFINE_CODEC(id, library, mn, mx, b, c, d, q) \
	ZS_CODEC_OBJECT(id, library, mn, mx, b, c, d, q) \
	extern "C" const zs_codec* zs_codec_##id(void) { return &zs_codec_obj; }
#endif

#endif
