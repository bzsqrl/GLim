cmake_minimum_required(VERSION 3.16)

# Universal binary for both Apple Silicon and Intel Macs. Set before project()
# so the FFGL SDK static library is built for both architectures too.
set(CMAKE_OSX_ARCHITECTURES "arm64;x86_64" CACHE STRING "")
set(CMAKE_OSX_DEPLOYMENT_TARGET "10.15" CACHE STRING "")

project(FFStudioPlugin CXX)

# Filled in by ffstudio/build_ffgl.py
set(FFGL_SDK_DIR "@FFGL_SDK_DIR@")

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

add_subdirectory("${FFGL_SDK_DIR}" ffgl-sdk)

if(APPLE)
    add_library(FFStudioPlugin MODULE Plugin.cpp FFStudioPlugin.h ShaderData.h)
    set_target_properties(FFStudioPlugin PROPERTIES
        BUNDLE TRUE
        BUNDLE_EXTENSION "bundle")
    target_link_libraries(FFStudioPlugin PRIVATE ffgl::sdk "-framework OpenGL" "-framework Cocoa")
else()
    add_library(FFStudioPlugin SHARED Plugin.cpp FFStudioPlugin.h ShaderData.h Plugin.def)
    set(GLEW_USE_STATIC_LIBS ON)
    add_definitions(-DGLEW_STATIC)
    find_package(GLEW REQUIRED)
    target_link_libraries(FFStudioPlugin PRIVATE ffgl::sdk GLEW::GLEW opengl32)
    set_target_properties(FFStudioPlugin PROPERTIES PREFIX "" SUFFIX ".dll")
endif()
