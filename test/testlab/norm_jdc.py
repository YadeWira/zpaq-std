#!/usr/bin/env python3
"""Pone en ceros la fecha de las cabeceras jDC de un .zpaq, para comparar dos
archivos bit a bit sin que el sello de reloj (segundos, en 4 lugares) mienta.

Cada bloque journaling arranca con "jDC" + 14 digitos ASCII (YYYYMMDDHHMMSS).
-timestamp NO fija ese campo, asi que dos corridas que cruzan un segundo dan
4 bytes distintos en archivos por lo demas identicos."""
import sys, re
d = open(sys.argv[1], 'rb').read()
d, n = re.subn(rb'jDC\d{14}', lambda m: b'jDC' + b'0' * 14, d)
open(sys.argv[2], 'wb').write(d)
print(n)
