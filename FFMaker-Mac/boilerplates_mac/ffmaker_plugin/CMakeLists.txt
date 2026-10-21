cmake_minimum_required(VERSION 3.16)
project(/* FFM_PLUGIN_NAME */)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Include the FFGL SDK
add_subdirectory(../ffgl ffgl-sdk)

add_library(/* FFM_PLUGIN_NAME */ MODULE Plugin.cpp Plugin.h)

# macOS specific configuration for Bundles
set_target_properties(/* FFM_PLUGIN_NAME */ PROPERTIES
    BUNDLE True
    BUNDLE_EXTENSION "bundle"
    MACOSX_BUNDLE_GUI_IDENTIFIER "com.ffmaker./* FFM_PLUGIN_NAME */"
    MACOSX_BUNDLE_BUNDLE_NAME "/* FFM_PLUGIN_NAME */"
)

# Link against the FFGL SDK and GLEW
find_package(GLEW REQUIRED)

if(APPLE)
    target_link_libraries(/* FFM_PLUGIN_NAME */ PRIVATE 
        ffgl::sdk 
        GLEW::GLEW 
        "-framework OpenGL" 
        "-framework AppKit"
    )
else()
    target_link_libraries(/* FFM_PLUGIN_NAME */ PRIVATE ffgl::sdk GLEW::GLEW opengl32)
endif()
