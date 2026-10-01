#!/usr/bin/env python3
# Generador de ZPAQKANZI7: decodificador de kanzi 2.6.0 (bitstream 7, sin cabecera),
# nivel 7 (LZP+TEXT+UTF+BWT+LZP, CM), en ZPAQL. zpaq-std, 2026. ZPAQL no tiene
# subrutinas: las macros se expanden en linea. Traduccion de ref7.py.
#
# Reusa, extrayendolas por nombre, las macros ya verificadas de gen5.py (BWT, UTF,
# TEXT y lo que usan). Ese programa esta congelado; este generador solo lo lee.
#
# Entrada del PCOMP: orig (4 LE), nivel (1), el diccionario estatico de kanzi (DLEN
# bytes), el flujo headerless.
# M: la entrada desde 0; 128 ceros; dos buffers X e Y de BUFSZ.
# H: tablas chicas y los contadores de CM abajo; desde HBIG el arreglo LF de la BWT o
# las tablas de TEXT.
# Modo DEBUG: env STAGE=k -> emite la salida de la etapa k (0 entropia, 1 LZP4, 2 BWT,
# 3 UTF, 4 TEXT, 5 LZP0) del primer bloque y termina.
import sys, os, re
out = []
def e(s): out.append(s)
STAGE = int(os.environ.get('STAGE', '-1'))
DLEN = 5487
HERE = os.path.dirname(os.path.abspath(__file__))

_next = [1]
def REG(n=1):
    r = _next[0]; _next[0] += n; assert _next[0] < 256, "registros"; return r

# --- registros
N, POS, LEVEL, ORIG, BSZ, BLK, PRE, MODE, SKIP, READ, NEXT = [REG() for _ in range(11)]
COPY, TCOPY, DSZ, LR = [REG() for _ in range(4)]
XB, YB, BUFSZ, PS, PD = [REG() for _ in range(5)]
SRC, LEN, DST, CAP = [REG() for _ in range(4)]
LIN, LOUT, LBUF, CIN, COUT = [REG() for _ in range(5)]
I, J, K, II, JJ, KK, V, W, X, Y, Z = [REG() for _ in range(11)]
T1, T2, T3, T4, T5, T6, T7, T8 = [REG() for _ in range(8)]
# CM
LOWH, LOWL, HIGHH, HIGHL, CURH, CURL, SPH, SPL, IDX, SZB, PB, CNTE, HN, CHUNK = [REG() for _ in range(14)]
CTX, RUN, CB1, CB2, PR, PP, PK, PROW = [REG() for _ in range(8)]
# TEXT
HMASK, DSIZE, SDS, WORDS, ANCHOR, WRUN, CRLF, VAR, OUTLEN, DE = [REG() for _ in range(10)]
# LZP
SI, REF, LCTX, ML = [REG() for _ in range(4)]

# --- H (palabras)
H_ALPH = 0                                       # (sin uso aca; gen5 lo nombra)
H_BKT = 256                                      # BWT: buckets
H_SPTR = 512; H_SLEN = 1536; H_SHASH = 2560      # diccionario estatico, 1024 c/u
H_UVAL = 3584; H_ULEN = 36352                    # UTF, 32768 c/u
H_CT = 69120                                     # tipos de caracter (256)
H_C1 = 69376                                     # CM: counter1 [256][257]
H_C2 = H_C1 + 256 * 257                          # CM: counter2 [512][17]
H_LZP = H_C2 + 512 * 17                          # LZP: 65536 hashes
HBIG = 1 << 18                                   # BWT LF / TEXT: mapa y entradas
assert H_LZP + 65536 <= HBIG
ENT_PTR = HBIG
ENT_HASH = HBIG + (1 << 19)
ENT_DATA = HBIG + 2 * (1 << 19)
MAPB = HBIG + 3 * (1 << 19)
NS = 1024

# --- helpers (como en gen5.py)
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
def WORD(posreg=POS):         # a = 32 bits desde el bit r posreg; valido para k <= 24
    e(f"a=r {posreg} a&= 7 b=a a=r {posreg} a>>= 3 c=a a=*c a<<= 8 c++ a+=*c a<<= 8 c++ a+=*c a<<= 8 c++ a+=*c a<<=b")
def GETK(k, dst, posreg=POS):
    WORD(posreg); e(f"a>>= {32 - k} r=a {dst} a=r {posreg} a+= {k} r=a {posreg}")
def GETR(kreg, dst):
    e(f"a=r {kreg} a> 0 ifl")
    WORD(); e(f"  r=a {T8} a= 32 b=r {kreg} a-=b b=a a=r {T8} a>>=b r=a {dst} a=r {POS} b=r {kreg} a+=b r=a {POS}")
    e(f"elsel a=0 r=a {dst} endif")
def GET32(dst):
    GETK(16, T7); GETK(16, dst); e(f"a=r {T7} a<<= 16 b=r {dst} a+=b r=a {dst}")
def HG(base, idxreg, dst): LK(base); e(f"b=r {idxreg} a+=b d=a a=*d r=a {dst}")
def HS(base, idxreg, valreg): LK(base); e(f"b=r {idxreg} a+=b d=a a=r {valreg} *d=a")
def MG(basereg, idxreg, dst): e(f"a=r {basereg} b=r {idxreg} a+=b c=a a=*c r=a {dst}")
def MS(basereg, idxreg, valreg): e(f"a=r {basereg} b=r {idxreg} a+=b c=a a=r {valreg} *c=a")
def FOR(reg, limreg, body):   # reg = 0 .. limreg-1 (limreg puede ser 0)
    e(f"a=0 r=a {reg}")
    e(f"a=r {limreg} a> 0 ifl")
    e("do")
    body()
    INC(reg); e(f"a=r {reg} b=r {limreg} a<b")
    e("while")
    e("endif")
def FORK(reg, lim, body):     # reg = 0 .. lim-1, lim constante >= 1
    e(f"a=0 r=a {reg}")
    e("do")
    body()
    INC(reg)
    if lim <= 255: e(f"a=r {reg} a< {lim}")
    else: LK(lim); e(f"b=a a=r {reg} a<b")
    e("while")
def HFILL(base, count, valreg):   # H[base .. base+count) = r val
    LK(base); e("d=a")
    SET(T8, count)
    e("do")
    e(f"a=r {valreg} *d=a d++ a=r {T8} a-- r=a {T8} a> 0")
    e("while")

def extract(path, names, repl=()):
    src = open(os.path.join(HERE, path)).read()
    code = []
    for nm in names:
        m = re.search(r'^def ' + nm + r'\(.*?(?=^def |^# |^e\("hcomp"\)|^[A-Z_]+ = )', src, re.S | re.M)
        assert m, nm
        code.append(m.group(0))
    txt = '\n'.join(code)
    for a, b in repl: txt = re.sub(a, b, txt)
    exec(txt, globals())
extract('gen5.py', ['LOG2', 'VARINT', 'UTF', 'EG', 'ES', 'CTYPE', 'HASHSTEP', 'STATICDICT', 'TEXT', 'OUTBUF'])

# ----------------------------------------------------------------- BWT sin limite de 16 MB
# La BWT de gen5.py guarda (indice << 8 | byte) en una palabra de H: con mas de 2^24
# posiciones el indice desborda (ZPAQKANZI5 falla con bloques de mas de 16 MB). Aca la
# palabra lleva solo el indice siguiente, y el byte de cada posicion sale de la primera
# columna (los simbolos en orden), escrita sobre la entrada, que ya no hace falta.
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
        e(f"a=r {I} a== 0 ifl a=0 elsel a=r {I} b=r {T4} a<b ifl a=r {I} a-- elsel a=r {I} endif endif r=a {T3}")
        HG(H_BKT, T1, T2); e(f"a=r {T2} b=a"); LK(HBIG); e(f"a+=b d=a a=r {T3} *d=a")
        INC(T2); HS(H_BKT, T1, T2)
    FOR(I, LEN, lf)
    # primera columna: H_BKT[v] es ahora el fin del cubo de v
    e(f"a=0 r=a {T5}")
    def fcol():
        HG(H_BKT, II, T6)
        e(f"a=r {T5} b=r {T6} a<b ifl")
        e("do")
        MS(SRC, T5, II); INC(T5); e(f"a=r {T5} b=r {T6} a<b")
        e("while")
        e("endif")
    FORK(II, 256, fcol)
    e(f"a=r {T4} a-- r=a {T1}")                 # t
    def walk():
        MG(SRC, T1, T3); MS(DST, I, T3)
        e(f"a=r {T1} b=a"); LK(HBIG); e(f"a+=b d=a a=*d r=a {T1}")
    FOR(I, LEN, walk)
    e("endif")

# ----------------------------------------------------------------- CM
def UPD(adrreg, rate, bit):
    """H[r adr] actualizado como CMPredictor::update: bit 0 x -= x >> rate;
    bit 1 x -= (x - 65520) >> rate con desplazamiento aritmetico, hecho sin
    negativos: x < 65520 -> x += ceil((65520 - x) / 2^rate)."""
    e(f"a=r {adrreg} d=a a=*d r=a {T6}")
    if bit == 0:
        e(f"a>>= {rate} b=a a=r {T6} a-=b *d=a")
    else:
        LK(65520); e(f"b=r {T6} a>b ifl")
        e(f"  a-=b a+= {(1 << rate) - 1} a>>= {rate} b=r {T6} a+=b *d=a")
        e("elsel")
        LK(65520); e(f"  b=a a=r {T6} a-=b a>>= {rate} b=a a=r {T6} a-=b *d=a")
        e("endif")
def CM():                     # PRE bytes -> M[XB..)
    # CHUNK = max(PRE, 64); >= 2^26: PRE >> 3 o >> 4
    e(f"a=r {PRE} a< 64 ifl a= 64 elsel a=r {PRE} endif r=a {CHUNK}")
    LK(1 << 26); e(f"b=a a=r {CHUNK} a<b ifnotl")
    e(f"  a=r {CHUNK} a>>= 3 b=a"); LK(1 << 26); e(f"  a>b ifl a=r {PRE} a>>= 3 elsel a=r {PRE} a>>= 4 endif r=a {CHUNK}")
    e("endif")
    # predictor nuevo por bloque
    SET(T1, 32768); HFILL(H_C1, 256 * 257, T1)
    def c2row():
        LK(17); e(f"b=r {II} a*=b b=a"); LK(H_C2); e(f"a+=b d=a a=0 r=a {T2}")
        e("do")
        e(f"a=r {T2} a<<= 12 *d=a d++ a=r {T2} a++ r=a {T2} a< 16")
        e("while")
        LK(65535); e("*d=a")
    FORK(II, 512, c2row)
    e(f"a= 1 r=a {CTX} a=0 r=a {RUN} r=a {CB1} r=a {CB2}")
    e(f"a=0 r=a {LOWH} r=a {LOWL}")
    LK(0xFFFFFF); e(f"r=a {HIGHH}"); LK(0xFFFFFFFF); e(f"r=a {HIGHL}")
    e(f"a=0 r=a {CNTE}")
    e("do")
    e(f"a=r {PRE} b=r {CNTE} a-=b r=a {HN} b=r {CHUNK} a>b ifl a=b r=a {HN} endif")
    VARINT(SZB)
    GETK(24, CURH); GET32(CURL)
    e(f"a=r {POS} r=a {PB} a=r {SZB} a<<= 3 b=r {POS} a+=b r=a {POS}")
    e(f"a=0 r=a {IDX} r=a {II}")
    e("do")                    # un byte por vuelta
    e(f"a=0 r=a {JJ}")
    e("do")                    # 8 bits
    # get(): p = (13*(c1[ctx][256] + c1[ctx][c1]) + 6*c1[ctx][c2]) >> 5
    LK(257); e(f"b=r {CTX} a*=b b=a"); LK(H_C1); e(f"a+=b r=a {PROW}")      # fila de counter1
    e(f"a=r {PROW} a+= 255 a++ d=a a=*d r=a {T1}")
    e(f"a=r {PROW} b=r {CB1} a+=b d=a a=*d b=r {T1} a+=b r=a {T1} a+=a r=a {T2} a+=a r=a {T3} a+=a b=r {T3} a+=b b=r {T1} a+=b r=a {T1}")   # 13x = 8x+4x+x
    e(f"a=r {PROW} b=r {CB2} a+=b d=a a=*d r=a {T2} a+=a b=r {T2} a+=b a+=a b=r {T1} a+=b a>>= 5 r=a {PP}")   # + 6x
    # pc2 = &c2[ctx | run][p >> 12]
    e(f"a=r {PP} a>>= 12 r=a {PK}")
    e(f"a=r {CTX} b=r {RUN} a|=b r=a {T1}"); LK(17); e(f"b=r {T1} a*=b b=r {PK} a+=b b=a"); LK(H_C2); e(f"a+=b r=a {T7}")   # T7 = &pc2[0]
    e(f"a=r {T7} d=a a=*d r=a {T1} a=r {T7} a++ d=a a=*d b=r {T1} a+=b r=a {T1} a+=a b=r {T1} a+=b r=a {T1}")       # 3*(q0+q1)
    e(f"a=r {PP} a+=a b=r {T1} a+=b a+= 64 a>>= 7 r=a {PR}")
    # range = high - low ; r4 = range >> 4 : H4 = rh >> 4, L4 = (rh & 15) << 28 | rl >> 4
    e(f"a=r {HIGHL} b=r {LOWL} a-=b r=a {T2}")
    e(f"a=r {HIGHH} b=r {LOWH} a-=b r=a {T3}")
    e(f"a=r {HIGHL} b=r {LOWL} a<b ifl a=r {T3} a-- r=a {T3} endif")
    e(f"a=r {T3} a>>= 4 r=a {T4}")
    e(f"a=r {T3} a&= 15 a<<= 28 r=a {T5} a=r {T2} a>>= 4 b=r {T5} a+=b r=a {T5}")
    # P = r4 * pr (pr de 12 bits): t0, t1, t2 en limbs de 16
    e(f"a=r {T5} a<<= 16 a>>= 16 b=r {PR} a*=b r=a {T6}")
    e(f"a=r {T5} a>>= 16 b=r {PR} a*=b b=a a=r {T6} a>>= 16 a+=b r=a {T8}")
    e(f"a=r {T4} b=r {PR} a*=b b=a a=r {T8} a>>= 16 a+=b r=a {T2}")
    e(f"a=r {T8} a<<= 16 b=a a=r {T6} a<<= 16 a>>= 16 a+=b r=a {T3}")
    # P >> 8 ; split = P>>8 + low
    e(f"a=r {T2} a>>= 8 r=a {SPH}")
    e(f"a=r {T2} a&= 255 a<<= 24 b=a a=r {T3} a>>= 8 a+=b r=a {SPL}")
    e(f"a=r {SPL} b=r {LOWL} a+=b r=a {SPL}")
    e(f"a=r {SPH} b=r {LOWH} a+=b r=a {SPH}")
    e(f"a=r {SPL} b=r {LOWL} a<b ifl a=r {SPH} a++ r=a {SPH} endif")
    # split >= cur ?
    e(f"a=0 r=a {T4}")
    e(f"a=r {SPH} b=r {CURH} a>b ifl a= 1 r=a {T4} elsel a=r {SPH} a==b ifl a=r {SPL} b=r {CURL} a<b ifnot a= 1 r=a {T4} endif endif endif")
    # direcciones a actualizar: c1[ctx][256] (T1), c1[ctx][cb1] (T2), pc2[0] (T7), pc2[1] (T3)
    e(f"a=r {PROW} a+= 255 a++ r=a {T1} a=r {PROW} b=r {CB1} a+=b r=a {T2} a=r {T7} a++ r=a {T3}")
    e(f"a=r {T4} a> 0 ifl")
    e(f"  a=r {SPH} r=a {HIGHH} a=r {SPL} r=a {HIGHL}")
    UPD(T1, 2, 1); UPD(T2, 4, 1); UPD(T7, 6, 1); UPD(T3, 6, 1)
    e(f"  a=r {CTX} a+=a a++ r=a {CTX}")
    e("elsel")
    e(f"  a=r {SPL} a++ r=a {LOWL} a=r {SPH} r=a {LOWH} a=r {LOWL} a== 0 ifl a=r {LOWH} a++ r=a {LOWH} endif")
    UPD(T1, 2, 0); UPD(T2, 4, 0); UPD(T7, 6, 0); UPD(T3, 6, 0)
    e(f"  a=r {CTX} a+=a r=a {CTX}")
    e("endif")
    e(f"a=r {CTX} a> 255 ifl")
    e(f"  a=r {CB1} r=a {CB2} a=r {CTX} a&= 255 r=a {CB1} a= 1 r=a {CTX}")
    e(f"  a=0 r=a {RUN} a=r {CB1} b=r {CB2} a==b ifl a= 1 a<<= 8 r=a {RUN} endif")
    e("endif")
    # (low ^ high) >> 24 == 0 <=> LOWH == HIGHH y los 8 bits altos de L iguales
    e(f"a=r {LOWH} b=r {HIGHH} a==b ifl a=r {LOWL} a>>= 24 b=a a=r {HIGHL} a>>= 24 a==b ifl")
    e(f"  a=r {LOWL} a<<= 8 a>>= 8 r=a {LOWH} a=0 r=a {LOWL}")
    e(f"  a=r {HIGHL} a<<= 8 a>>= 8 r=a {HIGHH}"); LK(0xFFFFFFFF); e(f"  r=a {HIGHL}")
    e(f"  a=r {CURL} a<<= 8 a>>= 8 r=a {CURH}")
    # 32 bits desde un bit no alineado: dos lecturas de 16
    e(f"  a=r {IDX} a<<= 3 b=r {PB} a+=b r=a {T5}"); WORD(T5); e(f"  a>>= 16 a<<= 16 r=a {CURL} a=r {T5} a+= 16 r=a {T5}")
    WORD(T5); e(f"  a>>= 16 b=r {CURL} a+=b r=a {CURL} a=r {IDX} a+= 4 r=a {IDX}")
    e("endif endif")
    INC(JJ); e(f"a=r {JJ} a< 8")
    e("while")
    e(f"a=r {CNTE} b=r {II} a+=b r=a {T2}"); MS(XB, T2, CB1)
    INC(II); e(f"a=r {II} b=r {HN} a<b")
    e("while")
    e(f"a=r {CNTE} b=r {HN} a+=b r=a {CNTE} b=r {PRE} a<b")
    e("while")

# ----------------------------------------------------------------- LZP
def LZP():                    # M[SRC..+LEN) -> M[DST..), LEN (lzp_inverse de ref7.py)
    e(f"a=0 r=a {T1}"); HFILL(H_LZP, 65536, T1)
    FORK(II, 4, lambda: (MG(SRC, II, T1), MS(DST, II, T1)))
    e(f"a=r {DST} a+= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a {LCTX}")
    e(f"a= 4 r=a {SI} r=a {J}")
    e(f"a=r {SI} b=r {LEN} a<b ifl")
    e("do")
    LK(0x7FEB352D); e(f"b=r {LCTX} a*=b a>>= 16 r=a {T2}")              # h
    HG(H_LZP, T2, REF); HS(H_LZP, T2, J)
    MG(SRC, SI, T3)
    e(f"a=0 r=a {T4}")                                                   # T4 = 1 literal, 2 escape, 3 match
    e(f"a=r {T3} a== 252 ifl a=r {REF} a== 0 ifl a= 1 r=a {T4} endif elsel a= 1 r=a {T4} endif")
    e(f"a=r {T4} a== 1 ifl")
    e(f"  a=r {LCTX} a<<= 8 b=r {T3} a+=b r=a {LCTX}"); MS(DST, J, T3); INC(J); INC(SI)
    e("elsel")
    INC(SI); MG(SRC, SI, T3)
    e(f"  a=r {T3} a== 255 ifl")
    e(f"    a=r {LCTX} a<<= 8 a+= 252 r=a {LCTX} a= 252 r=a {T3}"); MS(DST, J, T3); INC(J); INC(SI)
    e("  elsel")
    e(f"    a= 64 r=a {ML}")
    e(f"    a=r {T3} a== 254 ifl")
    e("    do")
    INC(SI); e(f"      a=r {ML} a+= 254 r=a {ML}"); MG(SRC, SI, T3)
    e(f"      a=r {T3} a== 254 ifl a=r {SI} b=r {LEN} a<b elsel a=0 a> 0 endif")
    e("    while")
    e("    endif")
    e(f"    a=r {ML} b=r {T3} a+=b r=a {ML}"); INC(SI)
    e(f"    a=r {DST} b=r {REF} a+=b r=a {T5} a=r {DST} b=r {J} a+=b r=a {T6}")
    e("    do")
    e(f"      a=r {T5} c=a a=*c b=a a=r {T6} c=a a=b *c=a a=r {T5} a++ r=a {T5} a=r {T6} a++ r=a {T6}")
    e(f"      a=r {ML} a-- r=a {ML} a> 0")
    e("    while")
    e(f"    a=r {T6} b=r {DST} a-=b r=a {J}")
    e(f"    a=r {T6} a-= 1 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a {LCTX}")
    e("  endif")
    e("endif")
    e(f"a=r {SI} b=r {LEN} a<b")
    e("while")
    e("endif")
    e(f"a=r {J} r=a {LEN}")

def DEBUGSTOP(k):
    if STAGE == k:
        OUTBUF(); e("halt")

# ----------------------------------------------------------------- principal
e("hcomp")
e("halt")
e("pcomp zpaqkanzi7 ;")
e("""(ZPAQKANZI7: decodificador de kanzi 2.6.0, bitstream 7 sin cabecera, nivel 7
 LZP+TEXT+UTF+BWT+LZP con CM, en ZPAQL, para zpaq-std -ma:kanzi. zpaq-std, 2026.
 Guarda la entrada en M y decodifica al final. La entrada lleva el diccionario
 estatico de kanzi detras de la cabecera.)""")
e("a> 255 ifl")
e(f"  a=c r=a {N}")
e(f"  a=0 r=a {T1} do a=0 *c=a c++ a=r {T1} a++ r=a {T1} a< 128 while")
e(f"  a= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a {ORIG}")
e(f"  a= 4 c=a a=*c r=a {LEVEL}")
e(f"  a=r {ORIG} a+= 15 a>>= 4 a<<= 4 r=a {BSZ}"); LK(1024); e(f"  b=a a=r {BSZ} a<b ifl a=b r=a {BSZ} endif")
e(f"  a=r {BSZ} a>>= 4 b=r {BSZ} a+=b r=a {BLK} a=r {BSZ} a+= 255 a+= 255 a+= 2 b=r {BLK} a>b ifl r=a {BLK} endif")
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
GETK(8, T1)                     # checksum de la cabecera del bloque (no se verifica)
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
CM()
e("        endif")
e(f"        a=r {XB} r=a {SRC} r=a {PS} a=r {YB} r=a {DST} r=a {PD} a=r {PRE} r=a {LEN}")
DEBUGSTOP(0)
e(f"        a=0 r=a {CIN} a= 1 r=a {COUT}")       # 0 in, 1 out, 2 buf
for stage, (ti, macro) in enumerate([(4, LZP), (3, BWT), (2, UTF), (1, TEXT), (0, LZP)], 1):
    e(f"        a=r {SKIP} a&= {1 << (7 - ti)} a== 0 ifl")
    e(f"          a=r {COUT} a== 0 ifl a=r {LIN} elsel a=r {COUT} a== 1 ifl a=r {LOUT} elsel a=r {LBUF} endif endif r=a {CAP}")
    e(f"          a=r {CAP} b=r {LOUT} a<b ifl")
    e(f"            a=r {COUT} a< 2 ifl a= 2 r=a {COUT} endif")
    e(f"            a=r {LBUF} b=r {LOUT} a<b ifl a=b r=a {LBUF} endif")
    e(f"            a=r {LBUF} r=a {CAP}")
    e("          endif")
    e(f"          a=r {CAP} r=a {OUTLEN} a=r {PS} r=a {SRC} a=r {PD} r=a {DST}")
    macro()
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
