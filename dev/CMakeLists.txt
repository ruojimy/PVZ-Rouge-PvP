cmake_minimum_required(VERSION 3.20)
project(PvZPvPNative C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

if(MSVC)
  # /utf-8: Chinese identifiers and literals (fields mirror the original game's names)
  # /fp:precise and no FMA/AVX2 contraction: float results equal CPython's
  add_compile_options(/utf-8 /W3 /permissive- /Zc:__cplusplus /fp:precise /bigobj /MP)
  add_compile_options($<$<CONFIG:Release>:/O2> $<$<CONFIG:RelWithDebInfo>:/O2> /Zi)
  add_link_options(/DEBUG:FASTLINK)
  add_compile_definitions(_CRT_SECURE_NO_WARNINGS NOMINMAX WIN32_LEAN_AND_MEAN)
endif()

set(TP ${CMAKE_SOURCE_DIR}/third_party)
# Standard zlib stream bytes for network snapshots. Symbols are isolated from
# SDL's private zlib copies; only upstream compression code is linked.
set(SNAPSHOT_ZLIB_ROOT ${TP}/zlib-1.3.2-compress)
add_library(pvzsnapshot_zlib STATIC
  ${SNAPSHOT_ZLIB_ROOT}/adler32.c ${SNAPSHOT_ZLIB_ROOT}/compress.c
  ${SNAPSHOT_ZLIB_ROOT}/crc32.c ${SNAPSHOT_ZLIB_ROOT}/deflate.c
  ${SNAPSHOT_ZLIB_ROOT}/trees.c ${SNAPSHOT_ZLIB_ROOT}/zutil.c)
target_compile_definitions(pvzsnapshot_zlib PRIVATE Z_PREFIX)
set(SDL2_DIR_ROOT ${TP}/SDL2-2.30.9)
set(SDL2_IMAGE_ROOT ${TP}/SDL2_image-2.8.2)
set(SDL2_TTF_ROOT ${TP}/SDL2_ttf-2.22.0)
set(SDL2_MIXER_ROOT ${TP}/SDL2_mixer-2.8.0)

file(GLOB_RECURSE CORE_SRC CONFIGURE_DEPENDS
  src/core/*.cpp src/data/*.cpp src/sim/*.cpp src/ai/*.cpp src/net/*.cpp)
list(FILTER CORE_SRC EXCLUDE REGEX "/shim_headless/")
# The typed migration is a separate library. Partial stages must not be linked
# accidentally into the production backend by the recursive source glob.
list(FILTER CORE_SRC EXCLUDE REGEX "/typed/")
list(FILTER CORE_SRC EXCLUDE REGEX "/typed72_app/")
option(PVZ_BUILD_TYPED72_STAGES "Build isolated typed72 migration verification targets" OFF)
if(PVZ_BUILD_TYPED72_STAGES)
  add_subdirectory(src/sim/typed)
endif()
add_library(pvzcore STATIC ${CORE_SRC})
target_link_libraries(pvzcore PUBLIC pvzsnapshot_zlib)
# headless stand-ins for UI modules the simulation touches (world_view, app, asset loaders);
# the game links the real translations from src/ui/gen instead
file(GLOB HEADLESS_SRC CONFIGURE_DEPENDS src/sim/pvp/shim_headless/*.cpp)
add_library(pvzheadless STATIC ${HEADLESS_SRC})
target_link_libraries(pvzheadless PUBLIC pvzcore)
target_include_directories(pvzcore PUBLIC src ${TP})
if(WIN32)
  target_link_libraries(pvzcore PUBLIC ws2_32)
endif()

# headless tools: oracle diff runner, unit tests
file(GLOB TOOL_SRC CONFIGURE_DEPENDS src/tools/*.cpp)
foreach(f ${TOOL_SRC})
  get_filename_component(n ${f} NAME_WE)
  add_executable(${n} ${f})
  if(n STREQUAL "run_battle")
    # Oracle runs need the same exact recipe pixel materializer as the game.
    # The software SDL driver keeps this command-line tool non-interactive.
    target_link_libraries(${n} PRIVATE pvzcore)
  else()
    target_link_libraries(${n} PRIVATE pvzcore pvzheadless)
  endif()
endforeach()

# UI: pygame facade over SDL2 (src/pg) + translated UI modules (src/ui)
set(SDL_INCLUDES ${SDL2_DIR_ROOT}/include ${SDL2_IMAGE_ROOT}/include ${SDL2_TTF_ROOT}/include ${SDL2_MIXER_ROOT}/include)
set(SDL_LIBS ${SDL2_DIR_ROOT}/lib/x64/SDL2.lib ${SDL2_IMAGE_ROOT}/lib/x64/SDL2_image.lib
             ${SDL2_TTF_ROOT}/lib/x64/SDL2_ttf.lib ${SDL2_MIXER_ROOT}/lib/x64/SDL2_mixer.lib)
set(SDL_DLLS ${SDL2_DIR_ROOT}/lib/x64/SDL2.dll ${SDL2_IMAGE_ROOT}/lib/x64/SDL2_image.dll
             ${SDL2_TTF_ROOT}/lib/x64/SDL2_ttf.dll ${SDL2_MIXER_ROOT}/lib/x64/SDL2_mixer.dll)
file(GLOB_RECURSE UI_SRC CONFIGURE_DEPENDS src/pg/*.cpp src/ui/*.cpp)
if(UI_SRC)
  # Typed PvP72 battle (the shipped dynamic path): the integrated typed kernel stage, and the app
  # bridge (cold export of the V-constructed battle, typed session, NativeBattle adapter).
  set(PVZ_TYPED72_STAGE "${CMAKE_SOURCE_DIR}/build/typed72-integrated-v44/source" CACHE PATH "integrated typed72 kernel stage")
  set(PVZ_TYPED72_COMPOSITION "${CMAKE_SOURCE_DIR}/src/sim/typed72_app/composition" CACHE PATH "generated typed72 app composition")
  # Generator is build-time tooling only. Reject stale production composition
  # rather than quietly compiling a mixture of old generated code and new probes.
  find_package(Python3 3.8 REQUIRED COMPONENTS Interpreter)
  add_custom_target(typed72_composition_check
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/tools/typed72/make_app_composition.py" --check --out "${PVZ_TYPED72_COMPOSITION}"
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    COMMENT "Verify typed72 production composition against its source manifest"
    VERBATIM)
  file(GLOB TYPED72_KERNEL_SRC CONFIGURE_DEPENDS ${PVZ_TYPED72_STAGE}/src/sim/typed/*.cpp)
  add_library(pvztyped72kernel STATIC ${TYPED72_KERNEL_SRC})
  target_include_directories(pvztyped72kernel BEFORE PUBLIC ${PVZ_TYPED72_STAGE}/src)
  target_include_directories(pvztyped72kernel PUBLIC src ${TP} ${CMAKE_SOURCE_DIR}/tools/typed72 ${SDL_INCLUDES})
  target_include_directories(pvztyped72kernel PRIVATE ${PVZ_TYPED72_STAGE}/src/sim/typed)
  target_link_libraries(pvztyped72kernel PUBLIC ${SDL_LIBS})
  add_library(pvztyped72app STATIC src/sim/typed72_app/cold_export.cpp src/sim/typed72_app/session.cpp src/sim/typed72_app/typed_battle.cpp src/sim/typed72_app/ai_planner_r22.cpp src/sim/typed72_app/ai/controller.cpp src/sim/typed72_app/ai/layers7.cpp src/sim/typed72_app/ai/layers11.cpp src/sim/typed72_app/ai/layers19.cpp)
  target_include_directories(pvztyped72app BEFORE PRIVATE ${PVZ_TYPED72_STAGE}/src ${PVZ_TYPED72_COMPOSITION} ${PVZ_TYPED72_COMPOSITION}/probes)
  target_include_directories(pvztyped72app PRIVATE ${SDL_INCLUDES})
  target_link_libraries(pvztyped72app PUBLIC pvztyped72kernel pvzcore)
  # Same generated composition and kernel as Session, but with the deterministic
  # match entry point enabled. No pvzcore/V runtime is linked into this verifier.
  # Keep it opt-in: it is an acceptance tool, not part of the shipped application.
  add_executable(typed72_match_gate EXCLUDE_FROM_ALL ${PVZ_TYPED72_COMPOSITION}/match_probe.cpp)
  target_include_directories(typed72_match_gate BEFORE PRIVATE ${PVZ_TYPED72_STAGE}/src ${PVZ_TYPED72_COMPOSITION} ${PVZ_TYPED72_COMPOSITION}/probes)
  target_compile_definitions(typed72_match_gate PRIVATE SDL_MAIN_HANDLED)
  target_link_libraries(typed72_match_gate PRIVATE pvztyped72kernel)
  add_dependencies(pvztyped72app typed72_composition_check)
  add_dependencies(typed72_match_gate typed72_composition_check)
  if(WIN32)
    target_link_libraries(typed72_match_gate PRIVATE ws2_32)
  endif()
  add_custom_command(TARGET typed72_match_gate POST_BUILD COMMAND ${CMAKE_COMMAND} -E copy_if_different ${SDL_DLLS} $<TARGET_FILE_DIR:typed72_match_gate>)
  add_library(pvzui STATIC ${UI_SRC})
  target_include_directories(pvzui PUBLIC ${SDL_INCLUDES})
  target_link_libraries(pvzui PUBLIC pvzcore ${SDL_LIBS})
  target_link_libraries(pvzui PUBLIC pvztyped72app)
  if(WIN32)
    target_link_libraries(pvzui PUBLIC comdlg32)
  endif()
  add_custom_target(texture74_hooks_check
    COMMAND "${Python3_EXECUTABLE}" -I -B "${CMAKE_SOURCE_DIR}/tools/pvp74_apply_hooks.py" --check
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}" VERBATIM)
  add_dependencies(pvzui texture74_hooks_check)
  add_custom_target(pvp741_hooks_check
    COMMAND "${Python3_EXECUTABLE}" -I -B "${CMAKE_SOURCE_DIR}/tools/pvp741_apply_hooks.py" --check
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}" VERBATIM)
  add_dependencies(pvzui pvp741_hooks_check)
  # The AISeat typed-observation bodies in src/ui/gen/pm_lobby_room.cpp are
  # generated from tools/pvp72_sources/lobby_room.py; reject a stale copy.
  add_custom_target(typed72_ai_bridge_check
    COMMAND "${Python3_EXECUTABLE}" -I -B "${CMAKE_SOURCE_DIR}/tools/typed72/make_ai_lobby_bridge.py" --check
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    COMMENT "Verify generated AISeat typed observation boundary"
    VERBATIM)
  add_dependencies(pvzui typed72_ai_bridge_check)
  if(TARGET run_battle)
    target_link_libraries(run_battle PRIVATE pvzui)
    target_compile_definitions(run_battle PRIVATE SDL_MAIN_HANDLED)
    add_custom_command(TARGET run_battle POST_BUILD COMMAND ${CMAKE_COMMAND} -E copy_if_different ${SDL_DLLS} $<TARGET_FILE_DIR:run_battle>)
  endif()
  # UI tools (console programs)
  file(GLOB UITOOL_SRC CONFIGURE_DEPENDS src/uitools/*.cpp)
  foreach(f ${UITOOL_SRC})
    get_filename_component(n ${f} NAME_WE)
    add_executable(${n} ${f})
    target_link_libraries(${n} PRIVATE pvzui)
    if(n STREQUAL "pvp741_hero_texture_audit" OR n STREQUAL "pvp742_terrain_units_audit" OR n STREQUAL "pvp742_reverse_subscription_bench" OR n STREQUAL "pvp742_plant_occupancy_audit" OR n STREQUAL "pvp742_secondhand_audit")
      # These verifiers construct production state (HeroState / FloodState).
      target_include_directories(${n} BEFORE PRIVATE ${PVZ_TYPED72_STAGE}/src)
    endif()
    target_compile_definitions(${n} PRIVATE SDL_MAIN_HANDLED)
    add_custom_command(TARGET ${n} POST_BUILD COMMAND ${CMAKE_COMMAND} -E copy_if_different ${SDL_DLLS} $<TARGET_FILE_DIR:${n}>)
  endforeach()
endif()

# the game
file(GLOB_RECURSE GAME_SRC CONFIGURE_DEPENDS src/render/*.cpp src/audio/*.cpp src/app/*.cpp)
if(GAME_SRC)
  add_executable(PvZPvPNative WIN32 ${GAME_SRC})
  if(WIN32)
    enable_language(RC)
    target_sources(PvZPvPNative PRIVATE src/app/pvp72.rc)
  endif()
  target_link_libraries(PvZPvPNative PRIVATE pvzui ${SDL2_DIR_ROOT}/lib/x64/SDL2main.lib)
  add_custom_command(TARGET PvZPvPNative POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different ${SDL_DLLS} $<TARGET_FILE_DIR:PvZPvPNative>)
  option(PVZ_BUILD_DEVELOPER_CANDIDATE "Build an independent optional developer API candidate" OFF)
  if(PVZ_BUILD_DEVELOPER_CANDIDATE)
    add_executable(PvZPvPNativeDev WIN32 ${GAME_SRC})
    if(WIN32)
      target_sources(PvZPvPNativeDev PRIVATE src/app/pvp72.rc)
    endif()
    target_link_libraries(PvZPvPNativeDev PRIVATE pvzui ${SDL2_DIR_ROOT}/lib/x64/SDL2main.lib)
    add_custom_command(TARGET PvZPvPNativeDev POST_BUILD
      COMMAND ${CMAKE_COMMAND} -E copy_if_different ${SDL_DLLS} $<TARGET_FILE_DIR:PvZPvPNativeDev>)
  endif()
endif()

# old-suite tests translated to C++ (tools/gen_cpp_tests.py), run on the released engine (pvzui + pvzcore)
file(GLOB CPPTEST_SRC CONFIGURE_DEPENDS src/cpptests/*.cpp)
include(src/cpptests/sources.cmake OPTIONAL)
if(DEFINED PVZ_CPPTEST_GENERATED_SRC)
  list(APPEND CPPTEST_SRC ${PVZ_CPPTEST_GENERATED_SRC})
else()
  file(GLOB CPPTEST_GEN CONFIGURE_DEPENDS src/cpptests/gen/*.cpp)
  list(APPEND CPPTEST_SRC ${CPPTEST_GEN})
endif()
if(CPPTEST_SRC AND UI_SRC)
  add_executable(cpp_tests ${CPPTEST_SRC})
  target_link_libraries(cpp_tests PRIVATE pvzui)
  target_compile_definitions(cpp_tests PRIVATE SDL_MAIN_HANDLED)
endif()

# The default font is a shipped asset, independent of Windows/system font choices.
foreach(n PvZPvPNative app_run run_battle cpp_tests)
  if(TARGET ${n})
    add_custom_command(TARGET ${n} POST_BUILD
      COMMAND ${CMAKE_COMMAND} -E copy_directory ${CMAKE_SOURCE_DIR}/fonts $<TARGET_FILE_DIR:${n}>/fonts)
  endif()
endforeach()
