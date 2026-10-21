cmake_minimum_required(VERSION 3.16)
project(/* FFM_PLUGIN_NAME */)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Include the FFGL SDK
add_subdirectory(../ffgl ffgl-sdk)

add_library(/* FFM_PLUGIN_NAME */ SHARED Plugin.cpp Plugin.h Plugin.def)

# Link against the FFGL SDK and GLEW
set(GLEW_USE_STATIC_LIBS ON)
add_definitions(-DGLEW_STATIC)
find_package(GLEW REQUIRED)
target_link_libraries(/* FFM_PLUGIN_NAME */ PRIVATE ffgl::sdk GLEW::GLEW opengl32)

# Output directory config
set_target_properties(/* FFM_PLUGIN_NAME */ PROPERTIES
    PREFIX ""
    SUFFIX ".dll"
)
