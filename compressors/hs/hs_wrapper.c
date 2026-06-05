/*
heatshrink one-shot compression/decompression wrappers for zpaq-std.

heatshrink uses a streaming sink/poll/finish API. These wrappers expose a
simple one-shot API matching the rest of zpaq-std's external compressors:

  hs_compress(in, inlen, out, outcap, outlen, level)
      - level=0: window=11, lookahead=4 (default, ~2048 byte window)
      - level=1: window=13, lookahead=5 (~8192 byte window)
      - level=2: window=15, lookahead=6 (max, ~32768 byte window)
      Returns 0 on success (and sets *outlen to compressed size), or -1
      on any heatshrink error / out-of-space condition.

  hs_decompress(in, inlen, out, outcap, produced)
      - Decompresses a heatshrink stream produced with the same window
        and lookahead params (we encode these in the first 2 bytes of
        the compressed stream: window_sz2 | (lookahead_sz2 << 4)).
      Returns 0 on success (and sets *produced to original size), or -1
      on any heatshrink error.

Why encode params in the stream: heatshrink's decompressor needs the same
window_sz2/lookahead_sz2 used at compression. To keep zpaq-std archives
self-describing we prepend a tiny 1-byte header to the compressed data.
*/

#include <stdint.h>
#include <stddef.h>
#include <string.h>

#include "heatshrink_encoder.h"
#include "heatshrink_decoder.h"

#define HS_INBUF 256

static int hs_window_for_level(int level) {
    if (level <= 0) return 11;
    if (level == 1) return 13;
    return 15; /* level >= 2 */
}

static int hs_lookahead_for_level(int level) {
    if (level <= 0) return 4;
    if (level == 1) return 5;
    return 6; /* level >= 2 */
}

int hs_compress_wrapper(const uint8_t* in, size_t inlen,
                        uint8_t* out, size_t outcap, size_t* outlen,
                        int level) {
    if (!in || !out || !outlen) return -1;
    if (inlen == 0) {
        *outlen = 0;
        return 0;
    }
    if (outcap < 1) return -1;

    const int window_sz2 = hs_window_for_level(level);
    const int lookahead_sz2 = hs_lookahead_for_level(level);

    heatshrink_encoder* hse = heatshrink_encoder_alloc(window_sz2, lookahead_sz2);
    if (!hse) return -1;

    /* Byte 0: low nibble = window_sz2, high nibble = lookahead_sz2 */
    out[0] = (uint8_t)((window_sz2 & 0x0F) | ((lookahead_sz2 & 0x0F) << 4));
    size_t produced = 1;

    size_t sunk = 0;
    while (sunk < inlen) {
        size_t in_sunk = 0;
        HSE_sink_res sr = heatshrink_encoder_sink(hse, (uint8_t*)(in + sunk),
                                                   inlen - sunk, &in_sunk);
        if (sr != HSER_SINK_OK) {
            heatshrink_encoder_free(hse);
            return -1;
        }
        sunk += in_sunk;

        HSE_poll_res pr;
        do {
            size_t out_used = 0;
            pr = heatshrink_encoder_poll(hse, out + produced,
                                         outcap - produced, &out_used);
            if (pr < 0) {
                heatshrink_encoder_free(hse);
                return -1;
            }
            produced += out_used;
        } while (pr == HSER_POLL_MORE);
    }

    HSE_finish_res fr = heatshrink_encoder_finish(hse);
    while (fr == HSER_FINISH_MORE) {
        size_t out_used = 0;
        HSE_poll_res pr = heatshrink_encoder_poll(hse, out + produced,
                                                  outcap - produced, &out_used);
        if (pr < 0) {
            heatshrink_encoder_free(hse);
            return -1;
        }
        produced += out_used;
        if (pr == HSER_POLL_EMPTY) {
            fr = heatshrink_encoder_finish(hse);
            if (fr == HSER_FINISH_MORE) continue;
            break;
        }
    }

    heatshrink_encoder_free(hse);

    if (produced >= inlen) {
        /* Compressed output is bigger than input: not worth using. */
        return -1;
    }

    *outlen = produced;
    return 0;
}

int hs_decompress_wrapper(const uint8_t* in, size_t inlen,
                          uint8_t* out, size_t outcap, size_t* produced_out) {
    if (!in || !out || !produced_out) return -1;
    if (inlen < 1) return -1;

    const int window_sz2 = in[0] & 0x0F;
    const int lookahead_sz2 = (in[0] >> 4) & 0x0F;
    if (window_sz2 < HEATSHRINK_MIN_WINDOW_BITS ||
        window_sz2 > HEATSHRINK_MAX_WINDOW_BITS) return -1;
    if (lookahead_sz2 < HEATSHRINK_MIN_LOOKAHEAD_BITS) return -1;

    heatshrink_decoder* hsd = heatshrink_decoder_alloc(HS_INBUF, window_sz2, lookahead_sz2);
    if (!hsd) return -1;

    size_t produced = 0;
    size_t sunk = 1;
    /* Safety iteration cap to prevent runaway loops from corrupt data. */
    const unsigned long MAX_ITER = 1000000UL;
    unsigned long iter = 0;
    while (sunk < inlen) {
        if (++iter > MAX_ITER) { heatshrink_decoder_free(hsd); return -1; }
        size_t in_sunk = 0;
        HSD_sink_res sr = heatshrink_decoder_sink(hsd, (uint8_t*)(in + sunk),
                                                   inlen - sunk, &in_sunk);
        if (sr < 0) {
            heatshrink_decoder_free(hsd);
            return -1;
        }
        if (sr == HSDR_SINK_FULL) {
            /* Internal input buffer is full. Poll to drain state, then retry. */
            size_t out_used = 0;
            HSD_poll_res pr = heatshrink_decoder_poll(hsd, out + produced,
                                                     outcap - produced, &out_used);
            if (pr < 0) { heatshrink_decoder_free(hsd); return -1; }
            produced += out_used;
            if (pr == HSDR_POLL_MORE) {
                /* Output buffer full and decoder needs to write more.
                 * If we already produced exactly outcap bytes, that is the
                 * expected hs_orig from the caller -- treat as success. */
                if (produced >= outcap) { heatshrink_decoder_free(hsd); *produced_out = produced; return 0; }
                continue;
            }
            /* POLL_EMPTY: no progress possible, bail out. */
            heatshrink_decoder_free(hsd); return -1;
        }
        sunk += in_sunk;

        HSD_poll_res pr;
        do {
            if (++iter > MAX_ITER) { heatshrink_decoder_free(hsd); return -1; }
            size_t out_used = 0;
            pr = heatshrink_decoder_poll(hsd, out + produced,
                                         outcap - produced, &out_used);
            if (pr < 0) {
                heatshrink_decoder_free(hsd);
                return -1;
            }
            produced += out_used;
            if (pr == HSDR_POLL_MORE && produced >= outcap) {
                /* Buffer full and decoder wants more: success if produced matches
                 * the caller's expected size, else error. The check below at
                 * call site enforces produced == hs_orig. */
                heatshrink_decoder_free(hsd);
                *produced_out = produced;
                return 0;
            }
        } while (pr == HSDR_POLL_MORE);
    }

    HSD_finish_res fr = heatshrink_decoder_finish(hsd);
    while (fr == HSDR_FINISH_MORE) {
        if (++iter > MAX_ITER) { heatshrink_decoder_free(hsd); return -1; }
        size_t out_used = 0;
        HSD_poll_res pr = heatshrink_decoder_poll(hsd, out + produced,
                                                  outcap - produced, &out_used);
        if (pr < 0) {
            heatshrink_decoder_free(hsd);
            return -1;
        }
        produced += out_used;
        if (pr == HSDR_POLL_MORE && produced >= outcap) {
            heatshrink_decoder_free(hsd);
            *produced_out = produced;
            return 0;
        }
        if (pr == HSDR_POLL_EMPTY) {
            fr = heatshrink_decoder_finish(hsd);
            if (fr == HSDR_FINISH_MORE) continue;
            break;
        }
    }

    heatshrink_decoder_free(hsd);

    *produced_out = produced;
    return 0;
}
