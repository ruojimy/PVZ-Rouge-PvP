#pragma once
// Reads an exported opening (build/pvp73-tools/cold73_export, build/ai-nn/cold-corpus) from
// files into a ColdExport for Session::create. No V dependency and no dependency on the
// composition: this is the file-side twin of cold_export.cpp (which reads the V-constructed
// battle). Files may be plain or gzip-compressed; both are read through zlib.
// Used by the headless AI tools only (build/ai-nn); the shipped game does not link it.
#include "sim/typed72_app/cold_data.h"
#include <string>
#include <vector>
namespace pvz::typed72app {
// Whole file, decompressed when it is a gzip stream. Throws std::runtime_error.
std::string read_file_maybe_gz(const std::string& path);
// cold.json, atlas.bin and atlas.bin.draw.json as written by cold73_export. Atlas entries keep
// their file order.
ColdExport load_cold_files(const std::string& cold_json,const std::string& atlas_bin,const std::string& draw_json);
// One entry of build/ai-nn/cold-corpus/index.json.
struct CorpusEntry {
    std::string id,map;
    bool night=false;
    double seed=0.;
    std::vector<std::string> bans,plant_deck,zombie_deck;
    std::string cold_path,draw_path,atlas_path;   // resolved against the corpus directory
};
std::vector<CorpusEntry> read_corpus_index(const std::string& corpus_dir);
CorpusEntry corpus_entry(const std::string& corpus_dir,const std::string& id);
ColdExport load_corpus_entry(const CorpusEntry&);
} // namespace pvz::typed72app
