cmake_minimum_required(VERSION 3.16)
project(zero_perturbation_pcl_point_to_plane LANGUAGES C CXX)

find_package(PCL 1.15 REQUIRED COMPONENTS common io features search kdtree registration)
find_package(nlohmann_json 3.2.0 REQUIRED)

add_executable(pcl_point_to_plane_cli pcl_point_to_plane_cli.cpp)
target_compile_features(pcl_point_to_plane_cli PRIVATE cxx_std_17)
target_include_directories(pcl_point_to_plane_cli PRIVATE ${PCL_INCLUDE_DIRS})
target_compile_definitions(pcl_point_to_plane_cli PRIVATE ${PCL_DEFINITIONS})
target_link_directories(pcl_point_to_plane_cli PRIVATE ${PCL_LIBRARY_DIRS})
target_link_libraries(
  pcl_point_to_plane_cli
  PRIVATE
    ${PCL_LIBRARIES}
    nlohmann_json::nlohmann_json
)

include(CTest)
if(BUILD_TESTING)
  add_test(
    NAME pcl_identical_cloud_identity
    COMMAND pcl_point_to_plane_cli
      --config
      ${CMAKE_CURRENT_SOURCE_DIR}/../../tests/data/pcl_backend/identity_config.json
  )
  set_tests_properties(
    pcl_identical_cloud_identity
    PROPERTIES
      PASS_REGULAR_EXPRESSION
        "\"has_converged\":true.*\"translation_update_norm_m\":0"
  )
endif()

