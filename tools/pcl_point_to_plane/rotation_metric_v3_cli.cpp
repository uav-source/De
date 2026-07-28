#include "rotation_metric_v3.hpp"

#include <nlohmann/json.hpp>

#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using json = nlohmann::json;

Eigen::Matrix3d parse_matrix(const json& value, const std::string& name) {
  if (!value.is_array() || value.size() != 9) {
    throw std::runtime_error(name + " must contain nine row-major values");
  }
  Eigen::Matrix3d result;
  for (int row = 0; row < 3; ++row) {
    for (int column = 0; column < 3; ++column) {
      result(row, column) = value.at(static_cast<std::size_t>(row * 3 + column))
                                .get<double>();
    }
  }
  return result;
}

std::vector<double> flatten(const Eigen::Matrix3d& matrix) {
  std::vector<double> result;
  result.reserve(9);
  for (int row = 0; row < 3; ++row) {
    for (int column = 0; column < 3; ++column) {
      result.push_back(matrix(row, column));
    }
  }
  return result;
}

json finite_or_null(double value) {
  return std::isfinite(value) ? json(value) : json(nullptr);
}

json serialize(const pcl_backend_v3::RotationMetricAudit& audit) {
  return {
      {"raw_rotation_finite", audit.raw_rotation_finite},
      {"raw_rotation_determinant_positive",
       audit.raw_rotation_determinant_positive},
      {"raw_rotation_3x3",
       audit.raw_rotation_finite ? json(flatten(audit.raw_rotation))
                                 : json(nullptr)},
      {"R_est_transpose_R_est",
       audit.raw_rotation_finite ? json(flatten(audit.raw_transpose_raw))
                                 : json(nullptr)},
      {"orthogonality_defect_fro",
       finite_or_null(audit.orthogonality_defect_fro)},
      {"determinant", finite_or_null(audit.determinant)},
      {"raw_trace_acos_argument",
       finite_or_null(audit.raw_trace_acos_argument)},
      {"raw_trace_acos_rotation_error_rad",
       finite_or_null(audit.raw_trace_acos_rotation_error_rad)},
      {"nearest_so3_projection",
       audit.nearest_so3_projection.allFinite()
           ? json(flatten(audit.nearest_so3_projection))
           : json(nullptr)},
      {"projected_determinant", finite_or_null(audit.projected_determinant)},
      {"projection_correction_fro",
       finite_or_null(audit.projection_correction_fro)},
      {"singular_values",
       audit.singular_values.allFinite()
           ? json(std::vector<double>{audit.singular_values(0),
                                      audit.singular_values(1),
                                      audit.singular_values(2)})
           : json(nullptr)},
      {"truth_rotation_finite", audit.truth_rotation_finite},
      {"truth_rotation_determinant",
       finite_or_null(audit.truth_rotation_determinant)},
      {"truth_rotation_orthogonality_defect_fro",
       finite_or_null(audit.truth_rotation_orthogonality_defect_fro)},
      {"truth_rotation_valid", audit.truth_rotation_valid},
      {"maximum_elementwise_error_to_truth",
       finite_or_null(audit.maximum_elementwise_error_to_truth)},
      {"cos_theta", finite_or_null(audit.cos_theta)},
      {"sin_theta", finite_or_null(audit.sin_theta)},
      {"rotation_error_rad", finite_or_null(audit.rotation_error_rad)},
      {"rotation_matrix_quality_pass",
       audit.rotation_matrix_quality_pass},
      {"float_serialization_max_digits10",
       std::numeric_limits<float>::max_digits10},
      {"double_serialization_max_digits10",
       std::numeric_limits<double>::max_digits10},
      {"projection_reflection_handling",
       "D=diag(1,1,sign(det(U*V^T)))"},
  };
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc != 3 || std::string(argv[1]) != "--input") {
      throw std::runtime_error("usage: rotation_metric_v3_cli --input INPUT.json");
    }
    std::ifstream stream(std::filesystem::absolute(argv[2]));
    if (!stream.good()) {
      throw std::runtime_error("cannot open rotation metric input");
    }
    json input;
    stream >> input;
    const Eigen::Matrix3d raw = parse_matrix(input.at("raw_rotation_3x3"), "raw");
    const Eigen::Matrix3d truth =
        parse_matrix(input.at("truth_rotation_3x3"), "truth");
    const auto audit = pcl_backend_v3::evaluate_rotation_metric(raw, truth);
    std::cout << serialize(audit).dump() << std::endl;
    return 0;
  } catch (const std::exception& error) {
    std::cout << json({{"failure_reason", "EXCEPTION"},
                       {"exception_message", error.what()}})
                     .dump()
              << std::endl;
    return 2;
  }
}
