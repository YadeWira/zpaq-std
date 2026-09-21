# Rama `upstream` — snapshots de zpaqfranz, sin modificar

Esta rama **no se compila y no se toca a mano**. Es un único archivo: el fuente
de [zpaqfranz](https://github.com/fcorbelli/zpaqfranz) tal como lo publica
fcorbelli, un commit por release.

## Para qué

zpaq-std es un fork vendorizado de zpaqfranz. Sin esta rama, cada actualización
de upstream era arqueología: había que adivinar de qué versión partía el fork,
bajar dos tarballs y hacer un `git merge-file` a mano. Con ella, `main` y
`upstream` comparten historia y traer una versión nueva es:

    git checkout upstream
    curl -L -o zpaq-std.cpp https://github.com/fcorbelli/zpaqfranz/releases/download/<TAG>/zpaqfranz.cpp
    git commit -am "upstream: zpaqfranz <TAG>"
    git checkout main && git merge upstream

y git calcula la base común solo.

## Por qué el archivo se llama `zpaq-std.cpp` y no `zpaqfranz.cpp`

Porque git empareja por RUTA. Si acá se llamara `zpaqfranz.cpp`, el merge vería
un archivo borrado y otro creado en vez de una modificación, y no habría fusión a
tres bandas. El contenido es el de upstream, byte a byte y sin editar.

## De dónde se baja: de las RELEASES, nunca de master

El `zpaqfranz.cpp` que está en la raíz de master **no es confiable**. Comprobado
el 2026-09-21: a las 14:50 fcorbelli subió el 65.2 a master, y a las 19:08 lo
pisó con un `zpaqfranz.cpp` de **63.5d (2025-10-13)** — dos versiones mayores
hacia atrás, 4,69 MB → 3,85 MB. El commit dice "Add files via upload", o sea
subida manual por la web, que es donde ese error es facilísimo.

O sea que master puede estar MÁS VIEJO que la última release. La fuente de verdad
es el **asset de la release**:

    https://github.com/fcorbelli/zpaqfranz/releases/download/<TAG>/zpaqfranz.cpp

Cada commit de esta rama anota el sha256 de lo que se bajó, justamente para poder
detectar una sorpresa así.

## Regla

Nada de cambios propios acá. Esta rama existe para responder "¿qué decía upstream
exactamente?" — si se la edita, deja de poder responderlo.
