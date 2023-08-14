#ifdef NDEBUG
#error broken config
#endif

#include <cassert>
#include <filesystem>
#include <fstream>
#include <string>

#include <bun.h>

int main(int argc, char **argv) {
    assert(argc == 4);
    std::string ggpkd(argv[1]);
    std::filesystem::path out(argv[2]);
    std::string path(argv[3]);

    Bun *bun =
        BunNew("extract/build/subprojects/ooz/liblibooz.so", "Ooz_Decompress");
    assert(bun);

    BunIndex *idx = BunIndexOpen(bun, nullptr, ggpkd.c_str());
    assert(idx);

    int32_t file_id = BunIndexLookupFileByPath(idx, path.c_str());
    assert(file_id >= 0);

    uint64_t path_hash;
    uint32_t bundle_id;
    uint32_t offset;
    uint32_t size;
    assert(BunIndexFileInfo(idx, file_id, &path_hash, &bundle_id, &offset,
                            &size) == 0);

    BunMem p = BunIndexExtractBundle(idx, bundle_id);
    assert(p);

    std::filesystem::create_directories(out.parent_path());

    std::ofstream outf(out);
    outf.write(reinterpret_cast<char *>(p) + offset, size);

    return 0;
}
