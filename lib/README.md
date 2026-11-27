# libzpaqstd

zpaq-std's compressor as a library: a stream in, a stream out, inside your own process. No program next
to it, nothing written to disk, no seeking: the input can be a pipe of any length.

It is the compressor only. The archiver (versions, deduplication, folders, the commands of zpaq-std) is
not in the library.

## The two functions

```c
int zpaqstd_run(int argc, char **argv, intptr_t in, intptr_t out, intptr_t err);
const char *zpaqstd_version(void);
```

C calling convention (cdecl). `in`, `out` and `err` are file descriptors on Linux and `HANDLE`s on
Windows; pipes, files and sockets all work. **`zpaqstd_run` closes the three of them before it returns.**

`argv` has no program name:

| | |
|---|---|
| `c [-m<level>[<block>]] [-ma:<codec>:<level>] [-t<threads>]` | compress `in` to `out` |
| `d [-t<threads>]` | decompress `in` to `out` |

- **`-m0` … `-m5`**: zpaq's levels (0 stores). Without it, `-m1`.
- **`<block>`**, a second number after the level: the size of a block, 2^n MiB, 0 to 11 (`-m36` = level 3,
  64 MiB). Without it: 16 MiB for `-m0` and `-m1`, 64 MiB for the others. Each block is compressed by
  itself, so smaller blocks use more threads and compress a little less.
- **`-ma:<codec>:<level>`**: one of zpaq-std's `-ma` codecs written in C or C++ (zstd, lzma, flzma2,
  uflzma2, lz, bzip2, bz2, deflate, brotli, bsc, bzip3, ppmd, kanzi, lzh, lzfse, lizard, lz5, lz6, lz6hc,
  snappy, hs, zxc). The level is always given. A block the codec does not make smaller is written with
  the `-m` level. Not here: sylz and sylzec (Rust), and lz4 and lzav.
- **`-t<n>`**: threads, 1 without it. `c` keeps a block and its output in memory for each thread; `d -t1`
  keeps one block at most, `d` with more threads a block and its data for each one.

## What it returns

| | |
|---|---|
| 0 | right |
| 1 | bad arguments |
| 2 | a read or a write failed |
| 3 | out of memory |
| 4 | damaged data |

It never ends the process and never throws. The text of an error goes to `err`, one line. With 4, part of
the output may have been written already: what was written before the damage is right, the stream as a
whole is not.

## What it writes

A standard ZPAQ stream (level 2, the streaming format): zpaq 7.15, zpaqfranz and zpaq-std read it. A
`-ma` block carries its decoder as a ZPAQL program, as in zpaq-std, so those read it too.

- **The bytes depend on the arguments and the data only**, never on the number of threads nor on the
  platform's word size beyond what zpaq-std's own `-ma` codecs do (a few of them write other bytes on 32
  bits; every build reads every stream).
- **The last block has no data.** Its comment says how many blocks and bytes came before it and the SHA-1
  of their SHA-1s: `zpaqstd-end:<blocks>:<bytes>:<hex>`. A ZPAQ block does not say it is the last one, so
  without this a stream cut between two blocks, or one whose first bytes are gone, would decode to less
  data and no error. `d` refuses a stream without it, and one with blocks missing, repeated or out of
  their order. So `d` reads what `c` wrote, not any ZPAQ stream.
- Every block has its SHA-1, checked by `d`.

## Calling it many times

It can be called any number of times in a process: no memory and no descriptors are left behind
(`lib_loop.c` checks it). Calls at the same time from several threads are not supported yet: make them
one after another.

## Building

```sh
bash lib/build_lib.sh linux64    # lib/out/linux64/libzpaqstd.so
bash lib/build_lib.sh linux86
bash lib/build_lib.sh win64      # lib/out/win64/zpaqstd.dll (mingw-w64, static runtime)
bash lib/build_lib.sh win32
```

The Windows DLLs import only system libraries (no libwinpthread, libgcc or libstdc++ DLL) and run from
Windows 7.

## Checking

```sh
python3 lib/lib_test.py lib/out/linux64/libzpaqstd.so <a file of some MB>
./lib_loop lib/out/linux64/libzpaqstd.so <file> 300 -m1 -t4
```
