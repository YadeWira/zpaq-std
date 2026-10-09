# codec_check

The checks zpaq-std runs on a compressor before bundling it, packaged so that the
codec's author can run them first. If your codec passes, the part of the review
that usually takes longest is already done.

Every buffer handed to the codec is allocated at its exact size, so AddressSanitizer
catches a read or write even one byte past the end. zpaq-std's own buffers have spare
room, which hides such bugs; two libraries bundled in zpaq-std had them.

## What it checks

For each file, block sizes from 1 byte to 16 MB, and each level:

| check | passes when |
|---|---|
| round trip | the block decompresses to the original, from exact-size buffers |
| determinism | two compressions, into buffers pre-filled differently, give the same bytes (uninitialised memory must not reach the output) |
| output cap | compressing into a buffer one byte smaller than the result fails without writing past it; so does decompressing into a buffer one byte smaller than the original |
| damage | a few hundred damaged copies of each block (flipped bits, overwritten bytes, damaged header, truncation) decompress without a memory error and without hanging (20 s per call); an error or wrong output is fine |

## How to run it

1. Copy `adapter_template.c` and fill in your codec's calls: a worst-case bound,
   compress and decompress, buffer to buffer. `examples/adapter_lz5.c` is a complete
   one.
2. Build it with your library's sources, under the sanitizers:

   ```sh
   cc -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
      -I. -Ipath/to/your/lib codec_check.c my_adapter.c path/to/your/lib/*.c \
      -o codec_check
   ```

3. Run it on a few different files (text, an executable, something already
   compressed), up to 16 MB each are read:

   ```sh
   ./codec_check text.txt program.exe photo.jpg
   ```

The last line says how many blocks were checked and how many failed; the exit code
is 0 when everything passes. A memory error stops the program with
AddressSanitizer's report, followed by a line naming the check, the level and the
block.

For the 32-bit and Windows requirements, build it once more without the sanitizers:

```sh
cc -m32 -O2 -I. -Ipath/to/your/lib codec_check.c my_adapter.c ... -o codec_check32
i686-w64-mingw32-gcc -O2 -I. -Ipath/to/your/lib codec_check.c my_adapter.c ... -o codec_check32.exe
```

On Windows the timeout is not available; a hang shows as a run that never ends.

## Settings

`-DCC_DAMAGE=N` sets the damaged copies per block (default 200; an eighth of that for
blocks of 1 MB or more). `-DCC_TIMEOUT=S` sets the seconds a single call may take
(default 20).

## What it does not check

- Speed and ratio: those are yours to choose.
- Thread safety: zpaq-std calls the codec from several threads at once, so the
  library should keep no global state, or document a one-time initialisation.
- Streams crafted to hit a specific path. Random damage finds most decoder bugs, not
  all of them; zpaq-std also fuzzes the codec inside real archives.

Proposing a codec: see [Adding a compressor](https://github.com/YadeWira/zpaq-std/wiki/Adding-a-compressor).
