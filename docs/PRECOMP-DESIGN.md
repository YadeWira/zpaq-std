# `-pc` Stream-Recompression Precompressor — Design

Status: **DESIGN / not implemented**. Author note: this is the planning artifact
requested before any code is written. Line numbers are as-of the current `main`
(commit `62fae20`) and must be re-confirmed during implementation.

---

## 1. Goal

Add a `-pc` (pre-compressor) stage that applies a **reversible, bit-exact
transform** to file content *before* it enters zpaq's fragmentation/dedup/compression
pipeline, so that already-compressed embedded data (deflate/zlib/gzip inside ZIP,
PDF, PNG, `.docx`, `.jar`, `.apk`, …) is **decompressed to its raw form**, stored
raw (and thus far more compressible by zpaq or `-ma`), and **re-encoded
byte-identically** on extraction.

This is the `precomp` model. It is *not* a compressor — by itself it usually
**expands** data; the win comes from the downstream compressor seeing the raw
bytes instead of an opaque high-entropy blob.

`-pc` and `-ma` **compose**: `-pc -ma:zstd` = recompress streams, then zstd the
result.

---

## 2. Why `-pc` cannot reuse the `-ma` hook

`-ma` intercepts at the **block** level. A block (`sb` StringBuffer, built around
`zpaq-std.cpp:101302`) is a concatenation of several **content-defined fragments**;
`-ma` compresses the whole block with an external codec and tags it with a comment
marker `zpaqstd-ma:<algo>:<level>:<origSize>` (compress side ~`101319`+, reverse
side ~`58999`+).

A deflate stream embedded in a file:
- **spans many fragments** (fragments are cut by a rolling hash, not by stream
  boundaries), and
- fragments are **deduplicated independently** and shared across files.

Therefore stream recompression **must** operate on **whole-file content, before
fragmentation** — exactly where `precomp` operates. The `-ma` block hook is the
wrong layer.

---

## 3. The two architectural constraints discovered

### 3.1 Ingest is *streaming*, but precomp needs the *whole* stream

`Jidac::add()` (`~100118`) reads each file in `g_ioBUFSIZE` chunks via
`fread(buf,…,in)` (`~100981`), updates the per-file hash with
`updatehash(&p,buf,buflen)` (`~101011`), and cuts fragments with a rolling hash
(`~101073–101171`) — all **buffer-by-buffer**. The file is **never** held whole in
memory.

preflate needs random access to a complete deflate stream to analyze and verify
it. So `-pc` must **buffer** at least each candidate stream (in practice, the whole
file) before transforming.

**Approach:** a per-file **pre-pass**. Before (or instead of) the streaming read,
read the file once, run the precompressor to produce the transformed **PCF**
content, then feed *that* into the existing pipeline. zpaq-std already has a
**memfile / ramfile** mechanism (`flagmemfile`, `thefranzfs.ramread`,
`DT::pramfile`) — the transformed content can be presented as a memfile so the rest
of `add()` is unchanged. (Fallback: a temp file opened as `in`.)

### 3.2 Extract writes *per-fragment with seeks*, but reverse needs the *whole* file

`decompressThread()` (`~58905`) decompresses a block into `StringBuffer out`,
reverses `-ma` codecs (`~59159–59372`), verifies **per-fragment SHA-1**
(`~59382–59410`), then writes fragments to disk with `fseeko`+`myfwrite`
(`~59771–59772`). A file's fragments may come from **multiple blocks decompressed
by multiple threads**. There is **no point where the full reassembled file sits in
one buffer**.

A whole-file reverse transform therefore needs the file's complete (transformed)
content buffered before re-encoding. **The reverse hook is at the per-file
reassembly/write boundary, NOT the block boundary `~59373`** (that block buffer
mixes fragments from several files — same lesson as §2).

---

## 3bis. DECISION (2026-06-08): store BOTH hashes

For `-pc` files we store **both**: the franz per-file `hexhash` = hash of the
**original** file (preserves franz semantics — `l`, `-test`, external compare all
behave normally), while the integrity of the stored **transformed (PCF)** stream is
covered by the **per-fragment SHA-1s** (already automatic). No new metadata field is
needed: `hexhash` is the existing field (just set to the original's value in the
pre-pass), and fragment SHA-1s already protect the stored stream.

Consequence (unavoidable in every option): the verify path must be **`-pc`-aware**,
because stored fragments are always of the transformed stream while the on-disk file
is the original. For a `-pc` file, `equal()`/`-test` compares the on-disk (or
reversed) original against `hexhash`, not against per-fragment SHA-1s.

Phase 0/1a status: ✅ preflate vendored + wired + bit-exact self-test passing in the
real binary on Linux and Windows (commits `f46d705`, `41d8713`).

## 4. Integrity model (the subtle part)

There are **two independent integrity layers**; keeping them straight is critical.

| Layer | Covers | Computed over | Checked when |
|---|---|---|---|
| **Fragment SHA-1** (`ht[].sha1`) | storage integrity | **transformed** (PCF) bytes | block decompress `~59394`, and post-extract `equal()` `~61217` |
| **Per-file hash** (`DT::hexhash`) | original-content integrity | **original** bytes | post-extract verify |

Consequences:

1. **`hexhash` must be computed on the ORIGINAL content**, not the transformed
   stream. Since the pipeline computes `hexhash` from the streamed (transformed)
   buffers via `updatehash`, the pre-pass must compute the original hash itself and
   **override** what the pipeline would store.

2. **`equal()` (`~61217`) breaks for `-pc` files.** It re-reads the *extracted file
   from disk* and compares its fragment SHA-1s against the stored `ht[].sha1` — but
   those are hashes of the **transformed** bytes, while the on-disk file is the
   **reversed original**. They will never match.
   **Resolution:** `equal()` (and the selective extract-time checksum path
   `~60000`) must detect a precompressed file and verify against `hexhash`
   (original) instead of per-fragment SHA-1, **or** skip fragment comparison for
   such files. This is a required, cross-cutting change.

3. **Verify-then-fallback (non-negotiable safety):** at compress time, after
   producing a PCF stream, immediately **re-encode and compare byte-for-byte to the
   original input**. Only transform if identical. On any mismatch (or unsupported
   stream), store the file **untransformed**. Worst case = no gain; **never
   corruption.**

---

## 5. Recording the `-pc` marker (per file)

Two candidate mechanisms (from the index survey):

- **(A) In-band PCF header** inside the file's content stream (magic + method +
  sizes + recon table). Pros: **zero archive-format change**. Cons: detection on
  extract happens after full-file reassembly (fine, that's where we reverse
  anyway); must escape original files that legitimately begin with our magic
  (handled by the compress-time verify + an escape byte).
- **(B) franz_block / franz_posix extension** — `DT` has spare bytes (V1 +48..49,
  V2 +72..75, V3 ~50 spare before the 360-byte `franz_posix` at +190). A per-file
  "precompressed=method" flag fits. Pros: explicit, no in-band escaping. Cons:
  touches the on-disk metadata format and its `decode_franz_block()`/`writefranzattr()`
  read/write paths.

**Recommendation:** **(A) in-band PCF header.** It localizes all `-pc` knowledge to
the content stream and the two hooks, and avoids archive-format/versioning churn.
The marker is recovered the moment the full file is reassembled on extract. A
1-byte "this is/ isn't PCF" escape prefix on *every* `-pc`-run file disambiguates
false positives deterministically.

---

## 6. PCF container format (draft)

A `-pc` file's stored content is a sequence of **segments**:

```
PCF := MAGIC(4) VERSION(1) SEGMENT+ 
SEGMENT :=
  | 0x00  LEN(varint)  RAW_BYTES[LEN]                       # literal passthrough
  | 0x01  RECON_LEN(varint) RECON[RECON_LEN]
          RAW_LEN(varint)   RAW_BYTES[RAW_LEN]              # recompressed deflate
```

- `MAGIC` = e.g. `"zPC1"`. A file that is *not* transformed is stored with a single
  `0x00` segment (or, cheaper, the 1-byte escape from §5 says "verbatim, no PCF").
- `RECON` = preflate reconstruction blob for that deflate stream (everything needed
  to reproduce the exact original deflate bitstream from `RAW_BYTES`).
- On reverse: walk segments; `0x00` → copy; `0x01` → `preflate_reencode(RAW,RECON)`
  → original deflate bytes. Concatenation === original file, guaranteed by the
  compress-time verify.

(Phase 1 only ever emits one segment per file; the segment list is what Phase 2
needs for embedded streams.)

---

## 7. Dependency: preflate

- **preflate** (Dirk Steinke) is the proven library for *exact* deflate
  reconstruction; it is what `precomp` uses. C++, self-contained.
- **License must be confirmed permissive (MIT/Apache/zlib) before bundling** — the
  project's whole premise is permissively-licensed, dependency-free vendoring
  (see the MIT-compliance work already done). If the license doesn't fit, `-pc`
  does not ship with preflate. **This is a Phase 0 gate.**
- Vendor under `compressors/preflate/`, wire into the `Makefile` like the other
  C++ codecs (it builds via `$(CXX)` — the `CC` cross-prefix bug is already fixed).

---

## 8. Phased plan

### Phase 0 — Foundation (low risk) — ✅ DONE
1. ✅ preflate license confirmed **Apache 2.0** (compatible). Vendored under
   `compressors/preflate/` (30 lib sources + headers + LICENSE; see `VENDORING.md`
   for provenance and the 3 portability patches). Compiles clean on native GCC and
   the MinGW cross-build. *Main-Makefile wiring deferred to Phase 1* (no caller yet —
   avoids dead weight in the shipped binary).
2. ✅ Vector API confirmed sufficient: `preflate_decode(unpacked, diff, deflate)` and
   `preflate_reencode(deflate, diff, unpacked)`. (The thin `pcf_*` wrapper is written
   in Phase 1 when wired into `add()`/`extract()`.)
3. ✅ **Self-test** `compressors/preflate/selftest.cpp`: raw DEFLATE → decode →
   reencode → assert byte-identical. Verified **BIT-EXACT on Linux native AND on a
   real Windows 10 VM** (zlib levels 1/6/9; recon diff ~13 bytes).

### Phase 1 — MVP: whole-file gzip/zlib/raw-deflate (medium risk)
1. CLI: parse `-pc` (and reserve `-pc:<method>`); global flag like `g_ma_algorithm`.
2. **Compress hook** in `add()`: per-file pre-pass — if the *entire* file is a
   gzip/zlib/deflate stream, produce PCF, **verify-then-fallback**, present PCF as
   the file content (memfile), compute & store **original** `hexhash`, mark file as
   `-pc`.
3. **Extract hook**: buffer a `-pc` file's full reassembled content, detect PCF,
   `preflate_reencode`, write original.
4. **Fix `equal()` / extract-time checksum** for `-pc` files (verify against
   original `hexhash`, not transformed fragment SHA-1s).
5. End-to-end test in-archive: `.gz`/`.zlib` corpus round-trips bit-exact; SHA-1 of
   original matches; verify path passes; untransformable files fall back cleanly.

### Phase 2 — Embedded-stream scanning (high risk, real-world payoff)
1. Scanner: walk file bytes, locate candidate deflate streams (zlib headers, gzip
   members, raw-deflate heuristics), determine stream end by trial-decode.
2. Emit multi-segment PCF (literal + recompressed interleaved).
3. Handle ZIP/PDF/PNG containers explicitly (their stream offsets are
   discoverable, far more reliable than blind scanning).
4. Per-stream verify-then-fallback; cap work; `log()` anything skipped.

### Phase 3 — optional, out of initial scope
JPEG (lepton-class), bzip2 streams, nested PCF, etc.

---

## 9. Hook summary (where the code goes)

| Concern | Function (approx line) | Change |
|---|---|---|
| CLI parse | flag table `~54393`; `-ma` parse `~55221` | add `-pc[:method]` |
| Compress pre-pass | `Jidac::add()` per-file open `~100746` | produce PCF, override `hexhash`, mark file |
| Original hash | `updatehash` `~101011` / `preparahashtobewritten` `~100017` | compute original hash in pre-pass; bypass streamed update for `-pc` files |
| Memfile feed | `flagmemfile`/`ramread` path `~100815` | route transformed content |
| Extract reverse | per-file reassembly before write `~59696` | buffer full file, detect PCF, reencode |
| Verify | `equal()` `~61217`; extract checksum `~60000` | verify original via `hexhash` for `-pc` files |
| Marker | in-band PCF header (§5/§6) | no archive-format change |

---

## 10. Risks & open questions

1. **Memory:** buffering whole files both at add and extract. Need a size cap /
   spill-to-temp for very large files (or only `-pc` files under N bytes in Phase 1).
2. **`equal()` semantics:** the verify change is cross-cutting and must not regress
   non-`-pc` archives. Needs careful gating.
3. **Dedup interaction:** dedup now keys on transformed fragments. Two identical
   originals transform identically → dedup still works. A `-pc` and a non-`-pc`
   archive of the same file won't dedup against each other (different stored bytes) —
   acceptable.
4. **preflate license** — Phase 0 gate; no fit → no ship.
5. **Threading:** extract reverse must hold per-file state across fragments arriving
   from multiple decompress threads; needs a per-file assembly buffer keyed by file.
6. **`-chunk` / `-stdout` / `-test` interactions** to be validated.

---

## 11. Testing strategy

- Phase 0: in-binary self-test, both platforms.
- Corpus round-trip (SHA-1 of every original) for: pure `.gz`, zlib blobs, a real
  ZIP, a PDF, a PNG, a `.docx`/`.jar`. Assert bit-exact and verify-path-passes.
- Negative tests: truncated/corrupt deflate, files that begin with the PCF magic,
  incompressible random files (must fall back, never corrupt).
- Cross-check on the Windows VM (the established workflow).
- Regression: full existing `-ma` × `-chunk` matrix still passes unchanged.
