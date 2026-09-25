# Generador de ZPAQLZHAM: flujos de LZHAM 1.0 (el de zpaq-std -ma:lzh: diccionario de
# 2^20, niveles 1-4) en ZPAQL, escrito para zpaq-std desde el codigo de lzham_decomp.
# ZPAQL no tiene subrutinas: todo son macros expandidas en linea. Mismo algoritmo que la
# referencia en Python con la que se probo (ref.py).
#   python3 gen.py salida.txt
#
# El flujo entra entero en M y se decodifica al final. M: la entrada desde 0, 32 ceros
# de relleno (LZHAM lee ceros pasado el fin) y la salida desde OB = n + 32 (entera: las
# copias miran hasta 1 MB atras). H (ph = 17): tablas de slots 0/64, modelos binarios
# 128, auxiliares de la reconstruccion 1024.., y los 134 modelos de Huffman
# cuasi-adaptativos desde 4096. Un modelo: +0 n, +1 cycle, +2 until, +3 total,
# +4 max_cycle, +8..23 limite (justificado a 16 bits) del largo L=1..16, +25..40
# indice de la lista para el largo L, +48 frecuencias, +48+n largos, +48+2n simbolos
# en orden canonico.
import sys, os
DEBUG = os.environ.get('DEBUG') == '1'
out = []
def e(s): out.append(s)

# registros
N, POS, OB, OUTP, PLIM = 1, 2, 3, 4, 5
FAST, POLAR, AV, AL, K24 = 7, 8, 9, 10, 11
H0, H1, H2, H3, ST, PC, PPC = 12, 13, 14, 15, 16, 17, 18
STOP, ERR, ML, SYM, MB, W, L = 19, 20, 21, 22, 23, 24, 25
T1, T2, SLOT, NE, EX, CONT, BT, FT = 26, 27, 28, 29, 30, 31, 32, 33
K2048, K32768 = 38, 39
# UPDATE: r40..r59
UN, UF, UC, UL = 40, 41, 42, 43
MI = 62                        # contador de modelos (FLUSH)
R0B, R1B, COPY, NEEDL, BR0 = 60, 61, 63, 64, 65

HB = dict(EB=0, DB=64, BM=128, HIST=1024, TMPA=1280, ORD=1600, MA=1920, NC=2240, NSO=2280,
          NEWL=2320, CNT=2640, OFS=2672)      # TMPA, ORD, MA y NEWL: 320 (el modelo mayor tiene 314)
BM_M, BM_R, BM_R0, BM_R0S, BM_R1, BM_R2 = 0, 768, 780, 792, 804, 816
STRIDE = 48 + 3 * 256
LITB = 4096
DLITB = LITB + 64 * STRIDE
NMAIN = 2 + 39 * 8
MAINB = DLITB + 64 * STRIDE
RL0 = MAINB + 1000
RL1 = RL0 + 820
LL0 = RL1 + 820
LL1 = LL0 + 800
DLSB = LL1 + 800
MTAB = DLSB + 100
assert MTAB + 134 < (1 << 17)
MODELS = [(LITB + i * STRIDE, 256) for i in range(64)] + [(DLITB + i * STRIDE, 256) for i in range(64)] + \
         [(MAINB, NMAIN), (RL0, 257), (RL1, 257), (LL0, 250), (LL1, 250), (DLSB, 16)]
REG = {}
for i, k in enumerate(list(HB) + ['LITB', 'DLITB', 'MAINB', 'RL0', 'RL1', 'LL0', 'LL1', 'DLSB', 'MTAB', 'K816']):
    REG[k] = 100 + i
R = lambda k: REG[k]
KV = dict(HB, LITB=LITB, DLITB=DLITB, MAINB=MAINB, RL0=RL0, RL1=RL1, LL0=LL0, LL1=LL1, DLSB=DLSB, MTAB=MTAB,
          K816=STRIDE)

def LOADK(v):
    if v < 256: e(f"a= {v}"); return
    bs = []
    while v: bs.append(v & 255); v >>= 8
    e(f"a= {bs[-1]}")
    for b in reversed(bs[:-1]):
        e(f"a<<= 8 a+= {b}" if b else "a<<= 8")

def WORD():                   # a = 32 bits desde POS, ya corridos (el bit POS arriba)
    e(f"a=r {POS} a&= 7 b=a a=r {POS} a>>= 3 c=a a=*c a<<= 8 c++ a+=*c a<<= 8 c++ a+=*c a<<= 8 c++ a+=*c a<<=b")
def GETK(k, dst):             # r dst = k bits (k inmediato 1..24), MSB primero
    WORD(); e(f"a>>= {32 - k} r=a {dst} a=r {POS} a+= {k} r=a {POS}")
def GETR(kreg, dst):          # r dst = r kreg bits (0..24)
    e(f"a=r {kreg} a> 0 ifl")
    WORD(); e(f"  r=a {T2} a= 32 b=r {kreg} a-=b b=a a=r {T2} a>>=b r=a {dst} a=r {POS} b=r {kreg} a+=b r=a {POS}")
    e(f"elsel a=0 r=a {dst} endif")
def ALIGN():
    e(f"a=r {POS} a+= 7 a>>= 3 a<<= 3 r=a {POS}")

def ARBIT():                  # a = indice absoluto en H de la probabilidad -> a = bit
    e("r=a 37")
    e(f"a=r {AL} b=r {K24} a<b ifl")
    e("  do")
    GETK(8, 36)
    e(f"    a=r {AV} a<<= 8 b=r 36 a+=b r=a {AV} a=r {AL} a<<= 8 r=a {AL} b=r {K24}")
    e("  a<b while")
    e("endif")
    e(f"a=r 37 d=a a=*d r=a 36 a=r {AL} a>>= 11 b=r 36 a*=b r=a 35")
    e(f"b=a a=r {AV} a<b ifl")
    e(f"  a=r 35 r=a {AL} a=r {K2048} b=r 36 a-=b a>>= 5 a+=b *d=a a=0")
    e("elsel")
    e(f"  a=r {AV} b=r 35 a-=b r=a {AV} a=r {AL} a-=b r=a {AL} a=r 36 a>>= 5 b=a a=r 36 a-=b *d=a a= 1")
    e("endif")

def HGET(base, idx):          # a = H[r base + r idx]
    br = R(base) if isinstance(base, str) else base
    e(f"a=r {idx} b=r {br} a+=b d=a a=*d")
def HSETA(base, idx):         # H[r base + r idx] = a (usa b, d y r 59)
    br = R(base) if isinstance(base, str) else base
    e(f"r=a 59 a=r {idx} b=r {br} a+=b d=a a=r 59 *d=a")
def FOR(i, lim, body):        # for r i in 0..lim-1 (lim: 'rN' o entero 1..256)
    e(f"a=0 r=a {i}")
    if isinstance(lim, str):
        e(f"a=r {lim[1:]} a> 0 ifl")
    e("do")
    body()
    if isinstance(lim, str):
        e(f"  a=r {i} a++ r=a {i} b=r {lim[1:]} a<b while")
        e("endif")
    elif lim == 256:
        e(f"  a=r {i} a++ r=a {i} a> 255 until")
    else:
        e(f"  a=r {i} a++ r=a {i} a< {lim} while")

def RESCALE():                # f = (f+1)>>1, total = suma
    e(f"a=0 r=a 45")
    def b():
        e(f"  a=r {UF} b=r 44 a+=b d=a a=*d a++ a>>= 1 *d=a b=a a=r 45 a+=b r=a 45")
    FOR(44, f"r{UN}", b)
    e(f"a=r {MB} a+= 3 d=a a=r 45 *d=a")

def SORT():
    """ORD (en r 58: base del resultado) = indices ordenados por frecuencia, estable."""
    FOR(44, 256, lambda: e(f"  a=0 b=r {R('HIST')} a=r 44 a+=b d=a a=0 *d=a"))
    e("a=0 r=a 46")                                    # OR de los bytes altos
    def h1():
        e(f"  a=r {UF} b=r 44 a+=b d=a a=*d r=a 45 a>>= 8 b=r 46 a|=b r=a 46")
        e(f"  a=r 45 a&= 255 b=r {R('HIST')} a+=b d=a *d++")
    FOR(44, f"r{UN}", h1)
    def pref():
        e(f"  a=r 44 b=r {R('HIST')} a+=b d=a a=*d r=a 45 a=r 47 *d=a b=r 45 a+=b r=a 47")
    e("a=0 r=a 47"); FOR(44, 256, pref)
    def pl1():
        e(f"  a=r {UF} b=r 44 a+=b d=a a=*d a&= 255 b=r {R('HIST')} a+=b d=a a=*d r=a 45 *d++")
        e(f"  a=r 45 b=r {R('TMPA')} a+=b d=a a=r 44 *d=a")
    FOR(44, f"r{UN}", pl1)
    e(f"a=r {R('TMPA')} r=a 58")
    e("a=r 46 a> 0 ifl")
    FOR(44, 256, lambda: e(f"  a=r 44 b=r {R('HIST')} a+=b d=a a=0 *d=a"))
    def h2():
        e(f"  a=r 44 b=r {R('TMPA')} a+=b d=a a=*d b=r {UF} a+=b d=a a=*d a>>= 8 b=r {R('HIST')} a+=b d=a *d++")
    FOR(44, f"r{UN}", h2)
    e("a=0 r=a 47"); FOR(44, 256, pref)
    def pl2():
        e(f"  a=r 44 b=r {R('TMPA')} a+=b d=a a=*d r=a 48 b=r {UF} a+=b d=a a=*d a>>= 8 b=r {R('HIST')} a+=b d=a a=*d r=a 45 *d++")
        e(f"  a=r 45 b=r {R('ORD')} a+=b d=a a=r 48 *d=a")
    FOR(44, f"r{UN}", pl2)
    e(f"a=r {R('ORD')} r=a 58")
    e("endif")

def AG(reg, dst):             # r dst = MA[r reg]
    e(f"a=r {reg} b=r {R('MA')} a+=b d=a a=*d r=a {dst}")
def AS(reg, src):             # MA[r reg] = r src
    e(f"a=r {reg} b=r {R('MA')} a+=b d=a a=r {src} *d=a")

def MOFFAT():
    """Largos de Huffman (Moffat-Katajainen) sobre MA[k] = f[ORD[k]], en el lugar."""
    def cp():
        e(f"  a=r 44 b=r 58 a+=b d=a a=*d b=r {UF} a+=b d=a a=*d r=a 45"); AS(44, 45)
    FOR(44, f"r{UN}", cp)
    e(f"a= 1 r=a 44"); AG(44, 45); e("a=0 r=a 44"); AG(44, 46); e("a=r 46 b=r 45 a+=b r=a 45"); AS(44, 45)
    e("a=0 r=a 46 a= 2 r=a 47 a= 1 r=a 48")          # root, leaf, next
    e(f"a=r {UN} a-- r=a 57")                         # n-1
    e("a=r 48 b=r 57 a<b ifl")
    e("do")
    for second in (False, True):
        # cond: leaf >= n  or  [root < next and]  A[root] < A[leaf]
        e(f"  a=r 47 b=r {UN} a<b ifl")
        if second:
            e("    a=r 46 b=r 48 a<b ifl")
        AG(46, 49); AG(47, 50); e("    a=r 49 b=r 50 a<b ifl a= 1 elsel a=0 endif")
        if second:
            e("    elsel a=0 endif")
        e("  elsel a= 1 endif")
        e("  a> 0 ifl")
        AG(46, 49)
        if second:
            AG(48, 50); e("    a=r 49 b=r 50 a+=b r=a 49")
        AS(48, 49); AS(46, 48); e("    a=r 46 a++ r=a 46")
        e("  elsel")
        AG(47, 49)
        if second:
            AG(48, 50); e("    a=r 49 b=r 50 a+=b r=a 49")
        AS(48, 49); e("    a=r 47 a++ r=a 47")
        e("  endif")
    e("  a=r 48 a++ r=a 48 b=r 57")
    e("a<b while")
    e("endif")
    e(f"a=r {UN} a-= 2 r=a 44 a=0 r=a 45"); AS(44, 45)
    e(f"a=r {UN} a-= 2 r=a 48")                       # next+1 desde n-2 hasta 1
    e("a=r 48 a> 0 ifl")
    e("do")
    e("  a=r 48 a-- r=a 44"); AG(44, 45); AG(45, 46); e("  a=r 46 a++ r=a 46"); AS(44, 46)
    e("  a=r 48 a-- r=a 48")
    e("a> 0 while")
    e("endif")
    # avbl r44, used r45, dpth r46, root+1 r47, next r48
    e(f"a= 1 r=a 44 a=0 r=a 45 r=a 46 a=r {UN} a-- r=a 47 r=a 48")
    e("do")
    e("  do")
    e("    a=r 47 a> 0 ifl a-- r=a 49"); AG(49, 50); e("      a=r 50 b=r 46 a==b ifl a=r 45 a++ r=a 45 a=r 47 a-- r=a 47 a= 1 elsel a=0 endif")
    e("    elsel a=0 endif")
    e("  a> 0 while")
    e("  do")
    e("    a=r 44 b=r 45 a>b ifl"); AS(48, 46); e("      a=r 48 a-- r=a 48 a=r 44 a-- r=a 44 a= 1")
    e("    elsel a=0 endif")
    e("  a> 0 while")
    e("  a=r 45 a<<= 1 r=a 44 a=r 46 a++ r=a 46 a=0 r=a 45")
    e("  a=r 44")
    e("a> 0 while")
    def back():
        e(f"  a=r 44 b=r 58 a+=b d=a a=*d r=a 49"); AG(44, 45); e("  a=r 45"); HSETA(UC, 49)
    FOR(44, f"r{UN}", back)

def POLARL():
    """Largos polares: MA[k] = log2 del tmp de rev[k] = ORD[n-1-k]."""
    e("a=0 r=a 51")                                   # tot
    def ini():
        e(f"  a=r {UN} a-- b=r 44 a-=b b=r 58 a+=b d=a a=*d b=r {UF} a+=b d=a a=*d r=a 45 b=r 51 a+=b r=a 51")
        e("  a=0 r=a 46 a=r 45 a>>= 1")
        e("  a> 0 ifl do a>>= 1 r=a 45 a=r 46 a++ r=a 46 a=r 45 a> 0 while endif")
        AS(44, 46)
        e("  a= 1 b=r 46 a<<=b b=r 52 a+=b r=a 52")
    e("a=0 r=a 52")                                   # cur
    FOR(44, f"r{UN}", ini)
    e("a=0 r=a 53 a= 1 r=a 54")                        # log2(tree), tree
    e("a=r 54 b=r 51 a<b ifl do a=r 54 a<<= 1 r=a 54 a=r 53 a++ r=a 53 a=r 54 b=r 51 a<b while endif")
    e("a=0 r=a 55")                                   # start
    e("a=r 52 b=r 54 a<b ifl")
    e("do")
    e("  a=r 55 r=a 44")
    e("  do")
    AG(44, 46); e("    a= 1 b=r 46 a<<=b r=a 47 b=r 52 a+=b r=a 48 b=a a=r 54 a<b ifl")
    e("      a=r 44 a++ r=a 55 a= 1")
    e("    elsel")
    e("      a=r 46 a++ r=a 46"); AS(44, 46); e("      a=r 48 r=a 52 b=r 54 a==b ifl a=0 elsel a= 1 endif")
    e("    endif")
    e(f"    a> 0 ifl a=r 44 a++ r=a 44 b=r {UN} a<b ifl a= 1 elsel a=0 endif endif")
    e("  a> 0 while")
    e(f"  a=r 52 b=r 54 a<b ifl a=r 55 b=r {UN} a<b ifl a= 1 elsel a=0 endif elsel a=0 endif")
    e("a> 0 while")
    e("endif")
    def back():
        e(f"  a=r {UN} a-- b=r 44 a-=b b=r 58 a+=b d=a a=*d r=a 49"); AG(44, 45)
        e("  a=r 53 b=r 45 a-=b"); HSETA(UC, 49)
    FOR(44, f"r{UN}", back)

def NCG(reg, dst): e(f"a=r {reg} b=r {R('NC')} a+=b d=a a=*d r=a {dst}")
def NCS(reg, src): e(f"a=r {reg} b=r {R('NC')} a+=b d=a a=r {src} *d=a")

def LIMIT():
    """Si hay largos > 16: el limitador de LZHAM (estilo LHArc)."""
    FOR(44, 35, lambda: e(f"  a=r 44 b=r {R('NC')} a+=b d=a a=0 *d=a"))
    e("a=0 r=a 56")                                   # maximo
    def cnt():
        HGET(UC, 44); e(f"  r=a 45 b=r 56 a>b ifl r=a 56 endif a=r 45 b=r {R('NC')} a+=b d=a *d++")
    FOR(44, f"r{UN}", cnt)
    e("a=r 56 a> 16 ifl")
    e("  a=0 r=a 45 a= 1 r=a 44")
    e("  do")
    e(f"    a=r 44 b=r {R('NSO')} a+=b d=a a=r 45 *d=a"); NCG(44, 46); e("    a=r 45 b=r 46 a+=b r=a 45")
    e("    a=r 44 a++ r=a 44 a< 35 while")
    e("  a= 17 r=a 44 a= 16 r=a 47"); NCG(47, 48)
    e("  do"); NCG(44, 46); e("    a=r 48 b=r 46 a+=b r=a 48 a=r 44 a++ r=a 44 a< 35 while")
    NCS(47, 48)
    e("  a=0 r=a 49 a= 1 r=a 44")                      # tot = sum nc[i] << (16-i)
    e("  do"); NCG(44, 46); e("    a= 16 b=r 44 a-=b b=a a=r 46 a<<=b b=r 49 a+=b r=a 49 a=r 44 a++ r=a 44 a< 17 while")
    e("  a= 1 a<<= 16 r=a 50")
    e("  a=r 49 b=r 50 a>b ifl")
    e("  do")
    NCG(47, 48); e("    a=r 48 a-- r=a 48"); NCS(47, 48)
    e("    a= 15 r=a 44")
    e("    do")
    NCG(44, 46); e("      a=r 46 a> 0 ifl a-- r=a 46"); NCS(44, 46)
    e("        a=r 44 a++ r=a 45"); NCG(45, 46); e("        a=r 46 a+= 2 r=a 46"); NCS(45, 46)
    e("        a=0")
    e("      elsel a=r 44 a-- r=a 44 endif")
    e("    a> 0 while")
    e("    a=r 49 a-- r=a 49 b=r 50 a>b")
    e("  while")
    e("  endif")
    e("  a=0 r=a 45 a= 1 r=a 44")                      # NEWL
    e("  do"); NCG(44, 46)
    e("    a=r 46 a> 0 ifl do a=r 45 b=r " + str(R('NEWL')) + " a+=b d=a a=r 44 *d=a a=r 45 a++ r=a 45 a=r 46 a-- r=a 46 a> 0 while endif")
    e("    a=r 44 a++ r=a 44 a< 17 while")
    def re():
        HGET(UC, 44); e(f"  r=a 45 a> 0 ifl b=r {R('NSO')} a+=b d=a a=*d r=a 46 *d++ a=r 46 b=r {R('NEWL')} a+=b d=a a=*d"); HSETA(UC, 44); e("  endif")
    FOR(44, f"r{UN}", re)
    e("endif")

def BUILD():
    FOR(44, 17, lambda: e(f"  a=r 44 b=r {R('CNT')} a+=b d=a a=0 *d=a"))
    def cnt():
        HGET(UC, 44); e(f"  b=r {R('CNT')} a+=b d=a *d++")
    FOR(44, f"r{UN}", cnt)
    e("a=0 r=a 45 r=a 46 a= 1 r=a 44")                  # code, ofs, L
    e("do")
    e(f"  a=r 44 b=r {R('CNT')} a+=b d=a a=*d r=a 47")
    e(f"  a=r 44 b=r {R('OFS')} a+=b d=a a=r 46 *d=a")
    e(f"  a=r 44 b=r {MB} a+=b a+= 24 d=a a=r {UL} b=r 46 a+=b b=r 45 a-=b *d=a")
    e(f"  a=r 45 b=r 47 a+=b r=a 45 a= 16 b=r 44 a-=b b=a a=r 45 a<<=b r=a 48")
    e(f"  a=r 44 b=r {MB} a+=b a+= 7 d=a a=r 48 *d=a")
    e("  a=r 46 b=r 47 a+=b r=a 46 a=r 45 a<<= 1 r=a 45")
    e("  a=r 44 a++ r=a 44 a< 17 while")
    def pl():
        HGET(UC, 44); e(f"  b=r {R('OFS')} a+=b d=a a=*d r=a 45 *d++ a=r 45 b=r {UL} a+=b d=a a=r 44 *d=a")
    FOR(44, f"r{UN}", pl)

def UPDATE():                 # modelo en r MB
    e(f"a=r {MB} d=a a=*d r=a {UN} a=r {MB} a+= 48 r=a {UF} b=r {UN} a+=b r=a {UC} a+=b r=a {UL}")
    e(f"a=r {MB} a+= 1 d=a a=*d b=a d++ d++ a=*d a+=b *d=a")
    e(f"b=r {K32768} a<b ifnotl")
    e("do")
    RESCALE()
    e(f"  a=r 45 b=r {K32768} a<b ifl a=0 elsel a= 1 endif")
    e("a> 0 while")
    e("endif")
    SORT()
    e(f"a=r {POLAR} a> 0 ifl")
    POLARL()
    e("elsel")
    MOFFAT()
    e("endif")
    LIMIT()
    BUILD()
    e(f"a=r {MB} a+= 1 d=a a=*d")
    e(f"r=a 45 a=r {FAST} a> 0 ifl a=r 45 a<<= 1 elsel a=r 45 a<<= 2 b=r 45 a+=b a>>= 2 endif")
    e(f"r=a 45 a=r {MB} a+= 4 d=a a=*d r=a 46 a=r 45 b=r 46 a>b ifl a=r 46 r=a 45 endif")
    e(f"a=r {MB} a+= 1 d=a a=r 45 *d=a d++ *d=a")
    if DEBUG:
        e(f"a=r {UN} out a>>= 8 out")
        FOR(44, f"r{UN}", lambda: (HGET(UC, 44), e("  out")))
        e(f"a=r {MB} a+= 1 d=a a=*d out a>>= 8 out")

def RESET():                  # modelo en r MB
    e(f"a=r {MB} d=a a=*d r=a {UN} a=r {MB} a+= 48 r=a {UF}")
    FOR(44, f"r{UN}", lambda: e(f"  a=r 44 b=r {UF} a+=b d=a a= 1 *d=a"))
    e(f"a=r {MB} a+= 1 d=a a=r {UN} *d=a d++ a=0 *d=a d++ *d=a")
    UPDATE()
    e(f"a=r {MB} a+= 1 d=a a= 8 *d=a d++ *d=a")

def RESET_RATE():
    e(f"a=r {MB} d=a a=*d r=a {UN} a=r {MB} a+= 48 r=a {UF}")
    e(f"a=r {MB} a+= 1 d=a a=*d r=a 44 d++ a=*d r=a 45 d++ a=r 44 b=r 45 a-=b a+=*d *d=a")
    e(f"b=r {UN} a>b ifl")
    RESCALE()
    e("endif")
    e(f"a=r {MB} a+= 1 d=a a=*d a> 8 ifl a= 8 endif *d=a d++ *d=a")

def ALLMODELS(body):
    def b():
        e(f"  a=r {MI} b=r {R('MTAB')} a+=b d=a a=*d r=a {MB}")
        body()
    FOR(MI, 134, b)

def BMINIT():
    LOADK(828); e(f"r=a 59 a=r {R('BM')} d=a a=0 r=a 44")
    e("do")
    e("  a= 4 a<<= 8 *d=a d++ a=r 44 a++ r=a 44")
    e("  b=r 59 a<b while")

def DEC():                    # r SYM = simbolo del modelo en r MB
    WORD(); e(f"a>>= 16 r=a {W}")
    e(f"a=r {MB} a+= 8 d=a a= 1 r=a {L}")
    e(f"a=r {W} a<*d ifnotl")
    e("  do")
    e(f"    d++ a=r {L} a++ r=a {L} a> 16 ifl a=0 elsel a=r {W} a<*d ifl a=0 elsel a= 1 endif endif")
    e("  a> 0 while")
    e("endif")
    e(f"a=r {L} a> 16 ifl")
    e(f"  a= 1 r=a {ERR} a=0 r=a {SYM}")
    e("elsel")
    e(f"  a= 16 b=r {L} a-=b b=a a=r {W} a>>=b r=a {T1}")
    e(f"  a=r {MB} b=r {L} a+=b a+= 24 d=a a=*d b=r {T1} a+=b d=a a=*d r=a {SYM}")
    e(f"  a=r {POS} b=r {L} a+=b r=a {POS}")
    e(f"  a=r {MB} a+= 48 b=r {SYM} a+=b d=a *d++")
    e(f"  a=r {MB} a+= 2 d=a *d-- a=*d a== 0 ifl")
    UPDATE()
    e("  endif")
    e("endif")

def HUGE():                   # r ML = largo enorme
    GETK(1, T1)
    e(f"a=r {T1} a> 0 ifl"); GETK(1, T1)
    e(f"  a=r {T1} a> 0 ifl"); GETK(1, T1)
    e(f"    a=r {T1} a> 0 ifl"); GETK(16, ML); LOADK(1538 + 4096); e(f"      b=r {ML} a+=b r=a {ML}")
    e("    elsel"); GETK(12, ML); LOADK(1538); e(f"      b=r {ML} a+=b r=a {ML} endif")
    e("  elsel"); GETK(10, ML); LOADK(514); e(f"    b=r {ML} a+=b r=a {ML} endif")
    e("elsel"); GETK(8, ML); LOADK(258); e(f"  b=r {ML} a+=b r=a {ML} endif")

def STGE7(): e(f"a=r {ST} a> 6")
def PUTB():                   # a (byte) al final de la salida
    e(f"c=r {OUTP} *c=a {'' if DEBUG else 'out '}a=c a++ r=a {OUTP}")

def FLUSH():                  # segun r FT
    e(f"a=r {FT} a== 1 ifl")
    ALLMODELS(RESET_RATE)
    e("elsel a== 2 ifl")
    ALLMODELS(RESET)
    BMINIT()
    e("endif endif")

def SYMBOL():
    e(f"a=0 r=a {COPY} a=r {ST} a<<= 6 b=a a=r {PC} a>>= 2 a+=b b=r {R('BM')} a+=b"); ARBIT()
    e("a== 0 ifl")
    STGE7()
    e("  ifl")
    e(f"    a=r {OUTP} b=r {H0} a-=b c=a a=*c r=a {R0B} c-- a=*c r=a {R1B}")
    e(f"    a=r {R1B} a>>= 5 a<<= 3 b=a a=r {R0B} a>>= 5 a+=b b=r {R('K816')} a*=b b=r {R('DLITB')} a+=b r=a {MB}")
    e("  elsel")
    e(f"    a=0 r=a {R0B}")
    e(f"    a=r {PPC} a>>= 5 a<<= 3 b=a a=r {PC} a>>= 5 a+=b b=r {R('K816')} a*=b b=r {R('LITB')} a+=b r=a {MB}")
    e("  endif")
    DEC()
    e(f"  a=r {SYM} b=r {R0B} a^=b"); PUTB()
    e(f"  a=r {PC} r=a {PPC} a=r {SYM} b=r {R0B} a^=b r=a {PC}")
    e(f"  a=r {ST} a< 4 ifl a=0 elsel a< 10 ifl a-= 3 elsel a-= 6 endif endif r=a {ST}")
    e("elsel")
    e(f"  a= 1 r=a {ML} r=a {COPY}")
    LOADK(BM_R); e(f"  r=a 59 a=r {ST} b=r {R('BM')} a+=b b=r 59 a+=b"); ARBIT()
    e("  a> 0 ifl")
    e(f"    a=0 r=a {NEEDL}")
    LOADK(BM_R0)
    e(f"    r=a 59 a=r {ST} b=r {R('BM')} a+=b b=r 59 a+=b"); ARBIT(); e(f"    r=a {BR0}")
    e("    a> 0 ifl")
    LOADK(BM_R0S); e(f"      r=a 59 a=r {ST} b=r {R('BM')} a+=b b=r 59 a+=b"); ARBIT()
    e("      a> 0 ifl")
    STGE7(); e(f"        ifl a= 11 elsel a= 9 endif r=a {ST}")
    e("      elsel")
    e(f"        a= 1 r=a {NEEDL}")
    e("      endif")
    e("    elsel")
    e(f"      a= 1 r=a {NEEDL}")
    e("    endif")
    e(f"    a=r {NEEDL} a> 0 ifl")
    STGE7(); e(f"      ifl a=r {R('RL1')} elsel a=r {R('RL0')} endif r=a {MB}")
    DEC()
    e(f"      a=r {SYM} a+= 2 r=a {ML}")
    e(f"      a= 1 a<<= 8 a+= 2 b=a a=r {ML} a==b ifl")
    HUGE()
    e("      endif")
    e(f"      a=r {BR0} a== 0 ifl")
    LOADK(BM_R1); e(f"        r=a 59 a=r {ST} b=r {R('BM')} a+=b b=r 59 a+=b"); ARBIT()
    e("        a> 0 ifl")
    e(f"          a=r {H0} r=a 59 a=r {H1} r=a {H0} a=r 59 r=a {H1}")
    e("        elsel")
    LOADK(BM_R2); e(f"          r=a 59 a=r {ST} b=r {R('BM')} a+=b b=r 59 a+=b"); ARBIT()
    e("          a> 0 ifl")
    e(f"            a=r {H2} r=a 59 a=r {H1} r=a {H2} a=r {H0} r=a {H1} a=r 59 r=a {H0}")
    e("          elsel")
    e(f"            a=r {H3} r=a 59 a=r {H2} r=a {H3} a=r {H1} r=a {H2} a=r {H0} r=a {H1} a=r 59 r=a {H0}")
    e("          endif")
    e("        endif")
    e("      endif")
    STGE7(); e(f"      ifl a= 11 elsel a= 8 endif r=a {ST}")
    e("    endif")
    e("  elsel")
    e(f"    a=r {R('MAINB')} r=a {MB}")
    DEC()
    e(f"    a=r {SYM} a< 2 ifl")
    e(f"      a=0 r=a {COPY} a=r {SYM} a== 0 ifl a=0 r=a {CONT} elsel a= 1 r=a {H0} r=a {H1} r=a {H2} r=a {H3} a=0 r=a {ST} endif")
    e("    elsel")
    e(f"      a=r {SYM} a-= 2 r=a {SYM} a&= 7 a+= 2 r=a {ML} a=r {SYM} a>>= 3 a++ r=a {SLOT}")
    e(f"      a=r {ML} a== 9 ifl")
    STGE7(); e(f"        ifl a=r {R('LL1')} elsel a=r {R('LL0')} endif r=a {MB}")
    DEC()
    e(f"        a=r {ML} b=r {SYM} a+=b r=a {ML}")
    e(f"        a= 1 a<<= 8 a+= 2 b=a a=r {ML} a==b ifl")
    HUGE()
    e("        endif")
    e("      endif")
    e(f"      a=r {SLOT} b=r {R('EB')} a+=b d=a a=*d r=a {NE}")
    e("      a< 3 ifl")
    GETR(NE, EX)
    e("      elsel")
    e(f"        a=0 r=a {EX} a=r {NE} a> 4 ifl a-= 4 r=a {NE}"); GETR(NE, EX); e(f"          a=r {EX} a<<= 4 r=a {EX} endif")
    e(f"        a=r {R('DLSB')} r=a {MB}")
    DEC()
    e(f"        a=r {EX} b=r {SYM} a+=b r=a {EX}")
    e("      endif")
    e(f"      a=r {H2} r=a {H3} a=r {H1} r=a {H2} a=r {H0} r=a {H1}")
    e(f"      a=r {SLOT} b=r {R('DB')} a+=b d=a a=*d b=r {EX} a+=b r=a {H0}")
    STGE7(); e(f"      ifl a= 10 elsel a= 7 endif r=a {ST}")
    e("    endif")
    e("  endif")
    # la copia
    e(f"  a=r {COPY} a> 0 ifl")
    e(f"    a=r {OUTP} b=r {OB} a-=b b=a a=r {H0} a>b ifl a= 1 r=a {ERR} elsel")
    e(f"      a=r {OUTP} b=r {H0} a-=b r=a {T1} a=r {ML} r=a {T2}")
    e("      do")
    e(f"        a=r {T1} c=a a=*c"); PUTB(); e(f"        a=r {T1} a++ r=a {T1} a=r {ML} a-- r=a {ML}")
    e("      a> 0 while")
    e(f"      a=r {T2} a== 1 ifl a=r {PC} r=a {PPC} elsel a=r {OUTP} a-= 2 c=a a=*c r=a {PPC} endif")
    e(f"      a=r {OUTP} a-- c=a a=*c r=a {PC}")
    e("    endif")
    e("  endif")
    e("endif")

# ---------------------------------------------------------------------------
e("hcomp")
e("halt")
e("pcomp zpaqlzham ;")
e("""(ZPAQLZHAM: decodificador de LZHAM 1.0 en ZPAQL, para zpaq-std -ma:lzh (diccionario
 de 2^20, niveles 1-4). zpaq-std, 2026. Guarda el flujo en M y lo decodifica al final:
 el codificador aritmetico binario, los modelos de Huffman cuasi-adaptativos (codigos
 polares o de Huffman, reconstruidos cada cycle simbolos) y el LZ de LZHAM.)""")
e("a> 255 ifl")
e(f"  a=c r=a {N}")
e("  a=0 r=a 44 do *c=a c++ a=r 44 a++ r=a 44 a< 32 while")     # relleno de ceros
e(f"  a=r {N} a+= 32 r=a {OB} r=a {OUTP} a=r {N} a+= 8 a<<= 3 r=a {PLIM}")
for k, v in KV.items(): LOADK(v); e(f"  r=a {R(k)}")
e(f"  a= 1 a<<= 24 r=a {K24} a= 8 a<<= 8 r=a {K2048} a= 128 a<<= 8 r=a {K32768}")
# tablas de slots
eb = [0] * 128; j = 0
for i in range(0, 128, 2):
    eb[i] = eb[i + 1] = j
    if i != 0 and j < 25: j += 1
base = [0] * 128; j = 0
for i in range(128): base[i] = j; j += 1 << eb[i]
for i in range(40):
    e(f"  a= {HB['EB'] + i} d=a a= {eb[i]} *d=a")
    LOADK(HB['DB'] + i); e("  d=a"); LOADK(base[i]); e("  *d=a")
# tabla de modelos, n de cada uno
for i, (b, n) in enumerate(MODELS):
    LOADK(MTAB + i); e("  d=a"); LOADK(b); e("  *d=a d=a"); LOADK(n); e("  *d=a")
e(f"  a=0 r=a {POS} r=a {ERR} r=a {STOP}")
GETK(2, T1)
e(f"  a=r {T1} a>>= 1 r=a {FAST} a=r {T1} a&= 1 r=a {POLAR}")
# max_cycle
def mc():
    e(f"  a=r {MI} b=r {R('MTAB')} a+=b d=a a=*d r=a {MB} d=a a=*d r=a 45")
    e(f"  a=r {FAST} a> 0 ifl")
    e("    a=r 45 a< 64 ifl a= 64 endif a+= 6 a<<= 5")
    e("  elsel")
    e("    a=r 45 a< 24 ifl a= 24 endif a+= 6 r=a 45 a<<= 3 b=a a=r 45 a<<= 2 a+=b")
    e("  endif")
    e(f"  b=r {K32768} a<b ifnot a=b a-- endif")
    e(f"  r=a 45 a=r {MB} a+= 4 d=a a=r 45 *d=a")
FOR(MI, 134, mc)
e(f"  a= 2 r=a {FT}")
FLUSH()
# bloques
e("  do")
GETK(2, BT)
e(f"    a=r {BT} a== 2 ifl")
GETK(24, T1); GETK(8, T2)
e(f"      a=r {T1} a&= 255 r=a 44 a=r {T1} a>>= 8 a&= 255 b=r 44 a^=b r=a 44 a=r {T1} a>>= 16 b=r 44 a^=b b=r {T2} a==b ifnotl a= 1 r=a {ERR} endif")
ALIGN()
e(f"      a=r {ERR} a== 0 ifl")
e(f"        a=r {T1} a++ r=a {T1}")
e("        do")
e(f"          a=r {POS} a>>= 3 c=a a=*c"); PUTB(); e(f"          a=r {POS} a+= 8 r=a {POS} a=r {T1} a-- r=a {T1}")
e("        a> 0 while")
e("      endif")
e(f"    elsel a=r {BT} a< 2 ifl")
e(f"      a=r {BT} a> 0 ifl")
GETK(16, T1); GETK(16, T2)
e(f"        a=r {T1} a<<= 16 b=r {T2} a+=b r=a {AV} a=0 a-- r=a {AL}")
e(f"        a= 1 r=a {H0} r=a {H1} r=a {H2} r=a {H3} a=0 r=a {ST} r=a {PC} r=a {PPC}")
e("      endif")
GETK(2, FT)
FLUSH()
e(f"      a=r {BT} a== 0 ifl")
ALIGN(); GETK(16, T1); GETK(16, T2)
e(f"        a=r {T1} a> 0 ifl a= 1 r=a {ERR} endif a= 255 a<<= 8 a+= 255 b=r {T2} a==b ifnot a= 1 r=a {ERR} endif")
e("      elsel")
e(f"        a= 1 r=a {CONT}")
e("        do")
SYMBOL()
e(f"          a=r {CONT} a> 0 ifl a=r {ERR} a== 0 ifl a=r {POS} b=r {PLIM} a<b ifl a= 1 elsel a=0 endif elsel a=0 endif endif")
e("        a> 0 while")
ALIGN()
e("      endif")
e("    elsel")
e(f"      a= 1 r=a {STOP}")
e("    endif endif")
e(f"    a=r {STOP} a== 0 ifl a=r {ERR} a== 0 ifl a=r {POS} b=r {PLIM} a<b ifl a= 1 elsel a=0 endif elsel a=0 endif elsel a=0 endif")
e("  a> 0 while")
e("  a=0 c=a")
e("elsel")
e("  *c=a c++")
e("endif")
e("halt")
e("end")
open(sys.argv[1], 'w').write('\n'.join(out) + '\n')
