# Generador de ZPAQBSC: flujos de libbsc 3.3.12 tal como los escribe zpaq-std -ma:bsc
# (sin LZP, transformada ST3/ST4/ST5, codificador QLFC estatico) en ZPAQL. ZPAQL no tiene
# subrutinas: todo son macros expandidas en linea. Mismo algoritmo que ref.py.
#   python3 gen.py salida.txt [tablas.h]   (tablas.h: el prefijo de datos como arreglo C)
#
# La entrada es un PREFIJO DE DATOS fijo (las dos tablas de estados del QLFC:
# model_rank_state_table, 32768 bytes, y model_run_state_table, 8192) y detras el bloque
# de bsc. M: la entrada desde 0, 16 ceros, T (la salida del QLFC = la entrada de la ST
# inversa) y la salida. H: auxiliares 0.., buckets 2048 (65536), los contadores del QLFC
# desde MODB y P (la ST inversa, n palabras) desde 2^20.
# Los contadores son enteros con signo de 16 bits en C; aca van en 32 bits con signo y
# los ">> 12" sobre negativos se hacen como en C (piso), con ASR.
import sys, os
DEBUG = os.environ.get('DEBUG') == '1'
out = []
def e(s): out.append(s)

PFX = 40960
# registros
NIN, RP, CODE, RANGE, N, K, IDX, TB, OB, TW = 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
NB, BI, BN, BEND, DP = 11, 12, 15, 16, 14
CR0, CR4, CRUN, MAXR, AVG, CH, STATE, RANK, BRS, RUNS, CTX, BIT = 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 32
SP, CP, TPR = 33, 34, 35
K10000, K80000000 = 70, 72
T1, T2, T3, T4 = 40, 41, 42, 43

# H
MISC_MTF, MISC_RANKH, MISC_RUNH, MISC_USED, MISC_CNT, MISC_IDX, MISC_GRP, MISC_RMTAB = 0, 256, 512, 768, 1024, 1280, 1536, 1792
BKT = 2048
MODB = BKT + 65536
lay = {}
p = MODB
def alloc(name, size):
    global p
    lay[name] = p; p += size
alloc('RKT', 1); alloc('RKS', 256); alloc('RKC', 256)
alloc('RET', 8); alloc('RES', 256 * 8); alloc('REC', 256 * 8)
RMB = {}
for b in range(1, 8):
    RMB[b] = p; p += (1 << b) + 2 * (256 << b)
alloc('RST', 256); alloc('RSS', 256 * 256); alloc('RSC', 256 * 256)
alloc('UNT', 1); alloc('UNS', 256); alloc('UNC', 256)
alloc('UET', 32); alloc('UES', 256 * 32); alloc('UEC', 256 * 32)
UMSTRIDE = 32 + 2 * 256 * 32
alloc('UM', 32 * UMSTRIDE)
MODE_ = p
PB = 1 << 20
assert MODE_ < PB

# constantes F_* (qlfc_model.h)
FK = {}
for line in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bsc', 'coder', 'qlfc', 'qlfc_model.h')):
    for part in line.split(';'):
        part = part.strip()
        if part.startswith('const int F_'):
            k, v = part[len('const int '):].split('=')
            FK[k.strip()[2:]] = int(v)

REG = {}
for i, k in enumerate(['BKT', 'MODB', 'MODE', 'PB', 'RMTAB'] + list(lay)):
    REG[k] = 100 + i
KV = dict(BKT=BKT, MODB=MODB, MODE=MODE_, PB=PB, RMTAB=MISC_RMTAB, **lay)
R = lambda k: REG[k]

def LOADK(v):
    v &= 0xFFFFFFFF
    if v < 256: e(f"a= {v}"); return
    bs = []
    while v: bs.append(v & 255); v >>= 8
    e(f"a= {bs[-1]}")
    for b in reversed(bs[:-1]):
        e(f"a<<= 8 a+= {b}" if b else "a<<= 8")

def ASR12():                  # a = a >> 12 con signo (piso)
    e(f"b=r {K80000000} a<b ifl a>>= 12 elsel b=a a=0 a-- a^=b a>>= 12 b=a a=0 a-- a^=b endif")

def SHORT():                  # a = siguiente short (little endian) del flujo
    e(f"a=r {RP} c=a a=*c r=a 37 c++ a=*c a<<= 8 b=r 37 a+=b r=a 37 a=r {RP} a+= 2 r=a {RP} a=r 37")

def BITP():                   # a = probabilidad (12 bits) -> a = r BIT = bit
    e("r=a 36")
    e(f"a=r {RANGE} b=r {K10000} a<b ifl")
    e(f"  a=r {RANGE} a<<= 16 r=a {RANGE}")
    SHORT(); e(f"  b=a a=r {CODE} a<<= 16 a+=b r=a {CODE}")
    e("endif")
    e(f"a=r {RANGE} a>>= 12 b=r 36 a*=b r=a 37 b=a a=r {CODE} a<b ifl")
    e(f"  a=r 37 r=a {RANGE} a=0")
    e("elsel")
    e(f"  a=r {CODE} a-=b r=a {CODE} a=r {RANGE} a-=b r=a {RANGE} a= 1")
    e("endif")
    e(f"r=a {BIT}")

def MULK(v):                  # a *= v (constante)
    v &= 0xFFFFFFFF
    if v < 256: e(f"a*= {v}")
    else:
        e("r=a 38"); LOADK(v); e("b=a a=r 38 a*=b")

def PMIX(g):                  # a = (C*LR0 + S*LR1 + T*LR2) >> 5 ; g = 'RANK_TM' etc.
    e(f"a=r {CP} d=a a=*d"); MULK(FK[g + '_LR0']); e("r=a 39")
    e(f"a=r {SP} d=a a=*d"); MULK(FK[g + '_LR1']); e("b=r 39 a+=b r=a 39")
    e(f"a=r {TPR} d=a a=*d"); MULK(FK[g + '_LR2']); e("b=r 39 a+=b a>>= 5")

def UPD1(reg, th, ar):        # p -= ((p - th) * ar) >> 12
    if ar == 0: return
    e(f"a=r {reg} d=a a=*d r=a 38"); LOADK(th); e("b=a a=r 38 a-=b"); MULK(ar); ASR12()
    e(f"b=a a=r {reg} d=a a=*d a-=b *d=a")
def UPD0(reg, th, ar):        # p += ((4096 - th - p) * ar) >> 12
    if ar == 0: return
    LOADK(4096 - th); e(f"r=a 38 a=r {reg} d=a a=*d b=a a=r 38 a-=b"); MULK(ar); ASR12()
    e(f"b=a a=r {reg} d=a a=*d a+=b *d=a")
def UPD(reg, th0, ar0, th1, ar1):   # segun r BIT
    e(f"a=r {BIT} a> 0 ifl")
    e(f"  a=r {reg} d=a a=*d"); MULK(ar1); e("r=a 38"); LOADK(th1 * ar1); e("b=a a=r 38 a-=b")
    e("elsel")
    e(f"  a=r {reg} d=a a=*d"); MULK(ar0); e("r=a 38"); LOADK((4096 - th0) * ar0 - 4095); e("b=a a=r 38 a-=b")
    e("endif")
    ASR12(); e(f"b=a a=r {reg} d=a a=*d a-=b *d=a")
def UPD1_3(g):
    UPD1(SP, FK[g + 'S_TH1'], FK[g + 'S_AR1']); UPD1(CP, FK[g + 'C_TH1'], FK[g + 'C_AR1']); UPD1(TPR, FK[g + 'P_TH1'], FK[g + 'P_AR1'])
def UPD0_3(g):
    UPD0(SP, FK[g + 'S_TH0'], FK[g + 'S_AR0']); UPD0(CP, FK[g + 'C_TH0'], FK[g + 'C_AR0']); UPD0(TPR, FK[g + 'P_TH0'], FK[g + 'P_AR0'])
def UPD_3(g):
    for x, reg in (('S', SP), ('C', CP), ('P', TPR)):
        UPD(reg, FK[g + x + '_TH0'], FK[g + x + '_AR0'], FK[g + x + '_TH1'], FK[g + x + '_AR1'])

def HG(base_reg, idx_reg, dst):      # r dst = H[r base + r idx]
    e(f"a=r {idx_reg} b=r {base_reg} a+=b d=a a=*d r=a {dst}")
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
def LE32(addr_reg, dst):
    e(f"a=r {addr_reg} a+= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a {dst}")
def PUTT():                   # a -> T[r TW++] si r TW < r BEND
    e(f"r=a 37 a=r {TW} b=r {BEND} a<b ifl c=a a=r 37 *c=a a=c a++ r=a {TW} endif")
def BSR(src, dst):            # r dst = posicion del bit mas alto de r src (src > 0)
    e(f"a=0 r=a {dst} a=r {src} a>>= 1 a> 0 ifl do r=a 38 a=r {dst} a++ r=a {dst} a=r 38 a>>= 1 a> 0 while endif")

def QLFC():
    """Un bloque QLFC estatico: flujo en M desde r DP, salida a T desde r TW (r BN bytes)."""
    # modelo: todo en 2048
    e(f"a=r {R('MODB')} d=a a=r {R('MODE')} r=a 38")
    e("do a= 8 a<<= 8 *d=a d++ a=d b=r 38 a<b while")
    e(f"a=r {DP} r=a {RP} a=0 r=a {CODE} a=0 a-- r=a {RANGE}")
    for _ in range(3): SHORT(); e(f"b=a a=r {CODE} a<<= 16 a+=b r=a {CODE}")
    e(f"a=0 r=a {CR0} r=a {CR4} r=a {CRUN} r=a {AVG} a= 7 r=a {MAXR}")
    # rankH (256), runH (512) y used (768) en 0
    FOR(T1, 256, lambda: e(f"  a=r {T1} a+= 255 a++ d=a a=0 *d=a a=r {T1} a+= 255 a+= 255 a+= 2 d=a a=0 *d=a a=r {T1} a+= 255 a+= 255 a+= 255 a+= 3 d=a a=0 *d=a"))
    e(f"a=0 r=a {BN}")
    def nb():
        e("  a= 8 a<<= 8 r=a 36"); BITP(); e(f"  a=r {BN} a<<= 1 b=r {BIT} a+=b r=a {BN}")
    FOR(T1, 32, nb)
    e(f"a=r {TW} b=r {BN} a+=b r=a {BEND}")
    # tabla MTF inicial: r T2 prev (999 = ninguno), r T1 rank, r T3 cur, r T4 bit
    e(f"a= 3 a<<= 8 a+= 231 r=a {T2} a=0 r=a {T1}")
    e("do")
    e(f"  a=0 r=a {T3} a= 7 r=a {T4}")
    e("  do")
    # c en [cur << (bit+1), (cur+1) << (bit+1)): r44 c, r45 fin, r46 b0, r47 b1
    e(f"    a=r {T4} a++ b=a a=r {T3} a<<=b r=a 44 a=r {T3} a++ a<<=b r=a 45 a=0 r=a 46 r=a 47")
    e("    do")
    e(f"      a=r 44 b=r {T2} a==b ifl a= 1 elsel a=r 44 a+= 255 a+= 255 a+= 255 a+= 3 d=a a=*d a== 0 ifl a= 1 elsel a=0 endif endif")
    e("      a> 0 ifl")
    e(f"        a= 1 b=r {T4} a<<=b b=a a=r 44 a&=b a> 0 ifl a= 1 r=a 47 elsel a= 1 r=a 46 endif")
    e("      endif")
    e("      a=r 44 a++ r=a 44 b=r 45 a<b ifl a=r 46 a> 0 ifl a=r 47 a== 0 ifl a= 1 elsel a=0 endif elsel a= 1 endif elsel a=0 endif")
    e("    a> 0 while")
    e("    a=r 46 a> 0 ifl a=r 47 a> 0 ifl")
    e("      a= 8 a<<= 8"); BITP(); e(f"      a=r {T3} a<<= 1 b=r {BIT} a+=b r=a {T3}")
    e(f"    elsel a=r {T3} a<<= 1 r=a {T3} endif")
    e(f"    elsel a=r 47 a> 0 ifl a=r {T3} a<<= 1 a++ r=a {T3} endif endif")
    e(f"    a=r {T4} a> 0 ifl a-- r=a {T4} a= 1 elsel a=0 endif")
    e("  a> 0 while")
    e(f"  a=r {T1} d=a a=r {T3} *d=a")
    e(f"  a=r {T3} b=r {T2} a==b ifl")
    e(f"    a=r {T1} a> 1 ifl a-- r=a 44"); BSR(44, MAXR); e(f"    elsel a= 63 r=a {MAXR} endif")
    e(f"    a=0 r=a 44")
    e("  elsel")
    e(f"    a=r {T3} r=a {T2} a+= 255 a+= 255 a+= 255 a+= 3 d=a a= 1 *d=a")
    e(f"    a=r {T1} a++ r=a {T1} a> 255 ifl a=0 elsel a= 1 endif r=a 44")
    e("  endif")
    e("  a=r 44")
    e("a> 0 while")
    # simbolos
    e(f"a=r {TW} b=r {BEND} a<b ifl")
    e("do")
    e(f"  a=0 d=a a=*d r=a {CH}")
    e(f"  a=r {CH} a+= 255 a++ d=a a=*d r=a 44 a=r {CRUN} a<<= 11 b=a a=r {CR4} a<<= 3 a+=b b=r 44 a+=b c=a a=*c r=a {STATE}")
    e(f"  a= 1 r=a {RANK}")
    e(f"  a=r {AVG} a< 32 ifl")
    e(f"    a=r {STATE} b=r {R('RKS')} a+=b r=a {SP} a=r {CH} b=r {R('RKC')} a+=b r=a {CP} a=r {R('RKT')} r=a {TPR}")
    PMIX('RANK_TM'); BITP()
    e("    a> 0 ifl")
    UPD1_3('RANK_T')
    e(f"      a=r {STATE} a<<= 3 b=r {R('RES')} a+=b r=a {SP} a=r {CH} a<<= 3 b=r {R('REC')} a+=b r=a {CP} a=r {R('RET')} r=a {TPR}")
    e(f"      a= 1 r=a {BRS}")
    e("      do")
    e(f"        a=r {BRS} b=r {MAXR} a==b ifl a=0 elsel")
    PMIX('RANK_EM'); BITP()
    e("        a> 0 ifl")
    UPD1_3('RANK_E')
    e(f"          a=r {SP} a++ r=a {SP} a=r {CP} a++ r=a {CP} a=r {TPR} a++ r=a {TPR} a=r {BRS} a++ r=a {BRS} a= 1")
    e("        elsel")
    UPD0_3('RANK_E')
    e("          a=0")
    e("        endif endif")
    e("      a> 0 while")
    e(f"      a=r {CH} a+= 255 a++ d=a a=r {BRS} *d=a")
    # mantisa: base del bloque b en H[RMTAB + b]
    e(f"      a=r {BRS} b=r {R('RMTAB')} a+=b d=a a=*d r=a 45")        # r45 base
    e(f"      a=r {BRS} r=a 46")                                         # r46 contador
    e("      do")
    e(f"        a=r 45 b=r {RANK} a+=b r=a {TPR}")
    e(f"        a= 1 b=r {BRS} a<<=b r=a 47 a=r {STATE} a<<=b b=r 47 a+=b b=r {TPR} a+=b r=a {SP}")
    e(f"        a=r {BRS} b=a a= 1 a<<= 8 a<<=b r=a 47 a=r {CH} a<<=b r=a 48 a= 1 a<<=b b=r 47 a+=b b=r 48 a+=b b=r {TPR} a+=b r=a {CP}")
    PMIX('RANK_MM'); BITP()
    UPD_3('RANK_M')
    e(f"        a=r {RANK} a<<= 1 b=r {BIT} a+=b r=a {RANK}")
    e("        a=r 46 a-- r=a 46")
    e("      a> 0 while")
    e("    elsel")
    e(f"      a=r {CH} a+= 255 a++ d=a a=0 *d=a")
    UPD0_3('RANK_T')
    e("    endif")
    e("  elsel")
    e(f"    a=0 r=a {RANK} a= 1 r=a {CTX} a=r {MAXR} a++ r=a 46")
    e("    do")
    e(f"      a=r {CTX} b=r {R('RST')} a+=b r=a {TPR}")
    e(f"      a=r {STATE} a<<= 8 b=r {CTX} a+=b b=r {R('RSS')} a+=b r=a {SP}")
    e(f"      a=r {CH} a<<= 8 b=r {CTX} a+=b b=r {R('RSC')} a+=b r=a {CP}")
    PMIX('RANK_PM'); BITP()
    UPD_3('RANK_P')
    e(f"      a=r {CTX} a<<= 1 b=r {BIT} a+=b r=a {CTX} a=r {RANK} a<<= 1 b=r {BIT} a+=b r=a {RANK}")
    e("      a=r 46 a-- r=a 46")
    e("    a> 0 while")
    BSR(RANK, 44); e(f"    a=r {CH} a+= 255 a++ d=a a=r 44 *d=a")
    e("  endif")
    # MTF: mtf[0..rank-1] = mtf[1..rank], mtf[rank] = ch
    e(f"  a=r {RANK} a> 0 ifl a=0 d=a do d++ a=*d d-- *d=a d++ a=d b=r {RANK} a<b while endif")
    e(f"  a=r {RANK} d=a a=r {CH} *d=a")
    e(f"  a=r {AVG} a*= 124 r=a 44 a=r {RANK} a<<= 2 b=r 44 a+=b a>>= 7 r=a {AVG}")
    e(f"  a=r {RANK} a-- r=a {RANK}")
    # estado de corrida
    e(f"  a=r {CH} a+= 255 a+= 255 a+= 2 d=a a=*d a> 7 ifl a= 7 endif r=a 44")
    e(f"  a=r {RANK} a> 7 ifl a= 7 endif a<<= 3 b=r 44 a+=b r=a 44 a=r {CRUN} a<<= 6 b=r 44 a+=b r=a 44 a=r {CR0} a<<= 10 b=r 44 a+=b r=a 44")
    e(f"  a= 128 a<<= 8 b=r 44 a+=b c=a a=*c r=a {STATE}")
    e(f"  a=r {STATE} b=r {R('UNS')} a+=b r=a {SP} a=r {CH} b=r {R('UNC')} a+=b r=a {CP} a=r {R('UNT')} r=a {TPR}")
    PMIX('RUN_TM'); BITP()
    e("  a> 0 ifl")
    UPD1_3('RUN_T')
    e(f"    a=r {STATE} a<<= 5 b=r {R('UES')} a+=b r=a {SP} a=r {CH} a<<= 5 b=r {R('UEC')} a+=b r=a {CP} a=r {R('UET')} r=a {TPR}")
    e(f"    a= 1 r=a {RUNS} r=a {BRS}")
    e("    do")
    PMIX('RUN_EM'); BITP()
    e("      a> 0 ifl")
    UPD1_3('RUN_E')
    e(f"        a=r {SP} a++ r=a {SP} a=r {CP} a++ r=a {CP} a=r {TPR} a++ r=a {TPR} a=r {BRS} a++ r=a {BRS} a> 31 ifl a=0 elsel a= 1 endif")
    e("      elsel")
    UPD0_3('RUN_E')
    e("        a=0")
    e("      endif")
    e("    a> 0 while")
    e(f"    a=r {BRS} a> 31 ifl a= 31 r=a {BRS} endif")        # solo con datos rotos
    e(f"    a=r {CH} a+= 255 a+= 255 a+= 2 d=a a=*d r=a 44 a=r {BRS} a*= 3 a+= 3 b=r 44 a+=b a>>= 2 *d=a")
    e(f"    a=r {BRS} r=a 38"); LOADK(UMSTRIDE); e(f"    b=r 38 a*=b b=r {R('UM')} a+=b r=a 45")   # base
    e(f"    a= 1 r=a {CTX} a=r {BRS} r=a 46")
    e("    do")
    e(f"      a=r 45 b=r {CTX} a+=b r=a {TPR}")
    e(f"      a=r {STATE} a<<= 5 b=r {TPR} a+=b a+= 32 r=a {SP}")
    e(f"      a=r {CH} a<<= 5 b=r {TPR} a+=b a+= 32 r=a {CP} a= 32 a<<= 8 b=r {CP} a+=b r=a {CP}")
    PMIX('RUN_MM'); BITP()
    UPD_3('RUN_M')
    e(f"      a=r {RUNS} a<<= 1 b=r {BIT} a+=b r=a {RUNS}")
    e(f"      a=r {BRS} a> 5 ifl a=r {CTX} a++ elsel a=r {CTX} a<<= 1 b=r {BIT} a+=b endif r=a {CTX}")
    e("      a=r 46 a-- r=a 46")
    e("    a> 0 while")
    e(f"    a=r {RUNS} a< 3 ifl a= 1 elsel a=0 endif r=a 44")
    e(f"    do a=r {CH}"); PUTT(); e(f"      a=r {RUNS} a-- r=a {RUNS} a> 0 while")
    e("  elsel")
    e(f"    a=r {CH} a+= 255 a+= 255 a+= 2 d=a a=*d a+= 2 a>>= 2 *d=a")
    UPD0_3('RUN_T')
    e(f"    a= 1 r=a 44 a=r {CH}"); PUTT()
    e("  endif")
    e(f"  a=r {CR0} a<<= 1 r=a 45 a=r {RANK} a== 0 ifl a=r 45 a++ r=a 45 endif a=r 45 a&= 7 r=a {CR0}")
    e(f"  a=r {RANK} a> 3 ifl a= 3 endif r=a 45 a=r {CR4} a<<= 2 b=r 45 a+=b a&= 255 r=a {CR4}")
    e(f"  a=r {CRUN} a<<= 1 b=r 44 a+=b a&= 15 r=a {CRUN}")
    e(f"  a=r {TW} b=r {BEND} a<b ifl a=r {NIN} a+= 64 b=a a=r {RP} a<b ifl a= 1 elsel a=0 endif elsel a=0 endif")
    e("a> 0 while")
    e("endif")

def TG(ireg, dst):            # r dst = T[r ireg]
    e(f"a=r {ireg} b=r {TB} a+=b c=a a=*c r=a {dst}")
def PG(ireg, dst):
    e(f"a=r {ireg} b=r {R('PB')} a+=b d=a a=*d r=a {dst}")

def UNST():
    e(f"a=r {N} a> 1 ifl")
    # P = 0, count = 0, bucket = 0
    FOR(T1, f"r{N}", lambda: e(f"  a=r {T1} b=r {R('PB')} a+=b d=a a=0 *d=a"))
    FOR(T1, 256, lambda: e(f"  a=r {T1} a+= 255 a+= 255 a+= 255 a+= 255 a+= 4 d=a a=0 *d=a"))
    e(f"a=r {R('BKT')} d=a a=0 r=a 44 do a=0 *d=a d++ a=r 44 a++ r=a 44 a=r 44 a>>= 16 a== 0 while")
    def cnt():
        TG(T1, 44); e(f"  a=r 44 a+= 255 a+= 255 a+= 255 a+= 255 a+= 4 d=a *d++")
    FOR(T1, f"r{N}", cnt)
    # count -> inicios; r45 suma. bucket[c<<8 | T[i]]++ para i en [inicio, fin)
    e("a=0 r=a 45")
    def pre():
        e(f"  a=r {T1} a+= 255 a+= 255 a+= 255 a+= 255 a+= 4 d=a a=*d r=a 46 a=r 45 *d=a r=a 47 b=r 46 a+=b r=a 45")
        e("  a=r 47 b=r 45 a<b ifl")
        e("    do")
        TG(47, 48); e(f"      a=r {T1} a<<= 8 b=r 48 a+=b b=r {R('BKT')} a+=b d=a *d++")
        e("      a=r 47 a++ r=a 47 b=r 45 a<b")
        e("    while")
        e("  endif")
    FOR(T1, 256, pre)
    # transponer
    def tr():
        e(f"  a=r {T1} a> 0 ifl")
        e("  a=0 r=a 44")
        e("  do")
        e(f"    a=r 44 a<<= 8 b=r {T1} a+=b b=r {R('BKT')} a+=b r=a 46 d=a a=*d r=a 48")
        e(f"    a=r {T1} a<<= 8 b=r 44 a+=b b=r {R('BKT')} a+=b d=a a=*d r=a 49 a=r 48 *d=a a=r 46 d=a a=r 49 *d=a")
        e(f"    a=r 44 a++ r=a 44 b=r {T1} a<b")
        e("  while")
        e("  endif")
    FOR(T1, 256, tr)
    e(f"a=r {K} a== 3 ifl")
    e(f"  a=0 r=a 45 r=a {T1}")
    e("  do")
    e(f"    a=r {T1} b=r {R('BKT')} a+=b d=a a=*d a> 0 ifl r=a 46 a=r 45 b=r {R('PB')} a+=b d=a a= 1 *d=a a=r 45 b=r 46 a+=b r=a 45 endif")
    e(f"    a=r {T1} a++ r=a {T1} a>>= 16 a== 0")
    e("  while")
    e("elsel")
    # index = count (MISC_IDX), group = -1 (MISC_GRP, 0xFFFFFFFF)
    def initig():
        e(f"  a=r {T1} a+= 255 a+= 255 a+= 255 a+= 255 a+= 4 d=a a=*d r=a 44")                 # count[c] (1024 + c)
        e(f"  a=r {T1} a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 5 d=a a=r 44 *d=a")          # index[c] (1280 + c)
        e(f"  a=r {T1} a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 6 d=a a=0 a-- *d=a")  # group[c] (1536 + c)
    FOR(T1, 256, initig)
    e(f"  a=0 r=a 45 r=a {T1}")                          # r45 suma, r T1 = w
    e("  do")
    e(f"    a=r {T1} b=r {R('BKT')} a+=b d=a a=*d r=a 46 a=r 45 r=a 47 b=r 46 a+=b r=a 45")
    e("    a=r 47 b=r 45 a<b ifl")
    e("      do")
    TG(47, 48)
    e(f"        a=r 48 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 6 d=a a=*d b=r {T1} a==b ifnotl")
    e(f"          a=r {T1} *d=a a=r 48 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 5 d=a a=*d b=r {R('PB')} a+=b d=a a=r {K80000000} *d=a")
    e("        endif")
    e("        a=r 48 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 5 d=a *d++")
    e("        a=r 47 a++ r=a 47 b=r 45 a<b")
    e("      while")
    e("    endif")
    e(f"    a=r {T1} a++ r=a {T1} a>>= 16 a== 0")
    e("  while")
    # rondas 4..k-1: r50 mask0, r51 mask1, r52 ronda
    e(f"  a=r {K80000000} r=a 50 a>>= 1 r=a 51 a= 4 r=a 52")
    e(f"  a=r 52 b=r {K} a<b ifl")
    e("  do")
    FOR(T1, 256, initig)
    e(f"    a=0 r=a 53 r=a {T1}")                        # r53 g
    e("    do")
    PG(T1, 44); e(f"      a=r 44 b=r 50 a&=b a> 0 ifl a=r {T1} r=a 53 endif")
    TG(T1, 48)
    e("      a=r 48 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 6 d=a a=*d b=r 53 a==b ifnotl")
    e(f"        a=r 53 *d=a a=r 48 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 5 d=a a=*d b=r {R('PB')} a+=b d=a a=*d b=r 51 a+=b *d=a")
    e("      endif")
    e("      a=r 48 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 5 d=a *d++")
    e(f"      a=r {T1} a++ r=a {T1} b=r {N} a<b")
    e("    while")
    e("    a=r 50 a>>= 1 r=a 50 a=r 51 a>>= 1 r=a 51 a=r 52 a++ r=a 52")
    e(f"    b=r {K} a<b")
    e("  while")
    e("  endif")
    e("endif")
    # reconstruccion: V en P; group+1 en MISC_GRP (0 = ninguno)
    def initig2():
        e(f"  a=r {T1} a+= 255 a+= 255 a+= 255 a+= 255 a+= 4 d=a a=*d r=a 44")
        e(f"  a=r {T1} a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 5 d=a a=r 44 *d=a")
        e(f"  a=r {T1} a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 6 d=a a=0 *d=a")
    FOR(T1, 256, initig2)
    e(f"a=0 r=a 53 r=a {T1}")
    e("do")
    PG(T1, 44); e(f"  a=r 44 a> 0 ifl a=r {T1} r=a 53 endif")
    TG(T1, 48)
    e("  a=r 48 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 6 d=a a=*d r=a 49 b=r 53 a>b ifl")      # G1 > g: ya tiene grupo
    e(f"    a=r 49 a-- r=a 49 b=r {K80000000} a+=b r=a 46"); e(f"    a=r {T1} b=r {R('PB')} a+=b d=a a=r 46 *d=a")
    e(f"    a=r 49 b=r {R('PB')} a+=b d=a *d++")
    e("  elsel")
    e(f"    a=r {T1} a++ *d=a")
    e(f"    a=r 48 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 5 d=a a=*d r=a 46 a=r {T1} b=r {R('PB')} a+=b d=a a=r 46 *d=a")
    e("  endif")
    e("  a=r 48 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 5 d=a *d++")
    e(f"  a=r {T1} a++ r=a {T1} b=r {N} a<b")
    e("while")
    # recorrido: p = idx, i = n-1 .. 0; salida en OB
    e(f"a=r {IDX} r=a 44 a=r {N} r=a {T1}")
    e("do")
    e(f"  a=r {T1} a-- r=a {T1}")
    PG(44, 45)
    e(f"  a=r 45 b=r {K80000000} a<b ifnot a-=b r=a 44"); PG(44, 45); e("  endif")
    e(f"  a=r 44 b=r {TB} a+=b c=a a=*c r=a 46 a=r {T1} b=r {OB} a+=b c=a a=r 46 *c=a")
    e(f"  a=r 44 b=r {R('PB')} a+=b d=a *d-- a=r 45 r=a 44")
    e(f"  a=r {T1}")
    e("a> 0 while")
    e("elsel")
    e(f"  a=r {N} a> 0 ifl a=r {TB} c=a a=*c r=a 46 a=r {OB} c=a a=r 46 *c=a endif")
    e("endif")

# ---------------------------------------------------------------------------
e("hcomp")
e("halt")
e("pcomp zpaqbsc ;")
e("""(ZPAQBSC: decodificador de libbsc 3.3.12 en ZPAQL, para zpaq-std -ma:bsc (sin LZP,
 ST3/ST4/ST5 y QLFC estatico). zpaq-std, 2026. Entrada: las dos tablas de estados del
 QLFC y el bloque de bsc; se guarda en M y se decodifica al final.)""")
e("a> 255 ifl")
e(f"  a=c r=a {NIN}")
e("  a=0 r=a 44 do *c=a c++ a=r 44 a++ r=a 44 a< 16 while")
for k, v in KV.items(): LOADK(v); e(f"  r=a {R(k)}")
e(f"  a= 1 a<<= 16 r=a {K10000} a= 128 a<<= 24 r=a {K80000000}")
for b in range(1, 8):
    LOADK(MISC_RMTAB + b); e("  d=a"); LOADK(RMB[b]); e("  *d=a")
# cabecera del bloque bsc (en PFX)
e(f"  a= 160 a<<= 8 r=a 44"); e("  a=r 44 a+= 4 r=a 45"); LE32(45, N)
e("  a=r 44 a+= 8 r=a 45"); LE32(45, 46); e(f"  a=r 46 a&= 31 r=a {K}")
e("  a=r 44 a+= 12 r=a 45"); LE32(45, IDX)
e(f"  a=r {NIN} a+= 16 r=a {TB} r=a {TW} b=r {N} a+=b r=a {OB}")
e(f"  a=r 46 a> 0 ifl")
e(f"  a=r 44 a+= 28 r=a 55 c=a a=*c r=a {NB}")
e(f"  a=r {NB} a== 1 ifl")
e(f"    a=r 55 a++ r=a {DP}")
QLFC()
e("  elsel")
e(f"    a=r {NB} a<<= 3 b=r 55 a+=b a++ r=a {DP} a=0 r=a {BI}")
e(f"    a=r {NB} a> 0 ifl")
e("    do")
e(f"      a=r {BI} a<<= 3 b=r 55 a+=b a++ r=a 50"); LE32(50, 51); e("      a=r 50 a+= 4 r=a 50"); LE32(50, 52)
e("      a=r 51 b=r 52 a==b ifl")
e(f"        a=r {TW} b=r 52 a+=b r=a {BEND}")
e(f"        a=r 52 a> 0 ifl a=r {DP} r=a 53 do a=r 53 c=a a=*c"); PUTT(); e("          a=r 53 a++ r=a 53 a=r 52 a-- r=a 52 a> 0 while endif")
e("      elsel")
e(f"        a=r {TW} b=r 51 a+=b r=a 54")
QLFC()
e("        a=r 54 r=a " + str(TW))
if DEBUG:
    for rr in (DP, TW, BN, BEND, 51, 52, 54):
        e(f"        a=r {rr} out a>>= 8 out a>>= 8 out a>>= 8 out")
e("      endif")
e(f"      a=r 50 a-= 4 r=a 50"); LE32(50, 51); e("      a=r 50 a+= 4 r=a 50"); LE32(50, 52)
e(f"      a=r {DP} b=r 52 a+=b r=a {DP}")
e(f"      a=r {BI} a++ r=a {BI} b=r {NB} a<b")
e("    while")
e("    endif")
e("  endif")
if DEBUG:
    e(f"  a=r {TB} r=a {OB}")
else:
    UNST()
e("  elsel")
# modo 0: guardado
e(f"    a=r {N} a> 0 ifl a=r 44 a+= 28 r=a 45 a=0 r=a 46 do a=r 45 b=r 46 a+=b c=a a=*c r=a 47 a=r {OB} b=r 46 a+=b c=a a=r 47 *c=a a=r 46 a++ r=a 46 b=r {N} a<b while endif")
e("  endif")
e(f"  a=r {N} a> 0 ifl a=0 r=a 44 do a=r {OB} b=r 44 a+=b c=a a=*c out a=r 44 a++ r=a 44 b=r {N} a<b while endif")
e("  a=0 c=a")
e("elsel")
e("  *c=a c++")
e("endif")
e("halt")
e("end")
open(sys.argv[1], 'w').write('\n'.join(out) + '\n')
if len(sys.argv) > 2:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ref import tablas
    t = tablas(); assert len(t) == PFX
    with open(sys.argv[2], 'w') as f:
        f.write('/* ZPAQBSC: the fixed data prefix of every -ma:bsc block: libbsc 3.3.12\n'
                '   model_rank_state_table (32768 bytes) and model_run_state_table (8192),\n'
                '   from compressors/bsc/coder/common/tables.h. Generated by gen.py; FROZEN\n'
                '   with the decoder. */\n')
        f.write('static const unsigned char ZPAQBSC_TABLAS[%d] = {\n' % PFX)
        for i in range(0, PFX, 24):
            f.write(','.join(str(x) for x in t[i:i + 24]) + (',\n' if i + 24 < PFX else '\n'))
        f.write('};\n')
