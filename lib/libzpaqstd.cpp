/// libzpaqstd: zpaq-std's compressor as a library, a stream in, a stream out.
///
///   int zpaqstd_run(int argc, char **argv, intptr_t in, intptr_t out, intptr_t err);
///   const char *zpaqstd_version(void);
///
/// argv (no program name):  c [-m<0..5>[<block>]] [-ma:<codec>:<level>] [-t<threads>]   compress in -> out
///                          d [-t<threads>]                         decompress in -> out
/// d with one thread keeps one block in memory at most; with more, a block and its data for each thread.
/// in, out, err: POSIX file descriptors, Windows HANDLEs. They are closed before
/// the function returns. Nothing is ever read twice and nothing seeks: the input
/// can be a pipe of any length.
/// Returns 0 right, 1 bad arguments, 2 read or write error, 3 out of memory,
/// 4 damaged data. It never ends the process; the text of an error goes to err.
///
/// What is written is a standard ZPAQ stream (level 2, streaming format): any
/// zpaq reads it. Its last block has no data: it says how many blocks and bytes
/// there were (see FINE), and d refuses a stream without it. The bytes depend on the method and the block size only, never
/// on the number of threads.
///
/// The whole program is in this file (zpaq-std.cpp is one translation unit): only
/// libzpaq is used here, none of the commands.

#define ZPAQSTD_LIB /// (see franzVSS: nothing of COM while the library is loaded)
#define main zpaqstd_program_main_not_used
#include "../zpaq-std.cpp"
#undef main

#include <condition_variable>
#include <deque>
#include <future>
#include <memory>

#if defined(_WIN32)
#define ZPAQSTD_API extern "C" __declspec(dllexport)
#else
#define ZPAQSTD_API extern "C" __attribute__((visibility("default")))
#endif

namespace zslib
{
struct errore_io
{
	const char *cosa;
};

#ifdef _WIN32
typedef HANDLE maniglia;
static int leggi(maniglia h, char *buf, int n)
{
	DWORD letti= 0;
	if (!ReadFile(h, buf, (DWORD)n, &letti, NULL))
	{
		const DWORD e= GetLastError();
		if ((e == ERROR_BROKEN_PIPE) || (e == ERROR_HANDLE_EOF))
			return 0;
		return -1;
	}
	return (int)letti;
}
static bool scrivi(maniglia h, const char *buf, size_t n)
{
	while (n > 0)
	{
		DWORD fatti= 0;
		const DWORD ora= (n > (1u << 20)) ? (1u << 20) : (DWORD)n;
		if ((!WriteFile(h, buf, ora, &fatti, NULL)) || (fatti == 0))
			return false;
		buf+= fatti;
		n-= fatti;
	}
	return true;
}
static void chiudi(maniglia h)
{
	if ((h != NULL) && (h != INVALID_HANDLE_VALUE))
		CloseHandle(h);
}
#else
typedef int maniglia;
static int leggi(maniglia h, char *buf, int n)
{
	for (;;)
	{
		const ssize_t r= ::read(h, buf, (size_t)n);
		if ((r < 0) && (errno == EINTR))
			continue;
		return (int)r;
	}
}
static bool scrivi(maniglia h, const char *buf, size_t n)
{
	while (n > 0)
	{
		const ssize_t r= ::write(h, buf, n);
		if (r < 0)
		{
			if (errno == EINTR)
				continue;
			return false;
		}
		if (r == 0)
			return false;
		buf+= r;
		n-= (size_t)r;
	}
	return true;
}
static void chiudi(maniglia h)
{
	if (h >= 0)
		::close(h);
}
#endif

static void dillo(maniglia i_err, const std::string &i_testo)
{
	const std::string t= "zpaqstd: " + i_testo + "\n";
	scrivi(i_err, t.data(), t.size());
}

/// the input, read ahead in pieces
class Lettore : public libzpaq::Reader
{
	maniglia h;
	std::vector<char> buf;
	int pos, len;
	bool fine;
	bool carica()
	{
		if (fine)
			return false;
		const int r= leggi(h, &buf[0], (int)buf.size());
		if (r < 0)
			throw errore_io{"read error"};
		if (r == 0)
		{
			fine= true;
			return false;
		}
		pos= 0;
		len= r;
		return true;
	}

public:
	Lettore(maniglia i_h) : h(i_h), buf(1 << 18), pos(0), len(0), fine(false) {}
	int get()
	{
		if ((pos >= len) && (!carica()))
			return -1;
		return (unsigned char)buf[pos++];
	}
	int read(char *o_buf, int n)
	{
		int fatti= 0;
		while (fatti < n)
		{
			if ((pos >= len) && (!carica()))
				break;
			const int ora= std::min(n - fatti, len - pos);
			memcpy(o_buf + fatti, &buf[pos], (size_t)ora);
			pos+= ora;
			fatti+= ora;
		}
		return fatti;
	}
};

/// the output, with the SHA-1 of what goes through (d: against the one of the segment)
class Scrittore : public libzpaq::Writer
{
	maniglia h;
	std::vector<char> buf;
	size_t n;

public:
	Scrittore(maniglia i_h) : h(i_h), buf(1 << 18), n(0) {}
	void flush()
	{
		if (n > 0)
		{
			if (!scrivi(h, &buf[0], n))
				throw errore_io{"write error"};
			n= 0;
		}
	}
	void put(int c)
	{
		if (n == buf.size())
			flush();
		buf[n++]= (char)c;
	}
	void write(const char *i_buf, int i_n)
	{
		if ((size_t)i_n >= buf.size())
		{
			flush();
			if (!scrivi(h, i_buf, (size_t)i_n))
				throw errore_io{"write error"};
			return;
		}
		if (n + (size_t)i_n > buf.size())
			flush();
		memcpy(&buf[n], i_buf, (size_t)i_n);
		n+= (size_t)i_n;
	}
};

typedef std::unique_ptr<libzpaq::StringBuffer> blocco;

/// The last block of a stream: no data, and in its comment how many blocks there were, how many bytes,
/// and the SHA-1 of the SHA-1 of each block in their order. A zpaq reads it as nothing. d asks for it:
/// a block of ZPAQ says nowhere that it is the last one, and a stream cut between two blocks, or with
/// its first bytes gone, would decode to less data with no error.
static const char FINE[]= "zpaqstd-end:";
struct catena
{
	int64_t blocchi, byte;
	libzpaq::SHA1 sha;
	catena() : blocchi(0), byte(0) {}
	void aggiungi(const char *i_sha20, int64_t i_byte)
	{
		blocchi++;
		byte+= i_byte;
		sha.write(i_sha20, 20);
	}
	std::string testo()
	{
		const char *r= sha.result();
		char hx[41];
		for (int q= 0; q < 20; ++q)
			snprintf(hx + 2 * q, 3, "%02x", (unsigned)(unsigned char)r[q]);
		return std::string(FINE) + itos(blocchi) + ":" + itos(byte) + ":" + hx;
	}
};
struct blocco_fatto
{
	blocco dati;
	std::string sha;
	int64_t byte;
};

/// one block. With a -ma codec: what the program does (ma_comprimir_con): the codec's output and its
/// ZPAQL decoder when the codec makes the block smaller, the block with the -m method when it does not
static blocco_fatto comprimi_blocco(blocco i_dati, std::string i_metodo, std::string i_ma, int i_malivello)
{
	blocco_fatto f;
	f.byte= (int64_t)i_dati->size();
	libzpaq::SHA1 sha;
	sha.write(i_dati->c_str(), f.byte);
	f.sha.assign(sha.result(), 20);
	f.dati.reset(new libzpaq::StringBuffer(i_dati->size() / 2 + 4096));
	std::string etichetta;
	if (!i_ma.empty())
		ma_comprimir_con(*i_dati, i_metodo, etichetta, i_ma, i_malivello);
	libzpaq::compressBlock(i_dati.get(), f.dati.get(), i_metodo.c_str(), "", etichetta.empty() ? NULL : etichetta.c_str(), true);
	return f;
}

static void comprimi(maniglia i_in, maniglia i_out, int i_livello, int i_blocco, int i_thread, const std::string &i_ma, int i_malivello)
{
	const size_t grande= ((size_t)1 << (20 + i_blocco)) - 4096;
	const std::string metodo= std::string(1, (char)('0' + i_livello)) + itos(i_blocco);
	Scrittore fuori(i_out);
	std::deque<std::future<blocco_fatto> > coda;
	catena tutto;
	bool finito= false;
	std::vector<char> pezzo(1 << 18);
	while (!finito)
	{
		blocco dati(new libzpaq::StringBuffer(grande));
		size_t presi= 0;
		while (presi < grande)
		{
			const int vuole= (int)std::min(pezzo.size(), grande - presi);
			const int r= leggi(i_in, &pezzo[0], vuole);
			if (r < 0)
				throw errore_io{"read error"};
			if (r == 0)
			{
				finito= true;
				break;
			}
			dati->write(&pezzo[0], r);
			presi+= (size_t)r;
		}
		if (presi > 0)
		{
			if (i_thread <= 1)
				coda.push_back(std::async(std::launch::deferred, comprimi_blocco, std::move(dati), metodo, i_ma, i_malivello));
			else
				coda.push_back(std::async(std::launch::async, comprimi_blocco, std::move(dati), metodo, i_ma, i_malivello));
		}
		while ((!coda.empty()) && ((coda.size() >= (size_t)i_thread) || finito))
		{
			blocco_fatto b= coda.front().get();
			coda.pop_front();
			tutto.aggiungi(b.sha.data(), b.byte);
			fuori.write(b.dati->c_str(), (int)b.dati->size());
		}
	}
	libzpaq::StringBuffer vuoto, ultimo;
	libzpaq::compressBlock(&vuoto, &ultimo, "00", "", tutto.testo().c_str(), true);
	fuori.write(ultimo.c_str(), (int)ultimo.size());
	fuori.flush();
}

struct errore_dati
{
	const char *cosa;
};

/// what a run of blocks gave: the SHA-1 and the size of each one, and the last block if it was there
struct letto
{
	std::vector<std::string> sha;
	std::vector<int64_t> byte;
	bool fine;
	std::string finetesto;
	letto() : fine(false) {}
};
/// every block of i_in to i_out. Throws errore_testo for what is damaged
struct errore_testo
{
	std::string cosa;
};
class Conta : public libzpaq::Writer
{
	libzpaq::Writer *w;

public:
	int64_t n;
	Conta(libzpaq::Writer *i_w) : w(i_w), n(0) {}
	void put(int c)
	{
		n++;
		w->put(c);
	}
	void write(const char *buf, int len)
	{
		n+= len;
		w->write(buf, len);
	}
};
static void leggi_blocchi(libzpaq::Reader *i_in, libzpaq::Writer *i_out, letto &o_letto)
{
	Conta conta(i_out);
	libzpaq::Decompresser d;
	d.setInput(i_in);
	d.setOutput(&conta);
	while (d.findBlock())
	{
		while (d.findFilename())
		{
			if (o_letto.fine)
				throw errore_testo{"damaged data: a block after the last one"};
			libzpaq::SHA1 sha;
			libzpaq::StringBuffer commento;
			const int64_t prima= conta.n;
			d.readComment(&commento);
			/// a -ma block is decoded by its own ZPAQL program, as any zpaq does it
			d.setSHA1(&sha);
			d.decompress();
			char atteso[21]= {0};
			d.readSegmentEnd(atteso);
			const std::string suo(sha.result(), 20);
			if ((!atteso[0]) || (memcmp(atteso + 1, suo.data(), 20) != 0))
				throw errore_testo{"damaged data: the checksum of a block is not the stored one"};
			const std::string c(commento.c_str(), commento.size());
			const size_t p= c.find(FINE);
			if (p != std::string::npos)
			{
				if (conta.n != prima)
					throw errore_testo{"damaged data: the last block has data"};
				o_letto.fine= true;
				o_letto.finetesto= c.substr(p);
			}
			else
			{
				o_letto.sha.push_back(suo);
				o_letto.byte.push_back(conta.n - prima);
			}
		}
	}
}
/// the blocks read, in their order, against what the last block says
struct verifica
{
	catena tutto;
	bool fine;
	std::string finetesto;
	verifica() : fine(false) {}
	void aggiungi(letto &i_l)
	{
		if (fine && ((!i_l.sha.empty()) || i_l.fine))
			throw errore_testo{"damaged data: a block after the last one"};
		for (size_t i= 0; i < i_l.sha.size(); i++)
			tutto.aggiungi(i_l.sha[i].data(), i_l.byte[i]);
		if (i_l.fine)
		{
			fine= true;
			finetesto= i_l.finetesto;
		}
	}
	void chiudi()
	{
		if (!fine)
			throw errore_testo{(tutto.blocchi == 0) ? "damaged data: not a stream of zpaqstd" : "damaged data: the stream is cut (its last block is missing)"};
		if (finetesto != tutto.testo())
			throw errore_testo{"damaged data: blocks are missing, or not in their order"};
	}
};
static void decomprimi(maniglia i_in, maniglia i_out)
{
	Lettore dentro(i_in);
	Scrittore fuori(i_out);
	letto l;
	verifica v;
	try
	{
		leggi_blocchi(&dentro, &fuori, l);
	}
	catch (const errore_testo &)
	{
		fuori.flush();
		throw;
	}
	fuori.flush();
	v.aggiungi(l);
	v.chiudi();
}

/// d with threads. A block says nowhere how long it is, so the input is cut where a block begins: the
/// 13 bytes that every block written here (and by zpaq) starts with, and "zPQ" after them. Each piece
/// is decoded in memory by a thread and written in its order. If those 16 bytes ever turn up inside a
/// block, its two pieces do not decode by themselves: a piece that fails is joined to the next one and
/// decoded again, so the cut is never trusted.
struct pezzo_fuori
{
	bool bene;
	std::string errore;
	blocco dati;
	letto l;
};
static pezzo_fuori decomprimi_pezzo(std::shared_ptr<std::string> i_pezzo)
{
	pezzo_fuori r;
	r.bene= false;
	try
	{
		libzpaq::StringBuffer dentro;
		dentro.write(i_pezzo->data(), (int)i_pezzo->size());
		r.dati.reset(new libzpaq::StringBuffer(i_pezzo->size() * 2 + 4096));
		leggi_blocchi(&dentro, r.dati.get(), r.l);
		r.bene= true;
	}
	catch (const std::bad_alloc &)
	{
		throw;
	}
	catch (const errore_testo &e)
	{
		r.errore= e.cosa;
	}
	catch (const std::exception &e)
	{
		r.errore= std::string("damaged data: ") + e.what();
	}
	return r;
}
static void decomprimi_thread(maniglia i_in, maniglia i_out, int i_thread)
{
	static const char firma[]= "\x37\x6b\x53\x74\xa0\x31\x83\xd3\x8c\xb2\x28\xb0\xd3zPQ";
	const size_t lfirma= 16;
	Scrittore fuori(i_out);
	struct lavoro
	{
		std::shared_ptr<std::string> pezzo;
		std::future<pezzo_fuori> esito;
	};
	std::deque<lavoro> coda;
	std::string acc;
	std::vector<char> letti(1 << 18);
	bool finito= false;
	verifica v;
	size_t cerca= 1;
	while ((!finito) || (!coda.empty()) || (!acc.empty()))
	{
		/// the next piece: up to where another block begins, or all that is left
		std::shared_ptr<std::string> pezzo;
		while ((!pezzo) && ((!finito) || (!acc.empty())))
		{
			size_t dove= std::string::npos;
			if (acc.size() >= cerca + lfirma)
			{
				const char *inizio= acc.data();
				const char *fine= inizio + acc.size();
				const char *fine_firma= firma + lfirma;
				const char *q= std::search(inizio + cerca, fine, (const char *)firma, fine_firma);
				if (q != fine)
					dove= (size_t)(q - acc.data());
				else
					cerca= acc.size() - lfirma + 1;
			}
			if (dove != std::string::npos)
			{
				pezzo.reset(new std::string(acc, 0, dove));
				acc.erase(0, dove);
				cerca= 1;
			}
			else if (finito)
			{
				pezzo.reset(new std::string());
				pezzo->swap(acc);
				cerca= 1;
			}
			else
			{
				const int r= leggi(i_in, &letti[0], (int)letti.size());
				if (r < 0)
					throw errore_io{"read error"};
				if (r == 0)
					finito= true;
				else
					acc.append(&letti[0], (size_t)r);
			}
		}
		if (pezzo)
		{
			lavoro l;
			l.pezzo= pezzo;
			l.esito= std::async(std::launch::async, decomprimi_pezzo, pezzo);
			coda.push_back(std::move(l));
		}
		/// write what is ready, in order: when the threads are all taken, or nothing is left to read
		while ((!coda.empty()) && ((coda.size() >= (size_t)i_thread) || (!pezzo)))
		{
			pezzo_fuori r= coda.front().esito.get();
			std::shared_ptr<std::string> suo= coda.front().pezzo;
			coda.pop_front();
			while (!r.bene)
			{
				/// not a whole block by itself? With the piece after it (already cut, or still to read)
				std::shared_ptr<std::string> dopo;
				if (!coda.empty())
				{
					coda.front().esito.wait();
					dopo= coda.front().pezzo;
					coda.pop_front();
				}
				else if ((!acc.empty()) || (!finito))
				{
					while (!finito)
					{
						const int n= leggi(i_in, &letti[0], (int)letti.size());
						if (n < 0)
							throw errore_io{"read error"};
						if (n == 0)
							finito= true;
						else
							acc.append(&letti[0], (size_t)n);
					}
					dopo.reset(new std::string());
					dopo->swap(acc);
					cerca= 1;
				}
				if ((!dopo) || dopo->empty())
				{
					fuori.flush();
					throw errore_testo{r.errore};
				}
				std::shared_ptr<std::string> insieme(new std::string(*suo));
				insieme->append(*dopo);
				suo= insieme;
				r= decomprimi_pezzo(suo);
			}
			fuori.write(r.dati->c_str(), (int)r.dati->size());
			v.aggiungi(r.l);
		}
	}
	fuori.flush();
	v.chiudi();
}
} // namespace zslib

ZPAQSTD_API const char *zpaqstd_version(void)
{
	return "zpaq-std " ZPAQSTD_VERSION " (zpaqfranz " ZPAQ_VERSION ") library 1";
}

static int zpaqstd_corri(int argc, char **argv, intptr_t i_in, intptr_t i_out, intptr_t i_err)
{
	using namespace zslib;
	const maniglia in= (maniglia)i_in, out= (maniglia)i_out, err= (maniglia)i_err;
	int rc= 0;
	try
	{
		char comando= 0;
		int livello= 1, blocco= -1, thread= 1, malivello= 0;
		std::string ma;
		bool male= (argc < 1) || (argv == NULL);
		for (int i= 0; (!male) && (i < argc); i++)
		{
			const std::string a= argv[i] ? argv[i] : "";
			if ((i == 0) && ((a == "c") || (a == "d")))
				comando= a[0];
			else if ((a.size() >= 3) && (a.compare(0, 2, "-m") == 0) && (a[2] >= '0') && (a[2] <= '5') && (a.find_first_not_of("0123456789", 2) == std::string::npos) && (a.size() <= 5))
			{
				livello= a[2] - '0';
				if (a.size() > 3)
					blocco= atoi(a.c_str() + 3);
			}
			else if ((a.size() >= 3) && (a.size() <= 5) && (a.compare(0, 2, "-t") == 0) && (a.find_first_not_of("0123456789", 2) == std::string::npos))
				thread= atoi(a.c_str() + 2);
			else if ((a.size() > 4) && (a.compare(0, 4, "-ma:") == 0))
			{
				/// -ma:<codec>:<level>, the level always given
				const size_t p= a.find(':', 4);
				const std::string lv= (p == std::string::npos) ? "" : a.substr(p + 1);
				ma= a.substr(4, (p == std::string::npos) ? std::string::npos : p - 4);
				const std::string plug= zs_plugin_name(ma);
				const zs_codec *zc= (plug == "") ? NULL : zs_get(plug.c_str());
				if (lv.empty() || (lv.size() > 4) || (lv.find_first_not_of("0123456789") != std::string::npos) || (zc == NULL) || (ma == "sylz") || (ma == "sylzec") || (ma == "lzav") || (ma.compare(0, 3, "lz4") == 0))
					male= true;
				else
					malivello= atoi(lv.c_str());
			}
			else
				male= true;
		}
		if (blocco < 0)
			blocco= (livello <= 1) ? 4 : 6;
		if (male || (comando == 0) || (blocco > 11) || (thread < 1) || (thread > 256))
		{
			dillo(err, "usage: c [-m<0..5>[<block 0..11: 2^n MiB>]] [-ma:<codec>:<level>] [-t<threads>] | d [-t<threads>]");
			rc= 1;
		}
		else if (comando == 'c')
			comprimi(in, out, livello, blocco, thread, ma, malivello);
		else if (thread <= 1)
			decomprimi(in, out);
		else
			decomprimi_thread(in, out, thread);
	}
	catch (const errore_io &e)
	{
		dillo(err, e.cosa);
		rc= 2;
	}
	catch (const errore_dati &e)
	{
		dillo(err, e.cosa);
		rc= 4;
	}
	catch (const errore_testo &e)
	{
		dillo(err, e.cosa);
		rc= 4;
	}
	catch (const std::bad_alloc &)
	{
		dillo(err, "out of memory");
		rc= 3;
	}
	catch (const std::exception &e)
	{
		dillo(err, std::string("damaged data: ") + e.what());
		rc= 4;
	}
	catch (...)
	{
		dillo(err, "unknown error");
		rc= 2;
	}
	chiudi(in);
	chiudi(out);
	chiudi(err);
	return rc;
}

#ifdef _WIN32
/// Windows: the work runs in a thread of the library, never in the caller's. mingw-w64's static runtime
/// keeps what C++ needs for each thread (exceptions, thread_local) in emulated TLS, freed when the thread
/// ends or the DLL goes; if the caller's thread had used it here (d throws and catches), the C++ streams'
/// destructor found it freed while the DLL was unloaded and wrote there: Windows 7 x64 ended the process
/// with a corrupted heap (0xC0000374) in one FreeLibrary out of three, and now and then at exit.
namespace zslib
{
struct chiamata
{
	int argc;
	char **argv;
	intptr_t in, out, err;
	int rc;
};
static DWORD WINAPI filo(LPVOID i_p)
{
	chiamata *c= (chiamata *)i_p;
	c->rc= zpaqstd_corri(c->argc, c->argv, c->in, c->out, c->err);
	return 0;
}
} // namespace zslib
#endif

ZPAQSTD_API int zpaqstd_run(int argc, char **argv, intptr_t i_in, intptr_t i_out, intptr_t i_err)
{
#ifdef _WIN32
	zslib::chiamata c= {argc, argv, i_in, i_out, i_err, 2};
	HANDLE h= CreateThread(NULL, (SIZE_T)16 << 20, zslib::filo, &c, 0, NULL);
	if (h == NULL)
	{
		static const char testo[]= "zpaqstd: cannot start a thread\n";
		DWORD fatti= 0;
		WriteFile((HANDLE)i_err, testo, (DWORD)(sizeof(testo) - 1), &fatti, NULL);
		CloseHandle((HANDLE)i_in);
		CloseHandle((HANDLE)i_out);
		CloseHandle((HANDLE)i_err);
		return 3;
	}
	WaitForSingleObject(h, INFINITE);
	CloseHandle(h);
	return c.rc;
#else
	return zpaqstd_corri(argc, argv, i_in, i_out, i_err);
#endif
}
