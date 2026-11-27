# libzpaqstd, the checks of one build: python3 lib_test.py <library> <file> [quick]
import ctypes, os, sys, hashlib, time
L = ctypes.CDLL(sys.argv[1]); src = sys.argv[2]; quick = len(sys.argv) > 3
L.zpaqstd_run.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_char_p), ctypes.c_ssize_t, ctypes.c_ssize_t, ctypes.c_ssize_t]
L.zpaqstd_version.restype = ctypes.c_char_p
print(L.zpaqstd_version().decode())
def run(args, i, o):
    a = (ctypes.c_char_p * len(args))(*[x.encode() for x in args])
    return L.zpaqstd_run(len(args), a, os.open(i, os.O_RDONLY), os.open(o, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644), os.open('/dev/null', os.O_WRONLY))
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]
bad = 0
def check(name, ok, extra=''):
    global bad; bad += (not ok); print(f"{'ok ' if ok else 'BAD'} {name} {extra}", flush=True)
h0 = sha(src)
# levels, threads on both sides
for m in (['-m0', '-m1', '-m2', '-m3'] if quick else ['-m0', '-m1', '-m2', '-m3', '-m4', '-m5']):
    r1 = run(['c', m + '2', '-t1'], src, 'a1.z'); r8 = run(['c', m + '2', '-t8'], src, 'a8.z')
    d1 = run(['d'], 'a8.z', 'o1'); d8 = run(['d', '-t8'], 'a8.z', 'o8')
    check(f'{m}2', r1 == 0 and r8 == 0 and d1 == 0 and d8 == 0 and sha('a1.z') == sha('a8.z') and sha('o1') == h0 and sha('o8') == h0, f"{os.path.getsize('a1.z')} {sha('a1.z')}")
# the signature of a block inside the data, stored: d -t must not trust the cut
sig = bytes([0x37, 0x6b, 0x53, 0x74, 0xa0, 0x31, 0x83, 0xd3, 0x8c, 0xb2, 0x28, 0xb0, 0xd3]) + b'zPQ'
data = bytearray(open(src, 'rb').read()[:6000000])
for k in range(40): data[100000 + k * 140000: 100000 + k * 140000] = sig + bytes([2, 1]) + os.urandom(k)
open('sig.bin', 'wb').write(data)
r = run(['c', '-m00', '-t4'], 'sig.bin', 'sig.z'); d1 = run(['d'], 'sig.z', 'sig.o1'); d4 = run(['d', '-t4'], 'sig.z', 'sig.o4')
check('signature inside stored blocks', r == 0 and d1 == 0 and d4 == 0 and sha('sig.o1') == sha('sig.bin') and sha('sig.o4') == sha('sig.bin'), f"signatures in the stream: {open('sig.z','rb').read().count(sig)}")
# empty, one byte
open('e.bin', 'wb').close(); open('b1.bin', 'wb').write(b'x')
for f in ('e.bin', 'b1.bin'):
    r = run(['c'], f, 'e.z'); d1 = run(['d'], 'e.z', 'e.o1'); d4 = run(['d', '-t4'], 'e.z', 'e.o4')
    check(f'{f}', r == 0 and d1 == 0 and d4 == 0 and sha('e.o1') == sha(f) and sha('e.o4') == sha(f))
# damaged: every answer is 4, with one thread and with four, and nothing crashes
run(['c', '-m10', '-t4'], src, 'g.z'); z = open('g.z', 'rb').read(); n4 = 0; tot = 0
import random; rnd = random.Random(7)
cuts = [i for i in range(len(z)) if z.startswith(sig, i)]
blocks = [z[cuts[i]:(cuts[i + 1] if i + 1 < len(cuts) else len(z))] for i in range(len(cuts))]
variants = [z[:len(z) // 3], z[:len(z) - 1], z[:20], os.urandom(50000), b'', z[1000:],
            b''.join(blocks[:-1]), b''.join(blocks[1:]), b''.join(blocks[:3] + blocks[4:]), b''.join(blocks[:2] + [blocks[3], blocks[2]] + blocks[4:]),
            b''.join(blocks[:5]), z + blocks[0], z + z, blocks[-1] + z]
print('  blocks in the stream:', len(blocks))
for k in range(8 if quick else 40):
    b = bytearray(z); p = rnd.randrange(len(b)); b[p] ^= 1 << rnd.randrange(8); variants.append(bytes(b))
for v in variants:
    open('dm.z', 'wb').write(v)
    for t in ('-t1', '-t4'):
        rc = run(['d', t], 'dm.z', 'dm.o'); tot += 1
        good = (rc == 4) or (rc == 0 and sha('dm.o') == h0)
        n4 += good
        if not good: print('  damaged case', len(v), t, 'rc', rc)
check('damaged inputs', n4 == tot, f'{n4}/{tot} refused (or right)')
# arguments
na = 0
for a in (['q'], [], ['c', '-m9'], ['c', '-ma:sylz:1'], ['c', '-ma:zstd'], ['c', '-t0'], ['d', 'x']):
    na += run(a, 'e.bin', 'e.z') == 1
check('bad arguments', na == 7, f'{na}/7')
# -ma
ma = ['zstd:3', 'flzma2:5', 'uflzma2:5', 'lzma:6', 'lz:6', 'bzip2:9', 'bz2:9', 'deflate:6', 'lizard:17', 'lz5:5', 'lz6:7', 'lz6hc:5', 'snappy:2', 'hs:1', 'lzfse:1', 'bzip3:5', 'brotli:5', 'bsc:3', 'bsc:10', 'lzh:2', 'ppmd:6', 'kanzi:2', 'kanzi:5', 'zxc:3']
if quick: ma = ['zstd:3', 'lzma:6', 'bsc:3', 'kanzi:2', 'zxc:3', 'brotli:5']
small = 'ma.bin'; open(small, 'wb').write(open(src, 'rb').read()[:8000000]); hs = sha(small)
for c in ma:
    r1 = run(['c', '-m12', '-ma:' + c, '-t1'], small, 'a1.z'); r4 = run(['c', '-m12', '-ma:' + c, '-t4'], small, 'a4.z')
    d4 = run(['d', '-t4'], 'a4.z', 'o4')
    check('-ma:' + c, r1 == 0 and r4 == 0 and d4 == 0 and sha('a1.z') == sha('a4.z') and sha('o4') == hs, f"{os.path.getsize('a1.z')} {sha('a1.z')}")
for f in ('a1.z', 'a8.z', 'a4.z', 'o1', 'o8', 'o4', 'sig.bin', 'sig.z', 'sig.o1', 'sig.o4', 'e.bin', 'b1.bin', 'e.z', 'e.o1', 'e.o4', 'g.z', 'dm.z', 'dm.o', 'ma.bin'):
    if os.path.exists(f): os.remove(f)
print('BAD', bad)
