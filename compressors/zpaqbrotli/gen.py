# Generador de ZPAQBROTLI: flujos de brotli (RFC 7932) en ZPAQL, escrito para zpaq-std
# desde la especificacion (no deriva de zpaqlpy). ZPAQL no tiene subrutinas: la lectura
# de codigos prefijo, que aparece en muchos lugares, es una MAQUINA DE ESTADOS (un solo
# lazo; "llamar" es guardar el estado de retorno); lo caliente (simbolos, literales,
# copias) va en linea. Mismo algoritmo que la referencia en Python con la que se probo.
#   python3 gen.py salida.txt
#
# La entrada es un PREFIJO DE DATOS fijo (126608 bytes: diccionario estatico, tabla de
# contexto, cadenas y tabla de transformaciones, tamanos del diccionario y constantes)
# y detras el flujo de brotli. M: la entrada desde 0; la salida en OB = n + 16 (hace falta
# entera: las copias y el contexto miran hacia atras). H (ph = 19): constantes 0..219,
# modos 256, indices de arboles 512/768/1024 (literales, comandos, distancias), largos
# del codigo de largos 1280, su arbol 1312, largos 1408, mapas de contexto 2176 (dist.) y
# 4096 (literales), y los arboles desde 20480. Un arbol: H[t] = 1 si tiene un solo
# simbolo (0 bits), H[t+1..15] cuantos codigos hay de cada largo, H[t+16..] los simbolos.
import sys
out = []
def e(s): out.append(s)

# desplazamientos en el prefijo (M)
D_LUT, D_PS, D_PSM, D_TR, D_SB, D_OF, D_K, PFX = 122784, 124832, 125056, 125184, 125568, 125600, 125728, 126608
# bases en H (registro -> valor)
HB = dict(INSB=0, INSX=24, CPYB=48, CPYX=72, CELI=96, CELC=107, BLB=118, BLX=144, CLO=170, CLPL=188, CLPV=204,
          MOD=256, LTI=512, ITI=768, DTI=1024, CLL=1280, CLT=1312, LENS=1408, CMDM=2176, CMLM=4096, HEAP=20480)
MB_ = dict(DLUT=D_LUT, DPS=D_PS, DPSM=D_PSM, DTR=D_TR, DSB=D_SB, DOF=D_OF)
REG = {}
for i, k in enumerate(list(HB) + list(MB_)): REG[k] = 150 + i
R = lambda k: REG[k]
# estados
S_END, S_HDR, S_MBH, S_CAT, S_CAT2, S_CAT3, S_POST, S_CML, S_CMD, S_TREES, S_CMDS, S_RC = range(12)

def LOADK(v):
    if v < 256: e(f"a= {v}"); return
    bs = []
    while v: bs.append(v & 255); v >>= 8
    e(f"a= {bs[-1]}")
    for b in reversed(bs[:-1]):
        e(f"a<<= 8 a+= {b}" if b else "a<<= 8")
def HGET(base, idx):          # a = H[r base + r idx]; base: nombre o numero de registro
    br = R(base) if isinstance(base, str) else base
    e(f"a=r {idx} b=r {br} a+=b d=a a=*d")
def HSET(base, idx, val):
    br = R(base) if isinstance(base, str) else base
    e(f"a=r {idx} b=r {br} a+=b d=a a=r {val} *d=a")
def MGET(base, idx):          # a = M[r base + r idx]
    e(f"a=r {idx} b=r {R(base)} a+=b c=a a=*c")
def BIT():                    # a = siguiente bit, LSB primero (r2 = bit absoluto en M)
    e("a=r 2 a>>= 3 c=a a=r 2 a&= 7 b=a a=*c a>>=b a&= 1 r=a 250 a=r 2 a++ r=a 2 a=r 250")
def BITS(n, dst):             # r dst = n bits (n inmediato o 'rN'), el primero es el bit 0
    if isinstance(n, int):
        e(f"a= {n} r=a 245")
    else:
        e(f"a=r {n[1:]} r=a 245")                  # antes de poner dst en 0: puede ser el mismo
    e(f"a=0 r=a {dst} r=a 246 a=r 245")
    e("a> 0 ifl")
    e("  do")
    BIT(); e(f"    b=r 246 a<<=b b=r {dst} a|=b r=a {dst} a=r 246 a++ r=a 246 b=r 245")
    e("  a<b while")
    e("endif")
def DECSYM(tree, dst):        # r dst = simbolo del arbol con base en r tree
    e(f"a=r {tree} d=a a=*d a> 0 ifl")
    e(f"  a=r {tree} a+= 16 d=a a=*d r=a {dst}")
    e("elsel")
    e("  a=0 r=a 240 r=a 241 r=a 242 a= 1 r=a 243")
    e("  do")
    BIT(); e("    b=a a=r 240 a|=b r=a 240")
    e(f"    a=r {tree} b=r 243 a+=b d=a a=*d r=a 244")
    e("    a=r 241 b=r 244 a+=b b=a a=r 240 a<b ifl")
    e(f"      a=r 240 b=r 241 a-=b b=r 242 a+=b b=r {tree} a+=b a+= 16 d=a a=*d r=a {dst} a=0")
    e("    elsel")
    e("      a=r 242 b=r 244 a+=b r=a 242 a=r 241 b=r 244 a+=b a<<= 1 r=a 241 a=r 240 a<<= 1 r=a 240")
    e(f"      a=r 243 a++ r=a 243 a> 15 ifl a=0 r=a {dst} a=0 elsel a= 1 endif")   # roto: no colgarse
    e("    endif")
    e("  a> 0 while")
    e("endif")
def BUILD(asize, lens, dest):
    """Arbol canonico desde H[r lens + i], i < r asize, en H[r dest ..]."""
    e("a=0 r=a 200 r=a 201")
    e("do")
    HSET(dest, 200, 201); e("  a=r 200 a++ r=a 200")
    e("a< 16 while")
    e("a=0 r=a 200 r=a 202 r=a 203")                  # i, nz, ultimo
    e("do")
    HGET(lens, 200)
    e("  a> 0 ifl")
    e(f"    r=a 204 b=r {dest} a+=b d=a a=*d a++ *d=a a=r 202 a++ r=a 202 a=r 200 r=a 203")
    e("  endif")
    e(f"  a=r 200 a++ r=a 200 b=r {asize}")
    e("a<b while")
    e("a=r 202 a< 2 ifl")                              # un simbolo (o ninguno): 0 bits
    e(f"  a=r {dest} d=a a= 1 *d=a a=r {dest} a+= 16 d=a a=r 203 *d=a")
    e("elsel")
    e(f"  a=r {dest} d=a a=0 *d=a r=a 205 a= 1 r=a 206")   # r205 k, r206 L
    e("  do")
    e("    a=0 r=a 200")
    e("    do")
    HGET(lens, 200); e("      b=r 206 a==b ifl")
    e(f"        a=r 205 b=r {dest} a+=b a+= 16 d=a a=r 200 *d=a a=r 205 a++ r=a 205")
    e("      endif")
    e(f"      a=r 200 a++ r=a 200 b=r {asize}")
    e("    a<b while")
    e("    a=r 206 a++ r=a 206")
    e("  a< 16 while")
    e("endif")
def ZERO(base, n):            # H[r base .. + r n] = 0
    e("a=0 r=a 200 r=a 201")
    e(f"a=r {n} a> 0 ifl")
    e("do")
    HSET(base, 200, 201); e(f"  a=r 200 a++ r=a 200 b=r {n}")
    e("a<b while")
    e("endif")
def VLU8(dst):
    BIT(); e(f"a== 0 ifl a=0 r=a {dst} elsel")
    BITS(3, 247); e(f"a=r 247 a== 0 ifl a= 1 r=a {dst} elsel")
    BITS('r247', 248); e(f"a= 1 b=r 247 a<<=b b=r 248 a+=b r=a {dst} endif endif")
def BLEN(ctree, dst):
    DECSYM(ctree, 207); HGET('BLX', 207); e("r=a 208"); BITS('r208', 209); HGET('BLB', 207); e(f"b=r 209 a+=b r=a {dst}")
def SWITCH(ttree, ctree, nbt, bt, pb, bl):
    DECSYM(ttree, 207)
    e("a=r 207 a== 0 ifl")
    e(f"  a=r {pb} r=a 208")
    e("elsel a== 1 ifl")
    e(f"  a=r {bt} a++ r=a 208 b=r {nbt} a<b ifnot a=0 r=a 208 endif")
    e("elsel")
    e("  a=r 207 a-= 2 r=a 208")
    e("endif endif")
    e(f"a=r {bt} r=a {pb} a=r 208 r=a {bt}")
    BLEN(ctree, bl)
def PUTO():                   # a al final de la salida (M y OUT)
    e("c=r 4 *c=a out a=c a++ r=a 4")
def CALLRC(asize_expr_done, ret):   # r12 asize y r13 destino ya puestos
    e(f"a= {ret} r=a 11 a= {S_RC} r=a 10")
def STATE(n):
    e(f"a=r 10 a== {n} ifl")

e("hcomp")
e("halt")
e("pcomp zpaqbrotli ;")
e("""(ZPAQBROTLI: decodificador de brotli - RFC 7932 - en ZPAQL, para zpaq-std -ma:brotli.
 zpaq-std, 2026, escrito desde la especificacion. Entrada: un prefijo de datos fijo con
 el diccionario estatico, la tabla de contexto y las transformaciones, y el flujo. La
 lectura de codigos prefijo es una maquina de estados. La salida queda en M y sale
 con out.)""")
e("a> 255 ifl")
e("  a=c r=a 1")
for k, v in HB.items(): LOADK(v); e(f"  r=a {R(k)}")
for k, v in MB_.items(): LOADK(v); e(f"  r=a {R(k)}")
# constantes del prefijo (LE32) a H[0..219]
LOADK(D_K); e("  r=a 90 a=0 r=a 91")
e("  do")
e("    a=r 90 a+= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a 92")
e("    a=r 91 d=a a=r 92 *d=a a=r 90 a+= 4 r=a 90 a=r 91 a++ r=a 91")
e("  a< 220 while")
e("  a=r 1 a+= 16 r=a 3 r=a 4")
LOADK(PFX * 8); e("  r=a 2")
e(f"  a= {S_HDR} r=a 10 a= 16 r=a 40 a= 15 r=a 41 a= 11 r=a 42 a= 4 r=a 43")
e("  do")
# ---- cabecera del flujo: WBITS
STATE(S_HDR)
BIT(); e("    a== 0 ifl a= 16 r=a 9 elsel")
BITS(3, 9); e("    a=r 9 a> 0 ifl a+= 17 r=a 9 elsel")
BITS(3, 9); e("    a=r 9 a> 0 ifl a+= 8 r=a 9 elsel a= 17 r=a 9 endif endif endif")
e("    a= 1 b=r 9 a<<=b a-= 16 r=a 5")
e(f"    a= {S_MBH} r=a 10")
e("  endif")
# ---- cabecera de meta-bloque
STATE(S_MBH)
BIT(); e("    r=a 6 a> 0 ifl"); BIT(); e(f"      a> 0 ifl a= {S_END} r=a 10 endif")
e("    endif")
e(f"    a=r 10 a== {S_MBH} ifl")
BITS(2, 9)
e("      a=r 9 a== 3 ifl")                             # metadatos
BIT(); BITS(2, 9); e("        a=r 9 r=a 98 a<<= 3 r=a 9"); BITS('r9', 9)
e("        a=r 98 a> 0 ifl a=r 9 a++ r=a 9 endif")
e("        a=r 2 a+= 7 a>>= 3 a<<= 3 b=r 9 a+=b a+=b a+=b a+=b a+=b a+=b a+=b a+=b r=a 2")
e(f"        a=r 6 a> 0 ifl a= {S_END} r=a 10 endif")
e("      elsel")
e("        a+= 4 a<<= 2 r=a 9"); BITS('r9', 7); e("        a=r 7 a++ r=a 7")
e("        a=0 r=a 9 a=r 6 a== 0 ifl"); BIT(); e("          r=a 9 endif")
e("        a=r 9 a> 0 ifl")                           # sin comprimir
e("          a=r 2 a+= 7 a>>= 3 a<<= 3 r=a 2")
e("          do")
e("            a=r 2 a>>= 3 c=a a=*c"); PUTO(); e("            a=r 2 a+= 8 r=a 2 a=r 7 a-- r=a 7")
e("          a> 0 while")
e("        elsel")
e(f"          a=0 r=a 37 r=a 8 a=r {R('HEAP')} r=a 14 a= {S_CAT} r=a 10")
e("        endif")
e("      endif")
e("    endif")
e("  endif")
# ---- las tres categorias: NBLTYPES y sus codigos
CATR = [(15, 18, 21, 24, 27, 30), (16, 19, 22, 25, 28, 31), (17, 20, 23, 26, 29, 32)]  # nbt bt pb bl ttree ctree
STATE(S_CAT)
e("    a=r 37 a== 3 ifl")
e(f"      a= {S_POST} r=a 10")
e("    elsel")
VLU8(9); e("      a=r 9 a++ r=a 9")
for c, (nbt, bt, pb, bl, tt, ct) in enumerate(CATR):
    e(f"      a=r 37 a== {c} ifl a=r 9 r=a {nbt} a=0 r=a {bt} a= 1 r=a {pb} endif")
e("      a=r 9 a> 1 ifl")
e("        a+= 2 r=a 12 a=r 14 r=a 13")
for c, (nbt, bt, pb, bl, tt, ct) in enumerate(CATR):
    e(f"        a=r 37 a== {c} ifl a=r 14 r=a {tt} endif")
e("        a=r 14 a+= 16 b=r 12 a+=b r=a 14")
CALLRC(0, S_CAT2)
e("      elsel")
for c, (nbt, bt, pb, bl, tt, ct) in enumerate(CATR):
    e(f"        a=r 37 a== {c} ifl a= 1 a<<= 28 r=a {bl} endif")
e(f"        a=r 37 a++ r=a 37")
e("      endif")
e("    endif")
e("  endif")
STATE(S_CAT2)
e("    a= 26 r=a 12 a=r 14 r=a 13")
for c, (nbt, bt, pb, bl, tt, ct) in enumerate(CATR):
    e(f"    a=r 37 a== {c} ifl a=r 14 r=a {ct} endif")
e("    a=r 14 a+= 42 r=a 14")
CALLRC(0, S_CAT3)
e("  endif")
STATE(S_CAT3)
for c, (nbt, bt, pb, bl, tt, ct) in enumerate(CATR):
    e(f"    a=r 37 a== {c} ifl"); BLEN(ct, bl); e("    endif")
e(f"    a=r 37 a++ r=a 37 a= {S_CAT} r=a 10")
e("  endif")
# ---- NPOSTFIX, NDIRECT, modos, mapa de contexto de literales
def CMAP_HEAD(ntrees, size_reg, next_state_direct, ret_state):
    """rlemax y el arbol del mapa (o, si hay un solo arbol, el mapa en ceros)."""
    e(f"    a=r {ntrees} a> 1 ifl")
    BIT(); e("      a> 0 ifl"); BITS(4, 38); e("        a=r 38 a++ r=a 38 elsel a=0 r=a 38 endif")
    e(f"      a=r {ntrees} b=r 38 a+=b r=a 12 a=r 14 r=a 13 r=a 39 a+= 16 b=r 12 a+=b r=a 14")
    CALLRC(0, ret_state)
    e("    elsel")
    e(f"      a= {next_state_direct} r=a 10")
    e("    endif")
STATE(S_POST)
BITS(2, 33); BITS(4, 34); e("    a=r 33 b=a a=r 34 a<<=b r=a 34")
e("    a=0 r=a 9")
e("    do")
BITS(2, 247); HSET('MOD', 9, 247); e("      a=r 9 a++ r=a 9 b=r 15")
e("    a<b while")
e("    a=r 15 a<<= 6 r=a 52"); ZERO('CMLM', 52)
VLU8(35); e("    a=r 35 a++ r=a 35")
CMAP_HEAD(35, 52, S_CML, S_CML)
e("    a=r 35 a< 2 ifl a=0 r=a 38 endif")
e("  endif")
def CMAP_READ(mapbase, size_reg, ntrees):
    """Los valores del mapa (arbol en r39, RLE de ceros hasta r38) y la IMTF."""
    e(f"    a=r {ntrees} a> 1 ifl")
    e("      a=0 r=a 53")
    e("      do")
    DECSYM(39, 54)
    e("        a=r 54 a== 0 ifl")
    e("          a=r 53 a++ r=a 53")
    e("        elsel a=r 38 b=r 54 a<b ifnotl")          # 1..rlemax: ceros (el mapa ya esta en 0)
    BITS('r54', 55); e("          a= 1 b=r 54 a<<=b b=r 55 a+=b b=r 53 a+=b r=a 53")
    e("        elsel")
    e("          a=r 54 b=r 38 a-=b r=a 55"); HSET(mapbase, 53, 55); e("          a=r 53 a++ r=a 53")
    e("        endif endif")
    e(f"        a=r 53 b=r {size_reg}")
    e("      a<b while")
    BIT(); e("      a> 0 ifl")                              # IMTF
    e("        a=0 r=a 53")
    e("        do")
    HSET('LENS', 53, 53); e("          a=r 53 a++ r=a 53")
    e("        a> 255 until")
    e("        a=0 r=a 53")
    e("        do")
    HGET(mapbase, 53); e("          r=a 54"); HGET('LENS', 54); e("          r=a 55"); HSET(mapbase, 53, 55)
    e("          a=r 54 a> 0 ifl")
    e("            do")
    e("              a=r 54 a-- r=a 56"); HGET('LENS', 56); e("              r=a 57"); HSET('LENS', 54, 57)
    e("              a=r 56 r=a 54")
    e("            a> 0 while")
    HSET('LENS', 54, 55)
    e("          endif")
    e(f"          a=r 53 a++ r=a 53 b=r {size_reg}")
    e("        a<b while")
    e("      endif")
    e("    endif")
STATE(S_CML)
CMAP_READ('CMLM', 52, 35)
e("    a=r 17 a<<= 2 r=a 52"); ZERO('CMDM', 52)
VLU8(36); e("    a=r 36 a++ r=a 36")
CMAP_HEAD(36, 52, S_CMD, S_CMD)
e("  endif")
STATE(S_CMD)
e("    a=r 17 a<<= 2 r=a 52")
CMAP_READ('CMDM', 52, 36)
e(f"    a=0 r=a 44 r=a 45 a= {S_TREES} r=a 10")
e("  endif")
# ---- los arboles: literales (256), comandos (704), distancias
STATE(S_TREES)
e("    a=r 45 a== 0 ifl a=r 44 b=r 35 a<b ifnot a= 1 r=a 45 a=0 r=a 44 endif endif")
e("    a=r 45 a== 1 ifl a=r 44 b=r 16 a<b ifnot a= 2 r=a 45 a=0 r=a 44 endif endif")
e("    a=r 45 a== 2 ifl a=r 44 b=r 36 a<b ifnot a= 3 r=a 45 endif endif")
e(f"    a=r 45 a== 3 ifl a= {S_CMDS} r=a 10 elsel")
e("      a=r 45 a== 0 ifl a= 255 a++ r=a 12 a=r 14"); HSET('LTI', 44, 14); e("      endif")
e("      a=r 45 a== 1 ifl a= 11 a<<= 6 r=a 12"); HSET('ITI', 44, 14); e("      endif")
e("      a=r 45 a== 2 ifl a= 48 b=r 33 a<<=b a+= 16 b=r 34 a+=b r=a 12"); HSET('DTI', 44, 14); e("      endif")
e("      a=r 14 r=a 13 a+= 16 b=r 12 a+=b r=a 14 a=r 44 a++ r=a 44")
CALLRC(0, S_TREES)
e("    endif")
e("  endif")
# ---- los comandos del meta-bloque
STATE(S_CMDS)
e("    a=r 8 b=r 7 a<b ifl")
e("      a=r 25 a== 0 ifl"); SWITCH(28, 31, 16, 19, 22, 25); e("      endif")
e("      a=r 25 a-- r=a 25")
HGET('ITI', 19); e("      r=a 58"); DECSYM(58, 46)
e("      a=r 46 a>>= 6 r=a 59"); HGET('CELI', 59); e("      r=a 56 a=r 46 a>>= 3 a&= 7 b=r 56 a+=b r=a 56")
HGET('CELC', 59); e("      r=a 57 a=r 46 a&= 7 b=r 57 a+=b r=a 57")
HGET('INSX', 56); e("      r=a 59"); BITS('r59', 47); HGET('INSB', 56); e("      b=r 47 a+=b r=a 47")
HGET('CPYX', 57); e("      r=a 59"); BITS('r59', 48); HGET('CPYB', 57); e("      b=r 48 a+=b r=a 48")
e("      a=r 47 a> 0 ifl")
e("        do")
e("          a=r 24 a== 0 ifl"); SWITCH(27, 30, 15, 18, 21, 24); e("          endif")
e("          a=r 24 a-- r=a 24")
e("          a=r 4 a-- c=a a=*c r=a 56 c-- a=*c r=a 57")         # p1, p2
HGET('MOD', 18); e("          a<<= 9 r=a 59 b=r 56 a+=b r=a 56 a=r 59 a+= 255 a++ b=r 57 a+=b r=a 57")
MGET('DLUT', 56); e("          r=a 56"); MGET('DLUT', 57); e("          b=r 56 a|=b r=a 56")
e("          a=r 18 a<<= 6 b=r 56 a+=b r=a 56"); HGET('CMLM', 56); e("          r=a 56"); HGET('LTI', 56); e("          r=a 58")
DECSYM(58, 56); e("          a=r 56"); PUTO()
e("          a=r 8 a++ r=a 8 a=r 47 a-- r=a 47")
e("        a> 0 while")
e("      endif")
e("      a=r 8 b=r 7 a<b ifl")                         # la copia (si queda meta-bloque)
e("        a=0 r=a 49 a=r 46 a> 127 ifl")
e("          a=r 26 a== 0 ifl"); SWITCH(29, 32, 17, 20, 23, 26); e("          endif")
e("          a=r 26 a-- r=a 26")
e("          a=r 48 a> 4 ifl a= 3 elsel a=r 48 a-= 2 endif r=a 56 a=r 20 a<<= 2 b=r 56 a+=b r=a 56")
HGET('CMDM', 56); e("          r=a 56"); HGET('DTI', 56); e("          r=a 58"); DECSYM(58, 49)
e("        endif")
# distancia
e("        a=r 49 a< 16 ifl")
e("          a< 4 ifl")
e("            a== 0 ifl a=r 43 elsel a== 1 ifl a=r 42 elsel a== 2 ifl a=r 41 elsel a=r 40 endif endif endif r=a 50")
e("          elsel")
e("            a< 10 ifl a-= 4 r=a 56 a=r 43 elsel a-= 10 r=a 56 a=r 42 endif r=a 50")
e("            a=r 56 a>>= 1 a++ r=a 57 a=r 56 a&= 1 a== 0 ifl a=r 50 b=r 57 a-=b elsel a=r 50 b=r 57 a+=b endif r=a 50")
e("          endif")
e("        elsel")
e("          b=r 34 a-= 16 a<b ifl")
e("            a=r 49 a-= 15 r=a 50")
e("          elsel")
e("            a=r 49 a-= 16 b=r 34 a-=b r=a 56 a=r 33 a++ b=a a=r 56 a>>=b a++ r=a 57")   # ndistbits
e("            a=r 33 b=a a=r 56 a>>=b a&= 1 a+= 2 b=r 57 a<<=b a-= 4 r=a 59")            # offset
BITS('r57', 55); e("            a=r 59 b=r 55 a+=b b=r 33 a<<=b r=a 50")
e("            a= 1 b=r 33 a<<=b a-- b=r 56 a&=b b=r 50 a+=b b=r 34 a+=b a++ r=a 50")
e("          endif")
e("        endif")
e("        a=r 4 b=r 3 a-=b r=a 51 b=r 5 a>b ifl a=r 5 r=a 51 endif")   # maxd = min(maxback, pos)
e("        a=r 50 b=r 51 a>b ifl")                     # palabra del diccionario
e("          a-=b a-- r=a 56 a=r 48 r=a 57")             # r56 word_id, r57 largo
MGET('DSB', 57); e("          r=a 58 a= 1 b=r 58 a<<=b a-- b=r 56 a&=b r=a 59 a=r 58 b=a a=r 56 a>>=b r=a 60")   # r59 indice, r60 transformacion
e("          a=r 57 a<<= 2 a+= 3 b=r "+str(R('DOF'))+" a+=b c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a 58")
e("          a=r 59 b=r 57 a*=b b=r 58 a+=b r=a 58")      # r58 inicio de la palabra
e("          a=r 60 a+=a b=r 60 a+=b r=a 59")             # 3 * transformacion
MGET('DTR', 59); e("          r=a 61"); e("          a=r 59 a++ r=a 59"); MGET('DTR', 59); e("          r=a 62"); e("          a=r 59 a++ r=a 59"); MGET('DTR', 59); e("          r=a 63")
e("          a=r 4 r=a 64")                               # comienzo de la salida de la palabra
def PSTR(idreg):              # copia la cadena de prefijo/sufijo r idreg a la salida (solo M)
    e(f"a=r {idreg} a+=a b=r {R('DPSM')} a+=b c=a a=*c r=a 65 c++ a=*c a<<= 8 b=r 65 a+=b b=r {R('DPS')} a+=b r=a 65")
    e("c=a a=*c r=a 66 a=r 65 a++ r=a 65 a=r 66")
    e("a> 0 ifl")
    e("  do")
    e("    a=r 65 c=a a=*c c=r 4 *c=a a=c a++ r=a 4 a=r 65 a++ r=a 65 a=r 66 a-- r=a 66")
    e("  a> 0 while")
    e("endif")
PSTR(61)
e("          a=r 62 a> 0 ifl a< 10 ifl")              # omitir los ultimos
e("            b=a a=r 57 a>b ifl a-=b elsel a=0 endif r=a 57")
e("          endif endif")
e("          a=r 62 a> 11 ifl")                         # omitir los primeros
e("            a-= 11 b=a a=r 57 a>b ifl a-=b r=a 57 a=r 58 a+=b r=a 58 elsel a=0 r=a 57 endif")
e("          endif")
e("          a=r 4 r=a 67 a=r 57 r=a 66")                 # r67 inicio de la palabra en la salida
e("          a> 0 ifl")
e("            do")
e("              a=r 58 c=a a=*c c=r 4 *c=a a=c a++ r=a 4 a=r 58 a++ r=a 58 a=r 66 a-- r=a 66")
e("            a> 0 while")
e("          endif")
def TOUPPER():                # en M[r67], quedan r66 bytes; deja el paso en r68
    e("a=r 67 c=a a=*c a< 192 ifl")
    e("  a> 96 ifl a< 123 ifl a^= 32 *c=a endif endif a= 1 r=a 68")
    e("elsel a< 224 ifl")
    e("  a=r 66 a> 1 ifl c++ a=*c a^= 32 *c=a endif a= 2 r=a 68")
    e("elsel")
    e("  a=r 66 a> 2 ifl c++ c++ a=*c a^= 5 *c=a endif a= 3 r=a 68")
    e("endif endif")
e("          a=r 57 r=a 66")
e("          a=r 62 a== 10 ifl a=r 66 a> 0 ifl"); TOUPPER(); e("          endif endif")
e("          a=r 62 a== 11 ifl")
e("            a=r 66 a> 0 ifl")
e("              do")
TOUPPER(); e("                a=r 67 b=r 68 a+=b r=a 67 a=r 66 b=r 68 a>b ifl a-=b elsel a=0 endif r=a 66")
e("              a> 0 while")
e("            endif")
e("          endif")
PSTR(63)
e("          a=r 64 r=a 66")                             # OUT de todo lo escrito
e("          a=r 4 b=r 66 a>b ifl")
e("            do")
e("              a=r 66 c=a a=*c out a=r 66 a++ r=a 66 b=r 4")
e("            a<b while")
e("          endif")
e("          a=r 4 b=r 64 a-=b b=r 8 a+=b r=a 8")
e("        elsel")                                     # copia normal
e("          a=r 4 b=r 50 a-=b r=a 56 a=r 48 r=a 57")
e("          a> 0 ifl")
e("            do")
e("              a=r 56 c=a a=*c"); PUTO(); e("              a=r 56 a++ r=a 56 a=r 57 a-- r=a 57")
e("            a> 0 while")
e("          endif")
e("          a=r 8 b=r 48 a+=b r=a 8")
e("          a=r 49 a> 0 ifl a=r 41 r=a 40 a=r 42 r=a 41 a=r 43 r=a 42 a=r 50 r=a 43 endif")
e("        endif")
e("      endif")
e("    elsel")                                       # fin del meta-bloque
e(f"      a=r 6 a> 0 ifl a= {S_END} elsel a= {S_MBH} endif r=a 10")
e("    endif")
e("  endif")
# ---- leer un codigo prefijo: r12 simbolos, arbol en r13; vuelve a r11
STATE(S_RC)
e("    a=r 12 a-- r=a 100"); e("    a=0 r=a 101 a=r 100 a>>= 1")      # abits = bit_length(asize-1)
e("    a> 0 ifl do r=a 102 a=r 101 a++ r=a 101 a=r 102 a>>= 1 a> 0 while endif")
e("    a=r 101 a++ r=a 101")
BITS(2, 103)
e("    a=r 103 a== 1 ifl")                            # simple
BITS(2, 104); e("      a=r 104 a++ r=a 104")
for k in range(4):
    e(f"      a=r 104 a> {k} ifl"); BITS('r101', 110 + k); e("      endif")
ZERO('LENS', 12)
e("      a= 1 r=a 105 a=r 104 a== 1 ifl")
e("        a=r 13 d=a a= 1 *d=a a=r 13 a+= 16 d=a a=r 110 *d=a a=0 r=a 105")
e("      elsel a== 2 ifl")
e("        a= 1 r=a 106"); HSET('LENS', 110, 106); HSET('LENS', 111, 106)
e("      elsel a== 3 ifl")
e("        a= 1 r=a 106"); HSET('LENS', 110, 106); e("        a= 2 r=a 106"); HSET('LENS', 111, 106); HSET('LENS', 112, 106)
e("      elsel")
BIT(); e("        a> 0 ifl")
e("          a= 1 r=a 106"); HSET('LENS', 110, 106); e("          a= 2 r=a 106"); HSET('LENS', 111, 106)
e("          a= 3 r=a 106"); HSET('LENS', 112, 106); HSET('LENS', 113, 106)
e("        elsel")
e("          a= 2 r=a 106"); HSET('LENS', 110, 106); HSET('LENS', 111, 106); HSET('LENS', 112, 106); HSET('LENS', 113, 106)
e("        endif")
e("      endif endif endif")
e("      a=r 105 a> 0 ifl")
e(f"        a=r {R('LENS')} r=a 107")
BUILD(12, 107, 13)
e("      endif")
e("    elsel")                                        # complejo
e("      a= 18 r=a 106"); ZERO('CLL', 106)
e("      a= 32 r=a 104 a=r 103 r=a 105")                # r104 space, r105 i
e("      do")
e("        a=r 2 r=a 108"); BITS(4, 109); e("        a=r 108 r=a 2")      # peek de 4 bits
HGET('CLPL', 109); e("        b=r 2 a+=b r=a 2"); HGET('CLPV', 109); e("        r=a 106")
HGET('CLO', 105); e("        r=a 107"); HSET('CLL', 107, 106)
e("        a=r 105 a++ r=a 105")
e("        a=r 106 a> 0 ifl")
e("          b=a a= 32 a>>=b b=a a=r 104 a-=b r=a 104")
e("          a> 0 ifl a> 32 ifl a= 18 r=a 105 endif elsel a= 18 r=a 105 endif")   # space <= 0: fin
e("        endif")
e("        a=r 105")
e("      a< 18 while")
e(f"      a= 18 r=a 106 a=r {R('CLL')} r=a 107 a=r {R('CLT')} r=a 108")
BUILD(106, 107, 108)
ZERO('LENS', 12)
e("      a= 128 a<<= 8 r=a 104 a=0 r=a 105 r=a 106 r=a 109 a= 8 r=a 107")   # space, i, rep, replen, prev
e("      do")
e("        a=r 105 b=r 12 a<b ifl a=r 104 a> 0 ifl a> 32768 ifl a=0 elsel a= 1 endif elsel a=0 endif elsel a=0 endif".replace("a> 32768", "a=r 104 a>>= 16 a> 0"))
e("        a> 0 ifl")
e(f"          a=r {R('CLT')} r=a 114"); DECSYM(114, 115)
e("          a=r 115 a< 16 ifl")
e("            a=0 r=a 106"); HSET('LENS', 105, 115); e("            a=r 105 a++ r=a 105")
e("            a=r 115 a> 0 ifl r=a 107 b=a a= 128 a<<= 8 a>>=b b=a a=r 104 a-=b r=a 104 endif")
e("          elsel")
e("            a== 16 ifl a= 2 r=a 116 a=r 107 elsel a= 3 r=a 116 a=0 endif r=a 117")   # eb, nl
e("            a=r 109 b=r 117 a==b ifnot a=0 r=a 106 a=r 117 r=a 109 endif")
e("            a=r 106 r=a 118 a> 0 ifl a-= 2 b=r 116 a<<=b r=a 106 endif")
BITS('r116', 119); e("            a=r 119 a+= 3 b=r 106 a+=b r=a 106 b=r 118 a-=b r=a 119")   # r119 delta
e("            a=r 119 r=a 120")
e("            a> 0 ifl")
e("              do")
e("                a=r 105 b=r 12 a<b ifl"); HSET('LENS', 105, 117); e("                endif")
e("                a=r 105 a++ r=a 105 a=r 120 a-- r=a 120")
e("              a> 0 while")
e("            endif")
e("            a=r 117 a> 0 ifl a= 15 b=r 117 a-=b b=a a=r 119 a<<=b b=a a=r 104 a-=b r=a 104 endif")
e("          endif")
e("          a= 1")
e("        endif")
e("      a> 0 while")
e(f"      a=r {R('LENS')} r=a 107")
BUILD(12, 107, 13)
e("    endif")
e("    a=r 11 r=a 10")
e("  endif")
e("  a=r 10")
e("  a> 0 while")
e("  a=0 c=a")
e("elsel")
e("  *c=a c++")
e("endif")
e("halt")
e("end")
open(sys.argv[1], 'w').write('\n'.join(out) + '\n')
