# PCL Dependency and Build Audit

The isolated dependency is ready, but the PCL backend build qualification is
not. System PCL was absent. The first isolated solve installed PCL 1.11.1,
whose conda package omitted the required pkg-config metadata. Before any PCL
implementation or qualification result existed, the same isolated environment
was upgraded to PCL 1.15.1. The required command
`pkg-config --modversion pcl_registration` then returned `1.15.1`.

The CLI configured and compiled with CMake 4.4.0 and GNU C++ 9.4.0. Its
SHA-256 is
`829eacdfc0cc8b3eb1a291c22e5e1af9d4ff4f0c696babec2bf3fcdf97f44aa1`.
The frozen identical-cloud identity CTest then returned
`has_converged=false` and `finite_output=false`; consequently the composite
`PCL_BACKEND_BUILD_PASS` gate is false. No parameter, fixture, threshold, or
backend substitution was attempted after this result.

Exact environment and build evidence is retained under
`reports/zero_perturbation_pcl_environment/`.

