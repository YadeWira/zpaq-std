#!/usr/bin/env python3
# Generador de ZPAQKANZI5B: ZPAQKANZI5 (kanzi 2.6.0 niveles 5 y 6) con la BWT inversa
# de ZPAQKANZI7, sin el limite de 16 MB. zpaq-std, 2026.
#
# La BWT de ZPAQKANZI5 guarda (indice << 8 | byte) en una palabra de H, asi que con mas
# de 2^24 posiciones el indice desborda: un bloque de mas de 16 MB (por ejemplo con
# -m5, que arma bloques de 64 MB) no se podia extraer en otro zpaq. ZPAQKANZI5 queda
# congelado (los archivos ya escritos llevan su copia y zpaq-std los sigue leyendo); los
# bloques nuevos llevan este.
#
# No se escribe de nuevo nada: se toma gen5.py tal cual y se reemplaza su funcion BWT
# por la de gen7.py (mismos nombres de registros y de tablas), el nombre del programa
# y su comentario. Lo demas (ANS0, FPAQ, ZRLT, RANK, SRT, UTF, TEXT) es el mismo codigo.
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src5 = open(os.path.join(HERE, 'gen5.py')).read()
src7 = open(os.path.join(HERE, 'gen7.py')).read()
pat = r'^def BWT\(\):.*?(?=^def |^# )'
bwt7 = re.search(pat, src7, re.S | re.M).group(0)
assert re.search(pat, src5, re.S | re.M)
src = re.sub(pat, lambda m: bwt7, src5, count=1, flags=re.S | re.M)
a = 'e("pcomp zpaqkanzi5 ;")'
assert src.count(a) == 1
src = src.replace(a, 'e("pcomp zpaqkanzi5b ;")')
a = '(ZPAQKANZI5: decodificador de kanzi 2.6.0'
assert src.count(a) == 1
src = src.replace(a, '(ZPAQKANZI5B: ZPAQKANZI5 con la BWT sin limite de 16 MB. Decodificador de kanzi 2.6.0')
exec(compile(src, 'gen5b(gen5.py)', 'exec'), {'__name__': '__main__'})
