# libmain.so for the Android APK (SDLActivity calls SDL_main = src/app/main.cpp).
# Built by android/build_android.sh with the NDK toolchain; SDL2 / SDL2_image / SDL2_mixer / SDL2_ttf are
# the prebuilt shared libraries (and headers) of the python APK's SDL bootstrap (SDL 2.28.5).
cmake_minimum_required(VERSION 3.20)
project(PvZPvPNativeAndroid C CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

set(SRC_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/..)
set(SNAPSHOT_ZLIB_ROOT ${SRC_ROOT}/third_party/zlib-1.3.2-compress)
add_library(pvzsnapshot_zlib STATIC
  ${SNAPSHOT_ZLIB_ROOT}/adler32.c ${SNAPSHOT_ZLIB_ROOT}/compress.c
  ${SNAPSHOT_ZLIB_ROOT}/crc32.c ${SNAPSHOT_ZLIB_ROOT}/deflate.c
  ${SNAPSHOT_ZLIB_ROOT}/trees.c ${SNAPSHOT_ZLIB_ROOT}/zutil.c)
set_target_properties(pvzsnapshot_zlib PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_compile_definitions(pvzsnapshot_zlib PRIVATE Z_PREFIX)
set(SDL_JNI "" CACHE PATH "p4a dist jni folder (SDL, SDL2_image, SDL2_mixer, SDL2_ttf sources/headers)")
set(SDL_LIBDIR "" CACHE PATH "folder with the prebuilt libSDL2*.so for this ABI")

file(GLOB_RECURSE SRC CONFIGURE_DEPENDS
  ${SRC_ROOT}/src/core/*.cpp ${SRC_ROOT}/src/data/*.cpp ${SRC_ROOT}/src/sim/*.cpp
  ${SRC_ROOT}/src/ai/*.cpp ${SRC_ROOT}/src/net/*.cpp
  ${SRC_ROOT}/src/pg/*.cpp ${SRC_ROOT}/src/ui/*.cpp ${SRC_ROOT}/src/app/*.cpp)
list(FILTER SRC EXCLUDE REGEX "/shim_headless/")
# Isolated typed migration stages are not linked through the recursive glob.
list(FILTER SRC EXCLUDE REGEX "/typed/")
list(FILTER SRC EXCLUDE REGEX "/typed72_app/")
# Typed PvP72 battle (the shipped dynamic path): integrated typed kernel stage + app bridge.
set(TYPED72_STAGE ${SRC_ROOT}/build/typed72-integrated-v44/source CACHE PATH "integrated typed72 kernel stage")
set(TYPED72_COMPOSITION ${SRC_ROOT}/src/sim/typed72_app/composition CACHE PATH "generated typed72 app composition")
set(TYPED72_FLAGS -O2 -ffp-contract=off -fno-fast-math -Wno-everything -fexceptions -frtti)
file(GLOB TYPED72_KERNEL_SRC CONFIGURE_DEPENDS ${TYPED72_STAGE}/src/sim/typed/*.cpp)
add_library(pvztyped72kernel STATIC ${TYPED72_KERNEL_SRC})
set_target_properties(pvztyped72kernel PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_include_directories(pvztyped72kernel BEFORE PRIVATE ${TYPED72_STAGE}/src ${TYPED72_STAGE}/src/sim/typed)
target_include_directories(pvztyped72kernel PRIVATE ${SRC_ROOT}/src ${SRC_ROOT}/third_party ${SRC_ROOT}/tools/typed72 ${SDL_JNI}/SDL/include)
target_compile_options(pvztyped72kernel PRIVATE ${TYPED72_FLAGS})
add_library(pvztyped72app STATIC ${SRC_ROOT}/src/sim/typed72_app/cold_export.cpp ${SRC_ROOT}/src/sim/typed72_app/session.cpp ${SRC_ROOT}/src/sim/typed72_app/typed_battle.cpp
  ${SRC_ROOT}/src/sim/typed72_app/ai_planner_r22.cpp ${SRC_ROOT}/src/sim/typed72_app/ai/controller.cpp
  ${SRC_ROOT}/src/sim/typed72_app/ai/layers7.cpp ${SRC_ROOT}/src/sim/typed72_app/ai/layers11.cpp ${SRC_ROOT}/src/sim/typed72_app/ai/layers19.cpp)
set_target_properties(pvztyped72app PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_include_directories(pvztyped72app BEFORE PRIVATE ${TYPED72_STAGE}/src ${TYPED72_COMPOSITION} ${TYPED72_COMPOSITION}/probes)
target_include_directories(pvztyped72app PRIVATE ${SRC_ROOT}/src ${SRC_ROOT}/third_party ${SRC_ROOT}/tools/typed72 ${SDL_JNI}/SDL/include)
target_compile_options(pvztyped72app PRIVATE ${TYPED72_FLAGS})

add_library(main SHARED ${SRC})
target_include_directories(main PRIVATE ${SRC_ROOT}/src ${SRC_ROOT}/third_party
  ${SDL_JNI}/SDL/include ${SDL_JNI}/SDL2_image/include ${SDL_JNI}/SDL2_mixer/include ${SDL_JNI}/SDL2_ttf)
# float results must equal the desktop build / CPython: no fused multiply-add contraction
target_compile_options(main PRIVATE -O2 -ffp-contract=off -fno-fast-math -Wno-everything -fexceptions -frtti)
foreach(lib SDL2 SDL2_image SDL2_mixer SDL2_ttf)
  add_library(${lib} SHARED IMPORTED)
  set_target_properties(${lib} PROPERTIES IMPORTED_LOCATION ${SDL_LIBDIR}/lib${lib}.so)
endforeach()
target_link_libraries(main PRIVATE pvztyped72app pvztyped72kernel pvzsnapshot_zlib SDL2 SDL2_image SDL2_mixer SDL2_ttf log android)
target_link_options(main PRIVATE -Wl,--gc-sections -static-libstdc++)
