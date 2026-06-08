/* pcf_wrapper.cpp — implementation of the collision-free preflate bridge.
   This is the ONLY translation unit that includes preflate headers. */
#include "pcf_wrapper.h"
#include "preflate_decoder.h"
#include "preflate_reencoder.h"

bool pcf_deflate_decode(const unsigned char* deflate, size_t deflate_len,
                        std::vector<unsigned char>& unpacked,
                        std::vector<unsigned char>& recon) {
  unpacked.clear();
  recon.clear();
  if (deflate == 0 || deflate_len == 0) return false;
  std::vector<unsigned char> in(deflate, deflate + deflate_len);
  try {
    if (!preflate_decode(unpacked, recon, in)) return false;
  } catch (...) {
    return false;
  }
  return true;
}

bool pcf_deflate_reencode(const std::vector<unsigned char>& unpacked,
                          const std::vector<unsigned char>& recon,
                          std::vector<unsigned char>& deflate_out) {
  deflate_out.clear();
  try {
    if (!preflate_reencode(deflate_out, recon, unpacked)) return false;
  } catch (...) {
    return false;
  }
  return true;
}

/* orig=2352 deflate=133 (raw deflate, wbits=-15, zlib level 6) */
static const unsigned char PCF_TEST_DEFLATE[133] = {
  11,112,118,83,200,204,211,77,202,204,75,44,170,84,40,78,205,73,211,45,73,45,46,177,82,40,
  201,72,85,40,44,205,76,206,86,72,42,202,47,207,83,72,203,175,208,83,8,24,85,61,170,122,84,
  245,168,234,81,213,163,170,71,164,106,6,70,38,102,22,86,54,118,14,78,46,110,30,94,62,126,
  1,65,33,97,17,81,49,113,9,73,41,105,25,89,57,121,5,69,37,101,21,85,53,117,13,77,45,109,29,
  93,61,125,3,67,35,99,19,83,51,115,11,75,43,107,27,91,59,251,81,253,67,91,63,0,
};

bool pcf_autotest() {
  std::vector<unsigned char> unpacked, recon, reencoded;
  if (!pcf_deflate_decode(PCF_TEST_DEFLATE, sizeof(PCF_TEST_DEFLATE), unpacked, recon))
    return false;
  if (!pcf_deflate_reencode(unpacked, recon, reencoded))
    return false;
  if (reencoded.size() != sizeof(PCF_TEST_DEFLATE)) return false;
  for (size_t i = 0; i < reencoded.size(); ++i)
    if (reencoded[i] != PCF_TEST_DEFLATE[i]) return false;
  return true;
}
