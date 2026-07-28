#pragma once

#include <Eigen/Core>
#include <Eigen/LU>
#include <Eigen/SVD>

#include <algorithm>
#include <cmath>
#include <limits>

namespace pcl_backend_v3 {

constexpr double kOrthogonalityDefectMaximum = 1.0e-5;
constexpr double kDeterminantErrorMaximum = 1.0e-5;
constexpr double kProjectionCorrectionMaximum = 1.0e-5;
constexpr double kTruthOrthogonalityTolerance = 1.0e-10;
constexpr double kTruthDeterminantTolerance = 1.0e-10;

struct RotationMetricAudit {
  bool raw_rotation_finite = false;
  bool raw_rotation_determinant_positive = false;
  Eigen::Matrix3d raw_rotation = Eigen::Matrix3d::Constant(
      std::numeric_limits<double>::quiet_NaN());
  Eigen::Matrix3d raw_transpose_raw = Eigen::Matrix3d::Constant(
      std::numeric_limits<double>::quiet_NaN());
  double orthogonality_defect_fro = std::numeric_limits<double>::quiet_NaN();
  double determinant = std::numeric_limits<double>::quiet_NaN();
  double raw_trace_acos_argument = std::numeric_limits<double>::quiet_NaN();
  double raw_trace_acos_rotation_error_rad =
      std::numeric_limits<double>::quiet_NaN();
  Eigen::Matrix3d nearest_so3_projection = Eigen::Matrix3d::Constant(
      std::numeric_limits<double>::quiet_NaN());
  double projected_determinant = std::numeric_limits<double>::quiet_NaN();
  double projection_correction_fro = std::numeric_limits<double>::quiet_NaN();
  Eigen::Vector3d singular_values = Eigen::Vector3d::Constant(
      std::numeric_limits<double>::quiet_NaN());
  bool truth_rotation_finite = false;
  double truth_rotation_determinant = std::numeric_limits<double>::quiet_NaN();
  double truth_rotation_orthogonality_defect_fro =
      std::numeric_limits<double>::quiet_NaN();
  bool truth_rotation_valid = false;
  double maximum_elementwise_error_to_truth =
      std::numeric_limits<double>::quiet_NaN();
  double cos_theta = std::numeric_limits<double>::quiet_NaN();
  double sin_theta = std::numeric_limits<double>::quiet_NaN();
  double rotation_error_rad = std::numeric_limits<double>::quiet_NaN();
  bool rotation_matrix_quality_pass = false;
};

inline RotationMetricAudit evaluate_rotation_metric(
    const Eigen::Matrix3d& raw, const Eigen::Matrix3d& truth) {
  RotationMetricAudit output;
  output.raw_rotation = raw;
  output.raw_rotation_finite = raw.allFinite();
  output.truth_rotation_finite = truth.allFinite();
  if (!output.raw_rotation_finite || !output.truth_rotation_finite) {
    return output;
  }

  output.raw_transpose_raw = raw.transpose() * raw;
  output.orthogonality_defect_fro =
      (output.raw_transpose_raw - Eigen::Matrix3d::Identity()).norm();
  output.determinant = raw.determinant();
  output.raw_rotation_determinant_positive = output.determinant > 0.0;

  Eigen::JacobiSVD<Eigen::Matrix3d> decomposition(
      raw, Eigen::ComputeFullU | Eigen::ComputeFullV);
  const Eigen::Matrix3d left = decomposition.matrixU();
  const Eigen::Matrix3d right_transpose = decomposition.matrixV().transpose();
  Eigen::Matrix3d reflection_correction = Eigen::Matrix3d::Identity();
  reflection_correction(2, 2) =
      (left * right_transpose).determinant() >= 0.0 ? 1.0 : -1.0;
  output.nearest_so3_projection = left * reflection_correction * right_transpose;
  output.projected_determinant = output.nearest_so3_projection.determinant();
  output.projection_correction_fro =
      (output.nearest_so3_projection - raw).norm();
  output.singular_values = decomposition.singularValues();

  output.truth_rotation_determinant = truth.determinant();
  output.truth_rotation_orthogonality_defect_fro =
      (truth.transpose() * truth - Eigen::Matrix3d::Identity()).norm();
  output.truth_rotation_valid =
      output.truth_rotation_finite && output.truth_rotation_determinant > 0.0 &&
      output.truth_rotation_orthogonality_defect_fro <=
          kTruthOrthogonalityTolerance &&
      std::abs(output.truth_rotation_determinant - 1.0) <=
          kTruthDeterminantTolerance;
  output.maximum_elementwise_error_to_truth =
      (raw - truth).cwiseAbs().maxCoeff();

  const Eigen::Matrix3d raw_error = truth.transpose() * raw;
  output.raw_trace_acos_argument = (raw_error.trace() - 1.0) * 0.5;
  output.raw_trace_acos_rotation_error_rad = std::acos(
      std::clamp(output.raw_trace_acos_argument, -1.0, 1.0));

  const Eigen::Matrix3d error = truth.transpose() * output.nearest_so3_projection;
  output.cos_theta = std::clamp((error.trace() - 1.0) * 0.5, -1.0, 1.0);
  const Eigen::Vector3d skew_vector(
      error(2, 1) - error(1, 2), error(0, 2) - error(2, 0),
      error(1, 0) - error(0, 1));
  output.sin_theta = 0.5 * skew_vector.norm();
  output.rotation_error_rad = std::atan2(output.sin_theta, output.cos_theta);
  output.rotation_matrix_quality_pass =
      output.raw_rotation_finite && output.raw_rotation_determinant_positive &&
      output.orthogonality_defect_fro <= kOrthogonalityDefectMaximum &&
      std::abs(output.determinant - 1.0) <= kDeterminantErrorMaximum &&
      output.projection_correction_fro <= kProjectionCorrectionMaximum &&
      output.projected_determinant > 0.0 && output.truth_rotation_valid;
  return output;
}

}  // namespace pcl_backend_v3
