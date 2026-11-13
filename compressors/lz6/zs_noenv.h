/* zpaq-std: force-included (-include) when compiling lz6's seq engine (entropy/lz6seq.c).
   lz6seq.c reads experiment switches from the environment (LZ6_NO_EPOCHS, LZ6_SEQ_DUMP...),
   which lz6 documents as experiments only. An archiver must write the same bytes whatever
   the environment holds, so getenv always answers "not set" in that file. The sources
   are not patched. */
#ifndef ZS_NOENV_H
#define ZS_NOENV_H
#include <stdlib.h>
#define getenv(name) ((char*)0)
#endif
