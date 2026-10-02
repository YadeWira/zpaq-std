#!/usr/bin/env python3
# Generador de ZPAQKANZI8: decodificador de kanzi 2.6.0 (bitstream 7, sin cabecera),
# niveles 8 y 9 (EXE+RLT+TEXT+UTF+DNA, entropia TPAQ / TPAQX), en ZPAQL. zpaq-std,
# 2026. ZPAQL no tiene subrutinas: las macros se expanden en linea. Traduccion de
# ref8.py.
#
# Reusa, extrayendolas por nombre, las macros ya verificadas de gen3.py (EXE, PACK) y
# gen5.py (UTF, TEXT, con el bit de hash de mas que TEXT usa con TPAQX). Esos
# programas estan congelados; este generador solo los lee. Las tablas fijas de TPAQ
# (transiciones, STATE_MAP, MATCH_PRED) salen del TPAQPredictor.hpp de kanzi.
#
# Aritmetica con signo: ZPAQL solo tiene enteros de 32 bits sin signo. Sumas, restas
# y productos dan lo mismo en complemento a dos; el desplazamiento aritmetico es
# ~((~x) >> k) para x negativo (ASR), y las comparaciones con signo miran el bit 31.
#
# Entrada del PCOMP: orig (4 LE), nivel (1), el diccionario estatico de kanzi (DLEN
# bytes), el flujo headerless.
# M: la entrada; 128 ceros; X e Y (BUFSZ); y, mientras dura la entropia, las tablas de
#    bytes de TPAQ: el buffer de historia, small0 (2^16), small1 (2^24) y big.
# H: tablas chicas abajo; desde HBIG, mientras dura la entropia, hashes, mezcladores
#    y SSE1 de TPAQ; despues, las tablas de TEXT.
# Modo DEBUG: env STAGE=k -> emite la salida de la etapa k (0 entropia, 1 DNA, 2 UTF,
# 3 TEXT, 4 RLT, 5 EXE) del primer bloque y termina.
import sys, os, re
out = []
def e(s): out.append(s)
STAGE = int(os.environ.get('STAGE', '-1'))
# KZROBUST=1: la version robusta ante datos danados (pre54); sin ella sale el programa congelado
ROBUST = os.environ.get('KZROBUST') == '1'
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
# decodificador binario
LOWH, LOWL, HIGHH, HIGHL, CURH, CURL, SPH, SPL, IDX, SZB, PB, CNTE, HN, CHUNK, BIT, BYTE = [REG() for _ in range(16)]
# TPAQ
XF, STMASK, MXMASK, HMSK, BMASK, MBUF, MSM0, MSM1, MBIG, HHASH, HMIX, HSSE1 = [REG() for _ in range(12)]
PR, C0, C4, C8, BPOS, TPOS, BIN, MLEN, MPOS, MVAL, THASH, MIX = [REG() for _ in range(12)]
CTX0 = REG(7); CP0 = REG(7); P0 = REG(8)
SIDX0, SIDX1, PP, ERR = [REG() for _ in range(4)]
# TEXT
HMASK, DSIZE, SDS, WORDS, ANCHOR, WRUN, CRLF, VAR, OUTLEN, DE = [REG() for _ in range(10)]
# EXE / PACK (nombres de gen3.py)
SI, CS, CE, JMP = [REG() for _ in range(4)]

# --- H (palabras)
H_ALPH = 0
H_TRANS = 256                                    # TPAQ: transiciones [2][256]
H_SMAP = 768                                     # STATE_MAP + 2048
H_MPRED = 1024                                   # MATCH_PRED (88)
H_SQ = 1152                                      # SQUASH (4096)
H_STR = 5248                                     # STRETCH (4096, con signo)
H_IE = 9344                                      # INV_EXP (33)
H_SPTR = 9472; H_SLEN = 10496; H_SHASH = 11520   # diccionario estatico, 1024 c/u
H_UVAL = 12544; H_ULEN = 45312                   # UTF, 32768 c/u
H_CT = 78080                                     # tipos de caracter (256)
H_IDX2 = 78336; H_MAP = 78352                    # PACK
H_SSE0 = 78608                                   # TPAQ: SSE0 [256][33]
HBIG = 1 << 17
assert H_SSE0 + 256 * 33 <= HBIG
ENT_PTR = HBIG
ENT_HASH = HBIG + (1 << 19)
ENT_DATA = HBIG + 2 * (1 << 19)
MAPB = HBIG + 3 * (1 << 19)
NS = 1024
MIXW = 19                                        # palabras por mezclador: w[8] p[8] pr skew lr

# --- tablas de kanzi
_kz = os.path.join(HERE, '..', 'kanzi')
_hpp = open(os.path.join(_kz, 'entropy', 'TPAQPredictor.hpp')).read()
def _arr(name):
    i = _hpp.index(name); j = _hpp.index('{', i); k = _hpp.index('};', j)
    return [int(x) for x in re.findall(r'-?\d+', re.sub(r'//[^\n]*', '', _hpp[j:k]))]
TRANS = _arr('STATE_TRANSITIONS[2][256]'); assert len(TRANS) == 512
SMAP = _arr('STATE_MAP[]'); assert len(SMAP) == 256
MPRED = _arr('MATCH_PRED[]'); assert len(MPRED) == 88
INV_EXP = [0, 8, 22, 47, 88, 160, 283, 492, 848, 1451, 2459, 4117, 6766, 10819, 16608, 24127,
           32768, 41409, 48928, 54717, 58770, 61419, 63077, 64085, 64688, 65044, 65253, 65376,
           65448, 65489, 65514, 65528, 65536]
HASH = 0x7FEB352D
# LogisticAdaptiveProbMap: _data[j] = squash((j - 16) * 128) << 4
_SQ = [0] * 4096
for _x in range(1, 4096):
    _w = _x & 127; _y = _x >> 7
    _SQ[_x - 1] = (INV_EXP[_y] * (128 - _w) + INV_EXP[_y + 1] * _w) >> 11
_SQ[4095] = 4095
def _squash(d): return 4095 if d >= 2048 else (0 if d <= -2048 else _SQ[d + 2047])
SSEINIT = [_squash((j - 16) * 128) << 4 for j in range(33)]

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
def LE32(basereg, off, dst):
    e(f"a=r {basereg} a+= {off + 3} c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a {dst}")
def ASR(reg, k):              # r reg = r reg >> k, aritmetico
    e(f"a=r {reg} a>>= 31 a> 0 ifl a=r {reg} a! a>>= {k} a! elsel a=r {reg} a>>= {k} endif r=a {reg}")
def MFILL0(basereg, cntreg):  # M[r base .. + r cnt) = 0 (cnt > 0)
    e(f"a=r {basereg} c=a a=r {cntreg} r=a {T8}")
    e("do")
    e(f"a=0 *c=a c++ a=r {T8} a-- r=a {T8} a> 0")
    e("while")
def HFILLR(basereg, cntreg, valreg):   # H[r base .. + r cnt) = r val (cnt > 0)
    e(f"a=r {basereg} d=a a=r {cntreg} r=a {T8}")
    e("do")
    e(f"a=r {valreg} *d=a d++ a=r {T8} a-- r=a {T8} a> 0")
    e("while")
def POW2FLOOR(reg):           # r reg = 2^floor(log2(r reg)), r reg >= 1
    e(f"a= 1 r=a {T8}")
    e(f"a=r {T8} a+=a b=r {reg} a>b ifnotl")
    e("do")
    e(f"a=r {T8} a+=a r=a {T8} a+=a b=r {reg} a>b ifnot a=r {T8} a>>= 31 a== 0 elsel a=0 a> 0 endif")
    e("while")
    e("endif")
    e(f"a=r {T8} r=a {reg}")

def extract(path, names, repl=()):
    src = open(os.path.join(HERE, path)).read()
    code = []
    for nm in names:
        m = re.search(r'^def ' + nm + r'\(.*?(?=^def |^# |^e\("hcomp"\)|^[A-Z_]+ = )', src, re.S | re.M)
        assert m, nm
        code.append(m.group(0))
    txt = '\n'.join(code)
    for a, b in repl:
        assert re.search(a, txt), a
        txt = re.sub(a, b, txt)
    exec(txt, globals())
extract('gen5.py', ['LOG2', 'VARINT', 'UTF', 'EG', 'ES', 'CTYPE', 'HASHSTEP', 'STATICDICT', 'OUTBUF'])
# TEXT con TPAQX: kanzi da a la tabla de hash un bit mas (_logHashSize = log + 1)
extract('gen5.py', ['TEXT'], [(r'(    e\(f"a=r \{T3\} a< 13 ifl a= 13 r=a \{T3\} endif"\)\n)(    e\(f"a= 1 b=r \{T3\} a<<=b a-- r=a \{HMASK\}"\))',
                               r'\1    e(f"a=r {LEVEL} a== 9 ifl a=r {T3} a++ r=a {T3} endif")\n\2')])
extract('gen3.py', ['PACK', 'COPY1', 'EXE'])

# ----------------------------------------------------------------- tablas fijas
def TABLES():
    LK(H_TRANS); e("d=a")
    for v in TRANS: e(f"a= {v} *d=a d++")
    LK(H_SMAP); e("d=a")
    for v in SMAP: LK(v + 2048); e("*d=a d++")
    LK(H_MPRED); e("d=a")
    for v in MPRED: LK(v); e("*d=a d++")
    LK(H_IE); e("d=a")
    for v in INV_EXP: LK(v); e("*d=a d++")
    # SQUASH[x-1] = (IE[x>>7]*(128-w) + IE[(x>>7)+1]*w) >> 11, w = x & 127
    e(f"a= 1 r=a {II}")
    e("do")
    e(f"a=r {II} a&= 127 r=a {T1} a=r {II} a>>= 7 r=a {T2}")
    HG(H_IE, T2, T3); e(f"a=r {T2} a++ r=a {T2}"); HG(H_IE, T2, T4)
    e(f"a= 128 b=r {T1} a-=b b=r {T3} a*=b r=a {T5} a=r {T4} b=r {T1} a*=b b=r {T5} a+=b a>>= 11 r=a {T5}")
    e(f"a=r {II} a-- r=a {T6}"); HS(H_SQ, T6, T5)
    INC(II); LK(4096); e(f"b=a a=r {II} a<b")
    e("while")
    SET(T5, 4095); SET(T6, 4095); HS(H_SQ, T6, T5)
    # STRETCH: n = 0; x = -2047..2047: while n <= squash(x): STR[n++] = x; corta si n >= 4096
    e(f"a=0 r=a {JJ} r=a {II}")                 # JJ = n, II = x + 2047
    e("do")
    HG(H_SQ, II, T1)                             # squash(x) = SQ[x + 2047]
    LK(2047); e(f"b=a a=r {II} a-=b r=a {T2}")   # x
    e(f"a=r {JJ} b=r {T1} a>b ifnotl")
    e("do")
    HS(H_STR, JJ, T2); INC(JJ)
    e(f"a=r {JJ} b=r {T1} a>b ifnot"); LK(4096); e(f"b=a a=r {JJ} a<b elsel a=0 a> 0 endif")
    e("while")
    e("endif")
    INC(II)
    LK(4096); e(f"b=a a=r {JJ} a<b ifl"); LK(4095); e(f"b=a a=r {II} a<b elsel a=0 a> 0 endif")
    e("while")
    SET(T5, 2047); SET(T6, 4095); HS(H_STR, T6, T5)

# ----------------------------------------------------------------- TPAQ
def SQUASHR(dreg, dst):       # r dst = squash(r dreg), r dreg con signo
    e(f"a=r {dreg} a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 7 r=a {T8}")   # d + 2047
    LK(4095); e(f"b=a a=r {T8} a<b ifl")
    HG(H_SQ, T8, dst)
    e("elsel")
    e(f"  a=r {dreg} a>>= 31 a> 0 ifl a=0 elsel"); LK(4095); e(f"  endif r=a {dst}")
    e("endif")
def STRETCHR(preg, dst): HG(H_STR, preg, dst)

def CCTX(idreg, cxreg, dst):  # createContext(id, cx): (rot16(cx*987654323 + id)) * 123456791 + id
    LK(987654323); e(f"b=r {cxreg} a*=b b=r {idreg} a+=b r=a {T8} a<<= 16 r=a {T7} a=r {T8} a>>= 16 b=r {T7} a|=b r=a {T8}")
    LK(123456791); e(f"b=r {T8} a*=b b=r {idreg} a+=b r=a {dst}")
def HASHF(xreg, yreg, dst):   # hash(x, y) de TPAQPredictor (h con signo)
    LK(HASH); e(f"b=r {xreg} a*=b r=a {T7}"); LK(HASH); e(f"b=r {yreg} a*=b b=r {T7} a^=b r=a {T7} r=a {T6}")
    ASR(T7, 1); ASR(T6, 9)
    e(f"a=r {T7} b=r {T6} a^=b r=a {T7} a=r {xreg} a>>= 2 b=r {T7} a^=b r=a {T7} a=r {yreg} a>>= 3 b=r {T7} a^=b b=a"); LK(HASH); e(f"a^=b r=a {dst}")

def MIXUPD():                 # TPAQMixer::update(BIT) sobre el mezclador r MIX
    e(f"a=r {MIX} a+= 16 d=a a=*d r=a {T1}")                          # pr
    e(f"a=r {BIT} a<<= 12 b=r {T1} a-=b r=a {ERR}")
    e(f"a=r {MIX} a+= 18 d=a a=*d b=a a=r {ERR} a*=b r=a {ERR}")       # * learnRate
    ASR(ERR, 10)
    e(f"a=r {ERR} a> 0 ifl")
    e(f"  a=r {MIX} a+= 18 d=a a=*d"); LK(11 << 7); e("  b=a a=*d a>b ifl a-- *d=a endif")
    e(f"  a=r {MIX} a+= 17 d=a a=*d b=r {ERR} a+=b *d=a")              # skew
    for i in range(8):
        e(f"  a=r {MIX} a+= {8 + i} d=a a=*d b=r {ERR} a*=b r=a {T2}")
        ASR(T2, 12)
        e(f"  a=r {MIX} a+= {i} d=a a=*d b=r {T2} a+=b *d=a")
    e("endif")
def MIXGET(dst):              # TPAQMixer::get(P0..P7) -> r dst
    e(f"a=0 r=a {T1}")
    for i in range(8):
        e(f"a=r {MIX} a+= {8 + i} d=a a=r {P0 + i} *d=a a=r {MIX} a+= {i} d=a a=*d b=r {P0 + i} a*=b b=r {T1} a+=b r=a {T1}")
    e(f"a=r {MIX} a+= 17 d=a a=*d b=r {T1} a+=b r=a {T1}")
    LK(65536); e(f"b=a a=r {T1} a+=b r=a {T1}")
    ASR(T1, 17)
    SQUASHR(T1, dst)
    e(f"a=r {MIX} a+= 16 d=a a=r {dst} *d=a")

def SSE(sidx, hbase_reg, rate, ctxreg, preg, dst):
    """LogisticAdaptiveProbMap<false, rate>::get(BIT, r preg, r ctxreg) -> r dst.
    r sidx = direccion absoluta en H de _index. hbase_reg: registro con la base, o
    None para H_SSE0."""
    for off in (0, 1):
        e(f"a=r {sidx} a+= {off} d=a a=*d r=a {T3}")
        e(f"a=r {BIT} a> 0 ifl"); LK(65528); e("elsel a=0 endif")
        e(f"b=r {T3} a-=b r=a {T4}"); ASR(T4, rate)
        e(f"a=r {T4} b=r {T3} a+=b b=r {BIT} a+=b a<<= 16 a>>= 16 *d=a")
    STRETCHR(preg, T3)                                                 # pr = stretch(pr)
    e(f"a=r {T3} a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 8 a>>= 7 r=a {T4}")   # (pr + 2048) >> 7
    e(f"a=r {ctxreg} b= 33 a*=b b=r {T4} a+=b b=a")
    if hbase_reg is None: LK(H_SSE0)
    else: e(f"a=r {hbase_reg}")
    e(f"a+=b r=a {sidx}")
    e(f"a=r {T3} a&= 127 r=a {T4}")                                   # w
    e(f"a=r {sidx} d=a a=*d r=a {T5} d++ a=*d b=r {T5} a-=b b=r {T4} a*=b r=a {T6} a=r {T5} a<<= 7 b=r {T6} a+=b a>>= 11 r=a {dst}")

def MATCHFIND():              # TPAQPredictor::findMatch
    e(f"a=r {MLEN} a> 0 ifl")
    e(f"  a=r {MLEN} a< 88 ifl a++ r=a {MLEN} endif a=r {MPOS} a++ r=a {MPOS}")
    e("elsel")
    e(f"  a=r {HHASH} b=r {THASH} a+=b d=a a=*d r=a {MPOS}")
    e(f"  a=r {MPOS} a> 0 ifl a=r {TPOS} b=r {MPOS} a-=b b=r {BMASK} a>b ifl a=0 elsel a= 1 endif elsel a=0 endif")
    e("  a> 0 ifl")
    e(f"    a= 2 r=a {T1}")                                            # r
    e("    do")
    e(f"      a=r {TPOS} b=r {T1} a-=b a-- b=r {BMASK} a&=b b=r {MBUF} a+=b c=a a=*c r=a {T2}")
    e(f"      a=r {MPOS} b=r {T1} a-=b a-- b=r {BMASK} a&=b b=r {MBUF} a+=b c=a a=*c b=r {T2} a==b ifl")
    e(f"        a=r {TPOS} b=r {T1} a-=b b=r {BMASK} a&=b b=r {MBUF} a+=b c=a a=*c r=a {T2}")
    e(f"        a=r {MPOS} b=r {T1} a-=b b=r {BMASK} a&=b b=r {MBUF} a+=b c=a a=*c b=r {T2} a==b ifl")
    e(f"          a=r {T1} a+= 2 r=a {T1} a> 88 ifl a=0 elsel a= 1 endif")
    e("        elsel a=0 endif")
    e("      elsel a=0 endif")
    e("      a> 0")
    e("    while")
    e(f"    a=r {T1} a-= 2 r=a {MLEN}")
    e("  endif")
    e("endif")

def TPAQUPD():                # TPAQPredictor::update(BIT) y la prediccion siguiente en PR
    MIXUPD()
    e(f"a=r {C0} a+=a b=r {BIT} a+=b r=a {C0} a=r {BPOS} a-- r=a {BPOS}")
    e(f"a=r {BPOS} a== 0 ifl")
    e(f"  a=r {TPOS} b=r {BMASK} a&=b b=r {MBUF} a+=b c=a a=r {C0} *c=a")
    e(f"  a=r {TPOS} a++ r=a {TPOS}")
    e(f"  a=r {C4} a>>= 24 b=a a=r {C8} a<<= 8 a|=b r=a {C8}")
    e(f"  a=r {C0} a&= 255 b=a a=r {C4} a<<= 8 a|=b r=a {C4}")
    LK(HASH); e(f"  b=r {THASH} a*=b a<<= 4 b=r {C4} a+=b b=r {HMSK} a&=b r=a {THASH}")
    e(f"  a= 1 r=a {C0} a= 8 r=a {BPOS}")
    e(f"  a=r {C4} a>>= 7 a&= 1 b=r {BIN} a+=b r=a {BIN}")
    e(f"  a=r {C4} b=r {MXMASK} a&=b r=a {T1} a=r {MLEN} a> 0 ifl a=r {T1} a++ r=a {T1} endif")
    e(f"  a=r {T1} b= {MIXW} a*=b b=r {HMIX} a+=b r=a {MIX}")
    e(f"  a=r {C4} a&= 255 a<<= 8 r=a {CTX0}")
    e(f"  a=r {C4} a<<= 16 a>>= 8 r=a {CTX0 + 1}")
    e(f"  a=r {C4} a<<= 8 a>>= 8 r=a {T5} a= 2 r=a {T4}"); CCTX(T4, T5, CTX0 + 2)
    e(f"  a= 3 r=a {T4}"); CCTX(T4, C4, CTX0 + 3)
    e(f"  a=r {TPOS} a>>= 2 b=a a=r {BIN} a<b ifl")
    e(f"    a=r {C8} a<<= 16 a>>= 16 b=r {C4} a^=b r=a {T5}"); CCTX(CTX0 + 1, T5, CTX0 + 4)
    LK(0xF0F0F000); e(f"    b=r {C4} a&=b a>>= 4 r=a {T5}"); LK(0xF0F0F000); e(f"    b=r {C8} a&=b b=r {T5} a|=b r=a {CTX0 + 5}")
    e(f"    a=r {XF} a> 0 ifl")
    for src_, dreg in ((C4, X), (C8, Y)):
        LK(0x80808080); e(f"      b=r {src_} a&=b a== 0 ifl"); LK(0x4F4FFFFF); e(f"      b=r {src_} a&=b elsel"); LK(0x80808080); e(f"      b=r {src_} a&=b endif r=a {dreg}")
    e(f"      a=r {X} a<<= 2 r=a {X} a=r {Y} a>>= 2 r=a {Y}"); HASHF(X, Y, CTX0 + 6)
    e("    endif")
    e("  elsel")
    LK(HASH); e(f"    b=r {MLEN} a+=b r=a {T4} a=r {C4} a>>= 20 a<<= 20 r=a {T5}"); CCTX(T4, T5, CTX0 + 4)
    e(f"    a=r {C8} a<<= 16 b=r {CTX0} a|=b r=a {CTX0 + 5}")
    e(f"    a=r {XF} a> 0 ifl")
    e(f"      a=r {C4} a>>= 16 a<<= 16 r=a {X} a=r {C8} a>>= 16 r=a {Y}"); HASHF(X, Y, CTX0 + 6)
    e("    endif")
    e("  endif")
    MATCHFIND()
    e(f"  a=r {MPOS} b=r {BMASK} a&=b b=r {MBUF} a+=b c=a a=*c a+= 255 a++ r=a {MVAL}")
    e(f"  a=r {HHASH} b=r {THASH} a+=b d=a a=r {TPOS} *d=a")
    e("endif")
    # transiciones de los estados actuales
    for k in range(6):
        e(f"a=r {CP0 + k} c=a a=*c b=a a=r {BIT} a<<= 8 a+=b b=a"); LK(H_TRANS); e(f"a+=b d=a a=*d *c=a")
    # punteros nuevos y predicciones
    e(f"a=r {CTX0} b=r {C0} a+=b b=r {MSM0} a+=b r=a {CP0}")
    e(f"a=r {CTX0 + 1} b=r {C0} a+=b b=r {MSM1} a+=b r=a {CP0 + 1}")
    for k in (2, 3, 4):
        e(f"a=r {CTX0 + k} b=r {C0} a+=b b=r {STMASK} a&=b b=r {MBIG} a+=b r=a {CP0 + k}")
    e(f"a=r {CTX0 + 5} b=r {C0} a^=b b=r {STMASK} a&=b b=r {MBIG} a+=b r=a {CP0 + 5}")
    for k in range(6):
        e(f"a=r {CP0 + k} c=a a=*c b=a"); LK(H_SMAP); e(f"a+=b d=a a=*d r=a {P0 + k}"); LK(2048); e(f"b=a a=r {P0 + k} a-=b r=a {P0 + k}")
    # modelo de coincidencias
    e(f"a=0 r=a {P0 + 7} a=r {MLEN} a> 0 ifl")
    e(f"  a=r {MVAL} b=r {BPOS} a>>=b b=r {C0} a==b ifl")
    e(f"    a=r {MLEN} a-- b=a"); LK(H_MPRED); e(f"    a+=b d=a a=*d r=a {P0 + 7}")
    e(f"    a=r {BPOS} a-- b=a a=r {MVAL} a>>=b a&= 1 a== 0 ifl a=0 b=r {P0 + 7} a-=b r=a {P0 + 7} endif")
    e(f"  elsel a=0 r=a {MLEN} endif")
    e("endif")
    e(f"a=r {XF} a== 0 ifl")
    e(f"  a=r {P0 + 7} r=a {P0 + 6}")
    MIXGET(PP)
    e(f"  a=r {TPOS} a>>= 3 b=a a=r {BIN} a<b ifl")
    SSE(SIDX0, None, 7, C0, PP, T1); e(f"    a=r {T1} b= 3 a*=b b=r {PP} a+=b a>>= 2 r=a {PP}")
    e("  endif")
    e("elsel")
    e(f"  a=r {CP0 + 6} c=a a=*c b=a a=r {BIT} a<<= 8 a+=b b=a"); LK(H_TRANS); e(f"  a+=b d=a a=*d *c=a")
    e(f"  a=r {CTX0 + 6} b=r {C0} a+=b b=r {STMASK} a&=b b=r {MBIG} a+=b r=a {CP0 + 6}")
    e(f"  a=r {CP0 + 6} c=a a=*c b=a"); LK(H_SMAP); e(f"  a+=b d=a a=*d r=a {P0 + 6}"); LK(2048); e(f"  b=a a=r {P0 + 6} a-=b r=a {P0 + 6}")
    MIXGET(PP)
    e(f"  a=r {CTX0} b=r {C0} a+=b r=a {T2}")                          # ctx de SSE1
    e(f"  a=r {TPOS} a>>= 3 b=a a=r {BIN} a<b ifl")
    SSE(SIDX1, HSSE1, 7, T2, PP, PP)
    e("  elsel")
    e(f"    a=r {TPOS} a>>= 2 b=a a=r {BIN} a<b ifnotl")
    SSE(SIDX0, None, 6, C0, PP, T1); e(f"      a=r {T1} b= 3 a*=b b=r {PP} a+=b a>>= 2 r=a {PP}")
    e("    endif")
    e(f"    a=r {CTX0} b=r {C0} a+=b r=a {T2}")
    SSE(SIDX1, HSSE1, 7, T2, PP, T1); e(f"    a=r {T1} b= 3 a*=b b=r {PP} a+=b a>>= 2 r=a {PP}")
    e("  endif")
    e("endif")
    LK(2048); e(f"b=a a=r {PP} a<b ifl a++ endif r=a {PR}")

def TPAQINIT():               # predictor nuevo por bloque: tamanos, tablas a cero, mezcladores, SSE
    e(f"a=r {LEVEL} a== 9 ifl a= 2 elsel a=0 endif r=a {XF}")
    # statesSize (de BSZ)
    e(f"a= 22 r=a {T1}")
    e(f"a=r {BSZ} a>>= 20 a> 0 ifl a= 24 r=a {T1} endif")
    e(f"a=r {BSZ} a>>= 22 a> 0 ifl a= 26 r=a {T1} endif")
    e(f"a=r {BSZ} a>>= 24 a> 0 ifl a= 27 r=a {T1} endif")
    e(f"a=r {BSZ} a>>= 26 a> 0 ifl a= 28 r=a {T1} endif")
    e(f"a=r {T1} b=r {XF} a+=b b=a a= 1 a<<=b a-- r=a {STMASK}")
    # mixersSize (de PRE)
    e(f"a= 8 r=a {T1}")
    e(f"a=r {PRE} a>>= 20 a> 0 ifl a= 11 r=a {T1} endif")
    e(f"a=r {PRE} a>>= 22 a> 0 ifl a= 13 r=a {T1} endif")
    e(f"a=r {PRE} a>>= 23 a> 0 ifl a= 14 r=a {T1} endif")
    e(f"a=r {PRE} a>>= 24 a> 0 ifl a= 15 r=a {T1} endif")
    e(f"a=r {PRE} a>>= 25 a> 0 ifl a= 16 r=a {T1} endif")
    e(f"a=r {T1} b=r {XF} a+=b b=a a= 1 a<<=b r=a {T7} a-- a>>= 1 a<<= 1 r=a {MXMASK}")      # T7 = mixersSize
    # bufferSize = pow2floor(min(BSZ, 64 MB))
    e(f"a=r {BSZ} r=a {T1}"); LK(64 << 20); e(f"b=a a=r {T1} a>b ifl a=b r=a {T1} endif")
    POW2FLOOR(T1); e(f"a=r {T1} a-- r=a {BMASK}")
    # hashSize = pow2floor(min(16M, PRE < 2^26 ? PRE*16 : 2^30)) << XF, <= 2^30
    e(f"a=r {PRE} a>>= 26 a> 0 ifl a= 1 a<<= 30 elsel a=r {PRE} a<<= 4 endif r=a {T1}")
    LK(16 << 20); e(f"b=a a=r {T1} a>b ifl a=b r=a {T1} endif")
    POW2FLOOR(T1); e(f"a=r {T1} b=r {XF} a<<=b r=a {T1}")
    LK(1 << 30); e(f"b=a a=r {T1} a>b ifl a=b r=a {T1} endif")
    e(f"a=r {T1} a-- r=a {HMSK}")
    # M: buffer, small0, small1, big detras de Y
    e(f"a=r {YB} b=r {BUFSZ} a+=b r=a {MBUF} b=r {BMASK} a+=b a++ r=a {MSM0} a= 1 a<<= 16 b=r {MSM0} a+=b r=a {MSM1}")
    e(f"a= 1 a<<= 24 b=r {MSM1} a+=b r=a {MBIG}")
    e(f"a=r {MBIG} b=r {STMASK} a+=b a++ b=r {MBUF} a-=b r=a {T1}"); MFILL0(MBUF, T1)
    # H: hashes, mezcladores, SSE1 desde HBIG
    SET(HHASH, HBIG)
    e(f"a=r {HMSK} a++ r=a {T1} a=0 r=a {T2}"); HFILLR(HHASH, T1, T2)
    e(f"a=r {HHASH} b=r {HMSK} a+=b a++ r=a {HMIX}")
    e(f"a=r {HMIX} d=a a=r {T7} r=a {T1}")                              # T1 = mezcladores
    e("do")
    for i in range(8): LK(32768); e("*d=a d++")
    for i in range(8): e("a=0 *d=a d++")
    LK(2048); e("*d=a d++ a=0 *d=a d++"); LK(60 << 7); e("*d=a d++")
    e(f"a=r {T1} a-- r=a {T1} a> 0")
    e("while")
    e(f"a=r {T7} b= {MIXW} a*=b b=r {HMIX} a+=b r=a {HSSE1}")
    # SSE: _data[j] = squash((j - 16) * 128) << 4, repetido por contexto
    def ssefill(basereg, nctx):
        e(f"a=r {basereg} d=a a=0 r=a {T2}")
        e("do")
        for v in SSEINIT: LK(v); e("*d=a d++")
        INC(T2); e(f"a=r {T2} b=r {nctx} a<b")
        e("while")
    SET(T6, H_SSE0); SET(T1, 256); ssefill(T6, T1)
    e(f"a=r {XF} a> 0 ifl a= 1 a<<= 16 elsel a= 1 a<<= 8 endif r=a {T1}"); ssefill(HSSE1, T1)
    SET(SIDX0, H_SSE0); e(f"a=r {HSSE1} r=a {SIDX1}")
    # estado
    e(f"a=0 r=a {C4} r=a {C8} r=a {TPOS} r=a {BIN} r=a {MLEN} r=a {MPOS} r=a {MVAL} r=a {THASH}")
    for k in range(7): e(f"a=0 r=a {CTX0 + k}")
    e(f"a= 1 r=a {C0} a= 8 r=a {BPOS} a=r {HMIX} r=a {MIX}")
    LK(2048); e(f"r=a {PR}")
    e(f"a=r {MSM0} r=a {CP0} a=r {MSM1} r=a {CP0 + 1}")
    for k in range(2, 7): e(f"a=r {MBIG} r=a {CP0 + k}")

def TPAQDEC():                # PRE bytes -> M[XB..) (BinaryEntropyDecoder con TPAQ)
    e(f"a=r {PRE} a< 64 ifl a= 64 elsel a=r {PRE} endif r=a {CHUNK}")
    LK(1 << 26); e(f"b=a a=r {CHUNK} a<b ifnotl")
    e(f"  a=r {CHUNK} a>>= 3 b=a"); LK(1 << 26); e(f"  a>b ifl a=r {PRE} a>>= 3 elsel a=r {PRE} a>>= 4 endif r=a {CHUNK}")
    e("endif")
    TPAQINIT()
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
    e(f"a=0 r=a {JJ} r=a {BYTE}")
    e("do")                    # 8 bits
    # r4 = (high - low) >> 4 ; P = r4 * PR ; split = (P >> 8) + low
    e(f"a=r {HIGHL} b=r {LOWL} a-=b r=a {T2}")
    e(f"a=r {HIGHH} b=r {LOWH} a-=b r=a {T3}")
    e(f"a=r {HIGHL} b=r {LOWL} a<b ifl a=r {T3} a-- r=a {T3} endif")
    e(f"a=r {T3} a>>= 4 r=a {T4}")
    e(f"a=r {T3} a&= 15 a<<= 28 r=a {T5} a=r {T2} a>>= 4 b=r {T5} a+=b r=a {T5}")
    e(f"a=r {T5} a<<= 16 a>>= 16 b=r {PR} a*=b r=a {T6}")
    e(f"a=r {T5} a>>= 16 b=r {PR} a*=b b=a a=r {T6} a>>= 16 a+=b r=a {T8}")
    e(f"a=r {T4} b=r {PR} a*=b b=a a=r {T8} a>>= 16 a+=b r=a {T2}")
    e(f"a=r {T8} a<<= 16 b=a a=r {T6} a<<= 16 a>>= 16 a+=b r=a {T3}")
    e(f"a=r {T2} a>>= 8 r=a {SPH}")
    e(f"a=r {T2} a&= 255 a<<= 24 b=a a=r {T3} a>>= 8 a+=b r=a {SPL}")
    e(f"a=r {SPL} b=r {LOWL} a+=b r=a {SPL}")
    e(f"a=r {SPH} b=r {LOWH} a+=b r=a {SPH}")
    e(f"a=r {SPL} b=r {LOWL} a<b ifl a=r {SPH} a++ r=a {SPH} endif")
    e(f"a=0 r=a {BIT}")
    e(f"a=r {SPH} b=r {CURH} a>b ifl a= 1 r=a {BIT} elsel a=r {SPH} a==b ifl a=r {SPL} b=r {CURL} a<b ifnot a= 1 r=a {BIT} endif endif endif")
    e(f"a=r {BIT} a> 0 ifl")
    e(f"  a=r {SPH} r=a {HIGHH} a=r {SPL} r=a {HIGHL}")
    e("elsel")
    e(f"  a=r {SPL} a++ r=a {LOWL} a=r {SPH} r=a {LOWH} a=r {LOWL} a== 0 ifl a=r {LOWH} a++ r=a {LOWH} endif")
    e("endif")
    TPAQUPD()
    e(f"a=r {BYTE} a+=a b=r {BIT} a+=b r=a {BYTE}")
    e(f"a=r {LOWH} b=r {HIGHH} a==b ifl a=r {LOWL} a>>= 24 b=a a=r {HIGHL} a>>= 24 a==b ifl")
    e(f"  a=r {LOWL} a<<= 8 a>>= 8 r=a {LOWH} a=0 r=a {LOWL}")
    e(f"  a=r {HIGHL} a<<= 8 a>>= 8 r=a {HIGHH}"); LK(0xFFFFFFFF); e(f"  r=a {HIGHL}")
    e(f"  a=r {CURL} a<<= 8 a>>= 8 r=a {CURH}")
    e(f"  a=r {IDX} a<<= 3 b=r {PB} a+=b r=a {T5}"); WORD(T5); e(f"  a>>= 16 a<<= 16 r=a {CURL} a=r {T5} a+= 16 r=a {T5}")
    WORD(T5); e(f"  a>>= 16 b=r {CURL} a+=b r=a {CURL} a=r {IDX} a+= 4 r=a {IDX}")
    e("endif endif")
    INC(JJ); e(f"a=r {JJ} a< 8")
    e("while")
    e(f"a=r {CNTE} b=r {II} a+=b r=a {T2}"); MS(XB, T2, BYTE)
    INC(II); e(f"a=r {II} b=r {HN} a<b")
    e("while")
    e(f"a=r {CNTE} b=r {HN} a+=b r=a {CNTE} b=r {PRE} a<b")
    e("while")

# ----------------------------------------------------------------- RLT
def RLT():                    # M[SRC..+LEN) -> M[DST..), LEN (rlt_inverse de ref8.py)
    e(f"a=0 r=a {T1}"); MG(SRC, T1, V)                                # escape
    e(f"a= 1 r=a {SI} a=0 r=a {J}")
    e(f"a=r {SI} b=r {LEN} a<b ifl"); MG(SRC, SI, T1); e(f"  a=r {T1} b=r {V} a==b ifl")
    INC(SI); MS(DST, J, V); INC(J); INC(SI)
    e("  endif")
    e("endif")
    e(f"a=r {SI} b=r {LEN} a<b ifl")
    e("do")
    MG(SRC, SI, T1); INC(SI)
    e(f"  a=r {T1} b=r {V} a==b ifnotl")
    MS(DST, J, T1); INC(J)
    e("  elsel")
    MG(SRC, SI, T2); INC(SI)
    e(f"    a=r {T2} a== 0 ifl")
    MS(DST, J, V); INC(J)
    e("    elsel")
    e(f"      a=r {T2} a== 255 ifl")
    MG(SRC, SI, T3); INC(SI); MG(SRC, SI, T4); INC(SI)
    e(f"        a=r {T3} a<<= 8 b=r {T4} a+=b r=a {T2}"); LK(31 << 8); e(f"        b=a a=r {T2} a+=b r=a {T2}")
    e("      elsel")
    e(f"        a=r {T2} a> 223 ifl")
    MG(SRC, SI, T3); INC(SI)
    e(f"          a=r {T2} a-= 224 a<<= 8 b=r {T3} a+=b a+= 224 r=a {T2}")
    e("        endif")
    e("      endif")
    e(f"      a=r {T2} a+= 2 r=a {T2} a=r {J} a-- r=a {T3}"); MG(DST, T3, T3)
    e(f"      a=r {DST} b=r {J} a+=b c=a")
    e("      do")
    e(f"        a=r {T3} *c=a c++ a=r {T2} a-- r=a {T2} a> 0")
    e("      while")
    e(f"      a=c b=r {DST} a-=b r=a {J}")
    e("    endif")
    e("  endif")
    e(f"  a=r {SI} b=r {LEN} a<b")
    e("while")
    e("endif")
    e(f"a=r {J} r=a {LEN}")

def DEBUGSTOP(k):
    if STAGE == k:
        OUTBUF(); e("halt")

# ----------------------------------------------------------------- principal
e("hcomp")
e("halt")
e("pcomp zpaqkanzi8b ;" if ROBUST else "pcomp zpaqkanzi8 ;")
e("""(ZPAQKANZI8: decodificador de kanzi 2.6.0, bitstream 7 sin cabecera, niveles 8
 EXE+RLT+TEXT+UTF+DNA con TPAQ y 9 lo mismo con TPAQX, en ZPAQL, para zpaq-std
 -ma:kanzi. zpaq-std, 2026. Guarda la entrada en M y decodifica al final. La entrada
 lleva el diccionario estatico de kanzi detras de la cabecera.)""")
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
TABLES()
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
TPAQDEC()
e("        endif")
e(f"        a=r {XB} r=a {SRC} r=a {PS} a=r {YB} r=a {DST} r=a {PD} a=r {PRE} r=a {LEN}")
DEBUGSTOP(0)
e(f"        a=0 r=a {CIN} a= 1 r=a {COUT}")       # 0 in, 1 out, 2 buf
for stage, (ti, macro) in enumerate([(4, PACK), (3, UTF), (2, TEXT), (1, RLT), (0, EXE)], 1):
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
