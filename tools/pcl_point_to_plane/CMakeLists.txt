cmake_minimum_required(VERSION 3.16)
project(zero_perturbation_pcl_point_to_plane LANGUAGES C CXX)

find_package(PCL 1.15 REQUIRED COMPONENTS common io features search kdtree registration)
find_package(nlohmann_json 3.2.0 REQUIRED)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

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
  set(PCL_V2_DATA_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../tests/data/pcl_backend_v2)
  set(PCL_V2_RESULT_DIR ${CMAKE_CURRENT_BINARY_DIR}/pcl_backend_v2_results)
  set(PCL_V2_VERIFIER ${CMAKE_CURRENT_SOURCE_DIR}/verify_pcl_backend_v2.py)
  file(MAKE_DIRECTORY ${PCL_V2_RESULT_DIR})

  add_test(
    NAME pcl_v2_nondegenerate_identity
    COMMAND ${Python3_EXECUTABLE} ${PCL_V2_VERIFIER}
      --cli $<TARGET_FILE:pcl_point_to_plane_cli>
      --config
      ${PCL_V2_DATA_DIR}/nondegenerate_identity_config.json
      --test NONDEGENERATE_IDENTITY
      --output ${PCL_V2_RESULT_DIR}/nondegenerate_identity.json
  )

  add_test(
    NAME pcl_v2_known_small_transform
    COMMAND ${Python3_EXECUTABLE} ${PCL_V2_VERIFIER}
      --cli $<TARGET_FILE:pcl_point_to_plane_cli>
      --config ${PCL_V2_DATA_DIR}/known_small_transform_config.json
      --test KNOWN_SMALL_TRANSFORM
      --truth ${PCL_V2_DATA_DIR}/known_small_transform_truth.json
      --output ${PCL_V2_RESULT_DIR}/known_small_transform.json
  )

  add_test(
    NAME pcl_v2_planar_degeneracy_diagnostic
    COMMAND ${Python3_EXECUTABLE} ${PCL_V2_VERIFIER}
      --cli $<TARGET_FILE:pcl_point_to_plane_cli>
      --config ${PCL_V2_DATA_DIR}/planar_degeneracy_config.json
      --test PLANAR_DEGENERACY_DIAGNOSTIC
      --output ${PCL_V2_RESULT_DIR}/planar_degeneracy_diagnostic.json
  )

  set_tests_properties(
    pcl_v2_nondegenerate_identity
    pcl_v2_known_small_transform
    pcl_v2_planar_degeneracy_diagnostic
    PROPERTIES LABELS pcl_backend_qualification_v2
  )
endif()
