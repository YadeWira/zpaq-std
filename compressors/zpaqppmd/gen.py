# Generador de ZPAQPPMD: PPMd var.H (Ppmd7 del 7-Zip SDK, codificador de rango de 7z) en
# ZPAQL, escrito para zpaq-std -ma:ppmd. Mismo algoritmo que ref.py (traduccion fiel de
# Ppmd7.c/Ppmd7Dec.c): el modelo vive en un monticulo de bytes y depende del asignador
# (compara desplazamientos, pega bloques libres y se reinicia sin memoria), asi que el
# monticulo se reproduce byte a byte en M.
#   python3 gen.py salida.txt
#
# ZPAQL no tiene subrutinas. Para que cada funcion pesada aparezca una sola vez, cada
# simbolo se hace en fases: decodificar (y marcar que actualizacion toca), Rescale si
# hace falta, y NextContext o UpdateModel; RestartModel queda como bandera y se hace al
# empezar el simbolo siguiente. Dentro de UpdateModel, CreateSuccessors y la asignacion
# del lazo aparecen una vez cada una.
#
# Entrada: [orden u8][memoria u32][tamano original u32][flujo de 7z]. M: el monticulo en
# [0, memoria) (desplazamiento = direccion) y la entrada movida a [memoria, ...). H (ph 14):
# BinSumm, See, las listas libres y las tablas de Ppmd7_Construct.
import sys, os
out = []
def e(s): out.append(s)

# ---- registros globales (1..39)
NIN, RP, CODE, RANGE, ORIG, OUTN, MEMSZ, MAXORD = 1, 2, 3, 4, 5, 6, 7, 8
MINC, MAXC, FS, OFALL, INITESC, PREVS, HIBITS, RUNL, INITRL, GLUEC = 9, 10, 11, 12, 13, 14, 15, 16, 17, 18
TEXT, LOU, HIU, UST, RS, K24, K8M, FORCEUM, DORESC, INEND = 19, 20, 21, 22, 23, 24, 25, 26, 27, 28
# decodificacion 40..59, rescale 60..79, update_model 80..99, create_successors 100..119,
# asignador 120..149, temporales de macros 150..159
# ---- H
BINS, SEE, DUMMY, FREEL, I2U, U2I, NS2BS, NS2I, EXPESC, MASK, PSST, IBE = \
    0, 8192, 9400, 9408, 9448, 9488, 9616, 9872, 10128, 10144, 10400, 10464
HB = dict(BINS=BINS, SEE=SEE, DUMMY=DUMMY, FREEL=FREEL, I2U=I2U, U2I=U2I, NS2BS=NS2BS, NS2I=NS2I,
          EXPESC=EXPESC, MASK=MASK, PSST=PSST, IBE=IBE)
REG = {k: 200 + i for i, k in enumerate(HB)}
R = lambda k: REG[k]
UNIT, MAX_FREQ, NUMI = 12, 124, 38

def LOADK(v):
    v &= 0xFFFFFFFF
    if v < 256: e(f"a= {v}"); return
    bs = []
    while v: bs.append(v & 255); v >>= 8
    e(f"a= {bs[-1]}")
    for b in reversed(bs[:-1]):
        e(f"a<<= 8 a+= {b}" if b else "a<<= 8")
def ADD(off):                 # a += off (constante >= 0)
    while off > 255: e("a+= 255"); off -= 255
    if off: e(f"a+= {off}")
def A(reg, off=0):            # a = r reg + off
    e(f"a=r {reg}"); ADD(off)
def R8(reg, off=0):   A(reg, off); e("c=a a=*c")
def R16(reg, off=0):  A(reg, off); e("c=a c++ a=*c a<<= 8 c-- a+=*c")
def R32(reg, off=0):  A(reg, off); e("c=a c++ c++ c++ a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c")
def W8(reg, off, val):        # val: registro
    A(reg, off); e(f"c=a a=r {val} *c=a")
def W16(reg, off, val):
    A(reg, off); e(f"c=a a=r {val} *c=a c++ a>>= 8 *c=a")
def W32(reg, off, val):
    A(reg, off); e(f"c=a a=r {val} *c=a c++ a>>= 8 *c=a c++ a>>= 8 *c=a c++ a>>= 8 *c=a")
def HG(base, idxreg):         # a = H[base + r idx]
    e(f"a=r {idxreg} b=r {R(base)} a+=b d=a a=*d")
def HS(base, idxreg, val):    # H[base + r idx] = r val
    e(f"a=r {idxreg} b=r {R(base)} a+=b d=a a=r {val} *d=a")
def SETK(reg, v): LOADK(v); e(f"r=a {reg}")
def CPY(dst, src, nbytes_reg=None, n=None):   # M[r dst ..] = M[r src ..] (n bytes, hacia adelante)
    e(f"a=r {src} b=a a=r {dst} c=a")
    if n is not None:
        e(" ".join(["*c=*b b++ c++"] * n))
    else:
        e(f"a=r {nbytes_reg} a> 0 ifl do *c=*b b++ c++ a-- a> 0 while endif")
def SWAP6(sreg):              # estado en r sreg <-> estado anterior
    e(f"a=r {sreg} c=a a-= 6 b=a")
    e(" ".join(["a=*c r=a 150 *c=*b a=r 150 *b=a b++ c++"] * 6))

# ---------------- rango de 7z
def RB():                     # a = siguiente byte de la entrada (0 pasado el fin)
    e(f"a=r {RP} b=r {INEND} a<b ifl c=a a=*c elsel a=0 endif r=a 150 a=r {RP} a++ r=a {RP} a=r 150")
def NORM1():
    e(f"a=r {RANGE} b=r {K24} a<b ifl")
    RB(); e(f"  b=a a=r {CODE} a<<= 8 a+=b r=a {CODE} a=r {RANGE} a<<= 8 r=a {RANGE}")
    e("endif")
def NORM():
    e(f"a=r {RANGE} b=r {K24} a<b ifl")
    RB(); e(f"  b=a a=r {CODE} a<<= 8 a+=b r=a {CODE} a=r {RANGE} a<<= 8 r=a {RANGE}")
    e(f"  b=r {K24} a<b ifl")
    RB(); e(f"    b=a a=r {CODE} a<<= 8 a+=b r=a {CODE} a=r {RANGE} a<<= 8 r=a {RANGE}")
    e("  endif")
    e("endif")
def THRESH(totreg):           # a = Code / (Range /= total)
    e(f"a=r {RANGE} b=r {totreg} a/=b r=a {RANGE} b=a a=r {CODE} a/=b")
def RCDEC(startreg, sizereg):
    e(f"a=r {startreg} b=r {RANGE} a*=b b=a a=r {CODE} a-=b r=a {CODE} a=r {RANGE} b=r {sizereg} a*=b r=a {RANGE}")

# ---------------- asignador (r120 indx de entrada, r121 resultado)
def INSERT(nodereg, indxreg):     # *(u32*)node = FreeList[indx]; FreeList[indx] = node
    assert nodereg != 158 and indxreg != 158
    HG('FREEL', indxreg); e("r=a 158"); W32(nodereg, 0, 158); HS('FREEL', indxreg, nodereg)
def REMOVE(indxreg, dst):         # dst = FreeList[indx]; FreeList[indx] = *(u32*)dst
    assert indxreg not in (159, dst)
    HG('FREEL', indxreg); e(f"r=a {dst}"); R32(dst, 0); e("r=a 159"); HS('FREEL', indxreg, 159)
def U2IG(nureg, dst):             # dst = U2I[nu - 1]
    e(f"a=r {nureg} a-- r=a 151"); HG('U2I', 151); e(f"r=a {dst}")
def I2UG(ireg, dst):
    HG('I2U', ireg); e(f"r=a {dst}")
def SPLIT(ptr, oldi, newi):       # usa r130..r135
    I2UG(oldi, 130); I2UG(newi, 131); e("a=r 130 b=r 131 a-=b r=a 132")        # nu
    e(f"a=r 131 a*= 12 b=r {ptr} a+=b r=a 133")                                   # ptr nuevo
    U2IG(132, 134); I2UG(134, 135)
    e("a=r 135 b=r 132 a==b ifnotl")
    e("  a=r 134 a-- r=a 134"); I2UG(134, 135)
    e("  a=r 135 a*= 12 b=r 133 a+=b r=a 136 a=r 132 b=r 135 a-=b a-- r=a 137"); INSERT(136, 137)
    e("endif")
    INSERT(133, 134)

def GLUE():                       # r138.. ; n r138, head r139, prev r140 (0 = head), node r141, nu r142
    e(f"a= 255 r=a {GLUEC}")
    e(f"a=r {LOU} b=r {HIU} a==b ifnotl a= 1 r=a 150"); W16(LOU, 0, 150); e("endif")
    e("a=0 r=a 138 r=a 143")
    e("do")
    HG('I2U', 143); e("r=a 144"); HG('FREEL', 143); e("r=a 145 a=0 r=a 150"); HS('FREEL', 143, 150)
    e("  a=r 145 a> 0 ifl do")
    e("    a=r 145 r=a 146"); R32(146, 0); e("r=a 145")
    e("    a=0 r=a 150"); W16(146, 0, 150); W16(146, 2, 144); W32(146, 4, 138)
    e("    a=r 146 r=a 138 a=r 145 a> 0 while endif")
    e("  a=r 143 a++ r=a 143 a< 38 while")
    e("a=r 138 r=a 139 a=0 r=a 140")
    e("a=r 138 a> 0 ifl do")
    e("  a=r 138 r=a 141"); R16(141, 2); e("r=a 142"); R32(141, 4); e("r=a 138")
    e("  a=r 142 a== 0 ifl")
    e("    a=r 140 a== 0 ifl a=r 138 r=a 139 elsel"); W32(140, 0, 138); e("    endif")
    e("  elsel")
    e("    a=r 141 a+= 4 r=a 140")
    e("    do")
    e("      a=r 142 a*= 12 b=r 141 a+=b r=a 147"); R16(147, 2); e("b=r 142 a+=b r=a 142")
    R16(147, 0); e("      a> 0 ifl a=0 elsel a=r 142 a>>= 16 a> 0 ifl a=0 elsel a= 1 endif endif")
    e("      a> 0 ifl"); W16(141, 2, 142); e("        a=0 r=a 150"); W16(147, 2, 150); e("        a= 1 endif")
    e("    a> 0 while")
    e("  endif")
    e("  a=r 138 a> 0 while endif")
    # llenar listas
    e("a=r 139 r=a 138")
    e("a=r 138 a> 0 ifl do")
    e("  a=r 138 r=a 141"); R16(141, 2); e("r=a 142"); R32(141, 4); e("r=a 138")
    e("  a=r 142 a> 0 ifl")
    e("    do a=r 142 a> 128 ifl a= 37 r=a 148"); INSERT(141, 148)
    e("      a=r 142 a-= 128 r=a 142 a= 128 a*= 12 b=r 141 a+=b r=a 141 a= 1 elsel a=0 endif a> 0 while")
    U2IG(142, 148); I2UG(148, 149)
    e("    a=r 149 b=r 142 a==b ifnotl")
    e("      a=r 148 a-- r=a 148"); I2UG(148, 149)
    e("      a=r 149 a*= 12 b=r 141 a+=b r=a 146 a=r 142 b=r 149 a-=b a-- r=a 147"); INSERT(146, 147)
    e("    endif")
    INSERT(141, 148)
    e("  endif")
    e("  a=r 138 a> 0 while endif")

def ALLOC_RARE():                 # indx r120 -> r121 (0 = sin memoria)
    e("a=0 r=a 122")              # r122 = hecho
    e(f"a=r {GLUEC} a== 0 ifl")
    GLUE()
    HG('FREEL', 120); e("  a> 0 ifl"); REMOVE(120, 121); e("    a= 1 r=a 122 endif")
    e("endif")
    e("a=r 122 a== 0 ifl")
    e("  a=r 120 r=a 123")
    e("  do a=r 123 a++ r=a 123 a== 38 ifl a=0 elsel"); HG('FREEL', 123); e("    a== 0 ifl a= 1 elsel a=0 endif endif a> 0 while")
    e("  a=r 123 a== 38 ifl")
    I2UG(120, 124); e(f"    a=r 124 a*= 12 r=a 124 a=r {GLUEC} a-- r=a {GLUEC}")
    e(f"    a=r {UST} b=r {TEXT} a-=b b=r 124 a>b ifl a=r {UST} a-=b r=a {UST} r=a 121 elsel a=0 r=a 121 endif")
    e("  elsel")
    REMOVE(123, 121); SPLIT(121, 123, 120)
    e("  endif")
    e("endif")

def ALLOC():                      # indx r120 -> r121
    HG('FREEL', 120)
    e("a> 0 ifl"); REMOVE(120, 121)
    e("elsel")
    I2UG(120, 124); e(f"  a=r 124 a*= 12 r=a 124 a=r {HIU} b=r {LOU} a-=b b=r 124 a<b ifnotl")
    e(f"    a=r {LOU} r=a 121 b=r 124 a+=b r=a {LOU}")
    e("  elsel")
    ALLOC_RARE()
    e("  endif")
    e("endif")

# ---------------- RestartModel
def RESTART():
    e("a=0 r=a 150"); FOR_(151, 38, lambda: HS('FREEL', 151, 150))
    e(f"a=0 r=a {TEXT} a=r {MEMSZ} r=a {HIU}")
    e(f"a=r {MEMSZ} a>>= 3 r=a 150 a= 12 b=a a=r 150 a/=b a*= 84 b=a a=r {HIU} a-=b r=a {LOU} r=a {UST}")
    e(f"a=0 r=a {GLUEC} a=r {MAXORD} r=a {OFALL}")
    e(f"a=r {MAXORD} a> 12 ifl a= 12 endif a++ b=a a=0 a-=b r=a {RUNL} r=a {INITRL} a=0 r=a {PREVS}")
    e(f"a=r {HIU} a-= 12 r=a {HIU} r=a {MINC} r=a {MAXC} a=r {LOU} r=a {FS} a= 128 a*= 12 b=r {LOU} a+=b r=a {LOU}")
    e("a= 1 a<<= 8 r=a 150"); W16(MINC, 0, 150); e("a= 1 a<<= 8 a++ r=a 150"); W16(MINC, 2, 150)
    W32(MINC, 4, FS); e("a=0 r=a 150"); W32(MINC, 8, 150)
    e(f"a=r {FS} c=a a=0 r=a 151")
    e("do a=r 151 *c=a c++ a= 1 *c=a c++ a=0 *c=a c++ *c=a c++ *c=a c++ *c=a c++ a=r 151 a++ r=a 151 a> 255 until")
    # BinSumm[i][k + m] = 2^14 - IBE[k] / (i + 2)
    e("a=0 r=a 151")
    e("do")
    e("  a=0 r=a 152")
    e("  do")
    HG('IBE', 152); e("    r=a 153 a=r 151 a+= 2 b=a a=r 153 a/=b b=a a= 64 a<<= 8 a-=b r=a 154")
    e("    a=r 151 a<<= 6 b=r 152 a+=b d=a")
    e("    a=r 154 *d=a d++ d++ d++ d++ d++ d++ d++ d++ *d=a d++ d++ d++ d++ d++ d++ d++ d++ *d=a d++ d++ d++ d++ d++ d++ d++ d++ *d=a")
    e("    d++ d++ d++ d++ d++ d++ d++ d++ *d=a d++ d++ d++ d++ d++ d++ d++ d++ *d=a d++ d++ d++ d++ d++ d++ d++ d++ *d=a d++ d++ d++ d++ d++ d++ d++ d++ *d=a")
    e("    a=r 152 a++ r=a 152 a< 8 while")
    e("  a=r 151 a++ r=a 151 a< 128 while")
    # See[i][k] = [(5i+10) << 3, 3, 4]
    e(f"a=r {R('SEE')} d=a a=0 r=a 151")
    e("do")
    e("  a=r 151 a*= 5 a+= 10 a<<= 3 r=a 152 a=0 r=a 153")
    e("  do a=r 152 *d=a d++ a= 3 *d=a d++ a= 4 *d=a d++ a=r 153 a++ r=a 153 a< 16 while")
    e("  a=r 151 a++ r=a 151 a< 25 while")
    e(f"a=r {R('DUMMY')} d=a a=0 *d=a d++ a= 7 *d=a d++ a= 64 *d=a")

def FOR_(i, lim, body):
    e(f"a=0 r=a {i}")
    e("do")
    body()
    e(f"  a=r {i} a++ r=a {i} a< {lim} while")

# ---------------- CreateSuccessors -> r100 (0 = sin memoria)
def CREATE_SUCC():
    # c r101, upBranch r102, numPs r103, s r104, newSym r105, newFreq r106
    e(f"a=r {MINC} r=a 101"); R32(FS, 2); e("r=a 102 a=0 r=a 103 r=a 100 r=a 107")   # r107 = listo
    e(f"a=r {OFALL} a> 0 ifl"); HS('PSST', 103, FS); e("  a=r 103 a++ r=a 103 endif")
    e("do")
    R32(101, 8); e("  a> 0 ifl")
    e("    r=a 101"); R16(101, 0)
    e("    a== 1 ifl a=r 101 a+= 2 r=a 104 elsel")
    R8(FS, 0); e("      r=a 108"); R32(101, 4); e("      r=a 104")
    e("      do"); R8(104, 0); e("        b=r 108 a==b ifl a=0 elsel a=r 104 a+= 6 r=a 104 a= 1 endif a> 0 while")
    e("    endif")
    R32(104, 2); e("    b=r 102 a==b ifnotl")
    e("      r=a 101 a=r 103 a== 0 ifl a=r 101 r=a 100 a= 2 r=a 107 endif")   # listo: devuelve c
    e("      a=0")
    e("    elsel")
    HS('PSST', 103, 104); e("      a=r 103 a++ r=a 103 a= 1")
    e("    endif")
    e("  endif")
    e("a> 0 while")
    e("a=r 107 a== 0 ifl")
    R8(102, 0); e("  r=a 105 a=r 102 a++ r=a 102")
    R16(101, 0); e("  a== 1 ifl"); R8(101, 3); e("    r=a 106")
    e("  elsel")
    R32(101, 4); e("    r=a 104")
    e("    do"); R8(104, 0); e("      b=r 105 a==b ifl a=0 elsel a=r 104 a+= 6 r=a 104 a= 1 endif a> 0 while")
    R8(104, 1); e("    a-- r=a 108"); R16(101, 2); e("    r=a 109"); R16(101, 0); e("    b=a a=r 109 a-=b b=r 108 a-=b r=a 109")  # cf r108, s0 r109
    e("    a=r 108 a<<= 1 b=r 109 a>b ifl")
    e("      a=r 109 a<<= 1 r=a 110 a=r 108 a<<= 1 b=r 109 a+=b a-- b=r 110 a/=b a++ a++ r=a 106")
    e("    elsel")
    e("      a=r 108 a*= 5 b=r 109 a>b ifl a= 2 elsel a= 1 endif r=a 106")
    e("    endif")
    e("    a=r 106 a&= 255 r=a 106")
    e("  endif")
    e("  do")
    e(f"    a=r {HIU} b=r {LOU} a==b ifnotl a=r {HIU} a-= 12 r=a {HIU} r=a 111")
    e("    elsel"); e("      a=0 r=a 150"); HG('FREEL', 150)
    e("      a> 0 ifl a=0 r=a 150"); REMOVE(150, 111)
    e("      elsel a=0 r=a 120"); ALLOC_RARE(); e("        a=r 121 r=a 111")
    e("      endif")
    e("    endif")
    e("    a=r 111 a== 0 ifl a=0 r=a 100 a= 1 r=a 107 a=0 elsel")
    e("      a= 1 r=a 150"); W16(111, 0, 150); W8(111, 2, 105); W8(111, 3, 106); W32(111, 4, 102); W32(111, 8, 101)
    e("      a=r 103 a-- r=a 103"); HG('PSST', 103); e("      r=a 112"); W32(112, 2, 111)
    e("      a=r 111 r=a 101 a=r 103")
    e("    endif")
    e("  a> 0 while")
    e("  a=r 107 a== 0 ifl a=r 101 r=a 100 endif")
    e("endif")

# ---------------- Rescale (MinContext, FoundState)
def RESCALE():
    # stats r60, s r61, sumFreq r62, escFreq r63, adder r64, i r65, freq r66, s1 r67
    R32(MINC, 4); e(f"r=a 60 a=r {FS} r=a 61")
    e("a=r 61 b=r 60 a==b ifnotl")
    e("  a=r 61 c=a a=*c r=a 70 c++ a=*c r=a 71 c++ a=*c r=a 72 c++ a=*c r=a 73 c++ a=*c r=a 74 c++ a=*c r=a 75")
    e("  do a=r 61 a-= 6 r=a 67"); CPY(61, 67, n=6); e("    a=r 67 r=a 61 b=r 60 a==b ifl a=0 elsel a= 1 endif a> 0 while")
    e("  a=r 61 c=a a=r 70 *c=a c++ a=r 71 *c=a c++ a=r 72 *c=a c++ a=r 73 *c=a c++ a=r 74 *c=a c++ a=r 75 *c=a")
    e("endif")
    R8(61, 1); e("r=a 62"); R16(MINC, 2); e("b=r 62 a-=b r=a 63")
    e(f"a=r {OFALL} a> 0 ifl a= 1 elsel a=0 endif r=a 64")
    e("a=r 62 a+= 4 b=r 64 a+=b a>>= 1 r=a 62"); R16(MINC, 0); e("a-- r=a 65"); W8(61, 1, 62)
    e("do")
    e("  a=r 61 a+= 6 r=a 61"); R8(61, 1); e("  r=a 66 b=a a=r 63 a-=b r=a 63")
    e("  a=r 66 b=r 64 a+=b a>>= 1 r=a 66 b=r 62 a+=b r=a 62"); W8(61, 1, 66)
    A(61, 0); e("  a-= 5 c=a a=*c b=a a=r 66 a>b ifl")        # freq > s[-1].Freq
    e("    a=r 61 c=a a=*c r=a 70 c++ a=*c r=a 71 c++ a=*c r=a 72 c++ a=*c r=a 73 c++ a=*c r=a 74 c++ a=*c r=a 75")
    e("    a=r 61 r=a 67")
    e("    do a=r 67 a-= 6 r=a 68"); CPY(67, 68, n=6)
    e("      a=r 68 r=a 67 b=r 60 a==b ifl a=0 elsel a=r 67 a-= 5 c=a a=*c b=a a=r 66 a>b ifl a= 1 elsel a=0 endif endif a> 0 while")
    e("    a=r 67 c=a a=r 70 *c=a c++ a=r 71 *c=a c++ a=r 72 *c=a c++ a=r 73 *c=a c++ a=r 74 *c=a c++ a=r 75 *c=a")
    e("  endif")
    e("  a=r 65 a-- r=a 65")
    e("a> 0 while")
    R8(61, 1); e("a== 0 ifl")
    e("  a=0 r=a 65")
    e("  do a=r 65 a++ r=a 65 a=r 61 a-= 6 r=a 61 a++ c=a a=*c a== 0 while")
    e("  a=r 63 b=r 65 a+=b r=a 63")
    R16(MINC, 0); e("  r=a 68 b=r 65 a-=b r=a 69"); W16(MINC, 0, 69)            # numStats r68, nuevo r69
    e("  a=r 68 a++ a>>= 1 r=a 76")                                              # n0
    e("  a=r 69 a== 1 ifl")
    R8(60, 1); e("    r=a 66")
    e("    do a=r 63 a>>= 1 r=a 63 a=r 66 a++ a>>= 1 r=a 66 a=r 63 a> 1 while")
    e(f"    a=r {MINC} a+= 2 r=a 67"); CPY(67, 60, n=6); W8(MINC, 3, 66)
    e(f"    a=r {MINC} a+= 2 r=a {FS}"); U2IG(76, 77); INSERT(60, 77)
    e("    a= 1 r=a 78")                                                            # r78 = termino
    e("  elsel")
    e("    a=r 69 a++ a>>= 1 r=a 77")                                              # n1
    e("    a=r 76 b=r 77 a==b ifnotl")
    U2IG(76, 70); U2IG(77, 71)
    e("      a=r 70 b=r 71 a==b ifnotl")
    HG('FREEL', 71); e("        a> 0 ifl"); REMOVE(71, 72); W32(MINC, 4, 72)
    e("          a=r 77 a*= 12 r=a 73"); CPY(72, 60, nbytes_reg=73); INSERT(60, 70)
    e("        elsel"); SPLIT(60, 70, 71); e("        endif")
    e("      endif")
    e("    endif")
    e("    a=0 r=a 78")
    e("  endif")
    e("elsel a=0 r=a 78 endif")
    e("a=r 78 a== 0 ifl")
    e("  a=r 63 a>>= 1 b=a a=r 63 a-=b b=r 62 a+=b r=a 150"); W16(MINC, 2, 150)
    R32(MINC, 4); e(f"  r=a {FS}")
    e("endif")

# ---------------- UpdateModel
def UPDATE_MODEL():
    # fsym r80 ffreq r81 c r82 s r83 csmode r84 done r85 maxS r86 minS r87 hadmin r88 mc r89 ns r90 s0 r91 ns1 r92 sum r93 cf r94 sf r95
    e("a=0 r=a 84 r=a 85 r=a 88")
    R8(FS, 0); e("r=a 80"); R8(FS, 1); e("r=a 81")
    R32(MINC, 8); e("r=a 82 a=r 81 a< 31 ifl a=r 82 a> 0 ifl")        # MAX_FREQ/4 = 31
    R16(82, 0); e("    a== 1 ifl"); R8(82, 3); e("      a< 32 ifl a++ r=a 150"); W8(82, 3, 150); e("      endif")
    e("    elsel")
    R32(82, 4); e("      r=a 83"); R8(83, 0); e("      b=r 80 a==b ifnotl")
    e("        do a=r 83 a+= 6 r=a 83"); R8(83, 0); e("          b=r 80 a==b ifl a=0 elsel a= 1 endif a> 0 while")
    R8(83, 1); e("        r=a 150"); A(83, 0); e("        a-= 5 c=a a=*c b=a a=r 150 a<b ifnotl")
    SWAP6(83); e("          a=r 83 a-= 6 r=a 83")
    e("        endif")
    e("      endif")
    R8(83, 1); e("      a< 115 ifl a+= 2 r=a 150"); W8(83, 1, 150); R16(82, 2); e("        a+= 2 r=a 150"); W16(82, 2, 150); e("      endif")
    e("    endif")
    e("endif endif")
    e(f"a=r {OFALL} a== 0 ifl")
    e("  a= 1 r=a 84")
    e("elsel")
    W8(TEXT, 0, 80); e(f"  a=r {TEXT} a++ r=a {TEXT} b=r {UST} a<b ifnotl a= 1 r=a {RS} r=a 85 endif")
    e("  a=r 85 a== 0 ifl")
    e(f"    a=r {TEXT} r=a 86"); R32(FS, 2); e("    r=a 87")
    e("    a> 0 ifl a= 1 r=a 88 a=r 87 b=r 86 a>b ifnot a= 2 r=a 84 endif")
    e("    elsel"); W32(FS, 2, 86); e(f"      a=r {MINC} r=a 87")
    e("    endif")
    e("  endif")
    e("endif")
    e("a=r 84 a> 0 ifl")
    CREATE_SUCC()
    e("  a=r 100 a== 0 ifl")
    e(f"    a= 1 r=a {RS} r=a 85")
    e("  elsel")
    e("    a=r 84 a== 1 ifl")
    e(f"      a=r 100 r=a {MINC} r=a {MAXC}"); W32(FS, 2, 100); e("      a= 1 r=a 85")
    e("    elsel a=r 100 r=a 87 endif")
    e("  endif")
    e("endif")
    e("a=r 85 a== 0 ifl")
    e(f"  a=r 88 a> 0 ifl a=r {OFALL} a-- r=a {OFALL} a== 0 ifl a=r 87 r=a 86 a=r {MAXC} b=r {MINC} a==b ifnot a=r {TEXT} a-- r=a {TEXT} endif endif endif")
    e(f"  a=r {MINC} r=a 89 a=r {MAXC} r=a 82 a=r 87 r=a {MINC} r=a {MAXC}")
    e("  a=r 82 b=r 89 a==b ifl a= 1 r=a 85 endif")
    e("endif")
    e("a=r 85 a== 0 ifl")
    R16(89, 0); e("  r=a 90"); R16(89, 2); e("  b=r 90 a-=b b=r 81 a-=b a++ r=a 91")
    e("  do")
    R16(82, 0); e("    r=a 92 a== 1 ifl a=0 r=a 120 a= 2 r=a 96 elsel")          # r96: 2 = de 1 a 2, 1 = expandir, 0 = nada
    e("      a=0 r=a 96 a=r 92 a&= 1 a== 0 ifl")
    e("        a=r 92 a>>= 1 r=a 97"); U2IG(97, 98); e("        a=r 97 a++ r=a 150"); U2IG(150, 99)
    e("        a=r 98 b=r 99 a==b ifnot a=r 98 a++ r=a 120 a= 1 r=a 96 endif")
    e("      endif")
    e("    endif")
    e("    a=r 96 a> 0 ifl")
    ALLOC()
    e(f"      a=r 121 a== 0 ifl a= 1 r=a {RS} r=a 85 endif")
    e("    endif")
    e("    a=r 85 a== 0 ifl")
    e("      a=r 96 a== 2 ifl")
    R8(82, 3); e("        r=a 97 a=r 121 r=a 83")
    R8(82, 2); e("        r=a 150"); W8(83, 0, 150)
    e("        a=r 82 a+= 4 b=a a=r 83 a+= 2 c=a *c=*b b++ c++ *c=*b b++ c++ *c=*b b++ c++ *c=*b"); W32(82, 4, 83)
    e("        a=r 97 a< 30 ifl a<<= 1 elsel a= 120 endif r=a 97"); W8(83, 1, 97)
    e(f"        a=r 90 a> 3 ifl a= 1 elsel a=0 endif b=r {INITESC} a+=b b=r 97 a+=b r=a 93")
    e("      elsel")
    e("        a=r 96 a== 1 ifl")
    R32(82, 4); e("          r=a 99 a=r 97 a*= 12 r=a 98"); CPY(121, 99, nbytes_reg=98)
    e("          a=r 97 r=a 150"); U2IG(150, 151); e("          a=r 151 r=a 152"); INSERT(99, 152); W32(82, 4, 121)
    e("        endif")
    R16(82, 2); e("        r=a 93")
    e("        a=r 92 a<<= 1 b=r 90 a<b ifl a= 1 elsel a=0 endif r=a 94")
    e("        a=r 92 a<<= 2 b=r 90 a>b ifl a=0 elsel a=r 92 a<<= 3 b=a a=r 93 a>b ifl a=0 elsel a= 2 endif endif b=r 94 a+=b b=r 93 a+=b r=a 93")
    e("      endif")
    R32(82, 4); e("      r=a 83 a=r 92 a*= 6 b=r 83 a+=b r=a 83")
    e("      a=r 93 a+= 6 a<<= 1 b=r 81 a*=b r=a 94 a=r 91 b=r 93 a+=b r=a 95")
    W8(83, 0, 80); e("      a=r 92 a++ r=a 150"); W16(82, 0, 150); W32(83, 2, 86)
    e("      a=r 95 a*= 6 b=a a=r 94 a<b ifl")
    e("        a=r 95 b=a a=r 94 a>b ifl a= 2 elsel a= 1 endif r=a 150 a=r 95 a<<= 2 b=a a=r 94 a<b ifnot a=r 150 a++ r=a 150 endif a=r 150 r=a 94")
    e("        a=r 93 a+= 3 r=a 93")
    e("      elsel")
    e("        a= 4 r=a 150 a=r 95 a*= 9 b=a a=r 94 a<b ifnot a=r 150 a++ r=a 150 endif a=r 95 a*= 12 b=a a=r 94 a<b ifnot a=r 150 a++ r=a 150 endif")
    e("        a=r 95 a*= 15 b=a a=r 94 a<b ifnot a=r 150 a++ r=a 150 endif a=r 150 r=a 94 b=r 93 a+=b r=a 93")
    e("      endif")
    W16(82, 2, 93); W8(83, 1, 94)
    R32(82, 8); e("      r=a 82 b=r 89 a==b ifl a=0 elsel a= 1 endif")
    e("    elsel a=0 endif")
    e("  a> 0 while")
    e("endif")

# ---------------- DecodeSymbol -> r40 simbolo; marca DORESC / FORCEUM / r41 (1 = NextContext)
def DECODE():
    # s r42, i r43, count r44, hiCnt r45, summ r46, mc r47, numMasked r48, see r49, freqSum r50, sym r51, tmp r52..
    e(f"a=0 r=a {DORESC} r=a {FORCEUM} r=a 41 r=a 53")          # r53 = listo
    FOR_(52, 64, lambda: e(f"  a=r 52 a<<= 2 b=r {R('MASK')} a+=b d=a a= 255 *d=a d++ *d=a d++ *d=a d++ *d=a"))
    R16(MINC, 0); e("a== 1 ifnotl")
    R32(MINC, 4); e("  r=a 42"); R16(MINC, 2); e("  r=a 46"); THRESH(46); e("  r=a 44 r=a 45")
    R8(42, 1); e(f"  b=a a=r 44 a-=b r=a 44 b=r {K8M} a<b ifnotl")
    e("    a=0 r=a 150"); R8(42, 1); e("    r=a 151"); RCDEC(150, 151); NORM()
    e(f"    a=r 42 r=a {FS}"); R8(42, 0); e("    r=a 40")
    # update1_0
    R8(42, 1); e("    r=a 54"); R16(MINC, 2); e(f"    r=a 55 a=r 54 a<<= 1 b=r 55 a>b ifl a= 1 elsel a=0 endif r=a {PREVS} b=r {RUNL} a+=b r=a {RUNL}")
    e("    a=r 55 a+= 4 r=a 150"); W16(MINC, 2, 150); e("    a=r 54 a+= 4 r=a 54"); W8(42, 1, 54)
    e(f"    a=r 54 a> 124 ifl a= 1 r=a {DORESC} endif a= 1 r=a 41 r=a 53")
    e("  elsel")
    e(f"    a=0 r=a {PREVS}"); R16(MINC, 0); e("    a-- r=a 43")
    e("    do")
    e("      a=r 42 a+= 6 r=a 42"); R8(42, 1); e(f"      b=a a=r 44 a-=b r=a 44 b=r {K8M} a<b ifnotl")
    R8(42, 1); e("        r=a 151 b=a a=r 45 b=r 44 a-=b b=r 151 a-=b r=a 150"); RCDEC(150, 151); NORM()
    e(f"        a=r 42 r=a {FS}"); R8(42, 0); e("        r=a 40")
    # update1
    R8(42, 1); e("        a+= 4 r=a 54"); R16(MINC, 2); e("        a+= 4 r=a 150"); W16(MINC, 2, 150); W8(42, 1, 54)
    A(42, 0); e("        a-= 5 c=a a=*c b=a a=r 54 a>b ifl")
    SWAP6(42); e(f"          a=r 42 a-= 6 r=a 42 r=a {FS} a=r 54 a> 124 ifl a= 1 r=a {DORESC} endif")
    e("        endif")
    e("        a= 1 r=a 41 r=a 53 a=0")
    e("      elsel")
    e("        a=r 43 a-- r=a 43")
    e("      endif")
    e("    a> 0 while")
    e("    a=r 53 a== 0 ifl")
    e("      a=r 45 b=r 44 a-=b r=a 45 a=r 46 b=r 45 a-=b r=a 150"); RCDEC(45, 150)
    R8(FS, 0); e(f"      a+= 192 a>>= 5 a&= 8 r=a {HIBITS}")
    R8(42, 0); e("      r=a 150 a=0 r=a 151"); HS('MASK', 150, 151)
    R32(MINC, 4); e("      r=a 52")
    e("      do"); R8(52, 0); e("        r=a 150"); HS('MASK', 150, 151); R8(52, 6); e("        r=a 150"); HS('MASK', 150, 151)
    e("        a=r 52 a+= 12 r=a 52 b=r 42 a<b while")
    e("    endif")
    e("  endif")
    e("elsel")
    # contexto binario
    e(f"  a=r {MINC} a+= 2 r=a 42"); R8(42, 1); e("  r=a 54")
    R8(FS, 0); e(f"  a+= 192 a>>= 5 a&= 8 r=a {HIBITS}")
    R32(MINC, 8); e("  r=a 150"); R16(150, 0); e("  a-- r=a 150"); HG('NS2BS', 150); e("  r=a 55")
    R8(42, 0); e(f"  a+= 192 a>>= 4 a&= 16 b=r 55 a+=b b=r {HIBITS} a+=b b=r {PREVS} a+=b r=a 55")
    e(f"  a=r {RUNL} b=r {K8M} a<b ifnot a=r 55 a+= 32 r=a 55 endif")
    e("  a=r 54 a-- a<<= 6 b=r 55 a+=b b=r " + str(R('BINS')) + " a+=b r=a 56 d=a a=*d r=a 57")      # r56 dir, r57 pr
    e(f"  a=r {RANGE} a>>= 14 b=r 57 a*=b r=a 58")                                             # size0
    e("  a=r 57 a+= 32 a>>= 7 b=a a=r 57 a-=b r=a 57")                                          # pr - mean
    e(f"  a=r {CODE} b=r 58 a<b ifl")
    e(f"    a=r 57 a+= 128 r=a 150 a=r 56 d=a a=r 150 *d=a a=r 58 r=a {RANGE}"); NORM1()
    R8(42, 0); e(f"    r=a 40 a=r 42 r=a {FS} a= 1 r=a {PREVS} a=r {RUNL} a++ r=a {RUNL}")
    e("    a=r 54 a< 128 ifl a++ r=a 150"); W8(42, 1, 150); e("    endif")
    e("    a= 1 r=a 41 r=a 53")
    e("  elsel")
    e("    a=r 56 d=a a=r 57 *d=a a>>= 10 r=a 150"); HG('EXPESC', 150); e(f"    r=a {INITESC}")
    e(f"    a=r {CODE} b=r 58 a-=b r=a {CODE} a=r {RANGE} a-=b r=a {RANGE}")
    R8(42, 0); e("    r=a 150 a=0 r=a 151"); HS('MASK', 150, 151)
    e(f"    a=0 r=a {PREVS}")
    e("  endif")
    e("endif")
    # escapes
    e("a=r 53 a== 0 ifl")
    e("do")
    NORM()
    e(f"  a=r {MINC} r=a 47"); R16(47, 0); e("  r=a 48")
    e("  do")
    e(f"    a=r {OFALL} a++ r=a {OFALL}"); R32(47, 8)
    e("    a== 0 ifl a= 2 r=a 53 a=0 elsel r=a 47"); R16(47, 0); e("      b=r 48 a==b ifl a= 1 elsel a=0 endif endif")
    e("  a> 0 while")
    e("  a=r 53 a== 0 ifl")
    R32(47, 4); e(f"    r=a 42 a=r 47 r=a {MINC}"); R16(47, 0); e("    r=a 43 a=0 r=a 45 a=r 42 r=a 52")
    e("    do"); R8(52, 0); e("      r=a 150"); HG('MASK', 150); e("      r=a 151"); R8(52, 1); e("      b=r 151 a&=b b=r 45 a+=b r=a 45")
    e("      a=r 52 a+= 6 r=a 52 a=r 43 a-- r=a 43 a> 0 while")
    # MakeEscFreq -> r49 (see), r50 (escFreq)
    R16(47, 0); e("    r=a 60 a> 255 ifl a=0 elsel a= 1 endif")      # numStats != 256
    e("    a> 0 ifl")
    e("      a=r 60 b=r 48 a-=b r=a 61 a-- r=a 150"); HG('NS2I', 150); e("      a*= 48 r=a 62")      # See[NS2I[nonMasked-1]] -> r62 (16*3 palabras)
    R32(47, 8); e("      r=a 150"); R16(150, 0); e("      b=r 60 a-=b b=a a=r 61 a<b ifl a= 1 elsel a=0 endif r=a 63")
    R16(47, 2); e("      r=a 150 a=r 60 a*= 11 b=a a=r 150 a<b ifl a=r 63 a+= 2 r=a 63 endif")
    e(f"      a=r 48 b=r 61 a>b ifl a=r 63 a+= 4 r=a 63 endif a=r 63 b=r {HIBITS} a+=b a*= 3 b=r 62 a+=b b=r {R('SEE')} a+=b r=a 49")
    e("      d=a a=*d a<<= 16 a>>= 16 r=a 150 d++ a=*d b=a a=r 150 a>>=b r=a 151 b=a a=r 150 a-=b d-- *d=a")
    e("      a=r 151 a== 0 ifl a= 1 endif r=a 50")
    e("    elsel")
    e(f"      a=r {R('DUMMY')} r=a 49 a= 1 r=a 50")
    e("    endif")
    e("    a=r 50 b=r 45 a+=b r=a 50"); THRESH(50); e("    r=a 44")
    e("    b=r 45 a<b ifl")
    R32(MINC, 4); e("      r=a 42 a=r 44 r=a 45")
    e("      do"); R8(42, 0); e("        r=a 150"); HG('MASK', 150); e("        r=a 151"); R8(42, 1)
    e(f"        b=r 151 a&=b b=a a=r 44 a-=b r=a 44 a=r 42 a+= 6 r=a 42 a=r 44 b=r {K8M} a<b while")
    e("      a=r 42 a-= 6 r=a 42"); R8(42, 1); e("      r=a 151 b=a a=r 45 b=r 44 a-=b b=r 151 a-=b r=a 150"); RCDEC(150, 151); NORM()
    # See_UPDATE
    e("      a=r 49 d=a d++ a=*d a< 7 ifl d++ a=*d a-- a&= 255 *d=a a== 0 ifl d-- d-- a=*d a<<= 1 a<<= 16 a>>= 16 *d=a d++ a=*d b=a a= 3 a<<=b a&= 255 d++ *d=a d-- a=*d a++ *d=a endif endif")
    e(f"      a=r 42 r=a {FS}"); R8(42, 0); e("      r=a 40")
    # update2
    R8(42, 1); e(f"      a+= 4 r=a 54 a=r {INITRL} r=a {RUNL}"); R16(MINC, 2); e("      a+= 4 r=a 150"); W16(MINC, 2, 150); W8(42, 1, 54)
    e(f"      a=r 54 a> 124 ifl a= 1 r=a {DORESC} endif a= 1 r=a {FORCEUM} r=a 53")
    e("    elsel")
    e("      a=r 50 b=a a=r 44 a<b ifnot a= 2 r=a 53 a= 3 r=a 59 endif")      # error
    e("      a=r 53 a== 0 ifl")
    e("        a=r 50 b=r 45 a-=b r=a 150"); RCDEC(45, 150)
    e("        a=r 49 d=a a=*d b=r 50 a+=b a<<= 16 a>>= 16 *d=a")
    R32(MINC, 4); e("        r=a 52"); R16(MINC, 0); e("        r=a 43 a=0 r=a 151")
    e("        do"); R8(52, 0); e("          r=a 150"); HS('MASK', 150, 151); e("          a=r 52 a+= 6 r=a 52 a=r 43 a-- r=a 43 a> 0 while")
    e("      endif")
    e("    endif")
    e("  endif")
    e("a=r 53 a== 0 while")
    e("endif")

# =======================================================================
e("hcomp")
e("halt")
e("pcomp zpaqppmd ;")
e("""(ZPAQPPMD: decodificador de PPMd var.H - Ppmd7 del 7-Zip SDK con el codificador de
 rango de 7z - en ZPAQL, para zpaq-std -ma:ppmd. zpaq-std, 2026. Entrada: orden, memoria,
 tamano original y el flujo; el monticulo del modelo se reproduce byte a byte en M.)""")
e("a> 255 ifl")
e(f"  a=c r=a {NIN}")
for k, v in HB.items(): LOADK(v); e(f"  r=a {R(k)}")
e(f"  a= 1 a<<= 24 r=a {K24} a= 128 a<<= 24 r=a {K8M}")
# cabecera
e(f"  a=0 c=a a=*c r=a {MAXORD}")
e(f"  a= 4 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a {MEMSZ}")
e(f"  a= 8 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a {ORIG}")
# mover la entrada (desde el byte 9) a [MEM, ...), de atras hacia adelante; poner en 0 lo que ocupaba
e(f"  a=r {NIN} a-= 9 r=a 150 b=r {MEMSZ} a+=b r=a {INEND} a=r {MEMSZ} r=a {RP}")
e("  a=r 150 a> 0 ifl do")
e(f"    a=r 150 a-- r=a 150 a+= 9 b=a a=r 150 b=r {MEMSZ} a+=b c=a")
e("    a=r 150 a+= 9 b=a *c=*b a=r 150 a> 0 while endif")
e(f"  a=r {NIN} b=r {MEMSZ} a>b ifl a=b endif r=a 150 a> 0 ifl a=0 c=a do a=0 *c=a c++ a=c b=r 150 a<b while endif")
# tablas de Ppmd7_Construct
e("  a=0 r=a 151 r=a 152")                     # i, k
e("  do")
e("    a=r 151 a> 11 ifl a= 4 elsel a=r 151 a>>= 2 a++ endif r=a 153")
e("    do"); HS('U2I', 152, 151); e("      a=r 152 a++ r=a 152 a=r 153 a-- r=a 153 a> 0 while")
HS('I2U', 151, 152)
e("    a=r 151 a++ r=a 151 a< 38 while")
e("  a=0 r=a 151")
e("  do a=r 151 a== 0 ifl a=0 elsel a== 1 ifl a= 2 elsel a< 11 ifl a= 4 elsel a= 6 endif endif endif r=a 150"); HS('NS2BS', 151, 150)
e("    a=r 151 a++ r=a 151 a> 255 until")
e("  a=0 r=a 151 do"); HS('NS2I', 151, 151); e("    a=r 151 a++ r=a 151 a< 3 while")
e("  a= 3 r=a 152 a= 1 r=a 153")                # m, k
e("  do"); HS('NS2I', 151, 152); e("    a=r 153 a-- r=a 153 a== 0 ifl a=r 152 a++ r=a 152 a-- a-- r=a 153 endif a=r 151 a++ r=a 151 a> 255 until")
for i, v in enumerate([25, 14, 9, 7, 5, 5, 4, 4, 4, 3, 3, 3, 2, 2, 2, 2]):
    e(f"  a= {i} r=a 151 a= {v} r=a 150"); HS('EXPESC', 151, 150)
for i, v in enumerate([0x3CDD, 0x1F3F, 0x59BF, 0x48F3, 0x64A1, 0x5ABC, 0x6632, 0x6051]):
    e(f"  a= {i} r=a 151"); LOADK(v); e("  r=a 150"); HS('IBE', 151, 150)
e(f"  a=0 r=a {HIBITS} r=a {INITESC} r=a {OUTN} a= 1 r=a {RS}")
# rc init: el primer byte tiene que ser 0
e(f"  a=0 r=a {CODE} a=0 a-- r=a {RANGE}")
RB(); e("  a> 0 ifl a=r " + str(ORIG) + " r=a " + str(OUTN) + " endif")      # flujo roto: no decodificar
for _ in range(4): RB(); e(f"  b=a a=r {CODE} a<<= 8 a+=b r=a {CODE}")
e(f"  a=r {OUTN} b=r {ORIG} a<b ifl")
e("  do")
e(f"    a=r {RS} a> 0 ifl")
RESTART()
e(f"      a=0 r=a {RS}")
e("    endif")
DECODE()
e("    a=r 53 a== 1 ifl")
e(f"      a=r 40 out a=r {OUTN} a++ r=a {OUTN}")
e(f"      a=r {DORESC} a> 0 ifl")
RESCALE()
e("      endif")
e(f"      a=r {FORCEUM} a> 0 ifl a= 1 elsel")
R32(FS, 2); e(f"        r=a 150 a=r {OFALL} a== 0 ifl a=r 150 b=r {TEXT} a>b ifl a=r 150 r=a {MINC} r=a {MAXC} a=0 elsel a= 1 endif elsel a= 1 endif")
e("      endif")
e("      a> 0 ifl")
UPDATE_MODEL()
e("      endif")
e(f"      a=r {OUTN} b=r {ORIG} a<b")
e("    elsel a=0 endif")
e("  while")
e("  endif")
e("  a=0 c=a")
e("elsel")
e("  *c=a c++")
e("endif")
e("halt")
e("end")
open(sys.argv[1], 'w').write('\n'.join(out) + '\n')
