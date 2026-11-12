#pragma once
#include <string>
namespace pvz {
// Opt-in, local developer API. No effect on the normal game entry.
int run_developer_tools(const std::string& request_path, const std::string& response_path);
}
