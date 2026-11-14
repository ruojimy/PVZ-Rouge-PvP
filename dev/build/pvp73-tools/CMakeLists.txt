cmake_minimum_required(VERSION 3.20)
project(Pvp73Tools LANGUAGES CXX)
# PvP73 V reference tools: record/export against the CURRENT V sources as compiled
# into build/app-typed72-v2 (not the frozen 11-05 build/Release libraries).
set(ROOT "C:/Users/xiech/Downloads/PVZ_rougePvP_native")
set(LIBDIR "${ROOT}/build/app-typed72-v2/Release")
set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)
set(LIBS "${LIBDIR}/pvzui.lib" "${LIBDIR}/pvztyped72app.lib" "${LIBDIR}/pvztyped72kernel.lib" "${LIBDIR}/pvzcore.lib" "${LIBDIR}/pvzsnapshot_zlib.lib"
    "${ROOT}/third_party/SDL2-2.30.9/lib/x64/SDL2.lib" "${ROOT}/third_party/SDL2_image-2.8.2/lib/x64/SDL2_image.lib"
    "${ROOT}/third_party/SDL2_ttf-2.22.0/lib/x64/SDL2_ttf.lib" "${ROOT}/third_party/SDL2_mixer-2.8.0/lib/x64/SDL2_mixer.lib" ws2_32)
foreach(n ref73_record cold73_export v_cold_catalog_probe deck73_corpus)
  add_executable(${n} ${n}.cpp)
  target_compile_features(${n} PRIVATE cxx_std_20)
  target_compile_options(${n} PRIVATE /utf-8 /fp:precise /MP1 /FS /bigobj)
  target_compile_definitions(${n} PRIVATE SDL_MAIN_HANDLED NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS)
  target_include_directories(${n} PRIVATE "${ROOT}/src" "${ROOT}/third_party" "${ROOT}/third_party/SDL2-2.30.9/include")
  target_link_libraries(${n} PRIVATE ${LIBS})
endforeach()

# Compile the current scenario cold-boundary owner rather than a stale library copy.
target_sources(cold73_export PRIVATE "${ROOT}/src/sim/pvp/battle_api.cpp")
