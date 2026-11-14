# Headless AI-vs-AI build of the current typed kernel for Windows and Linux, no V runtime.
# Separate from the root game CMakeLists.txt; nothing here is part
# of the shipped game. See docs/ai-nn/ and build/ai-nn/README.md.
#
#   cmake -S build/ai-nn -B /tmp/ai-nn-build -DCMAKE_BUILD_TYPE=Release
#   cmake --build /tmp/ai-nn-build -j 4
cmake_minimum_required(VERSION 3.20)
project(PvZAiNnHeadless CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

get_filename_component(DEV_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
set(STAGE ${DEV_ROOT}/build/typed72-integrated-v44/source)
set(COMPOSITION ${DEV_ROOT}/src/sim/typed72_app/composition)
set(APP ${DEV_ROOT}/src/sim/typed72_app)

# Same float rules as the Android build (android/CMakeLists.txt TYPED72_FLAGS): no FMA
# contraction, no fast-math.
if(MSVC)
  set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)
  set(AI_NN_FLAGS /O2 /fp:precise /utf-8 /bigobj /EHsc /GR /w)
  add_compile_definitions(NOMINMAX WIN32_LEAN_AND_MEAN SDL_MAIN_HANDLED)
else()
  set(AI_NN_FLAGS -O2 -ffp-contract=off -fno-fast-math -w -fexceptions -frtti)
endif()

# SDL: the kernel needs it only for SDL_SoftStretch in native_art.cpp.
#   system = a real SDL2 development package (preferred when present)
#   shim   = build/ai-nn/sdl_shim (reimplementation of the one routine)
set(AI_NN_SDL "auto" CACHE STRING "auto | system | shim")
set(SDL_INC "")
set(SDL_LINK "")
set(SDL_SHIM_SRC "")
if(WIN32 AND NOT AI_NN_SDL STREQUAL "shim")
  set(SDL2_FOUND TRUE)
  set(SDL2_INCLUDE_DIRS ${DEV_ROOT}/third_party/SDL2-2.30.9/include)
  set(SDL2_LIBRARIES ${DEV_ROOT}/third_party/SDL2-2.30.9/lib/x64/SDL2.lib)
elseif(NOT AI_NN_SDL STREQUAL "shim")
  find_package(SDL2 QUIET)
endif()
if(SDL2_FOUND AND NOT AI_NN_SDL STREQUAL "shim")
  message(STATUS "ai-nn: using system SDL2")
  set(SDL_INC ${SDL2_INCLUDE_DIRS})
  set(SDL_LINK ${SDL2_LIBRARIES})
elseif(AI_NN_SDL STREQUAL "system")
  message(FATAL_ERROR "AI_NN_SDL=system but SDL2 was not found")
else()
  message(STATUS "ai-nn: using build/ai-nn/sdl_shim (no system SDL2)")
  set(SDL_INC ${CMAKE_CURRENT_SOURCE_DIR}/sdl_shim)
  set(SDL_SHIM_SRC ${CMAKE_CURRENT_SOURCE_DIR}/sdl_shim/sdl_shim.cpp)
  add_compile_definitions(PVZ_AI_NN_SDL_SHIM)
endif()
if(WIN32)
  set(GZIP_DEFAULT OFF)
else()
  set(GZIP_DEFAULT ON)
endif()
option(AI_NN_GZIP "Read gzip corpus directly (requires full zlib)" ${GZIP_DEFAULT})
if(AI_NN_GZIP)
  find_package(ZLIB REQUIRED)
else()
  add_compile_definitions(PVZ_AI_NN_PLAIN_FILES)
endif()
find_package(Python3 COMPONENTS Interpreter REQUIRED)
add_custom_target(ai_nn_composition_gate ALL
  COMMAND ${Python3_EXECUTABLE} -B ${DEV_ROOT}/tools/typed72/make_app_composition.py --check)

file(GLOB KERNEL_SRC CONFIGURE_DEPENDS ${STAGE}/src/sim/typed/*.cpp)
file(GLOB_RECURSE AI_RULE_INPUTS CONFIGURE_DEPENDS
  ${STAGE}/src/sim/typed/*.cpp ${STAGE}/src/sim/typed/*.h
  ${COMPOSITION}/*.cpp ${COMPOSITION}/*.h ${COMPOSITION}/*.inc
  ${APP}/ai/*.cpp ${APP}/ai/*.h)
list(APPEND AI_RULE_INPUTS ${APP}/session.cpp ${APP}/session.h
  ${APP}/ai_planner_r22.cpp ${APP}/ai_planner_r22.h)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${AI_RULE_INPUTS})
list(SORT AI_RULE_INPUTS)
set(AI_RULE_DIGESTS "")
foreach(input ${AI_RULE_INPUTS})
  file(SHA256 ${input} input_sha)
  file(RELATIVE_PATH input_name ${DEV_ROOT} ${input})
  string(APPEND AI_RULE_DIGESTS "${input_name}:${input_sha}\n")
endforeach()
string(SHA256 AI_NN_SIM_FINGERPRINT "${AI_RULE_DIGESTS}")
file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/ai_nn_build.h
  "#pragma once\n#define AI_NN_SIM_FINGERPRINT \"${AI_NN_SIM_FINGERPRINT}\"\n")
add_library(pvztyped72kernel STATIC ${KERNEL_SRC} ${SDL_SHIM_SRC})
add_dependencies(pvztyped72kernel ai_nn_composition_gate)
target_include_directories(pvztyped72kernel BEFORE PUBLIC ${STAGE}/src)
target_include_directories(pvztyped72kernel PUBLIC ${DEV_ROOT}/src ${DEV_ROOT}/third_party ${DEV_ROOT}/tools/typed72 ${SDL_INC})
target_include_directories(pvztyped72kernel PRIVATE ${STAGE}/src/sim/typed)
target_compile_options(pvztyped72kernel PRIVATE ${AI_NN_FLAGS})
target_link_libraries(pvztyped72kernel PUBLIC ${SDL_LINK})

# The existing file-driven verifier (root CMake target of the same name), unchanged source.
add_executable(typed72_match_gate ${COMPOSITION}/match_probe.cpp)
target_include_directories(typed72_match_gate BEFORE PRIVATE ${STAGE}/src ${COMPOSITION} ${COMPOSITION}/probes)
target_compile_definitions(typed72_match_gate PRIVATE SDL_MAIN_HANDLED)
target_compile_options(typed72_match_gate PRIVATE ${AI_NN_FLAGS})
target_link_libraries(typed72_match_gate PRIVATE pvztyped72kernel)

# Session + r22 AI without the V-side files (cold_export.cpp, typed_battle.cpp) and without pvzcore.
add_library(pvztyped72headless STATIC
  ${APP}/session.cpp ${APP}/ai_planner_r22.cpp ${APP}/cold_file.cpp
  ${APP}/ai/controller.cpp ${APP}/ai/layers7.cpp ${APP}/ai/layers11.cpp ${APP}/ai/layers19.cpp)
target_include_directories(pvztyped72headless BEFORE PRIVATE ${STAGE}/src ${COMPOSITION} ${COMPOSITION}/probes)
target_compile_options(pvztyped72headless PRIVATE ${AI_NN_FLAGS})
target_link_libraries(pvztyped72headless PUBLIC pvztyped72kernel)
target_include_directories(pvztyped72headless PUBLIC ${CMAKE_CURRENT_BINARY_DIR})
if(AI_NN_GZIP)
  target_link_libraries(pvztyped72headless PUBLIC ZLIB::ZLIB)
endif()

foreach(tool headless_match headless_neural session_trace card_features replay_planner neural_dataset neural_contract fixture_retention_test)
  set(tool_source src/${tool}.cpp)
  if(tool STREQUAL "headless_neural")
    set(tool_source src/headless_match.cpp)
  endif()
  if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/${tool_source})
    add_executable(${tool} ${tool_source})
    if(WIN32)
      target_sources(${tool} PRIVATE research_utf8.manifest)
    endif()
    target_include_directories(${tool} BEFORE PRIVATE ${STAGE}/src ${COMPOSITION} ${COMPOSITION}/probes)
    target_compile_options(${tool} PRIVATE ${AI_NN_FLAGS})
    target_link_libraries(${tool} PRIVATE pvztyped72headless)
    if(WIN32 AND NOT AI_NN_SDL STREQUAL "shim")
      add_custom_command(TARGET ${tool} POST_BUILD COMMAND ${CMAKE_COMMAND} -E copy_if_different
        ${DEV_ROOT}/third_party/SDL2-2.30.9/lib/x64/SDL2.dll $<TARGET_FILE_DIR:${tool}>)
    endif()
  endif()
endforeach()

# Explicit opt-in A/B harness. The kernel/controller objects are identical; only
# Session's composition include changes to a preserved, reviewed pre-fix tree.
set(AI_NN_BASELINE_COMPOSITION "" CACHE PATH "Preserved composition for memory A/B only")
if(AI_NN_BASELINE_COMPOSITION)
  add_executable(headless_match_before src/headless_match.cpp ${APP}/session.cpp)
  target_include_directories(headless_match_before BEFORE PRIVATE
    ${STAGE}/src ${AI_NN_BASELINE_COMPOSITION} ${AI_NN_BASELINE_COMPOSITION}/probes)
  target_compile_options(headless_match_before PRIVATE ${AI_NN_FLAGS})
  target_link_libraries(headless_match_before PRIVATE pvztyped72headless)
endif()
