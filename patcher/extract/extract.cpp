#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>

#include <bun.h>

#ifdef BAZEL_BUILD
#include <memory>
#include "rules_cc/cc/runfiles/runfiles.h"
using rules_cc::cc::runfiles::Runfiles;
#endif

int main(int argc, char **argv) {
    if (argc != 3 && argc != 4) {
        fprintf(stderr, "usage: %s <ggpkd> <path> [output]\n", argv[0]);
        return 1;
    }
    std::string ggpkd(argv[1]);
    std::string path(argv[2]);
    std::optional<std::filesystem::path> out;
    if (argc == 4) {
        out = argv[3];
    }

#ifdef BAZEL_BUILD
    std::string error;
    auto runfiles = std::unique_ptr<Runfiles>(
        Runfiles::Create(argv[0], BAZEL_CURRENT_REPOSITORY, &error));
    if (!runfiles) {
        fprintf(stderr, "Failed to create runfiles: %s\n", error.c_str());
        return 1;
    }
    auto ooz_path = runfiles->Rlocation("ooz/liblibooz.so");
    Bun *bun = BunNew(ooz_path.c_str(), "Ooz_Decompress");
#else
    Bun *bun =
        BunNew("extract/build/subprojects/ooz/liblibooz.so", "Ooz_Decompress");
#endif
    if (!bun) {
        fprintf(stderr, "Failed to load liblibooz.so\n");
        return 1;
    }

    BunIndex *idx = BunIndexOpen(bun, nullptr, ggpkd.c_str());
    if (!idx) {
        fprintf(stderr, "Failed to open bundle index at %s\n", ggpkd.c_str());
        return 1;
    }

    int32_t file_id = BunIndexLookupFileByPath(idx, path.c_str());
    if (file_id < 0) {
        fprintf(stderr, "File not found: %s\n", path.c_str());
        return 1;
    }

    uint64_t path_hash;
    uint32_t bundle_id;
    uint32_t offset;
    uint32_t size;
    BunIndexFileInfo(idx, file_id, &path_hash, &bundle_id, &offset, &size);

    if (!out) {
        const char* name;
        uint32_t uncompressed_size;
        BunIndexBundleInfo(idx, bundle_id, &name, &uncompressed_size);
        printf("%s\n", name);
    } else {
        BunMem p = BunIndexExtractBundle(idx, bundle_id);
        if (!p) {
            fprintf(stderr, "Failed to extract bundle %u\n", bundle_id);
            return 1;
        }

        std::filesystem::create_directories(out->parent_path());

        std::ofstream outf(*out);
        outf.write(reinterpret_cast<char *>(p) + offset, size);
    }

    return 0;
}
