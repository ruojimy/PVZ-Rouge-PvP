// Both platforms keep the native 71 save location. Upgrade takes a recoverable
// byte-for-byte snapshot once, before a 72 Application can change player files.
#include "core/save_upgrade72.h"
#include "core/fsutil.h"
#include <nlohmann/json.hpp>
#include <chrono>
#include <fstream>
#include <stdexcept>

namespace pvz {
void backup_native_save72(const std::filesystem::path& root) {
    namespace fs=std::filesystem;
    if(!fs::is_directory(root))return;
    const auto marker=root/"native-save-version.json";
    if(fs::exists(marker)) {
        std::ifstream input(marker);nlohmann::json old;
        input>>old;if(old.value("ruleset",std::string())=="pvp72")return;
    }
    const auto stamp=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
    const auto backup=root.parent_path()/"pvp_userdata_backups"/("before-pvp72-"+std::to_string(stamp));
    fs::create_directories(backup);
    nlohmann::json manifest=nlohmann::json::array();
    for(const auto& item:fs::recursive_directory_iterator(root)) {
        if(item.is_symlink())continue;
        if(!item.is_regular_file())continue;
        auto relative=fs::relative(item.path(),root),destination=backup/relative;
        fs::create_directories(destination.parent_path());
        fs::copy_file(item.path(),destination,fs::copy_options::none);
        std::ifstream a(item.path(),std::ios::binary),b(destination,std::ios::binary);
        std::string original((std::istreambuf_iterator<char>(a)),{}),copy((std::istreambuf_iterator<char>(b)),{});
        if(original!=copy)throw std::runtime_error("Save backup verification failed: "+p8(relative));
        manifest.push_back({{"path",p8(relative)},{"bytes",copy.size()}});
    }
    std::ofstream evidence(backup/"backup-manifest.json",std::ios::binary);
    evidence<<nlohmann::json{{"ruleset_from","native71"},{"ruleset_to","pvp72"},{"source",p8(root)},{"files",manifest}}.dump(2);evidence.close();
    if(evidence.fail())throw std::runtime_error("Cannot save upgrade backup manifest");
    const auto pending=root/"native-save-version.json.pending";
    std::ofstream output(pending,std::ios::binary);
    output<<nlohmann::json{{"format",1},{"ruleset","pvp72"},{"save_schema",1},{"backup",p8(backup)}}.dump(2);output.close();
    if(output.fail())throw std::runtime_error("Cannot record save upgrade");
    if(fs::exists(marker))fs::remove(marker);
    fs::rename(pending,marker);
}
}
