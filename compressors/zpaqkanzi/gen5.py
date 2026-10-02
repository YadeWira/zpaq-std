#!/usr/bin/env python3
# Generador de ZPAQKANZI5: decodificador de kanzi 2.6.0 (bitstream 7, sin cabecera),
# niveles 5 (TEXT+UTF+BWT+RANK+ZRLT, ANS0) y 6 (TEXT+UTF+BWT+SRT+ZRLT, FPAQ), en ZPAQL.
# zpaq-std, 2026. ZPAQL no tiene subrutinas: las macros se expanden en linea.
# Traduccion de ref5.py, que a su vez lo es del C++ de kanzi.
#
# Entrada del PCOMP: orig (4 LE), nivel (1), el diccionario estatico de kanzi (DLEN
# bytes, DICT_EN_1024), el flujo headerless.
# M: la entrada desde 0; 64 ceros; dos buffers X e Y de BUFSZ (los calcula al vuelo).
# H: tablas chicas abajo, y desde HBIG el arreglo LF de BWT y las tablas de TEXT.
# Modo DEBUG: env STAGE=k -> emite la salida de la etapa k (0 entropia, 1 ZRLT, 2
# RANK/SRT, 3 BWT, 4 UTF, 5 TEXT) del primer bloque y termina.
import sys, os
out = []
def e(s): out.append(s)
STAGE = int(os.environ.get('STAGE', '-1'))
# KZROBUST=1: la version robusta ante datos danados (pre54); sin ella sale el programa congelado
ROBUST = os.environ.get('KZROBUST') == '1'
DLEN = 5487

_next = [1]
def REG(n=1):
    r = _next[0]; _next[0] += n; assert _next[0] < 256; return r

# --- registros
N, POS, LEVEL, ORIG, BSZ, BLK, PRE, MODE, SKIP, READ, NEXT = [REG() for _ in range(11)]
COPY, TCOPY, DSZ, LR = [REG() for _ in range(4)]
XB, YB, BUFSZ = [REG() for _ in range(3)]
SRC, LEN, DST, CAP = [REG() for _ in range(4)]   # transformacion actual: M[SRC..+LEN) -> M[DST..), cap
LIN, LOUT, LBUF, CIN, COUT = [REG() for _ in range(5)]   # largos logicos de kanzi (TransformSequence)
TI = REG()
PS, PD = REG(), REG()
I, J, K, II, JJ, KK, V, W, X, Y, Z = [REG() for _ in range(11)]
T1, T2, T3, T4, T5, T6, T7, T8 = [REG() for _ in range(8)]
# entropia
ST0 = REG(4)                      # ST0..ST0+3
LRG, SCALE, MASK, PB, CNTE, CNK, HN = [REG() for _ in range(7)]
LOWH, LOWL, HIGHH, HIGHL, CURH, CURL, SPH, SPL, IDX, SZB, PCTX, PROBB = [REG() for _ in range(12)]
# TEXT
HMASK, DSIZE, SDS, WORDS, ANCHOR, WRUN, CRLF, VAR, OUTLEN, DE = [REG() for _ in range(10)]

# --- H
H_ALPH = 0          # 256: alfabeto
H_F = 256           # 256: frecuencias / SRT freqs
H_CUM = 512         # 256
H_FQ = 768          # 256
H_P = 1024          # 256 (RANK p) ; FPAQ probs 4x256 en H_PR
H_Q = 1280          # 256
H_R2S = 1536        # 256
H_BKT = 1792        # 256 buckets / SRT buckets
H_END = 2048        # 256 SRT ends
H_SYM = 2304        # 256 SRT symbols
H_PR = 2560         # 1024 FPAQ probs
H_SPTR = 3584       # 1024 diccionario estatico: puntero en M
H_SLEN = 4608       # 1024 largo
H_SHASH = 5632      # 1024 hash
H_UVAL = 6656       # 32768 UTF: bytes empaquetados (LE)
H_ULEN = 39424      # 32768 largos
H_F2S = 72192       # 32768 ANS freq->simbolo
HBIG = 1 << 17      # BWT LF / TEXT: mapa y entradas
assert H_F2S + 32768 <= HBIG

def LK(v):
    v &= 0xFFFFFFFF
    if v < 256: e(f"a= {v}"); return
    bs = []
    while v: bs.append(v & 255); v >>= 8
    e(f"a= {bs[-1]}")
    for b in reversed(bs[:-1]):
        e(f"a<<= 8 a+= {b}" if b else "a<<= 8")
def SET(r, v): LK(v); e(f"r=a {r}")
def INC(r, n=1): e(f"a=r {r} a+= {n} r=a {r}")
def MOV(d, s): e(f"a=r {s} r=a {d}")
def WORD(posreg=POS):         # a = 32 bits desde el bit r posreg (arriba)
    e(f"a=r {posreg} a&= 7 b=a a=r {posreg} a>>= 3 c=a a=*c a<<= 8 c++ a+=*c a<<= 8 c++ a+=*c a<<= 8 c++ a+=*c a<<=b")
def GETK(k, dst, posreg=POS):  # k <= 24
    WORD(posreg); e(f"a>>= {32 - k} r=a {dst} a=r {posreg} a+= {k} r=a {posreg}")
def GETR(kreg, dst):           # r kreg bits (0..24)
    e(f"a=r {kreg} a> 0 ifl")
    WORD(); e(f"  r=a {T8} a= 32 b=r {kreg} a-=b b=a a=r {T8} a>>=b r=a {dst} a=r {POS} b=r {kreg} a+=b r=a {POS}")
    e(f"elsel a=0 r=a {dst} endif")
def GET32(dst):
    GETK(16, T7); GETK(16, dst); e(f"a=r {T7} a<<= 16 b=r {dst} a+=b r=a {dst}")
def HG(base, idxreg, dst):      # r dst = H[base + r idx]
    LK(base); e(f"b=r {idxreg} a+=b d=a a=*d r=a {dst}")
def HS(base, idxreg, valreg):   # H[base + r idx] = r val
    LK(base); e(f"b=r {idxreg} a+=b d=a a=r {valreg} *d=a")
def MG(basereg, idxreg, dst):   # r dst = M[r base + r idx]
    e(f"a=r {basereg} b=r {idxreg} a+=b c=a a=*c r=a {dst}")
def MS(basereg, idxreg, valreg):
    e(f"a=r {basereg} b=r {idxreg} a+=b c=a a=r {valreg} *c=a")
def FOR(reg, limreg, body):     # for reg = 0 .. limreg-1 (limreg puede ser 0)
    e(f"a=0 r=a {reg}")
    e(f"a=r {limreg} a> 0 ifl")
    e("do")
    body()
    INC(reg); e(f"a=r {reg} b=r {limreg} a<b")
    e("while")
    e("endif")
def FORK(reg, lim, body):       # for reg = 0 .. lim-1, lim constante >= 1
    e(f"a=0 r=a {reg}")
    e("do")
    body()
    INC(reg)
    if lim <= 255: e(f"a=r {reg} a< {lim}")
    else: LK(lim); e(f"b=a a=r {reg} a<b")
    e("while")
def LOG2(src, dst):             # r dst = floor(log2(r src)), r src >= 1
    e(f"a=0 r=a {dst} a=r {src} r=a {T8}")
    e(f"a=r {T8} a> 1 ifl")
    e("do")
    e(f"a=r {T8} a>>= 1 r=a {T8} a=r {dst} a++ r=a {dst} a=r {T8} a> 1")
    e("while")
    e("endif")
def VARINT(dst):                # varint 7 bits LE
    e(f"a=0 r=a {dst} r=a {T6}")
    e("do")
    GETK(8, T5)
    e(f"a=r {T5} a&= 127 b=r {T6} a<<=b b=a a=r {dst} a|=b r=a {dst}")
    e(f"a=r {T6} a+= 7 r=a {T6} a=r {T5} a> 127")
    e("while")

def ALPHABET():                 # H_ALPH[0..K) , r K
    e(f"a=0 r=a {K}")
    GETK(1, T1)
    e(f"a=r {T1} a== 0 ifl")
    GETK(1, T1)
    FORK(II, 256, lambda: HS(H_ALPH, II, II))
    SET(K, 256)
    e("elsel")
    GETK(5, T3)
    e(f"a=0 r=a {II}")
    e("do")
    GETK(8, T4)
    e(f"a=0 r=a {KK}")
    e("do")
    e(f"a=r {T4} b=r {KK} a>>=b a&= 1 a> 0 ifl")
    e(f"a=r {II} a<<= 3 b=r {KK} a+=b r=a {T1}"); HS(H_ALPH, K, T1); INC(K)
    e("endif")
    INC(KK); e(f"a=r {KK} a< 8")
    e("while")
    INC(II); e(f"a=r {T3} b=r {II} a<b")
    e("until")
    e("endif")

# ----------------------------------------------------------------- entropia
def ANS0():                     # PRE bytes -> M[XB..)
    e(f"a=r {PRE} a< 33 ifl")
    FOR(II, PRE, lambda: (GETK(8, T1), MS(XB, II, T1)))
    e("elsel")
    e(f"a=0 r=a {CNTE}")        # bytes ya decodificados
    e("do")
    e(f"a=r {PRE} b=r {CNTE} a-=b r=a {HN}"); LK(16384); e(f"b=a a=r {HN} a>b ifl a=b r=a {HN} endif")
    GETK(3, LRG); INC(LRG, 8)
    e(f"a= 1 b=r {LRG} a<<=b r=a {SCALE} a-- r=a {MASK}")
    ALPHABET()
    FORK(II, 256, lambda: (e(f"a=0 r=a {T1}"), HS(H_F, II, T1)))
    e(f"a=0 r=a {T2}")          # suma
    e(f"a=r {K} a> 63 ifl a= 8 elsel a= 6 endif r=a {T3}")   # chk
    e(f"a= 1 r=a {II}")
    e(f"a=r {II} b=r {K} a<b ifl")
    e("do")
    GETK(4, T4)                 # logMax (llr = 4 para lr 8..15)
    e(f"a=r {II} b=r {T3} a+=b r=a {JJ} b=r {K} a>b ifl a=b r=a {JJ} endif")   # fin = min(i+chk, K)
    e(f"a=r {II} r=a {KK}")
    e("do")
    e(f"a=r {T4} a== 0 ifl a= 1 r=a {T5} elsel")
    GETR(T4, T5); INC(T5)
    e("endif")
    HG(H_ALPH, KK, T6); HS(H_F, T6, T5)
    e(f"a=r {T2} b=r {T5} a+=b r=a {T2}")
    INC(KK); e(f"a=r {KK} b=r {JJ} a<b")
    e("while")
    e(f"a=r {JJ} r=a {II} b=r {K} a<b")
    e("while")
    e("endif")
    e(f"a=r {SCALE} b=r {T2} a-=b r=a {T5} a=0 r=a {T6}"); HG(H_ALPH, T6, T6); HS(H_F, T6, T5)
    e(f"a=r {K} a== 1 ifl")
    e(f"a=0 r=a {T6}"); HG(H_ALPH, T6, T6)
    FOR(II, HN, lambda: (e(f"a=r {CNTE} b=r {II} a+=b r=a {T1}"), MS(XB, T1, T6)))
    e("elsel")
    # f2s, CUM, FQ
    e(f"a=0 r=a {T2}")          # cum
    def body():
        HG(H_F, II, T3)
        e(f"a=r {T3} a> 0 ifl")
        HS(H_CUM, II, T2)
        e(f"a=r {SCALE} a-- b=a a=r {T3} a>b ifl a=b endif r=a {T4}"); HS(H_FQ, II, T4)
        e(f"a=r {T3} r=a {T4}")
        LK(H_F2S); e(f"b=r {T2} a+=b d=a")
        e("do")
        e(f"a=r {II} *d=a d++ a=r {T4} a-- r=a {T4} a> 0")
        e("while")
        e(f"a=r {T2} b=r {T3} a+=b r=a {T2}")
        e("endif")
    FORK(II, 256, body)
    VARINT(SZB)
    for k in range(4): GET32(ST0 + k)
    e(f"a=r {POS} r=a {PB}")    # puntero de bits del payload
    e(f"a=r {HN} a>>= 2 a<<= 2 r=a {T1}")   # count4
    e(f"a=0 r=a {II}")
    e(f"a=r {T1} a> 0 ifl")
    e("do")
    for k, si in ((3, 0), (2, 1), (1, 2), (0, 3)):
        st = ST0 + k
        e(f"a=r {st} b=r {MASK} a&=b b=a"); LK(H_F2S); e(f"a+=b d=a a=*d r=a {T3}")      # simbolo
        e(f"a=r {CNTE} b=r {II} a+=b a+= {si} r=a {T4}"); MS(XB, T4, T3)
        HG(H_FQ, T3, T5); HG(H_CUM, T3, T6)
        e(f"a=r {st} b=r {LRG} a>>=b b=r {T5} a*=b r=a {T5}")
        e(f"a=r {st} b=r {MASK} a&=b b=r {T5} a+=b b=r {T6} a-=b r=a {st}")
        LK(32768); e(f"b=a a=r {st} a<b ifl")
        WORD(PB); e(f"a>>= 16 r=a {T5} a=r {PB} a+= 16 r=a {PB}")
        e(f"a=r {st} a<<= 16 b=r {T5} a+=b r=a {st}")
        e("endif")
    INC(II, 4); e(f"a=r {II} b=r {T1} a<b")
    e("while")
    e("endif")
    e(f"a=r {T1} r=a {II} b=r {HN} a<b ifl")
    e("do")
    WORD(PB); e(f"a>>= 24 r=a {T3} a=r {PB} a+= 8 r=a {PB}")
    e(f"a=r {CNTE} b=r {II} a+=b r=a {T4}"); MS(XB, T4, T3)
    INC(II); e(f"a=r {II} b=r {HN} a<b")
    e("while")
    e("endif")
    e(f"a=r {SZB} a<<= 3 b=r {POS} a+=b r=a {POS}")
    e("endif")
    e(f"a=r {CNTE} b=r {HN} a+=b r=a {CNTE} b=r {PRE} a<b")
    e("while")
    e("endif")

def FPAQ():                     # PRE bytes -> M[XB..); 56 bits como (H 24, L 32)
    # probs = 32768
    e(f"a= 128 a<<= 8 r=a {T1}")
    LK(H_PR); e("d=a")
    e(f"a=0 r=a {II}")
    e("do")
    e(f"a=r {T1} *d=a d++ a=r {II} a++ r=a {II}"); LK(1024); e(f"b=a a=r {II} a<b")
    e("while")
    e(f"a=0 r=a {LOWH} r=a {LOWL}")
    LK(0xFFFFFF); e(f"r=a {HIGHH}"); LK(0xFFFFFFFF); e(f"r=a {HIGHL}")
    e(f"a=0 r=a {CNTE}")
    e("do")
    e(f"a=r {PRE} b=r {CNTE} a-=b r=a {HN}"); LK(4 << 20); e(f"b=a a=r {HN} a>b ifl a=b r=a {HN} endif")
    VARINT(SZB)
    GETK(24, CURH); GET32(CURL)
    e(f"a=r {POS} r=a {PB} a=r {SZB} a<<= 3 b=r {POS} a+=b r=a {POS}")   # el buffer: desde PB
    e(f"a=0 r=a {IDX}")
    SET(PROBB, H_PR)
    e(f"a=0 r=a {II}")
    e("do")                    # un byte por vuelta
    e(f"a= 1 r=a {PCTX} a=0 r=a {JJ}")
    e("do")                    # 8 bits
    # pr = H[PROBB + ctx]
    e(f"a=r {PROBB} b=r {PCTX} a+=b d=a a=*d r=a {T1}")
    # range = high - low  (H,L)
    e(f"a=r {HIGHL} b=r {LOWL} a-=b r=a {T2}")                 # rl
    e(f"a=r {HIGHH} b=r {LOWH} a-=b r=a {T3}")                 # rh (sin borrow)
    e(f"a=r {HIGHL} b=r {LOWL} a<b ifl a=r {T3} a-- r=a {T3} endif")
    # r8 = range >> 8 : H8 = rh>>8 (16 bits), L8 = (rh&255)<<24 | rl>>8
    e(f"a=r {T3} a>>= 8 r=a {T4}")                             # H8
    e(f"a=r {T3} a&= 255 a<<= 24 r=a {T5} a=r {T2} a>>= 8 b=r {T5} a+=b r=a {T5}")   # L8
    # t0 = (L8 & 0xFFFF) * p ; t1 = (L8 >> 16) * p + (t0 >> 16) ; t2 = H8 * p + (t1 >> 16)
    e(f"a=r {T5} a<<= 16 a>>= 16 b=r {T1} a*=b r=a {T6}")      # t0
    e(f"a=r {T5} a>>= 16 b=r {T1} a*=b b=a a=r {T6} a>>= 16 a+=b r=a {T7}")   # t1
    e(f"a=r {T4} b=r {T1} a*=b b=a a=r {T7} a>>= 16 a+=b r=a {T2}")           # t2
    # low32(P) = (t1 & 0xFFFF) << 16 | (t0 & 0xFFFF)
    e(f"a=r {T7} a<<= 16 b=a a=r {T6} a<<= 16 a>>= 16 a+=b r=a {T3}")
    # P>>8: Ph = t2 >> 8, Pl = (t2 & 255) << 24 | low32 >> 8
    e(f"a=r {T2} a>>= 8 r=a {SPH}")
    e(f"a=r {T2} a&= 255 a<<= 24 b=a a=r {T3} a>>= 8 a+=b r=a {SPL}")
    # split += low
    e(f"a=r {SPL} b=r {LOWL} a+=b r=a {SPL}")
    e(f"a=r {SPH} b=r {LOWH} a+=b r=a {SPH}")
    e(f"a=r {SPL} b=r {LOWL} a<b ifl a=r {SPH} a++ r=a {SPH} endif")
    # split >= cur ?
    e(f"a=0 r=a {T4}")
    e(f"a=r {SPH} b=r {CURH} a>b ifl a= 1 r=a {T4} elsel a=r {SPH} a==b ifl a=r {SPL} b=r {CURL} a<b ifnot a= 1 r=a {T4} endif endif endif")
    e(f"a=r {T4} a> 0 ifl")
    e(f"  a=r {SPH} r=a {HIGHH} a=r {SPL} r=a {HIGHL}")
    # p -= (p - 65536 + 64) >> 6 (piso con signo): p + ((65472 - p) + 63) / 64 ... exacto:
    #   d = 65472 - p >= 1 siempre (p <= 65535 => d >= -63). Usar: if p >= 65472: t = (p-65472)>>6 (0) else t = -ceil((65472-p)/64)
    e(f"  a=r {T1} b=a"); LK(65472); e(f"  a>b ifl a-=b a+= 63 a>>= 6 b=r {T1} a+=b elsel a=r {T1} a-=b a>>= 6 a=r {T1} endif")
    e(f"  a<<= 16 a>>= 16 r=a {T2}")
    e(f"  a=r {PROBB} b=r {PCTX} a+=b d=a a=r {T2} *d=a")
    e(f"  a=r {PCTX} a+=a a++ r=a {PCTX}")
    e("elsel")
    e(f"  a=r {SPL} a++ r=a {LOWL} a=r {SPH} r=a {LOWH} a=r {LOWL} a== 0 ifl a=r {LOWH} a++ r=a {LOWH} endif")
    e(f"  a=r {T1} a>>= 6 b=a a=r {T1} a-=b r=a {T2}")
    e(f"  a=r {PROBB} b=r {PCTX} a+=b d=a a=r {T2} *d=a")
    e(f"  a=r {PCTX} a+=a r=a {PCTX}")
    e("endif")
    # (low ^ high) >> 24 == 0  <=> LOWH == HIGHH y los 8 bits altos de L iguales
    e(f"a=r {LOWH} b=r {HIGHH} a==b ifl a=r {LOWL} a>>= 24 b=a a=r {HIGHL} a>>= 24 a==b ifl")
    e(f"  a=r {LOWL} a<<= 8 a>>= 8 r=a {LOWH} a=0 r=a {LOWL}")
    e(f"  a=r {HIGHL} a<<= 8 a>>= 8 r=a {HIGHH}"); LK(0xFFFFFFFF); e(f"  r=a {HIGHL}")
    e(f"  a=r {CURL} a<<= 8 a>>= 8 r=a {CURH}")
    e(f"  a=r {IDX} a+= 4 b=r {SZB} a>b ifl")
    e(f"    a=0 r=a {CURL} a=r {SZB} a++ r=a {IDX}")
    e("  elsel")
    # 32 bits desde un bit no alineado: WORD solo sirve para 24 -> dos lecturas de 16
    e(f"    a=r {IDX} a<<= 3 b=r {PB} a+=b r=a {T5}"); WORD(T5); e(f"    a>>= 16 a<<= 16 r=a {CURL} a=r {T5} a+= 16 r=a {T5}")
    WORD(T5); e(f"    a>>= 16 b=r {CURL} a+=b r=a {CURL} a=r {IDX} a+= 4 r=a {IDX}")
    e("  endif")
    e("endif endif")
    INC(JJ); e(f"a=r {JJ} a< 8")
    e("while")
    e(f"a=r {PCTX} a&= 255 r=a {T1} a=r {CNTE} b=r {II} a+=b r=a {T2}"); MS(XB, T2, T1)
    if os.environ.get('FPAQDBG'):
        for rg in (T1, LOWH, LOWL, HIGHH, HIGHL, CURH, CURL, IDX):
            for sh in (24, 16, 8, 0): e(f"a=r {rg} a>>= {sh} out")
    e(f"a=r {T1} a>>= 6 a<<= 8 b=a"); LK(H_PR); e(f"a+=b r=a {PROBB}")
    INC(II); e(f"a=r {II} b=r {HN} a<b")
    e("while")
    e(f"a=r {CNTE} b=r {HN} a+=b r=a {CNTE} b=r {PRE} a<b")
    e("while")

# ----------------------------------------------------------------- transformaciones
def ZRLT():                     # M[SRC..+LEN) -> M[DST..), LEN = salida; CAP
    e(f"a=0 r=a {I} r=a {J} r=a {V} r=a {W}")            # I si, J di, V run, W fin
    e("do")
    MG(SRC, I, X)
    e(f"a=r {X} a< 2 ifl")
    e(f"  a= 1 r=a {V}")
    e("  do")
    e(f"    a=r {V} a+=a b=r {X} a+=b r=a {V}"); INC(I)
    e(f"    a=r {I} b=r {LEN} a<b ifl"); MG(SRC, I, X); e(f"    a=r {X} a< 2 elsel a= 1 r=a {W} a=0 endif")
    e("  while")
    e(f"  a=r {W} a== 0 ifl")
    e(f"    a=r {V} a-- r=a {V} a> 0 ifl")
    e(f"      a=r {CAP} b=r {J} a-=b b=a a=r {V} a<b ifnot a= 1 r=a {W} elsel")
    e("        do")
    e(f"          a=r {DST} b=r {J} a+=b c=a a=0 *c=a"); INC(J)
    e(f"          a=r {V} a-- r=a {V} a> 0")
    e("        while")
    e(f"        a= 2 r=a {W}")     # 2 = continuar
    e("      endif")
    e("    endif")
    e("  endif")
    e("endif")
    e(f"a=r {W} a== 0 ifl")
    e(f"  a=r {X} a== 255 ifl")
    INC(I); MG(SRC, I, Y); e(f"    a=r {Y} a+= 254 a&= 255 r=a {Y}")
    e("  elsel")
    e(f"    a=r {X} a-- r=a {Y}")
    e("  endif")
    MS(DST, J, Y); INC(I); INC(J)
    e(f"  a=r {I} b=r {LEN} a<b ifnot a= 1 r=a {W} endif")
    e(f"  a=r {J} b=r {CAP} a<b ifnot a= 1 r=a {W} endif")
    e("endif")
    e(f"a=r {W} a== 2 ifl a=0 r=a {W} endif")
    e(f"a=r {W} a== 0")
    e("while")
    # final: run pendiente
    e(f"a=r {V} a> 0 ifl")
    e(f"  a=r {V} a-- r=a {V} a> 0 ifl")
    e("    do")
    e(f"      a=r {DST} b=r {J} a+=b c=a a=0 *c=a"); INC(J)
    e(f"      a=r {V} a-- r=a {V} a> 0")
    e("    while")
    e("  endif")
    e("endif")
    e(f"a=r {J} r=a {LEN}")

def RANK():
    FORK(II, 256, lambda: (e(f"a=0 r=a {T1}"), HS(H_P, II, T1), HS(H_Q, II, T1), HS(H_R2S, II, II)))
    def body():
        MG(SRC, I, X)                         # r
        HG(H_R2S, X, Y)                       # c
        MS(DST, I, Y)
        HG(H_P, Y, T2); e(f"a=r {I} b=r {T2} a+=b a>>= 1 r=a {Z}")   # qc
        HS(H_P, Y, I); HS(H_Q, Y, Z)
        e(f"a=r {X} a> 0 ifl")
        e("do")
        e(f"a=r {X} a-- r=a {T3}"); HG(H_R2S, T3, T4); HG(H_Q, T4, T5)
        e(f"a=r {T5} b=r {Z} a>b ifl a=0 elsel")
        HS(H_R2S, X, T4); e(f"a=r {X} a-- r=a {X} a= 1")
        e("endif")
        e(f"a> 0 ifl a=r {X} a> 0 endif")
        e("while")
        e("endif")
        HS(H_R2S, X, Y)
    FOR(I, LEN, body)

def SRT():
    # cabecera: 256 varints
    e(f"a=0 r=a {I}")
    def hdr():
        e(f"a=0 r=a {T1} r=a {T2}")
        e("do")
        MG(SRC, I, T3); INC(I)
        e(f"a=r {T3} a&= 127 b=r {T2} a<<=b b=a a=r {T1} a|=b r=a {T1} a=r {T2} a+= 7 r=a {T2} a=r {T3} a> 127")
        e("while")
        HS(H_F, II, T1)
    FORK(II, 256, hdr)
    e(f"a=r {LEN} b=r {I} a-=b r=a {LEN} a=r {SRC} b=r {I} a+=b r=a {SRC}")     # datos
    # simbolos: orden por (-freq, sym), seleccion
    e(f"a=0 r=a {K}")
    FORK(II, 256, lambda: (HG(H_F, II, T1), e(f"a=r {T1} a> 0 ifl"), HS(H_SYM, K, II), INC(K), e("endif")))
    # orden por insercion estable (freq descendente): los simbolos ya estan por valor ascendente
    e(f"a= 1 r=a {II}")
    e(f"a=r {II} b=r {K} a<b ifl")
    e("do")
    HG(H_SYM, II, T1); HG(H_F, T1, T2)          # t, f[t]
    e(f"a=r {II} r=a {JJ}")
    e("do")
    e(f"a=r {JJ} a> 0 ifl")
    e(f"  a=r {JJ} a-- r=a {T3}"); HG(H_SYM, T3, T4); HG(H_F, T4, T5)
    e(f"  a=r {T5} b=r {T2} a<b ifl")
    HS(H_SYM, JJ, T4); e(f"    a=r {JJ} a-- r=a {JJ} a= 1")
    e("  elsel a=0 endif")
    e("elsel a=0 endif")
    e("a> 0")
    e("while")
    HS(H_SYM, JJ, T1)
    INC(II); e(f"a=r {II} b=r {K} a<b")
    e("while")
    e("endif")
    # buckets
    e(f"a=0 r=a {T1}")       # bucketPos
    def bk():
        HG(H_SYM, II, T2)
        MG(SRC, T1, T3); HS(H_R2S, T3, T2)
        e(f"a=r {T1} a++ r=a {T4}"); HS(H_BKT, T2, T4)
        HG(H_F, T2, T4); e(f"a=r {T1} b=r {T4} a+=b r=a {T1}"); HS(H_END, T2, T1)
    FOR(II, K, bk)
    e(f"a=0 r=a {T1}"); HG(H_R2S, T1, Y)        # c
    e(f"a=r {K} r=a {Z}")                        # nb
    def dec():
        MS(DST, I, Y)
        HG(H_BKT, Y, T2); HG(H_END, Y, T3)
        e(f"a=r {T2} b=r {T3} a<b ifl")
        MG(SRC, T2, T4); INC(T2); HS(H_BKT, Y, T2)
        e(f"  a=r {T4} a> 0 ifl")
        e(f"    a=0 r=a {T5}")
        e("    do")
        e(f"      a=r {T5} a++ r=a {T6}"); HG(H_R2S, T6, T7); HS(H_R2S, T5, T7)
        e(f"      a=r {T6} r=a {T5} b=r {T4} a<b")
        e("    while")
        HS(H_R2S, T4, Y); e(f"    a=0 r=a {T5}"); HG(H_R2S, T5, Y)
        e("  endif")
        e("elsel")
        e(f"  a=r {Z} a> 1 ifl")
        e(f"    a=r {Z} a-- r=a {Z} a=0 r=a {T5}")
        e("    do")
        e(f"      a=r {T5} a++ r=a {T6}"); HG(H_R2S, T6, T7); HS(H_R2S, T5, T7)
        e(f"      a=r {T6} r=a {T5} b=r {Z} a<b")
        e("    while")
        e(f"    a=0 r=a {T5}"); HG(H_R2S, T5, Y)
        e("  endif")
        e("endif")
    FOR(I, LEN, dec)

def BWT():                      # LF en H[HBIG..)
    e(f"a=0 r=a {T1}"); MG(SRC, T1, T1)        # modo
    e(f"a=r {T1} a>>= 2 a&= 7 r=a {T2} a= 1 b=r {T2} a<<=b r=a {T2}")   # chunks
    e(f"a=r {T1} a&= 3 a++ r=a {T3}")           # pis
    e(f"a=0 r=a {T4} a= 1 r=a {I}")             # primer indice primario
    def pib(): MG(SRC, I, T5); e(f"a=r {T4} a<<= 8 b=r {T5} a+=b r=a {T4}"); INC(I)
    FOR(II, T3, pib)
    INC(T4)                                     # pIdx = v + 1
    e(f"a=r {T2} b=r {T3} a*=b a++ r=a {T5}")   # header size
    e(f"a=r {SRC} b=r {T5} a+=b r=a {SRC} a=r {LEN} b=r {T5} a-=b r=a {LEN}")
    e(f"a=r {LEN} a== 1 ifl")
    e(f"  a=0 r=a {I}"); MG(SRC, I, T1); MS(DST, I, T1)
    e("elsel")
    FORK(II, 256, lambda: (e(f"a=0 r=a {T1}"), HS(H_BKT, II, T1)))
    FOR(I, LEN, lambda: (MG(SRC, I, T1), HG(H_BKT, T1, T2), INC(T2), HS(H_BKT, T1, T2)))
    e(f"a=0 r=a {T2}")
    FORK(II, 256, lambda: (HG(H_BKT, II, T1), HS(H_BKT, II, T2), e(f"a=r {T2} b=r {T1} a+=b r=a {T2}")))
    def lf():
        MG(SRC, I, T1)
        e(f"a=r {I} a== 0 ifl a=r {T1} elsel a=r {I} b=r {T4} a<b ifl a=r {I} a-- elsel a=r {I} endif a<<= 8 b=r {T1} a+=b endif r=a {T3}")
        HG(H_BKT, T1, T2); e(f"a=r {T2} b=a"); LK(HBIG); e(f"a+=b d=a a=r {T3} *d=a")
        INC(T2); HS(H_BKT, T1, T2)
    FOR(I, LEN, lf)
    e(f"a=r {T4} a-- r=a {T1}")                 # t
    def walk():
        e(f"a=r {T1} b=a"); LK(HBIG); e(f"a+=b d=a a=*d r=a {T2}")
        e(f"a=r {T2} a&= 255 r=a {T3}"); MS(DST, I, T3)
        e(f"a=r {T2} a>>= 8 r=a {T1}")
    FOR(I, LEN, walk)
    e("endif")

def UTF():
    e(f"a=0 r=a {T1}"); MG(SRC, T1, T1); e(f"a=r {T1} a&= 3 r=a {T2}")             # start
    e(f"a= 1 r=a {T1}"); MG(SRC, T1, T1); e(f"a=r {T1} a&= 3 r=a {T3}")            # adjust
    e(f"a= 2 r=a {T1}"); MG(SRC, T1, T4); e(f"a= 3 r=a {T1}"); MG(SRC, T1, T5)
    e(f"a=r {T4} a<<= 8 b=r {T5} a+=b r=a {K}")                                     # n
    e(f"a= 4 r=a {I}")
    def tab():
        MG(SRC, I, T4); INC(I); MG(SRC, I, T5); INC(I); MG(SRC, I, T6); INC(I)
        e(f"a=r {T4} a<<= 8 b=r {T5} a+=b a<<= 8 b=r {T6} a+=b r=a {T4}")          # s
        e(f"a=r {T4} a>>= 19 r=a {T5}")
        e(f"a=r {T5} a== 0 ifl a=r {T4} a&= 255 r=a {T6} a= 1 r=a {T7} elsel")
        e(f"a=r {T5} a== 1 ifl a=r {T4} a&= 255 a<<= 8 r=a {T6} a=r {T4} a>>= 8 a&= 255 b=r {T6} a+=b r=a {T6} a= 2 r=a {T7} elsel")
        e(f"a=r {T5} a== 2 ifl")
        e(f"  a=r {T4} a&= 63 a|= 128 a<<= 8 r=a {T6} a=r {T4} a>>= 6 a&= 63 a|= 128 b=r {T6} a+=b a<<= 8 r=a {T6}")
        e(f"  a=r {T4} a>>= 12 a&= 15 a|= 224 b=r {T6} a+=b r=a {T6} a= 3 r=a {T7}")
        e("elsel")
        e(f"  a=r {T4} a&= 63 a|= 128 a<<= 8 r=a {T6} a=r {T4} a>>= 6 a&= 63 a|= 128 b=r {T6} a+=b a<<= 8 r=a {T6}")
        e(f"  a=r {T4} a>>= 12 a&= 63 a|= 128 b=r {T6} a+=b a<<= 8 r=a {T6}")
        e(f"  a=r {T4} a>>= 18 a&= 7 a|= 240 b=r {T6} a+=b r=a {T6} a= 4 r=a {T7}")
        e("endif endif endif")
        HS(H_UVAL, II, T6); HS(H_ULEN, II, T7)
    FOR(II, K, tab)
    e(f"a=r {LEN} a-= 4 b=r {T3} a+=b r=a {T5}")                                   # srcEnd
    e(f"a=0 r=a {J}")
    FOR(II, T2, lambda: (MG(SRC, I, T4), MS(DST, J, T4), INC(I), INC(J)))
    def emit(areg):
        HG(H_UVAL, areg, T6); HG(H_ULEN, areg, T7)
        if ROBUST: e(f"a=r {T7} a> 0 ifl")      # indice danado fuera de la tabla: largo 0
        e("do")
        e(f"a=r {T6} a&= 255 r=a {T4}"); MS(DST, J, T4); INC(J)
        e(f"a=r {T6} a>>= 8 r=a {T6} a=r {T7} a-- r=a {T7} a> 0")
        e("while")
        if ROBUST: e("endif")
    e(f"a=r {I} b=r {T5} a<b ifl")
    e("do")
    MG(SRC, I, T1); INC(I)
    e(f"a=r {K} a> 128 ifl a=r {T1} a> 127 ifl"); MG(SRC, I, T4); INC(I); e(f"a=r {T4} a<<= 7 b=r {T1} a+=b a-= 128 r=a {T1} endif endif")
    emit(T1)
    e(f"a=r {I} b=r {T5} a<b")
    e("while")
    e("endif")
    e(f"a=r {CAP} a-= 4 b=r {T3} a+=b b=r {J} a>b ifl")
    e(f"a= 4 b=r {T3} a-=b r=a {T2}")
    FOR(II, T2, lambda: (MG(SRC, I, T4), MS(DST, J, T4), INC(I), INC(J)))
    e("endif")
    e(f"a=r {J} r=a {LEN}")

# --- TEXT: entradas en H: ENT_PTR, ENT_HASH, ENT_DATA (3 x 2^19); mapa en MAPB (slot -> idx+1)
ENT_PTR = HBIG
ENT_HASH = HBIG + (1 << 19)
ENT_DATA = HBIG + 2 * (1 << 19)
MAPB = HBIG + 3 * (1 << 19)
NS = 1024
def EG(base, idxreg, dst):
    HG(base, idxreg, dst)
def ES(base, idxreg, valreg):
    HS(base, idxreg, valreg)
H_CT = HBIG - 256
def CTYPE(creg, dst):           # 1 delimitador, 0 letra, 2 otro (-1): tabla H_CT
    HG(H_CT, creg, dst)
def CTYPE_OLD(creg, dst):
    e(f"a=r {creg} a> 31 ifl a< 48 ifl a= 1 elsel a=r {creg} a> 57 ifl a< 64 ifl a= 1 elsel a=r {creg} a> 64 ifl a< 91 ifl a=0 elsel a=r {creg} a> 96 ifl a< 123 ifl a=0 elsel a= 2 endif elsel a= 2 endif endif elsel a= 2 endif endif elsel a= 2 endif endif elsel a= 2 endif")
    e(f"r=a {dst}")
    # especiales: \n \r \t _ | { } [ ] -> 1
    e(f"a=r {creg} a== 10 ifl a= 1 r=a {dst} endif a=r {creg} a== 13 ifl a= 1 r=a {dst} endif a=r {creg} a== 9 ifl a= 1 r=a {dst} endif")
    e(f"a=r {creg} a== 95 ifl a= 1 r=a {dst} endif a=r {creg} a== 124 ifl a= 1 r=a {dst} endif a=r {creg} a== 123 ifl a= 1 r=a {dst} endif")
    e(f"a=r {creg} a== 125 ifl a= 1 r=a {dst} endif a=r {creg} a== 91 ifl a= 1 r=a {dst} endif a=r {creg} a== 93 ifl a= 1 r=a {dst} endif")
def HASHSTEP(hreg, breg):        # h = h*HASH1 ^ b*HASH2
    LK(0x7FEB352D); e(f"b=r {hreg} a*=b r=a {hreg}")
    LK(0x846CA68B); e(f"b=r {breg} a*=b b=r {hreg} a^=b r=a {hreg}")

def STATICDICT():                # una vez: palabras de M[5..5+DLEN) a H_SPTR/SLEN/SHASH, en minusculas
    e(f"a=0 r=a {K} r=a {T1}")   # K palabras, T1 ancla (relativa)
    e("a= 5 r=a {} ".format(T2).strip())      # T2 = base M del diccionario
    SET(T3, DLEN)                              # el NUL del literal C nunca es mayuscula
    def body():
        LK(1024); e(f"b=a a=r {K} a<b ifl")
        e(f"a=r {T2} b=r {II} a+=b c=a a=*c r=a {T4}")
        e(f"a=r {T4} a> 64 ifl a< 91 ifl")
        e(f"  a=r {II} b=r {T1} a>b ifl")
        e(f"    a=r {T2} b=r {T1} a+=b r=a {T5}"); HS(H_SPTR, K, T5)
        e(f"    a=r {II} b=r {T1} a-=b r=a {T5}"); HS(H_SLEN, K, T5)
        INC(K); e(f"    a=r {II} r=a {T1}")
        e("  endif")
        e(f"  a=r {T2} b=r {II} a+=b c=a a=*c a^= 32 *c=a")
        e("endif endif")
        e("endif")
    FOR(II, T3, body)
    LK(1024); e(f"b=a a=r {K} a<b ifl")
    e(f"a=r {T2} b=r {T1} a+=b r=a {T5}"); HS(H_SPTR, K, T5)
    e(f"a=r {T3} b=r {T1} a-=b r=a {T5}"); HS(H_SLEN, K, T5); INC(K)
    e("endif")
    # hashes
    def hs():
        HG(H_SPTR, II, T5); HG(H_SLEN, II, T6)
        SET(T4, 0x7FEB352D)
        if ROBUST: e(f"a=r {T6} a> 0 ifl")      # diccionario danado: menos de 1024 palabras
        e("do")
        e(f"a=r {T5} c=a a=*c r=a {T7}"); HASHSTEP(T4, T7); INC(T5)
        e(f"a=r {T6} a-- r=a {T6} a> 0")
        e("while")
        if ROBUST: e("endif")
        HS(H_SHASH, II, T4)
    FORK(II, 1024, hs)

def TEXT():
    # VAR: 1 o 2 (bit 0x10 del primer byte)
    e(f"a=0 r=a {T1}"); MG(SRC, T1, T1)
    e(f"a=r {T1} a&= 16 a> 0 ifl a= 2 elsel a= 1 endif r=a {VAR}")
    e(f"a=r {T1} a&= 64 r=a {CRLF}")
    # hmask
    e(f"a=r {VAR} a== 1 ifl a=r {BSZ} a>>= 3 elsel a=r {BSZ} a>>= 5 endif r=a {T2}")
    LOG2(T2, T3)
    e(f"a=r {VAR} a== 1 ifl a=r {T3} a> 26 ifl a= 26 r=a {T3} endif elsel a=r {T3} a> 24 ifl a= 24 r=a {T3} endif endif")
    e(f"a=r {T3} a< 13 ifl a= 13 r=a {T3} endif")
    e(f"a= 1 b=r {T3} a<<=b a-- r=a {HMASK}")
    # dictSize
    e(f"a= 13 r=a {T3} a=r {OUTLEN}"); LK(1024); e(f"b=a a=r {OUTLEN} a<b ifnot a=r {OUTLEN} a>>= 7 r=a {T2}")
    LOG2(T2, T3)
    e(f"a=r {T3} a> 18 ifl a= 18 r=a {T3} endif a=r {T3} a< 13 ifl a= 13 r=a {T3} endif")
    e("endif")
    e(f"a= 1 b=r {T3} a<<=b r=a {DSIZE}")
    e(f"a=r {VAR} a== 1 ifl"); SET(SDS, NS + 2); e("elsel"); SET(SDS, NS); e("endif")
    e(f"a=r {DSIZE} b=r {SDS} a<b ifl a=b r=a {DSIZE} endif")
    # limpiar mapa
    e(f"a=r {HMASK} a++ r=a {T2}")
    LK(MAPB); e("d=a")
    e(f"a=0 r=a {II}")
    e("do")
    e(f"a=0 *d=a d++ a=r {II} a++ r=a {II} b=r {T2} a<b")
    e("while")
    # entradas estaticas
    def st():
        HG(H_SPTR, II, T4); ES(ENT_PTR, II, T4)
        HG(H_SHASH, II, T4); ES(ENT_HASH, II, T4)
        HG(H_SLEN, II, T4); e(f"a=r {T4} a<<= 24 b=r {II} a+=b r=a {T4}"); ES(ENT_DATA, II, T4)
    FORK(II, NS, st)
    e(f"a=r {VAR} a== 1 ifl")
    # escapes 0x0E / 0x0F en M: usar 2 bytes de la cola de M? se guardan en M[N+40], M[N+41]
    e(f"  a=r {N} a+= 40 c=a a= 14 *c=a c++ a= 15 *c=a")
    SET(II, NS); e(f"  a=r {N} a+= 40 r=a {T4}"); ES(ENT_PTR, II, T4); e(f"  a=0 r=a {T4}"); ES(ENT_HASH, II, T4)
    e(f"  a= 1 a<<= 24 b=r {II} a+=b r=a {T4}"); ES(ENT_DATA, II, T4)
    SET(II, NS + 1); e(f"  a=r {N} a+= 41 r=a {T4}"); ES(ENT_PTR, II, T4); e(f"  a=0 r=a {T4}"); ES(ENT_HASH, II, T4)
    e(f"  a= 1 a<<= 24 b=r {II} a+=b r=a {T4}"); ES(ENT_DATA, II, T4)
    e("endif")
    # mapa de las estaticas
    def mp():
        EG(ENT_HASH, II, T4); e(f"a=r {T4} b=r {HMASK} a&=b r=a {T4} a=r {II} a++ r=a {T5}"); HS(MAPB, T4, T5)
    FOR(II, SDS, mp)
    # entradas libres
    e(f"a=r {SDS} r=a {II}")
    e(f"a=r {II} b=r {DSIZE} a<b ifl")
    e("do")
    e(f"a=0 r=a {T4}"); ES(ENT_PTR, II, T4); ES(ENT_HASH, II, T4); ES(ENT_DATA, II, II)
    INC(II); e(f"a=r {II} b=r {DSIZE} a<b")
    e("while")
    e("endif")
    # decodificacion
    e(f"a= 1 r=a {I} a=0 r=a {J}")
    MG(SRC, I, T1); CTYPE(T1, T2)
    e(f"a=r {T2} a== 0 ifl a=r {I} a-- elsel a=r {I} endif r=a {ANCHOR}")
    e(f"a=r {SDS} r=a {WORDS} a=0 r=a {WRUN}")
    e(f"a=r {I} b=r {LEN} a<b ifl")
    e("do")
    MG(SRC, I, X); CTYPE(X, T2)
    e(f"a=r {T2} a== 0 ifl")
    MS(DST, J, X); INC(I); INC(J)
    e("elsel")
    # insercion de palabra
    e(f"a=r {T2} a== 1 ifl a=r {ANCHOR} a+= 3 b=a a=r {I} a>b ifl")
    e(f"  a=r {I} b=r {ANCHOR} a-=b a-- r=a {T3}")     # length
    e(f"  a=r {T3} a< 32 ifl")
    SET(T4, 0x7FEB352D)
    e(f"    a=r {ANCHOR} a++ r=a {T5}")
    e("    do")
    MG(SRC, T5, T6); HASHSTEP(T4, T6); INC(T5)
    e(f"      a=r {T5} b=r {I} a<b")
    e("    while")
    # pe1 = map[h & mask]
    e(f"    a=r {T4} b=r {HMASK} a&=b r=a {T5}"); HG(MAPB, T5, T6)      # T6 = idx+1 o 0
    e(f"    a=0 r=a {T7}")                                               # T7 = 1 si encontrada
    e(f"    a=r {T6} a> 0 ifl")
    e(f"      a=r {T6} a-- r=a {DE}"); EG(ENT_HASH, DE, T8)
    e(f"      a=r {T8} b=r {T4} a==b ifl"); EG(ENT_DATA, DE, T8); e(f"        a=r {T8} a>>= 24 b=r {T3} a==b ifl a= 1 r=a {T7} endif")
    e("      endif")
    e("    endif")
    e(f"    a=r {T7} a== 0 ifl a=r {T6} a== 0 ifl")
    e(f"      a=r {T3} a> 3 ifl a= 1 elsel"); LK(16384); e(f"      b=a a=r {WORDS} a<b ifl a= 1 elsel a=0 endif endif")
    e("      a> 0 ifl")
    EG(ENT_DATA, WORDS, T8); LK(0x7FFFF); e(f"        b=r {T8} a&=b b=r {SDS} a<b ifnotl")
    EG(ENT_HASH, WORDS, T8); e(f"          a=r {T8} b=r {HMASK} a&=b r=a {T8} a=0 r=a {DE}"); HS(MAPB, T8, DE)
    e(f"          a=r {SRC} b=r {ANCHOR} a+=b a++ r=a {T8}"); ES(ENT_PTR, WORDS, T8)
    ES(ENT_HASH, WORDS, T4)
    e(f"          a=r {T3} a<<= 24 b=r {WORDS} a+=b r=a {T8}"); ES(ENT_DATA, WORDS, T8)
    e("        endif")
    e(f"        a=r {WORDS} a++ r=a {T8}"); HS(MAPB, T5, T8)
    INC(WORDS)
    e(f"        a=r {WORDS} b=r {DSIZE} a<b ifnotl")
    LK(1 << 19); e(f"          b=a a=r {DSIZE} a<b ifl")
    # expandir: entradas nuevas y mapa reconstruido
    e(f"            a=r {DSIZE} r=a {II} a+=a r=a {T8}")
    e("            do")
    e(f"              a=0 r=a {DE}"); ES(ENT_PTR, II, DE); ES(ENT_HASH, II, DE); ES(ENT_DATA, II, II)
    INC(II); e(f"              a=r {II} b=r {T8} a<b")
    e("            while")
    e(f"            a=0 r=a {II}")
    e("            do")
    EG(ENT_HASH, II, DE); e(f"              a=r {DE} b=r {HMASK} a&=b r=a {DE} a=r {II} a++ r=a {T6}"); HS(MAPB, DE, T6)
    INC(II); e(f"              a=r {II} b=r {DSIZE} a<b")
    e("            while")
    e(f"            a=r {DSIZE} a+=a r=a {DSIZE}")
    e("          elsel")
    e(f"            a=r {SDS} r=a {WORDS}")
    e("          endif")
    e("        endif")
    e("      endif")
    e("    endif endif")
    e("  endif")
    e("endif endif")
    INC(I)
    # token
    e(f"a=0 r=a {T7}")                       # T7 = 1 si es palabra; T6 = flip; DE = idx
    e(f"a=r {VAR} a== 1 ifl")
    e(f"  a=r {X} a== 14 ifl a= 1 r=a {T7} endif a=r {X} a== 15 ifl a= 1 r=a {T7} endif")
    e(f"  a=r {T7} a> 0 ifl")
    MG(SRC, I, DE); INC(I)
    e(f"    a=r {DE} a> 127 ifl")
    MG(SRC, I, T5); INC(I)
    e(f"      a=r {T5} a> 127 ifl")
    MG(SRC, I, T8); INC(I)
    e(f"        a=r {DE} a&= 31 a<<= 14 r=a {DE} a=r {T5} a&= 127 a<<= 7 b=r {DE} a+=b b=r {T8} a+=b r=a {DE}")
    e("      elsel")
    e(f"        a=r {DE} a&= 127 a<<= 7 b=r {T5} a+=b r=a {DE}")
    e("      endif")
    e("    endif")
    e(f"    a=r {X} a== 14 ifl a= 32 elsel a=0 endif r=a {T6}")
    e("  endif")
    e("elsel")
    e(f"  a=r {X} a> 127 ifl")
    e(f"    a= 1 r=a {T7} a=0 r=a {T6}")
    e(f"    a=r {X} a== 128 ifl a= 32 r=a {T6}"); MG(SRC, I, X); INC(I); e("    endif")
    e(f"    a=r {X} a&= 127 r=a {DE} a< 64 ifl a= 1 elsel a=0 endif r=a {T5}")   # T5 = oneByte
    e(f"    a=r {DE} a> 63 ifl")
    e(f"      a=r {DE} a> 111 ifl")
    MG(SRC, I, T8); INC(I); MG(SRC, I, T3); INC(I)
    e(f"        a=r {DE} a&= 15 a<<= 8 b=r {T8} a+=b a<<= 8 b=r {T3} a+=b r=a {DE}"); LK(8255); e(f"        b=r {DE} a+=b r=a {DE}")
    e("      elsel")
    MG(SRC, I, T8); INC(I)
    e(f"        a=r {DE} a&= 31 a<<= 8 b=r {T8} a+=b a+= 63 r=a {DE}")
    e("      endif")
    e("    endif")
    e(f"    a=r {DE} b=r {T5} a-=b r=a {DE}")
    e("  endif")
    e("endif")
    e(f"a=r {T7} a> 0 ifl")
    EG(ENT_DATA, DE, T8); e(f"  a=r {T8} a>>= 24 r=a {T3}"); EG(ENT_PTR, DE, T4)
    e(f"  a=r {T3} a> 1 ifl")
    e(f"    a=r {WRUN} a> 0 ifl a= 32 r=a {T5}"); MS(DST, J, T5); INC(J); e("    endif")
    e(f"    a= 1 r=a {WRUN} a=r {I} r=a {ANCHOR}")
    e("  elsel")
    e(f"    a=0 r=a {WRUN} a=r {I} a-- r=a {ANCHOR}")
    e("  endif")
    e(f"  a=r {J} r=a {T5}")
    if ROBUST: e(f"  a=r {T3} a> 0 ifl")     # largo 0 (dato danado): no copia, como el memcpy de kanzi
    e("  do")
    e(f"    a=r {T4} c=a a=*c r=a {T8}"); MS(DST, J, T8); INC(T4); INC(J)
    e(f"    a=r {T3} a-- r=a {T3} a> 0")
    e("  while")
    if ROBUST: e("  endif")
    e(f"  a=r {DST} b=r {T5} a+=b c=a a=*c b=r {T6} a^=b *c=a")
    e("elsel")
    e(f"  a=r {VAR} a== 2 ifl a=r {X} a== 15 ifl a= 1 elsel a=0 endif elsel a=0 endif")
    e("  a> 0 ifl")
    MG(SRC, I, T8); MS(DST, J, T8); INC(I); INC(J)
    e("  elsel")
    e(f"    a=r {CRLF} a> 0 ifl a=r {X} a== 10 ifl a= 13 r=a {T8}"); MS(DST, J, T8); INC(J); e("    endif endif")
    MS(DST, J, X); INC(J)
    e("  endif")
    e(f"  a=0 r=a {WRUN} a=r {I} a-- r=a {ANCHOR}")
    e("endif")
    e("endif")
    e(f"a=r {I} b=r {LEN} a<b ifl a=r {J} b=r {OUTLEN} a<b ifl a= 1 elsel a=0 endif elsel a=0 endif")
    e("a> 0")
    e("while")
    e("endif")
    e(f"a=r {J} r=a {LEN}")

def OUTBUF():
    e(f"a=r {LEN} a> 0 ifl")
    e(f"  a=r {SRC} r=a {T1} a=r {LEN} r=a {T2}")
    e("  do")
    e(f"    a=r {T1} c=a a=*c out a=r {T1} a++ r=a {T1} a=r {T2} a-- r=a {T2} a> 0")
    e("  while")
    e("endif")

def DEBUGSTOP(k):
    if STAGE == k:
        OUTBUF(); e("halt")

# ----------------------------------------------------------------- principal
e("hcomp")
e("halt")
e("pcomp zpaqkanzi5 ;")
e("""(ZPAQKANZI5: decodificador de kanzi 2.6.0, bitstream 7 sin cabecera, niveles 5
 TEXT+UTF+BWT+RANK+ZRLT con ANS0 y 6 TEXT+UTF+BWT+SRT+ZRLT con FPAQ, en ZPAQL, para
 zpaq-std -ma:kanzi. zpaq-std, 2026. Guarda la entrada en M y decodifica al final.
 La entrada lleva el diccionario estatico de kanzi detras de la cabecera.)""")
e("a> 255 ifl")
e(f"  a=c r=a {N}")
e(f"  a=0 r=a {T1} do *c=a c++ a=r {T1} a++ r=a {T1} a< 64 while")
e(f"  a= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a {ORIG}")
e(f"  a= 4 c=a a=*c r=a {LEVEL}")
# bs = max(1024, (orig+15)&~15), min 2^30 ; blk = max(bs+512, bs + bs>>4)
e(f"  a=r {ORIG} a+= 15 a>>= 4 a<<= 4 r=a {BSZ}"); LK(1024); e(f"  b=a a=r {BSZ} a<b ifl a=b r=a {BSZ} endif")
e(f"  a=r {BSZ} a>>= 4 b=r {BSZ} a+=b r=a {BLK} a=r {BSZ} b= 0 a+= 255 a+= 255 a+= 2 b=r {BLK} a>b ifl r=a {BLK} endif")
def ct(c):
    if 0x20 <= c <= 0x2F or 0x3A <= c <= 0x3F or c in b'\n\r\t_|{}[]': return 1
    if 0x41 <= c <= 0x5A or 0x61 <= c <= 0x7A: return 0
    return 2
LK(H_CT); e("  d=a")
for c in range(256): e(f"  a= {ct(c)} *d=a d++")
STATICDICT()
SET(POS, 8 * (5 + DLEN))
e("  do")
GETK(5, LR); INC(LR, 3)
e(f"    a=r {LR} a> 24 ifl")
e(f"      a=r {LR} a-= 24 r=a {T1}"); GETR(T1, T2); GETK(24, T3)
e(f"      a=r {T2} a<<= 24 b=r {T3} a+=b r=a {READ}")
e("    elsel")
GETR(LR, READ)
e("    endif")
e(f"    a=r {READ} a> 0 ifl")
e(f"      a=r {POS} b=r {READ} a+=b r=a {NEXT}")
GETK(8, MODE)
e(f"      a=r {MODE} a&= 128 r=a {COPY} a=0 r=a {TCOPY}")
e(f"      a=r {COPY} a> 0 ifl a=r {MODE} a&= 16 a> 0 ifl a= 1 r=a {TCOPY} endif endif")
e(f"      a=r {TCOPY} a> 0 ifl a= 1 elsel a=r {COPY} a== 0 ifl a=r {MODE} a&= 16 a> 0 ifl a= 1 elsel a=0 endif elsel a=0 endif endif")
e("      a> 0 ifl")
GETK(8, SKIP)
e("      elsel")
e(f"        a=r {MODE} a<<= 4 a|= 15 a&= 255 r=a {SKIP}")
e("      endif")
e(f"      a=r {MODE} a>>= 5 a&= 3 a++ r=a {DSZ} a=0 r=a {PRE}")
e("      do")
GETK(8, T1)
e(f"        a=r {PRE} a<<= 8 b=r {T1} a+=b r=a {PRE} a=r {DSZ} a-- r=a {DSZ} a> 0")
e("      while")
GETK(8, T1)
# buffers: BUFSZ = max(blk, pre+512) + 64 ; X en N+128, Y detras
e(f"      a=r {PRE} a+= 255 a+= 255 a+= 2 b=r {BLK} a<b ifl a=b endif r=a {LIN} a+= 64 r=a {BUFSZ}")
e(f"      a=r {BLK} r=a {LOUT} a=0 r=a {LBUF}")
e(f"      a=r {N} a+= 128 r=a {XB} b=r {BUFSZ} a+=b r=a {YB}")
e(f"      a=r {COPY} a> 0 ifl a=r {TCOPY} a== 0 ifl a= 1 elsel a=0 endif elsel a=0 endif")
e("      a> 0 ifl")
e(f"        a=r {PRE} a> 0 ifl")
e("          do")
GETK(8, T1)
e(f"            a=r {T1} out a=r {PRE} a-- r=a {PRE} a> 0")
e("          while")
e("        endif")
e("      elsel")
e(f"        a=r {TCOPY} a> 0 ifl")
FOR(II, PRE, lambda: (GETK(8, T1), MS(XB, II, T1)))
e("        elsel")
e(f"          a=r {LEVEL} a== 5 ifl")
ANS0()
e("          elsel")
FPAQ()
e("          endif")
e("        endif")
e(f"        a=r {XB} r=a {SRC} r=a {PS} a=r {YB} r=a {DST} r=a {PD} a=r {PRE} r=a {LEN}")
DEBUGSTOP(0)
# CIN/COUT: 0 in, 1 out, 2 buf
e(f"        a=0 r=a {CIN} a= 1 r=a {COUT}")
for i, (stage, macro) in enumerate([(1, ZRLT), (2, None), (3, BWT), (4, UTF), (5, TEXT)]):
    ti = 4 - i                    # posicion en la cadena
    e(f"        a=r {SKIP} a&= {1 << (7 - ti)} a== 0 ifl")
    # largo logico del destino (TransformSequence)
    e(f"          a=r {COUT} a== 0 ifl a=r {LIN} elsel a=r {COUT} a== 1 ifl a=r {LOUT} elsel a=r {LBUF} endif endif r=a {CAP}")
    e(f"          a=r {CAP} b=r {LOUT} a<b ifl")
    e(f"            a=r {COUT} a< 2 ifl a= 2 r=a {COUT} endif")
    e(f"            a=r {LBUF} b=r {LOUT} a<b ifl a=b r=a {LBUF} endif")
    e(f"            a=r {LBUF} r=a {CAP}")
    e("          endif")
    e(f"          a=r {CAP} r=a {OUTLEN} a=r {PS} r=a {SRC} a=r {PD} r=a {DST}")
    if macro is None:
        e(f"          a=r {LEVEL} a== 5 ifl")
        RANK()
        e("          elsel")
        SRT()
        e("          endif")
    else:
        macro()
    # intercambiar
    e(f"          a=r {CIN} r=a {T1} a=r {COUT} r=a {CIN} a=r {T1} r=a {COUT}")
    e(f"          a=r {PS} r=a {T1} a=r {PD} r=a {PS} a=r {T1} r=a {PD}")
    e("        endif")
    e(f"        a=r {PS} r=a {SRC}")
    DEBUGSTOP(stage)
OUTBUF()
e("      endif")
e(f"      a=r {NEXT} r=a {POS} a= 1")
e("    elsel a=0 endif")
e("  a> 0 while")
e("  a=0 c=a")
e("elsel")
e("  *c=a c++")
e("endif")
e("halt")
e("end")
open(sys.argv[1], 'w').write('\n'.join(out) + '\n')
