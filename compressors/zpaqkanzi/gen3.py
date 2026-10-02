#!/usr/bin/env python3
# Generador de ZPAQKANZI3: decodificador de kanzi 2.6.0 (bitstream 7, sin cabecera),
# niveles 3 (TEXT+UTF+PACK+MM+LZX, Huffman) y 4 (TEXT+UTF+EXE+PACK+MM+ROLZ, sin
# entropia), en ZPAQL. zpaq-std, 2026. ZPAQL no tiene subrutinas: las macros se
# expanden en linea. Traduccion de ref3.py.
#
# Reusa, extrayendolas por nombre, las macros ya verificadas de gen.py (Huffman, LZX)
# y gen5.py (alfabeto, varint, TEXT, UTF). Esos dos programas estan congelados; este
# generador solo las lee.
#
# Entrada del PCOMP: orig (4 LE), nivel (1), el diccionario estatico de kanzi (DLEN
# bytes), el flujo headerless.
# M: la entrada desde 0; 128 ceros; X e Y (BUFSZ cada uno); el area de ROLZ (4 x
# BUFSZ: literales, tokens, largos, indices); la tabla f2s de ANS (256 << 15).
# H: tablas chicas abajo; desde HBIG las coincidencias de ROLZ o las tablas de TEXT.
# Modo DEBUG: env STAGE=k -> emite la salida de la etapa k (0 entropia, 1 ROLZ, 2 LZX,
# 3 MM, 4 PACK, 5 EXE, 6 UTF, 7 TEXT) del primer bloque y termina.
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
# ANS
ST0 = REG(4)
LRG, SCALE, MASK, PB, CNTE, HN, CHK, DIM, CTX, SZB = [REG() for _ in range(10)]
PRV0, PRV1, PRV2, PRV3, C0, C1, C2, C3 = [REG() for _ in range(8)]
# TEXT
HMASK, DSIZE, SDS, WORDS, ANCHOR, WRUN, CRLF, VAR, OUTLEN, DE = [REG() for _ in range(10)]
# Huffman y LZX (nombres de gen.py; su LOG2 se llama LOG2R aca)
CUR, LOG2R, BASE, CODE, CL, Q, FP, P, S, L = [REG() for _ in range(10)]
SZ0 = REG(4)
TK, MI, ML, SE, MM, SI, DI, R0, R1, TOK, MLEN, DIST, LIT = [REG() for _ in range(13)]
# EXE / FSD
CS, CE, DIST2, COD, BUCK, JMP = [REG() for _ in range(6)]
# ROLZ
RAREA, F2SM, RLB, RTB, RNB, RMB, RPOS, DEND, REND, RSTART, RSZC = [REG() for _ in range(11)]
RLO, RMM, RDELTA, RLPC, RMSK, RLIT, RTKL, RMLL, RMIL = [REG() for _ in range(9)]
RLI, RTI, RMII, RLNI, RBASE, RDI, KEY, RREF, RFIN, SAVEPOS = [REG() for _ in range(10)]
KX0, KX1, KX2, KX3 = [REG() for _ in range(4)]

# --- H (palabras)
HT, HSIZE, HCNT, HORD = 0, 4096, 4352, 4400   # Huffman de gen.py (HT tiene que ser 0)
H_ALPH = 4656
H_F = 4912
H_SPTR = 5168; H_SLEN = 6192; H_SHASH = 7216     # diccionario estatico, 1024 c/u
H_UVAL = 8240; H_ULEN = 41008                    # UTF, 32768 c/u
H_CT = 73776                                     # tipos de caracter
H_IDX2 = 74032; H_MAP = 74048                    # PACK
H_CNT16 = 74304                                  # ROLZ: contadores
H_CUM = 139840; H_FQ = 205376                    # ANS: 256 contextos x 256
HBIG = 1 << 19
assert H_FQ + 65536 <= HBIG
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
# los nombres que usa gen.py
def MB(basereg, idxreg): e(f"a=r {basereg} b=r {idxreg} a+=b c=a a=*c")
def MBSET(basereg, idxreg, valreg): MS(basereg, idxreg, valreg)
def HGETK(base, idxreg, dst): HG(base, idxreg, dst)
def HSETK(base, idxreg, valreg): HS(base, idxreg, valreg)
def LE32(basereg, off, dst):
    e(f"a=r {basereg} a+= {off + 3} c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a {dst}")

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
# gen.py: Huffman escribe M[AB + ..] (aca XB); LZ escribe M[BB + ..] (aca DST)
extract('gen.py', ['HUFFMAN', 'RL', 'LZ'], [(r'\bLOG2\b', 'LOG2R'), (r'\bAB\b', 'XB'), (r'\bBB\b', 'DST')])
extract('gen5.py', ['LOG2', 'VARINT', 'ALPHABET', 'UTF', 'EG', 'ES', 'CTYPE', 'HASHSTEP', 'STATICDICT', 'TEXT', 'OUTBUF'])

# el ALPHABET de gen5.py toma el modo "completo" siempre como 256 simbolos: ANS de orden
# 1 manda los contextos vacios como completo + bit 1 (0 simbolos)
_ALPHABET5 = ALPHABET
def ALPHABET():
    e(f"a=0 r=a {K}")
    WORD(); e("a>>= 30 a== 1")               # 01: completo, vacio
    e("ifl")
    INC(POS, 2)
    e("elsel")
    _ALPHABET5()
    e("endif")

# ----------------------------------------------------------------- ANS orden 0 y 1
def ANS(order, chunk, cntreg, dstreg):
    """M[r dst .. + r cnt) = ANS de orden 0/1 desde el bit POS (ans_decode de ref3.py)."""
    e(f"a=r {cntreg} a< 33 ifl")
    FOR(II, cntreg, lambda: (GETK(8, T1), MS(dstreg, II, T1)))
    e("elsel")
    e(f"a=0 r=a {CNTE}")
    e("do")
    e(f"a=r {cntreg} b=r {CNTE} a-=b r=a {HN}"); LK(min(chunk << (8 * order), 1 << 27)); e(f"b=a a=r {HN} a>b ifl a=b r=a {HN} endif")
    GETK(3, LRG); INC(LRG, 8)
    e(f"a= 1 b=r {LRG} a<<=b r=a {SCALE} a-- r=a {MASK}")
    SET(DIM, 255 * order + 1)
    e(f"a=0 r=a {T6} r=a {CTX}")       # T6 = simbolo unico + 1 (orden 0)
    e("do")
    ALPHABET()
    e(f"a=r {K} a== 0 ifl")
    # contexto vacio (orden 1): f2s a 0, simbolo 0 con frecuencia scale-1
    e(f"  a=r {CTX} b=r {LRG} a<<=b b=r {F2SM} a+=b r=a {T4} a=r {SCALE} r=a {T5}")
    e("  do")
    e(f"    a=r {T4} c=a a=0 *c=a a=r {T4} a++ r=a {T4} a=r {T5} a-- r=a {T5} a> 0")
    e("  while")
    e(f"  a=r {CTX} a<<= 8 r=a {T4} a=0 r=a {T5}"); HS(H_CUM, T4, T5)
    e(f"  a=r {SCALE} a-- r=a {T5}"); HS(H_FQ, T4, T5)
    e("elsel")
    FORK(II, 256, lambda: (e(f"a=0 r=a {T1}"), HS(H_F, II, T1)))
    e(f"a=0 r=a {T2}")
    e(f"a=r {K} a> 63 ifl a= 8 elsel a= 6 endif r=a {CHK}")
    e(f"a= 1 r=a {II}")
    e(f"a=r {II} b=r {K} a<b ifl")
    e("do")
    GETK(4, T4)
    e(f"a=r {II} b=r {CHK} a+=b r=a {JJ} b=r {K} a>b ifl a=b r=a {JJ} endif")
    e(f"a=r {II} r=a {KK}")
    e("do")
    e(f"a=r {T4} a== 0 ifl a= 1 r=a {T5} elsel")
    GETR(T4, T5); INC(T5)
    e("endif")
    HG(H_ALPH, KK, T3); HS(H_F, T3, T5)
    e(f"a=r {T2} b=r {T5} a+=b r=a {T2}")
    INC(KK); e(f"a=r {KK} b=r {JJ} a<b")
    e("while")
    e(f"a=r {JJ} r=a {II} b=r {K} a<b")
    e("while")
    e("endif")
    e(f"a=r {SCALE} b=r {T2} a-=b r=a {T5} a=0 r=a {T3}"); HG(H_ALPH, T3, T3); HS(H_F, T3, T5)
    if order == 0:
        e(f"a=r {K} a== 1 ifl a=r {T3} a++ r=a {T6} endif")
    e(f"a=0 r=a {T2}")
    def body():
        HG(H_F, II, T3)
        e(f"a=r {T3} a> 0 ifl")
        e(f"a=r {CTX} a<<= 8 b=r {II} a+=b r=a {T4}"); HS(H_CUM, T4, T2)
        e(f"a=r {SCALE} a-- b=a a=r {T3} a>b ifl a=b endif r=a {T5}"); HS(H_FQ, T4, T5)
        e(f"a=r {CTX} b=r {LRG} a<<=b b=r {T2} a+=b b=r {F2SM} a+=b r=a {T4} a=r {T3} r=a {T5}")
        e("do")
        e(f"a=r {T4} c=a a=r {II} *c=a a=r {T4} a++ r=a {T4} a=r {T5} a-- r=a {T5} a> 0")
        e("while")
        e(f"a=r {T2} b=r {T3} a+=b r=a {T2}")
        e("endif")
    FORK(II, 256, body)
    e("endif")
    INC(CTX); e(f"a=r {CTX} b=r {DIM} a<b")
    e("while")
    e(f"a=r {T6} a> 0 ifl")                 # orden 0 con un solo simbolo: sin payload
    e(f"a=r {T6} a-- r=a {T6}")
    FOR(II, HN, lambda: (e(f"a=r {CNTE} b=r {II} a+=b r=a {T1}"), MS(dstreg, T1, T6)))
    e("elsel")
    VARINT(SZB)
    for k in range(4): GET32(ST0 + k)
    e(f"a=r {POS} r=a {PB}")
    e(f"a=r {HN} a>>= 2 a<<= 2 r=a {T1}")   # count4
    def step(k, ctxreg, symreg):            # x = fq*(x>>lr) + (x&mask) - cum; renormalizar
        st = ST0 + k
        e(f"a=r {ctxreg} a<<= 8 b=r {symreg} a+=b r=a {T4}"); HG(H_FQ, T4, T5); HG(H_CUM, T4, T3)
        e(f"a=r {st} b=r {LRG} a>>=b b=r {T5} a*=b r=a {T5}")
        e(f"a=r {st} b=r {MASK} a&=b b=r {T5} a+=b b=r {T3} a-=b r=a {st}")
        LK(32768); e(f"b=a a=r {st} a<b ifl")
        WORD(PB); e(f"a>>= 16 r=a {T5} a=r {PB} a+= 16 r=a {PB}")
        e(f"a=r {st} a<<= 16 b=r {T5} a+=b r=a {st}")
        e("endif")
    def f2s(k, ctxreg, dst):
        e(f"a=r {ctxreg} b=r {LRG} a<<=b b=r {F2SM} a+=b r=a {T4} a=r {ST0 + k} b=r {MASK} a&=b b=r {T4} a+=b c=a a=*c r=a {dst}")
    e(f"a=0 r=a {II}")
    e(f"a=r {T1} a> 0 ifl")
    if order == 0:
        e(f"a=0 r=a {CTX}")
        e("do")
        for k, si in ((3, 0), (2, 1), (1, 2), (0, 3)):
            f2s(k, CTX, T2)
            e(f"a=r {CNTE} b=r {II} a+=b a+= {si} r=a {T4}"); MS(dstreg, T4, T2)
            step(k, CTX, T2)
        INC(II, 4); e(f"a=r {II} b=r {T1} a<b")
        e("while")
    else:
        e(f"a=r {T1} a>>= 2 r=a {Q}")
        e(f"a=0 r=a {PRV0} r=a {PRV1} r=a {PRV2} r=a {PRV3}")
        PC = ((PRV0, C0), (PRV1, C1), (PRV2, C2), (PRV3, C3))
        e("do")
        for k, (prv, cur) in enumerate(PC): f2s(k, prv, cur)
        for k in (3, 2, 1, 0): step(k, PC[k][0], PC[k][1])
        for k, (prv, cur) in enumerate(PC):
            e(f"a=r {CNTE} b=r {II} a+=b" + f" b=r {Q} a+=b" * k + f" r=a {T4}"); MS(dstreg, T4, cur)
            e(f"a=r {cur} r=a {prv}")
        INC(II); e(f"a=r {II} b=r {Q} a<b")
        e("while")
    e("endif")
    e(f"a=r {T1} r=a {II} b=r {HN} a<b ifl")
    e("do")
    WORD(PB); e(f"a>>= 24 r=a {T3} a=r {PB} a+= 8 r=a {PB}")
    e(f"a=r {CNTE} b=r {II} a+=b r=a {T4}"); MS(dstreg, T4, T3)
    INC(II); e(f"a=r {II} b=r {HN} a<b")
    e("while")
    e("endif")
    e(f"a=r {SZB} a<<= 3 b=r {POS} a+=b r=a {POS}")
    e("endif")
    e(f"a=r {CNTE} b=r {HN} a+=b r=a {CNTE} b=r {cntreg} a<b")
    e("while")
    e("endif")

# ----------------------------------------------------------------- PACK (AliasCodec)
def PACK():                     # M[SRC..+LEN) -> M[DST..), LEN (dna_inverse de ref.py)
    e(f"a=0 r=a {J} r=a {T1}"); MG(SRC, T1, DE)
    e(f"a=r {DE} a> 239 ifl")
    e(f"  a= 1 a<<= 8 b=r {DE} a-=b r=a {DE}")
    e(f"  a=r {DE} a== 1 ifl")
    e(f"    a= 1 r=a {T1}"); MG(SRC, T1, V); LE32(SRC, 2, T2)
    FOR(II, T2, lambda: (MS(DST, J, V), INC(J)))
    e("  elsel")
    FOR(II, DE, lambda: (e(f"a=r {II} a++ r=a {T1}"), MG(SRC, T1, T1), HS(H_IDX2, II, T1)))
    e(f"    a=r {DE} a++ r=a {T1}"); MG(SRC, T1, T3); e(f"    a=r {DE} a+= 2 r=a {SI}")   # T3 = adjust
    e(f"    a=r {DE} a< 5 ifl")
    FOR(II, T3, lambda: COPY1())
    e(f"      a=r {SI} b=r {LEN} a<b ifl")
    e("        do")
    MG(SRC, SI, V); INC(SI)
    for sh in (6, 4, 2, 0):
        e(f"          a=r {V} a>>= {sh} a&= 3 r=a {T1}"); HG(H_IDX2, T1, T1); MS(DST, J, T1); INC(J)
    e(f"          a=r {SI} b=r {LEN} a<b")
    e("        while")
    e("      endif")
    e("    elsel")
    e(f"      a=r {T3} a> 0 ifl"); COPY1(); e("      endif")
    e(f"      a=r {SI} b=r {LEN} a<b ifl")
    e("        do")
    MG(SRC, SI, V); INC(SI)
    e(f"          a=r {V} a>>= 4 r=a {T1}"); HG(H_IDX2, T1, T1); MS(DST, J, T1); INC(J)
    e(f"          a=r {V} a&= 15 r=a {T1}"); HG(H_IDX2, T1, T1); MS(DST, J, T1); INC(J)
    e(f"          a=r {SI} b=r {LEN} a<b")
    e("        while")
    e("      endif")
    e("    endif")
    e("  endif")
    e("elsel")
    e(f"  a= 1 r=a {T1}"); MG(SRC, T1, T3)
    e(f"  a=r {LEN} b=r {T3} a-=b r=a {T4} a= 2 r=a {SI}")     # T3 adjust, T4 fin
    FORK(II, 256, lambda: (e(f"a= 1 a<<= 16 b=r {II} a+=b r=a {T1}"), HS(H_MAP, II, T1)))
    def ent():
        e(f"a=r {SI} a+= 2 r=a {T1}"); MG(SRC, T1, T2)
        MG(SRC, SI, T1); INC(SI); MG(SRC, SI, T5); INC(SI); INC(SI)
        e(f"a=r {T5} a<<= 8 b=r {T1} a+=b r=a {T1} a= 2 a<<= 16 b=r {T1} a+=b r=a {T1}"); HS(H_MAP, T2, T1)
    FOR(KK, DE, ent)
    e(f"  a=r {SI} b=r {T4} a<b ifl")
    e("    do")
    MG(SRC, SI, T1); INC(SI); HG(H_MAP, T1, V)
    e(f"      a=r {V} a&= 255 r=a {T1}"); MS(DST, J, T1); INC(J)
    e(f"      a=r {V} a>>= 16 a== 2 ifl a=r {V} a>>= 8 a&= 255 r=a {T1}"); MS(DST, J, T1); INC(J); e("      endif")
    e(f"      a=r {SI} b=r {T4} a<b")
    e("    while")
    e("  endif")
    e(f"  a=r {T3} a> 0 ifl"); COPY1(); e("  endif")
    e("endif")
    e(f"a=r {J} r=a {LEN}")

# ----------------------------------------------------------------- MM (FSDCodec)
def FSD():                      # M[SRC..+LEN) -> M[DST..), LEN; CAP
    e(f"a=0 r=a {T1}"); MG(SRC, T1, T1)
    e(f"a=r {T1} a&= 1 r=a {COD} a=r {T1} a&= 2 r=a {BUCK}")
    e(f"a= 1 r=a {T1}"); MG(SRC, T1, DIST2)
    e(f"a=r {LEN} a-= 2 r=a {T7}")                       # dataLength
    FOR(II, DIST2, lambda: (e(f"a=r {II} a+= 2 r=a {T1}"), MG(SRC, T1, T2), MS(DST, II, T2)))
    e(f"a=r {DIST2} a+= 2 r=a {SI} a=r {DIST2} r=a {J}")
    def one(posreg):            # dst[pos] = f(src[si++], dst[pos - dist])
        MG(SRC, SI, T2); INC(SI)
        e(f"a=r {posreg} b=r {DIST2} a-=b r=a {T3}"); MG(DST, T3, T3)
        e(f"a=r {COD} a== 0 ifl")
        e(f"  a=r {T2} a&= 1 a> 0 ifl a=r {T2} a>>= 1 a++ b=a a=r {T3} a-=b elsel a=r {T2} a>>= 1 b=r {T3} a+=b endif a&= 255 r=a {T2}")
        e("elsel")
        e(f"  a=r {T2} b=r {T3} a^=b r=a {T2}")
        e("endif")
        MS(DST, posreg, T2)
    e(f"a=r {BUCK} a> 0 ifl")
    e(f"  a=r {DIST2} a<<= 15 r=a {T5} a=0 r=a {T6}")   # tl, ts
    e(f"  a=r {T6} b=r {T7} a<b ifl")
    e("  do")
    e(f"    a=r {T6} b=r {T5} a+=b b=r {T7} a>b ifl a=b endif r=a {T8}")   # te
    e(f"    a=0 r=a {KK}")
    e("    do")
    e(f"      a=r {T6} a== 0 ifl a=r {DIST2} elsel a=0 endif b=r {KK} a+=b b=r {T6} a+=b r=a {J}")
    e(f"      a=r {J} b=r {T8} a<b ifl")
    e("      do")
    one(J)
    e(f"        a=r {J} b=r {DIST2} a+=b r=a {J} b=r {T8} a<b")
    e("      while")
    e("      endif")
    INC(KK); e(f"      a=r {KK} b=r {DIST2} a<b")
    e("    while")
    e(f"    a=r {T8} r=a {T6} b=r {T7} a<b")
    e("  while")
    e("  endif")
    e(f"  a=r {T7} r=a {J}")
    e("elsel")
    def cond(): e(f"  a=r {SI} b=r {LEN} a<b ifl a=r {J} b=r {CAP} a<b ifl a= 1 elsel a=0 endif elsel a=0 endif a> 0")
    cond(); e("  ifl")
    e("  do")
    one(J); INC(J)
    cond()
    e("  while")
    e("  endif")
    e("endif")
    e(f"a=r {J} r=a {LEN}")

# ----------------------------------------------------------------- EXE (EXECodec)
def COPY1():                    # dst[J++] = src[SI++]
    MG(SRC, SI, T1); MS(DST, J, T1); INC(SI); INC(J)
def EXE():
    e(f"a=0 r=a {T1}"); MG(SRC, T1, T7)                  # modo
    LE32(SRC, 1, CS); LE32(SRC, 5, CE)
    e(f"a= 9 r=a {SI} a=0 r=a {J}")
    FOR(II, CS, COPY1)
    e(f"a=r {T7} a== 64 ifl")
    # x86. JMP: 0 seguir, 1 salto en src[SI], 2 cortar
    e(f"  a=r {SI} b=r {CE} a<b ifl")
    e("  do")
    e(f"    a=0 r=a {JMP}"); MG(SRC, SI, X)
    e(f"    a=r {X} a== 15 ifl")
    e(f"      a=r {SI} a++ b=r {CE} a<b ifnotl")
    COPY1(); e(f"        a= 2 r=a {JMP}")
    e("      elsel")
    COPY1(); MG(SRC, SI, X)
    e(f"        a=r {X} a&= 240 a== 128 ifl a= 1 r=a {JMP} elsel")
    e(f"          a=r {X} a== 155 ifl"); INC(SI); e("          endif")
    COPY1()
    e("        endif")
    e("      endif")
    e("    elsel")
    e(f"      a=r {X} a&= 254 a== 232 ifl a= 1 r=a {JMP} elsel")
    e(f"        a=r {X} a== 155 ifl"); INC(SI); e("        endif")
    COPY1()
    e("      endif")
    e("    endif")
    e(f"    a=r {JMP} a== 1 ifl")
    # off = (BE32(src+si+1) ^ 0xF0F0F0F0) - J ; negativo: -((-off) & 0xFFFFFF)
    e(f"      a=r {SRC} b=r {SI} a+=b a++ c=a a=*c a<<= 8 c++ a+=*c a<<= 8 c++ a+=*c a<<= 8 c++ a+=*c r=a {T2}")
    LK(0xF0F0F0F0); e(f"      b=r {T2} a^=b b=r {J} a-=b r=a {T2}")
    e(f"      a>>= 31 a> 0 ifl a=0 b=r {T2} a-=b a<<= 8 a>>= 8 b=a a=0 a-=b r=a {T2} endif")
    COPY1()
    for sh in (0, 8, 16, 24):
        e(f"      a=r {T2} a>>= {sh} a&= 255 r=a {T3}"); MS(DST, J, T3); INC(J)
    INC(SI, 4)
    e("    endif")
    e(f"    a=r {JMP} a< 2 ifl a=r {SI} b=r {CE} a<b elsel a=0 a> 0 endif")
    e("  while")
    e("  endif")
    e("elsel")
    # ARM64: B (0x14000000) y BL (0x94000000)
    e(f"  a=r {SI} b=r {CE} a<b ifl")
    e("  do")
    e(f"    a=r {SRC} b=r {SI} a+=b a+= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a {T2}")
    e(f"    a>>= 26 a<<= 26 r=a {T3} a=0 r=a {JMP}")
    LK(0x14000000); e(f"    b=r {T3} a==b ifl a= 1 r=a {JMP} endif")
    LK(0x94000000); e(f"    b=r {T3} a==b ifl a= 1 r=a {JMP} endif")
    e(f"    a=r {JMP} a== 0 ifl")
    FORK(KK, 4, COPY1)
    e("    elsel")
    e(f"      a=r {T2} a<<= 6 a>>= 4 r=a {T4}")            # addr
    e(f"      a=r {T4} a== 0 ifl")
    INC(SI, 4); FORK(KK, 4, COPY1)
    e("      elsel")
    e(f"        a=r {T4} b=r {J} a-=b a>>= 2 a<<= 6 a>>= 6 b=r {T3} a|=b r=a {T5}")
    for sh in (0, 8, 16, 24):
        e(f"        a=r {T5} a>>= {sh} a&= 255 r=a {T1}"); MS(DST, J, T1); INC(J)
    INC(SI, 4)
    e("      endif")
    e("    endif")
    e(f"    a=r {SI} b=r {CE} a<b")
    e("  while")
    e("  endif")
    e("endif")
    e(f"a=r {SI} b=r {LEN} a<b ifl")
    e("do")
    COPY1()
    e(f"a=r {SI} b=r {LEN} a<b")
    e("while")
    e("endif")
    e(f"a=r {J} r=a {LEN}")

# ----------------------------------------------------------------- ROLZ (ROLZCodec1)
def RLEN(posreg, dst):          # readLength sobre M[RNB + pos]: hasta 4 bytes de 7 bits
    MG(RNB, posreg, dst); INC(posreg)
    e(f"a=r {dst} a> 127 ifl")
    e(f"  a=r {dst} a&= 127 r=a {dst}")
    for depth in range(3):
        MG(RNB, posreg, T8); INC(posreg)
        e(f"  a=r {dst} a<<= 7 r=a {dst} a=r {T8} a&= 127 b=r {dst} a+=b r=a {dst}")
        if depth < 2: e(f"  a=r {T8} a> 127 ifl")
    e("  endif endif")
    e("endif")

def ROLZ_KEY(posreg, dst):      # clave de out[base + pos - delta]
    e(f"a=r {RBASE} b=r {posreg} a+=b b=r {RDELTA} a-=b b=r {DST} a+=b r=a {T1}")
    e(f"a=r {RMM} a== 3 ifl")
    e(f"  a=r {T1} a++ c=a a=*c a<<= 8 c-- a+=*c r=a {dst}")
    e("elsel")
    # ((LE64 * 200002979) >> 40) & 0xFFFF, en limbs de 16 bits
    for k, rk in enumerate((KX0, KX1, KX2, KX3)):
        e(f"  a=r {T1} a+= {2 * k + 1} c=a a=*c a<<= 8 c-- a+=*c r=a {rk}")
    H0, H1 = 200002979 & 0xFFFF, 200002979 >> 16
    def mul(xr, h, d): LK(h); e(f"  b=r {xr} a*=b r=a {d}")
    mul(KX0, H0, T2)                                   # c0
    mul(KX1, H0, T3); mul(KX0, H1, T4)                 # c1 = c1a + c1b
    e(f"  a=r {T2} a>>= 16 r=a {T5} a=r {T3} a<<= 16 a>>= 16 b=r {T5} a+=b r=a {T5} a=r {T4} a<<= 16 a>>= 16 b=r {T5} a+=b")
    e(f"  a>>= 16 r=a {T5} a=r {T3} a>>= 16 b=r {T5} a+=b r=a {T5} a=r {T4} a>>= 16 b=r {T5} a+=b r=a {T5}")   # acarreo al bit 32
    mul(KX2, H0, T2); mul(KX1, H1, T3)                 # c2
    e(f"  a=r {T2} b=r {T5} a+=b b=r {T3} a+=b r=a {T5}")
    mul(KX3, H0, T2); mul(KX2, H1, T3)                 # c3 (desde el bit 48)
    e(f"  a=r {T2} b=r {T3} a+=b a<<= 16 b=r {T5} a+=b a>>= 8 a<<= 16 a>>= 16 r=a {dst}")
    e("endif")

def MATCHSLOT(dst):             # r dst = HBIG + (KEY << lpc) + a  (a = contador)
    e(f"r=a {T6} a=r {KEY} b=r {RLPC} a<<=b b=r {T6} a+=b b=a"); LK(HBIG); e(f"a+=b r=a {dst}")

def ROLZ():                     # M[SRC..+LEN) -> M[DST..), LEN
    e(f"a=r {SRC} c=a a=*c a<<= 8 c++ a+=*c a<<= 8 c++ a+=*c a<<= 8 c++ a+=*c a-= 4 r=a {DEND}")
    e(f"a= 4 r=a {T1}"); MG(SRC, T1, T1)
    e(f"a=r {T1} a&= 1 r=a {RLO} a= 3 r=a {RMM} a= 2 r=a {RDELTA}")
    e(f"a=r {T1} a&= 14 a== 2 ifl a= 4 r=a {RMM} a= 8 r=a {RDELTA} endif")
    e(f"a=r {T1} a&= 14 a== 4 ifl a= 7 r=a {RMM} a= 8 r=a {RDELTA} endif")
    e(f"a=r {T1} a&= 14 a== 8 ifl a= 3 r=a {RDELTA} endif")
    e(f"a=r {T1} a>>= 4 r=a {RLPC} a= 1 b=r {RLPC} a<<=b a-- r=a {RMSK}")
    e(f"a=r {DEND} r=a {RSZC}"); LK(16 << 20); e(f"b=a a=r {RSZC} a>b ifl a=b r=a {RSZC} endif")
    FORK(II, 65536, lambda: (e(f"a=0 r=a {T1}"), HS(H_CNT16, II, T1)))
    e(f"a=r {POS} r=a {SAVEPOS}")
    e(f"a= 5 r=a {SI} a=0 r=a {RSTART} r=a {J}")
    e(f"a=r {RSTART} b=r {DEND} a<b ifl")
    e("do")
    e(f"a=r {RSTART} b=r {RSZC} a+=b b=r {DEND} a>b ifl a=b endif r=a {REND} b=r {RSTART} a-=b r=a {RSZC}")
    e(f"a=r {SRC} b=r {SI} a+=b a<<= 3 r=a {POS} r=a {RPOS}")
    GET32(RLIT); GET32(RTKL); GET32(RMLL); GET32(RMIL)
    e(f"a=r {RAREA} r=a {RLB} b=r {RLIT} a+=b a+= 8 r=a {RTB} b=r {RTKL} a+=b a+= 8 r=a {RNB} b=r {RMLL} a+=b a+= 8 r=a {RMB}")
    e(f"a=r {RLO} a> 0 ifl")
    ANS(1, 16384, RLIT, RLB)
    e("elsel")
    ANS(0, 16384, RLIT, RLB)
    e("endif")
    ANS(0, 32768, RTKL, RTB); ANS(0, 32768, RMLL, RNB); ANS(0, 32768, RMIL, RMB)
    e(f"a=r {RNB} b=r {RMLL} a+=b c=a a=0 *c=a c++ *c=a c++ *c=a c++ *c=a")
    e(f"a=r {POS} b=r {RPOS} a-=b a+= 7 a>>= 3 b=r {SI} a+=b r=a {SI}")
    e(f"a=r {J} r=a {RBASE}")
    e(f"a=r {RTKL} a== 0 ifl")
    FOR(II, RSZC, lambda: (MG(RLB, II, T1), MS(DST, J, T1), INC(J)))
    e("elsel")
    e(f"a= 1 a<<= 16 b=r {RLPC} a<<=b r=a {T1}"); LK(HBIG); e("d=a")
    e(f"a=0 r=a {II}")
    e("do")
    e(f"a=0 *d=a d++ a=r {II} a++ r=a {II} b=r {T1} a<b")
    e("while")
    e(f"a=0 r=a {RLI} r=a {RTI} r=a {RMII} r=a {RLNI} r=a {RDI}")
    e(f"a=r {DEND} b=r {RBASE} a-=b r=a {T2} a> 8 ifl a= 8 r=a {T2} endif")
    FOR(II, T2, lambda: (MG(RLB, RLI, T1), MS(DST, J, T1), INC(RLI), INC(J), INC(RDI)))
    e(f"a=r {RDI} b=r {RSZC} a<b ifl")
    e("do")
    e(f"  a=0 r=a {RFIN}")
    MG(RTB, RTI, TOK); INC(RTI)
    e(f"  a=r {TOK} a&= 7 r=a {MLEN} a== 7 ifl")
    RLEN(RLNI, T2); e(f"    a=r {MLEN} b=r {T2} a+=b b=r {RMM} a+=b r=a {MLEN}")
    e(f"  elsel a=r {MLEN} b=r {RMM} a+=b r=a {MLEN} endif")
    e(f"  a=r {TOK} a>>= 3 r=a {LIT}")
    e(f"  a=r {TOK} a> 247 ifl"); RLEN(RLNI, T2); e(f"    a=r {T2} a+= 31 r=a {LIT} endif")
    e(f"  a=r {LIT} a> 0 ifl")
    FOR(II, LIT, lambda: (MG(RLB, RLI, T1), MS(DST, J, T1), INC(RLI), INC(J)))
    e(f"    a=0 r=a {KK} r=a {T7}")                      # k, inc
    e("    do")
    e(f"      a=r {RDI} b=r {KK} a+=b r=a {T8}"); ROLZ_KEY(T8, KEY)
    HG(H_CNT16, KEY, T2); e(f"      a=r {T2} a++ b=r {RMSK} a&=b r=a {T2}"); HS(H_CNT16, KEY, T2)
    e(f"      a=r {T2}"); MATCHSLOT(T3); e(f"      a=r {T3} d=a a=r {T8} *d=a")
    e(f"      a=r {T7} a>>= 6 b=r {KK} a+=b a++ r=a {KK} a=r {T7} a++ r=a {T7}")
    e(f"      a=r {KK} b=r {LIT} a<b")
    e("    while")
    e(f"    a=r {RDI} b=r {LIT} a+=b r=a {RDI} b=r {RSZC} a<b ifnot a= 1 r=a {RFIN} endif")
    e("  endif")
    e(f"  a=r {RFIN} a== 0 ifl")
    ROLZ_KEY(RDI, KEY)                                     # (usa T1..T5)
    HG(H_CNT16, KEY, T2)
    MG(RMB, RMII, T4); INC(RMII)                           # mIdx
    e(f"    a=r {T2} b=r {T4} a-=b b=r {RMSK} a&=b"); MATCHSLOT(T3); e(f"    a=r {T3} d=a a=*d r=a {RREF}")
    e(f"    a=r {T2} a++ b=r {RMSK} a&=b r=a {T2}"); HS(H_CNT16, KEY, T2)
    e(f"    a=r {T2}"); MATCHSLOT(T3); e(f"    a=r {T3} d=a a=r {RDI} *d=a")
    e(f"    a=r {DST} b=r {RBASE} a+=b b=r {RREF} a+=b r=a {T4} a=r {DST} b=r {J} a+=b r=a {T5}")
    e(f"    a=r {MLEN} a> 0 ifl")
    e("    do")
    e(f"      a=r {T4} c=a a=*c b=a a=r {T5} c=a a=b *c=a a=r {T4} a++ r=a {T4} a=r {T5} a++ r=a {T5}")
    e(f"      a=r {MLEN} a-- r=a {MLEN} a> 0")
    e("    while")
    e("    endif")
    e(f"    a=r {T5} b=r {DST} a-=b r=a {J} b=r {RBASE} a-=b r=a {RDI}")
    e(f"    a=r {RDI} b=r {RSZC} a<b ifnot a= 1 r=a {RFIN} endif")
    e("  endif")
    e(f"  a=r {RFIN} a== 0")
    e("while")
    e("endif")
    e("endif")
    e(f"a=r {REND} r=a {RSTART} b=r {DEND} a<b")
    e("while")
    e("endif")
    FORK(KK, 4, COPY1)                                     # 4 bytes crudos del final
    e(f"a=r {SAVEPOS} r=a {POS}")
    e(f"a=r {J} r=a {LEN}")

def DEBUGSTOP(k):
    if STAGE == k:
        OUTBUF(); e("halt")

# ----------------------------------------------------------------- principal
e("hcomp")
e("halt")
e("pcomp zpaqkanzi3b ;" if ROBUST else "pcomp zpaqkanzi3 ;")
e("""(ZPAQKANZI3: decodificador de kanzi 2.6.0, bitstream 7 sin cabecera, niveles 3
 TEXT+UTF+PACK+MM+LZX con Huffman y 4 TEXT+UTF+EXE+PACK+MM+ROLZ sin entropia, en
 ZPAQL, para zpaq-std -ma:kanzi. zpaq-std, 2026. Guarda la entrada en M y decodifica
 al final. La entrada lleva el diccionario estatico de kanzi detras de la cabecera.)""")
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
# buffers: BUFSZ = max(blk, pre+512) + 64; X en N+128, Y, ROLZ (4 x BUFSZ), f2s
e(f"      a=r {PRE} a+= 255 a+= 255 a+= 2 b=r {BLK} a<b ifl a=b endif r=a {LIN} a+= 64 r=a {BUFSZ}")
e(f"      a=r {BLK} r=a {LOUT} a=0 r=a {LBUF}")
e(f"      a=r {N} a+= 128 r=a {XB} b=r {BUFSZ} a+=b r=a {YB} b=r {BUFSZ} a+=b r=a {RAREA}")
e(f"      a=r {BUFSZ} a<<= 2 b=r {RAREA} a+=b r=a {F2SM}")
e(f"      a=r {COPY} a> 0 ifl a=r {TCOPY} a== 0 ifl a= 1 elsel a=0 endif elsel a=0 endif")
e("      a> 0 ifl")
e(f"        a=r {PRE} a> 0 ifl")
e("          do")
GETK(8, T1)
e(f"            a=r {T1} out a=r {PRE} a-- r=a {PRE} a> 0")
e("          while")
e("        endif")
e("      elsel")
e(f"        a=r {TCOPY} a> 0 ifl a= 1 elsel a=r {LEVEL} a== 4 ifl a= 1 elsel a=0 endif endif")
e("        a> 0 ifl")
FOR(II, PRE, lambda: (GETK(8, T1), MS(XB, II, T1)))
e("        elsel")
HUFFMAN()
e("        endif")
e(f"        a=r {XB} r=a {SRC} r=a {PS} a=r {YB} r=a {DST} r=a {PD} a=r {PRE} r=a {LEN}")
DEBUGSTOP(0)
e(f"        a=0 r=a {CIN} a= 1 r=a {COUT}")       # 0 in, 1 out, 2 buf
# orden de aplicacion comun a los dos niveles; (bit en nivel 3, bit en nivel 4)
STEPS = [(1, ROLZ, None, 5), (2, LZ, 4, None), (3, FSD, 3, 4), (4, PACK, 2, 3),
         (5, EXE, None, 2), (6, UTF, 1, 1), (7, TEXT, 0, 0)]
for stage, macro, b3, b4 in STEPS:
    m3 = 0 if b3 is None else 1 << (7 - b3)
    m4 = 0 if b4 is None else 1 << (7 - b4)
    # T1 = mascara del bit de esta transformacion (0 = no esta en este nivel)
    e(f"        a=r {LEVEL} a== 3 ifl a= {m3} elsel a= {m4} endif r=a {T1}")
    e(f"        a=r {T1} a> 0 ifl b=r {SKIP} a&=b a== 0 ifl a= 1 elsel a=0 endif elsel a=0 endif")
    e("        a> 0 ifl")
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
