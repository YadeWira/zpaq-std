# Huff0 (el de zstd 1.4, que Lizard 2.1 usa en los niveles 30-49) en ZPAQL, para
# gen.py --huff. Mismo algoritmo que la referencia en Python con la que se probo:
# pesos con FSE (o crudos de 4 bits), Huffman canonico decodificado bit a bit
# (como ZPAQDEFLATE), cuatro flujos leidos hacia atras. Todo son macros: ZPAQL no
# tiene subrutinas, asi que cada una se expande una sola vez en el programa.
#
# Registros (los de gen.py llegan hasta r31):
#   r34 puntero de reserva en M (buffers de los flujos Huffman, detras de la entrada)
#   r35 s (inicio del flujo Huff0), r36 cl (su largo), r37 sl (largo decodificado),
#   r38 destino
#   r40 POS (bits que quedan, lector hacia atras), r41 BASE, r42 OVF (se leyo de mas)
#   r43 codigo, r44 largo del codigo, r45 simbolos que faltan, r46 temporal
#   r47/r48 puntero/fin del flujo actual (los guarda gen.py)
#   r50 i (lector hacia adelante), r51 hs, r52 inicio, r53 tableLog de FSE
#   r54 remaining, r55 threshold, r56 nbBits, r57 charnum, r58 previous0, r59 max
#   r60 valor leido, r61 cuenta, r62 n0, r63 T (tableLog de Huffman), r64 n pesos
#   r65 total / start, r66 k, r67 temporal, r68 j, r69 temporal
#   r91 temporal de HIGHBIT, r92..r94 de INITB, r95 = 0 (base de los pesos)
#   r70..r80 constantes > 255 (bases de las tablas en H)
#   r81 tamano de la tabla FSE, r82 highThreshold, r83 paso, r84 posicion
#   r85 estado 1, r86 estado 2, r87 ip, r88 segmento, r89 flujo (0..3)
# H (ph = 11):
#   0..255 pesos    256..511 simbolos ordenados   512 first[L]   528 base[L]
#   544 cnt[L]      560 desplazamientos de los flags (2 3 1 0)   576 punteros de flujo
#   592 inicios de los 4 subflujos + fin    600 cuentas de NCount (sin restar 1)
#   856 symbolNext  1112 simbolo FSE  1176 nbBits FSE  1240 newState FSE
W, SY, FI, BA, CN, SH, SP, SS, NC, NX, FS, FB, FN = 95, 70, 71, 72, 73, 80, 79, 90, 74, 75, 76, 77, 78

def consts(e):
    """Constantes: en ZPAQL los inmediatos van de 0 a 255. r95 = 0 es la base de los pesos."""
    e("a=0 r=a 95")
    for reg, v, sh in [(70, 1, 8), (71, 2, 8), (72, 33, 4), (73, 34, 4), (80, 35, 4),
                       (79, 36, 4), (90, 37, 4), (74, 75, 3), (75, 107, 3), (76, 139, 3),
                       (77, 147, 3), (78, 155, 3)]:
        e(f"a= {v} a<<= {sh} r=a {reg}")
    # desplazamientos de los flags por flujo: offset16 bit 2, offset24 bit 3, flags 1, literales 0
    e("a=r 80 d=a a= 2 *d=a d++ a= 3 *d=a d++ a= 1 *d=a d++ a=0 *d=a")

def HGET(e, base, idx):      # a = H[r base + r idx]
    e(f"a=r {idx} b=r {base} a+=b d=a a=*d")
def HSET(e, base, idx, val): # H[r base + r idx] = r val
    e(f"a=r {idx} b=r {base} a+=b d=a a=r {val} *d=a")
def HIGHBIT(e, src, dst):    # r dst = posicion del bit alto de r src (src >= 1)
    e(f"a=0 r=a {dst} a=r {src} a>>= 1")
    e("a> 0 ifl")
    e("  do")
    e(f"    r=a 91 a=r {dst} a++ r=a {dst} a=r 91 a>>= 1")
    e("  a> 0 while")
    e("endif")

def BITB(e):
    """a = siguiente bit del lector hacia atras (r40 POS bits por debajo, en M[r41..]).
    Pasado el principio da 0 y marca r42: es el 'overflow' de BIT_reloadDStream."""
    e("a=r 40 a== 0 ifl")
    e("  a= 1 r=a 42 a=0")
    e("elsel")
    e("  a-- r=a 40 a>>= 3 b=r 41 a+=b c=a")
    e("  a=r 40 a&= 7 b=a a=*c a>>=b a&= 1")
    e("endif")
def READB(e, nreg, dst):     # r dst = r nreg bits hacia atras, el primero es el mas alto
    e(f"a=0 r=a {dst} a=r {nreg} r=a 67")
    e("a> 0 ifl")
    e("  do")
    BITB(e)
    e(f"    r=a 69 a=r {dst} a<<= 1 b=r 69 a+=b r=a {dst}")
    e("    a=r 67 a-- r=a 67")
    e("  a> 0 while")
    e("endif")
def INITB(e, start, length):  # lector hacia atras sobre r start, r length bytes: salta el centinela
    e(f"a=r {length} r=a 92 a=r {start} r=a 41 b=r 92 a+=b a-- c=a a=*c r=a 93")
    HIGHBIT(e, 93, 94)
    e("a=r 92 a-- a<<= 3 b=r 94 a+=b r=a 40 a=0 r=a 42")

def FPEEK(e, n):
    """r60 = los n bits siguientes (n inmediato, o 'rN' = los que diga el registro N)
    del lector hacia adelante (LSB primero), sin avanzar.
    Pasado el final del encabezado (r51 bytes desde r52) da ceros, como FSE_readNCount."""
    e(f"a=0 r=a 60 r=a 66")
    e("do")
    e("  a=r 50 b=r 66 a+=b r=a 67 a>>= 3 b=r 51")
    e("  a<b ifl")
    e("    b=r 52 a+=b c=a a=r 67 a&= 7 b=a a=*c a>>=b a&= 1")
    e("    b=r 66 a<<=b b=r 60 a|=b r=a 60")
    e("  endif")
    e("  a=r 66 a++ r=a 66")
    e(f"a< {n} while" if isinstance(n, int) else f"b=r {n[1:]} a<b while")   # 'r56': registro
def FSKIP(e, n):
    e(f"a=r 50 a+= {n} r=a 50")

def FSE_WEIGHTS(e):
    """FSE_decompress de los pesos: r51 bytes desde r52. Deja n en r64."""
    e("a=0 r=a 50")
    FPEEK(e, 4); e("a=r 60 a+= 5 r=a 53"); FSKIP(e, 4)
    e("a= 1 b=r 53 a<<=b r=a 55 a++ r=a 54 a=r 53 a++ r=a 56")
    e("a=0 r=a 57 r=a 58")
    e("a=r 54 a> 1 ifl")
    e("do")
    e("  a=r 58 a> 0 ifl")                          # previous0: corridas de ceros
    e("    a=r 57 r=a 62")
    e("    do")
    FPEEK(e, 16)
    e("      a=r 60 b=a a= 255 a<<= 8 a+= 255 a==b ifl")
    e("        a=r 62 a+= 24 r=a 62"); FSKIP(e, 16)
    e("        a= 1")
    e("      elsel")
    e("        a=0")
    e("      endif")
    e("    a> 0 while")
    e("    do")
    FPEEK(e, 2)
    e("      a=r 60 a== 3 ifl")
    e("        a=r 62 a+= 3 r=a 62"); FSKIP(e, 2)
    e("        a= 1")
    e("      elsel")
    e("        a=0")
    e("      endif")
    e("    a> 0 while")
    FPEEK(e, 2); e("    a=r 60 b=r 62 a+=b r=a 62"); FSKIP(e, 2)
    e("    a=r 57 b=r 62 a<b ifl")
    e("      do")
    e("        a= 1 r=a 61"); HSET(e, NC, 57, 61)
    e("        a=r 57 a++ r=a 57 b=r 62")
    e("      a<b while")
    e("    endif")
    e("  endif")
    e("  a=r 55 a<<= 1 a-- b=r 54 a-=b r=a 59")       # max = 2*threshold-1-remaining
    FPEEK(e, 'r56')
    e("  a=r 55 a-- b=a a=r 60 a&=b r=a 61 b=r 59")
    e("  a<b ifl")
    e("    a=r 56 a-- b=a a=r 50 a+=b r=a 50")
    e("  elsel")
    e("    a=r 55 a<<= 1 a-- b=a a=r 60 a&=b r=a 61 b=r 55")
    e("    a<b ifnot")
    e("      a=r 61 b=r 59 a-=b r=a 61")
    e("    endif")
    e("    a=r 56 b=a a=r 50 a+=b r=a 50")
    e("  endif")
    HSET(e, NC, 57, 61)                             # la cuenta SIN restar 1: 0 es -1
    e("  a=r 57 a++ r=a 57")
    e("  a=r 61 a== 0 ifl")
    e("    a=r 54 a-- r=a 54")
    e("  elsel")
    e("    a-- b=a a=r 54 a-=b r=a 54")
    e("  endif")
    e("  a=r 61 a== 1 ifl a= 1 elsel a=0 endif r=a 58")
    e("  a=r 54 b=r 55 a<b ifl")
    e("    do")
    e("      a=r 56 a-- r=a 56 a=r 55 a>>= 1 r=a 55 b=a a=r 54")
    e("    a<b while")
    e("  endif")
    e("  a=r 54")
    e("a> 1 while")
    e("endif")
    # tabla de decodificacion (FSE_buildDTable)
    e("a= 1 b=r 53 a<<=b r=a 81 a-- r=a 82")
    e("a=0 r=a 66")
    e("do")
    HGET(e, NC, 66)
    e("  a== 0 ifl")
    e("    a=r 66 r=a 69"); HSET(e, FS, 82, 69)
    e("    a=r 82 a-- r=a 82 a= 1 r=a 69"); HSET(e, NX, 66, 69)
    e("  elsel")
    e("    a-- r=a 69"); HSET(e, NX, 66, 69)
    e("  endif")
    e("  a=r 66 a++ r=a 66 b=r 57")
    e("a<b while")
    e("a=r 81 a>>= 1 r=a 83 a=r 81 a>>= 3 b=r 83 a+=b a+= 3 r=a 83")
    e("a=0 r=a 84 r=a 66")
    e("do")
    HGET(e, NC, 66)
    e("  a> 1 ifl")
    e("    a-- r=a 68")
    e("    do")
    e("      a=r 66 r=a 69"); HSET(e, FS, 84, 69)
    e("      do")
    e("        a=r 81 a-- r=a 69 a=r 84 b=r 83 a+=b b=r 69 a&=b r=a 84 b=r 82")
    e("      a>b while")
    e("      a=r 68 a-- r=a 68")
    e("    a> 0 while")
    e("  endif")
    e("  a=r 66 a++ r=a 66 b=r 57")
    e("a<b while")
    e("a=0 r=a 66")
    e("do")
    HGET(e, FS, 66); e("  r=a 68")                  # simbolo
    HGET(e, NX, 68); e("  r=a 67 a++ r=a 69"); HSET(e, NX, 68, 69)
    HIGHBIT(e, 67, 69)
    e("  a=r 53 b=r 69 a-=b r=a 69"); HSET(e, FB, 66, 69)
    e("  b=a a=r 67 a<<=b b=r 81 a-=b r=a 69"); HSET(e, FN, 66, 69)
    e("  a=r 66 a++ r=a 66 b=r 81")
    e("a<b while")
    # el flujo, hacia atras, con dos estados
    e("a=r 50 a+= 7 a>>= 3 r=a 69 b=r 52 a+=b r=a 46")   # inicio = s + encabezado
    e("a=r 51 b=r 69 a-=b r=a 69")                       # largo = hs - encabezado
    INITB(e, 46, 69)
    READB(e, 53, 85); READB(e, 53, 86)
    e("a=0 r=a 64")
    e("do")
    for (me, otro) in [(85, 86), (86, 85)]:
        HGET(e, FS, me); e("  r=a 69"); HSET(e, W, 64, 69); e("  a=r 64 a++ r=a 64")
        HGET(e, FB, me); e("  r=a 68"); READB(e, 68, 61)
        HGET(e, FN, me); e(f"  b=r 61 a+=b r=a {me}")
        e("  a=r 42 a> 0 ifl")
        HGET(e, FS, otro); e("    r=a 69"); HSET(e, W, 64, 69); e("    a=r 64 a++ r=a 64")
        e("  endif")
        if me == 85:
            e("  a=r 42 a== 0 ifl")
    e("  endif")
    e("a=r 42 a== 0 while")

def HUFF(e):
    """Decodifica el flujo Huff0 de r36 bytes en M[r35] a M[r38], r37 bytes."""
    e("a=r 36 a== 1 ifl")                            # RLE: HUF_compress devolvio 1
    e("  a=r 35 c=a a=*c r=a 46 a=r 37 r=a 45")
    e("  do")
    e("    a=r 46 c=r 38 *c=a a=c a++ r=a 38 a=r 45 a-- r=a 45")
    e("  a> 0 while")
    e("elsel")
    e("a=r 36 b=r 37 a==b ifl")                       # sin comprimir
    e("  a=r 35 r=a 87 a=r 37 r=a 45")
    e("  do")
    e("    a=r 87 c=a a=*c c=r 38 *c=a a=c a++ r=a 38 a=r 87 a++ r=a 87 a=r 45 a-- r=a 45")
    e("  a> 0 while")
    e("elsel")
    e("  a=r 35 c=a a=*c r=a 46 a=r 35 a++ r=a 87")        # r87 = ip despues del byte de encabezado
    e("  a=r 46 a> 127 ifl")                          # pesos crudos de 4 bits
    e("    a-= 127 r=a 64 a=0 r=a 66")
    e("    do")
    e("      a=r 66 a>>= 1 b=r 87 a+=b c=a a=*c r=a 69 a=r 66 a&= 1 a== 0 ifl")
    e("        a=r 69 a>>= 4")
    e("      elsel")
    e("        a=r 69 a&= 15")
    e("      endif")
    e("      r=a 69"); HSET(e, W, 66, 69)
    e("      a=r 66 a++ r=a 66 b=r 64")
    e("    a<b while")
    e("    a=r 64 a++ a>>= 1 b=r 87 a+=b r=a 87")
    e("  elsel")
    e("    a=r 46 r=a 51 a=r 87 r=a 52")
    FSE_WEIGHTS(e)
    e("    a=r 87 b=r 51 a+=b r=a 87")
    e("  endif")
    # total, tableLog y el ultimo peso implicito
    e("  a=0 r=a 65 r=a 66")
    e("  do")
    HGET(e, W, 66); e("    b=a a= 1 a<<=b a>>= 1 b=r 65 a+=b r=a 65")
    e("    a=r 66 a++ r=a 66 b=r 64")
    e("  a<b while")
    HIGHBIT(e, 65, 63); e("  a=r 63 a++ r=a 63")
    e("  a= 1 b=r 63 a<<=b b=r 65 a-=b r=a 46")
    HIGHBIT(e, 46, 69); e("  a=r 69 a++ r=a 69"); HSET(e, W, 64, 69)
    e("  a=r 64 a++ r=a 64")
    # cnt[L], con L = T+1-w; first[L] y base[L] en 0 para L de 0 a 15 (un flujo roto no cuelga)
    e("  a=0 r=a 66 r=a 69")
    e("  do")
    HSET(e, CN, 66, 69); HSET(e, FI, 66, 69); HSET(e, BA, 66, 69)
    e("    a=r 66 a++ r=a 66")
    e("  a< 16 while")
    e("  a=0 r=a 66")
    e("  do")
    HGET(e, W, 66)
    e("    a> 0 ifl")
    e("      b=a a=r 63 a++ a-=b r=a 68"); HGET(e, CN, 68); e("      a++ r=a 69"); HSET(e, CN, 68, 69)
    e("    endif")
    e("    a=r 66 a++ r=a 66 b=r 64")
    e("  a<b while")
    e("  a=r 63 r=a 68 a=0 r=a 65 r=a 62")            # L = T; start = 0; ns = 0
    e("  do")
    e("    a=r 63 b=r 68 a-=b b=a a=r 65 a>>=b r=a 69"); HSET(e, FI, 68, 69)
    HSET(e, BA, 68, 62)
    e("    a=0 r=a 66")
    e("    do")
    HGET(e, W, 66)
    e("      a> 0 ifl")
    e("        b=a a=r 63 a++ a-=b b=r 68 a==b ifl")
    HSET(e, SY, 62, 66); e("          a=r 62 a++ r=a 62")
    e("        endif")
    e("      endif")
    e("      a=r 66 a++ r=a 66 b=r 64")
    e("    a<b while")
    HGET(e, CN, 68); e("    r=a 69 a=r 63 b=r 68 a-=b b=a a=r 69 a<<=b b=r 65 a+=b r=a 65")
    e("    a=r 68 a-- r=a 68")
    e("  a> 0 while")
    # los cuatro subflujos: tabla de saltos de 6 bytes
    e("  a=r 87 a+= 6 r=a 69 a=0 r=a 66"); HSET(e, SS, 66, 69)
    for k in range(3):
        e(f"  a=r 87 a+= {2*k+1} c=a a=*c a<<= 8 c-- a+=*c b=r 69 a+=b r=a 69 a= {k+1} r=a 66"); HSET(e, SS, 66, 69)
    e("  a=r 35 b=r 36 a+=b r=a 69 a= 4 r=a 66"); HSET(e, SS, 66, 69)
    e("  a=r 37 a+= 3 a>>= 2 r=a 88")
    e("  a=0 r=a 89")
    e("  do")
    HGET(e, SS, 89); e("    r=a 46 a=r 89 a++ r=a 66"); HGET(e, SS, 66); e("    b=r 46 a-=b r=a 67")
    INITB(e, 46, 67)
    e("    a=r 88 r=a 45 a=r 89 a== 3 ifl")
    e("      a=r 88 a<<= 1 b=r 88 a+=b b=a a=r 37 a-=b r=a 45")
    e("    endif")
    e("    a=r 45 a> 0 ifl")
    e("    do")
    e("      a=0 r=a 43 r=a 44")
    e("      do")
    BITB(e)
    e("        r=a 46 a=r 43 a<<= 1 b=r 46 a+=b r=a 43 a=r 44 a++ r=a 44")
    e("        b=r 71 a+=b d=a a=*d b=a a=r 43")
    e("      a<b while")
    e("      a-=b r=a 46 a=r 44 b=r 72 a+=b d=a a=*d b=r 46 a+=b b=r 70 a+=b d=a a=*d")
    e("      c=r 38 *c=a a=c a++ r=a 38")
    e("      a=r 45 a-- r=a 45")
    e("    a> 0 while")
    e("    endif")
    e("    a=r 89 a++ r=a 89")
    e("  a< 4 while")
    e("endif")
    e("endif")
