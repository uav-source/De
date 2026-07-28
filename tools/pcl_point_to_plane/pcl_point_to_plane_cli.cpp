#include <pcl/common/io.h>
#include <pcl/features/normal_3d_omp.h>
#include <pcl/io/pcd_io.h>
#include <pcl/pcl_config.h>
#include <pcl/point_cloud.h>
#include <pcl/point_types.h>
#include <pcl/registration/icp.h>
#include <pcl/registration/transformation_estimation_point_to_plane_lls.h>
#include <pcl/search/kdtree.h>

#include <Eigen/Core>
#include <Eigen/Eigenvalues>
#include <Eigen/Geometry>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

using json = nlohmann::json;
using PointXYZ = pcl::PointXYZ;
using PointNormal = pcl::PointNormal;
using CloudXYZ = pcl::PointCloud<PointXYZ>;
using CloudNormal = pcl::PointCloud<PointNormal>;

class AuditedICP
    : public pcl::IterativeClosestPointWithNormals<PointNormal, PointNormal> {
 public:
  int final_iteration_count() const { return this->nr_iterations_; }

  std::size_t final_correspondence_count() const {
    return this->correspondences_ ? this->correspondences_->size() : 0;
  }
};

struct NormalStatistics {
  std::size_t finite_count = 0;
  std::size_t zero_count = 0;
  std::size_t nan_count = 0;
  double norm_min = std::numeric_limits<double>::quiet_NaN();
  double norm_median = std::numeric_limits<double>::quiet_NaN();
  double norm_max = std::numeric_limits<double>::quiet_NaN();
  int direction_rank = 0;
};

struct EstimatedCloud {
  CloudNormal::Ptr cloud;
  NormalStatistics statistics;
};

struct RankDiagnostics {
  int point_cloud_rank = 0;
  std::vector<double> point_cloud_covariance_eigenvalues;
  int point_to_plane_jacobian_rank = 0;
  std::vector<double> point_to_plane_hessian_eigenvalues;
  double point_cloud_rank_tolerance = 0.0;
  double point_to_plane_rank_tolerance = 0.0;
  std::size_t diagnostic_correspondence_count = 0;
  bool rank_deficient = true;
  std::string condition_status = "NO_CORRESPONDENCES";
};

constexpr int kNormalNeighbors = 50;
constexpr double kMaximumCorrespondenceDistanceM = 0.50;
constexpr int kMaximumIterations = 50;
constexpr double kTransformationEpsilon = 1.0e-10;
constexpr double kEuclideanFitnessEpsilon = 1.0e-10;

void require(bool condition, const std::string& message) {
  if (!condition) {
    throw std::runtime_error(message);
  }
}

bool contains_forbidden_key(const json& value) {
  static const std::vector<std::string> forbidden = {
      "scene_variant", "theoretical_weak_direction", "ground_truth", "gt_pose",
      "offline_error", "open3d_result", "native_result"};
  if (value.is_object()) {
    for (auto iterator = value.begin(); iterator != value.end(); ++iterator) {
      if (std::find(forbidden.begin(), forbidden.end(), iterator.key()) != forbidden.end()) {
        return true;
      }
      if (contains_forbidden_key(iterator.value())) {
        return true;
      }
    }
  } else if (value.is_array()) {
    for (const auto& child : value) {
      if (contains_forbidden_key(child)) {
        return true;
      }
    }
  }
  return false;
}

void validate_parameters(const json& config) {
  require(!contains_forbidden_key(config), "forbidden scene, GT, or backend-result input");
  const auto& normal = config.at("parameters").at("normal_estimation");
  const auto& icp = config.at("parameters").at("icp");
  require(normal.at("method").get<std::string>() == "KSearch", "normal method changed");
  require(normal.at("k").get<int>() == kNormalNeighbors, "normal k changed");
  require(
      icp.at("maximum_correspondence_distance_m").get<double>() ==
          kMaximumCorrespondenceDistanceM,
      "maximum correspondence distance changed");
  require(icp.at("maximum_iterations").get<int>() == kMaximumIterations,
          "maximum iterations changed");
  require(icp.at("transformation_epsilon").get<double>() == kTransformationEpsilon,
          "transformation epsilon changed");
  require(icp.at("euclidean_fitness_epsilon").get<double>() ==
              kEuclideanFitnessEpsilon,
          "fitness epsilon changed");
  require(!icp.at("use_reciprocal_correspondences").get<bool>(),
          "reciprocal correspondences changed");
  require(!icp.at("use_symmetric_objective").get<bool>(),
          "symmetric objective changed");
  require(icp.at("enforce_same_direction_normals").get<bool>(),
          "normal direction contract changed");
}

Eigen::Matrix4f parse_transform(const json& value) {
  require(value.is_array() && value.size() == 16, "initial transform must have 16 values");
  Eigen::Matrix4f transform;
  for (int row = 0; row < 4; ++row) {
    for (int column = 0; column < 4; ++column) {
      const double item = value.at(static_cast<std::size_t>(row * 4 + column)).get<double>();
      require(std::isfinite(item), "initial transform contains a non-finite value");
      transform(row, column) = static_cast<float>(item);
    }
  }
  require(transform.allFinite(), "initial transform is not finite after conversion");
  return transform;
}

std::filesystem::path resolve_input_path(
    const std::filesystem::path& config_path, const std::string& value) {
  std::filesystem::path path(value);
  if (path.is_relative()) {
    path = config_path.parent_path() / path;
  }
  return std::filesystem::weakly_canonical(path);
}

CloudXYZ::Ptr load_xyz(const std::filesystem::path& path) {
  auto cloud = std::make_shared<CloudXYZ>();
  require(pcl::io::loadPCDFile<PointXYZ>(path.string(), *cloud) == 0,
          "failed to load PCD: " + path.string());
  require(!cloud->empty(), "point cloud is empty");
  require(cloud->is_dense, "point cloud contains non-finite coordinates");
  for (const auto& point : *cloud) {
    require(std::isfinite(point.x) && std::isfinite(point.y) && std::isfinite(point.z),
            "point cloud contains non-finite coordinates");
  }
  return cloud;
}

std::pair<int, double> eigen_rank(
    const Eigen::VectorXd& eigenvalues, std::size_t observation_count) {
  const double maximum = eigenvalues.size() == 0
                             ? 0.0
                             : std::max(0.0, eigenvalues.maxCoeff());
  const double tolerance =
      static_cast<double>(std::max<std::size_t>(observation_count, eigenvalues.size())) *
      std::numeric_limits<double>::epsilon() * std::max(1.0, maximum);
  int rank = 0;
  for (Eigen::Index index = 0; index < eigenvalues.size(); ++index) {
    if (eigenvalues(index) > tolerance) {
      ++rank;
    }
  }
  return {rank, tolerance};
}

std::vector<double> eigenvalues_vector(const Eigen::VectorXd& values) {
  std::vector<double> result;
  result.reserve(static_cast<std::size_t>(values.size()));
  for (Eigen::Index index = 0; index < values.size(); ++index) {
    result.push_back(values(index));
  }
  return result;
}

EstimatedCloud estimate_normals(const CloudXYZ::Ptr& xyz) {
  auto normals = std::make_shared<pcl::PointCloud<pcl::Normal>>();
  auto tree = std::make_shared<pcl::search::KdTree<PointXYZ>>();
  pcl::NormalEstimationOMP<PointXYZ, pcl::Normal> estimator;
  estimator.setNumberOfThreads(1);
  estimator.setInputCloud(xyz);
  estimator.setSearchMethod(tree);
  estimator.setKSearch(kNormalNeighbors);
  estimator.compute(*normals);
  require(normals->size() == xyz->size(), "normal count does not match point count");

  auto result = std::make_shared<CloudNormal>();
  pcl::concatenateFields(*xyz, *normals, *result);
  NormalStatistics statistics;
  std::vector<double> norms;
  Eigen::Matrix3d normal_gram = Eigen::Matrix3d::Zero();
  for (const auto& point : *result) {
    if (!std::isfinite(point.normal_x) || !std::isfinite(point.normal_y) ||
        !std::isfinite(point.normal_z)) {
      ++statistics.nan_count;
      continue;
    }
    ++statistics.finite_count;
    const Eigen::Vector3d normal(
        static_cast<double>(point.normal_x), static_cast<double>(point.normal_y),
        static_cast<double>(point.normal_z));
    const double norm = normal.norm();
    norms.push_back(norm);
    if (norm <= 1.0e-12) {
      ++statistics.zero_count;
    } else {
      const Eigen::Vector3d unit = normal / norm;
      normal_gram += unit * unit.transpose();
    }
  }
  if (!norms.empty()) {
    std::sort(norms.begin(), norms.end());
    statistics.norm_min = norms.front();
    statistics.norm_max = norms.back();
    const std::size_t middle = norms.size() / 2;
    statistics.norm_median = norms.size() % 2 == 0
                                 ? 0.5 * (norms[middle - 1] + norms[middle])
                                 : norms[middle];
  }
  const Eigen::SelfAdjointEigenSolver<Eigen::Matrix3d> normal_solver(normal_gram);
  if (normal_solver.info() == Eigen::Success) {
    statistics.direction_rank =
        eigen_rank(normal_solver.eigenvalues(), result->size()).first;
  }
  return {result, statistics};
}

bool valid_normals(const NormalStatistics& statistics, std::size_t expected_count) {
  return statistics.finite_count == expected_count && statistics.nan_count == 0 &&
         statistics.zero_count == 0;
}

json finite_or_null(double value) {
  return std::isfinite(value) ? json(value) : json(nullptr);
}

void add_normal_statistics(
    json& output, const std::string& prefix, const NormalStatistics& statistics) {
  output[prefix + "_normal_finite_count"] = statistics.finite_count;
  output[prefix + "_normal_zero_count"] = statistics.zero_count;
  output[prefix + "_normal_nan_count"] = statistics.nan_count;
  output[prefix + "_normal_norm_min"] = finite_or_null(statistics.norm_min);
  output[prefix + "_normal_norm_median"] = finite_or_null(statistics.norm_median);
  output[prefix + "_normal_norm_max"] = finite_or_null(statistics.norm_max);
  output[prefix + "_normal_direction_rank"] = statistics.direction_rank;
}

RankDiagnostics compute_rank_diagnostics(
    const CloudNormal::Ptr& source, const CloudNormal::Ptr& target,
    const Eigen::Matrix4f& initial) {
  RankDiagnostics result;
  Eigen::Vector3d mean = Eigen::Vector3d::Zero();
  for (const auto& point : *target) {
    mean += Eigen::Vector3d(point.x, point.y, point.z);
  }
  mean /= static_cast<double>(target->size());
  Eigen::Matrix3d covariance = Eigen::Matrix3d::Zero();
  for (const auto& point : *target) {
    const Eigen::Vector3d centered = Eigen::Vector3d(point.x, point.y, point.z) - mean;
    covariance += centered * centered.transpose();
  }
  covariance /= static_cast<double>(target->size());
  const Eigen::SelfAdjointEigenSolver<Eigen::Matrix3d> covariance_solver(covariance);
  require(covariance_solver.info() == Eigen::Success, "point-cloud covariance eigensolver failed");
  const auto cloud_rank = eigen_rank(covariance_solver.eigenvalues(), target->size());
  result.point_cloud_rank = cloud_rank.first;
  result.point_cloud_rank_tolerance = cloud_rank.second;
  result.point_cloud_covariance_eigenvalues =
      eigenvalues_vector(covariance_solver.eigenvalues());

  auto search = std::make_shared<pcl::search::KdTree<PointNormal>>();
  search->setInputCloud(target);
  Eigen::Matrix<double, 6, 6> hessian = Eigen::Matrix<double, 6, 6>::Zero();
  std::vector<int> indices(1);
  std::vector<float> squared_distances(1);
  for (const auto& point : *source) {
    const Eigen::Vector4f transformed =
        initial * Eigen::Vector4f(point.x, point.y, point.z, 1.0f);
    PointNormal query;
    query.x = transformed.x();
    query.y = transformed.y();
    query.z = transformed.z();
    if (search->nearestKSearch(query, 1, indices, squared_distances) != 1 ||
        squared_distances[0] >
            static_cast<float>(kMaximumCorrespondenceDistanceM *
                               kMaximumCorrespondenceDistanceM)) {
      continue;
    }
    const auto& matched = target->at(static_cast<std::size_t>(indices[0]));
    const Eigen::Vector3d normal(
        static_cast<double>(matched.normal_x), static_cast<double>(matched.normal_y),
        static_cast<double>(matched.normal_z));
    if (!normal.allFinite() || normal.norm() <= 1.0e-12) {
      continue;
    }
    const Eigen::Vector3d unit = normal.normalized();
    const Eigen::Vector3d position(
        static_cast<double>(transformed.x()), static_cast<double>(transformed.y()),
        static_cast<double>(transformed.z()));
    Eigen::Matrix<double, 6, 1> row;
    row.head<3>() = position.cross(unit);
    row.tail<3>() = unit;
    hessian += row * row.transpose();
    ++result.diagnostic_correspondence_count;
  }
  const Eigen::SelfAdjointEigenSolver<Eigen::Matrix<double, 6, 6>> hessian_solver(hessian);
  require(hessian_solver.info() == Eigen::Success, "point-to-plane Hessian eigensolver failed");
  const auto hessian_rank =
      eigen_rank(hessian_solver.eigenvalues(), result.diagnostic_correspondence_count);
  result.point_to_plane_jacobian_rank = hessian_rank.first;
  result.point_to_plane_rank_tolerance = hessian_rank.second;
  result.point_to_plane_hessian_eigenvalues =
      eigenvalues_vector(hessian_solver.eigenvalues());
  result.rank_deficient = result.point_to_plane_jacobian_rank < 6;
  result.condition_status = result.diagnostic_correspondence_count == 0
                                ? "NO_CORRESPONDENCES"
                                : (result.rank_deficient ? "RANK_DEFICIENT" : "FULL_RANK");
  return result;
}

std::vector<double> flatten(const Eigen::Matrix4f& transform) {
  std::vector<double> values;
  values.reserve(16);
  for (int row = 0; row < 4; ++row) {
    for (int column = 0; column < 4; ++column) {
      values.push_back(static_cast<double>(transform(row, column)));
    }
  }
  return values;
}

bool finite_transform(const Eigen::Matrix4f& transform) {
  return transform.allFinite();
}

json failure_result(const std::string& trial_id, const std::string& reason) {
  json output = {
      {"trial_id", trial_id},
      {"backend_name", "pcl_point_to_plane"},
      {"pcl_version", PCL_VERSION_PRETTY},
      {"has_converged_raw", false},
      {"has_converged", false},
      {"final_transform_finite", false},
      {"fitness_finite", false},
      {"fitness_score", nullptr},
      {"final_transformation_4x4", nullptr},
      {"translation_update_norm_m", nullptr},
      {"rotation_update_norm_rad", nullptr},
      {"source_point_count", 0},
      {"target_point_count", 0},
      {"finite_output", false},
      {"qualification_pass", false},
      {"iteration_count", 0},
      {"correspondence_count", 0},
      {"point_cloud_rank", nullptr},
      {"point_cloud_covariance_eigenvalues", nullptr},
      {"point_cloud_rank_tolerance", nullptr},
      {"point_to_plane_jacobian_rank", nullptr},
      {"point_to_plane_hessian_eigenvalues", nullptr},
      {"point_to_plane_rank_tolerance", nullptr},
      {"diagnostic_correspondence_count", 0},
      {"rank_deficient", nullptr},
      {"condition_status", "EXCEPTION"},
      {"runtime_ms", 0.0},
      {"failure_reason", "EXCEPTION"},
      {"failure_flags", json::array({"EXCEPTION"})},
      {"exception_message", reason},
      {"source_checksum", ""},
      {"target_checksum", ""},
      {"reference_pose_checksum", ""},
      {"snapshot_checksum", ""},
  };
  add_normal_statistics(output, "source", NormalStatistics{});
  add_normal_statistics(output, "target", NormalStatistics{});
  return output;
}

json run(const std::filesystem::path& config_path) {
  std::ifstream stream(config_path);
  require(stream.good(), "cannot open config JSON");
  json config;
  stream >> config;
  const std::string trial_id = config.at("trial_id").get<std::string>();
  require(!trial_id.empty(), "trial_id must be non-empty");
  validate_parameters(config);

  const auto source_path = resolve_input_path(config_path, config.at("source_path"));
  const auto target_path = resolve_input_path(config_path, config.at("target_path"));
  const Eigen::Matrix4f initial = parse_transform(config.at("initial_transformation_4x4"));

  const auto started = std::chrono::steady_clock::now();
  const auto source_xyz = load_xyz(source_path);
  const auto target_xyz = load_xyz(target_path);
  const auto source_estimated = estimate_normals(source_xyz);
  const auto target_estimated = estimate_normals(target_xyz);
  const auto source = source_estimated.cloud;
  const auto target = target_estimated.cloud;
  const bool source_normals_valid =
      valid_normals(source_estimated.statistics, source_xyz->size());
  const bool target_normals_valid =
      valid_normals(target_estimated.statistics, target_xyz->size());
  const bool normals_valid = source_normals_valid && target_normals_valid;
  const RankDiagnostics rank = compute_rank_diagnostics(source, target, initial);

  AuditedICP icp;
  auto point_to_plane = std::make_shared<
      pcl::registration::TransformationEstimationPointToPlaneLLS<PointNormal, PointNormal>>();
  icp.setTransformationEstimation(point_to_plane);
  icp.setInputSource(source);
  icp.setInputTarget(target);
  icp.setMaxCorrespondenceDistance(kMaximumCorrespondenceDistanceM);
  icp.setMaximumIterations(kMaximumIterations);
  icp.setTransformationEpsilon(kTransformationEpsilon);
  icp.setEuclideanFitnessEpsilon(kEuclideanFitnessEpsilon);
  icp.setUseReciprocalCorrespondences(false);
  icp.setUseSymmetricObjective(false);
  icp.setEnforceSameDirectionNormals(true);

  CloudNormal aligned;
  if (normals_valid) {
    icp.align(aligned, initial);
  }
  const Eigen::Matrix4f final = icp.getFinalTransformation();
  const double fitness = normals_valid
                             ? icp.getFitnessScore(kMaximumCorrespondenceDistanceM)
                             : std::numeric_limits<double>::quiet_NaN();
  const auto finished = std::chrono::steady_clock::now();
  const double runtime_ms =
      std::chrono::duration<double, std::milli>(finished - started).count();
  const bool has_converged_raw = normals_valid && icp.hasConverged();
  const bool final_transform_finite = finite_transform(final);
  const bool fitness_finite = std::isfinite(fitness);

  Eigen::Matrix4f delta = initial.inverse() * final;
  const double translation_update = static_cast<double>(delta.block<3, 1>(0, 3).norm());
  const Eigen::Matrix3f rotation = delta.block<3, 3>(0, 0);
  const double cosine = std::clamp(
      (static_cast<double>(rotation.trace()) - 1.0) * 0.5, -1.0, 1.0);
  const double rotation_update = std::acos(cosine);
  const bool finite_output = final_transform_finite && fitness_finite &&
                             std::isfinite(translation_update) &&
                             std::isfinite(rotation_update);
  const std::size_t correspondence_count = icp.final_correspondence_count();
  const bool qualification_pass = has_converged_raw && finite_output &&
                                  correspondence_count > 0 && normals_valid &&
                                  !rank.rank_deficient;

  std::vector<std::string> failure_flags;
  if (!normals_valid) {
    failure_flags.emplace_back("INVALID_NORMALS");
  }
  if (correspondence_count == 0) {
    failure_flags.emplace_back("NO_CORRESPONDENCES");
  }
  if (rank.rank_deficient) {
    failure_flags.emplace_back("RANK_DEFICIENT_DIAGNOSTIC");
  }
  if (!final_transform_finite) {
    failure_flags.emplace_back("NONFINITE_TRANSFORM");
  }
  if (!fitness_finite) {
    failure_flags.emplace_back("NONFINITE_FITNESS");
  }
  if (!has_converged_raw) {
    failure_flags.emplace_back("PCL_NOT_CONVERGED");
  }
  std::string reason;
  for (const auto& candidate : {
           std::string("INVALID_NORMALS"), std::string("NO_CORRESPONDENCES"),
           std::string("RANK_DEFICIENT_DIAGNOSTIC"),
           std::string("NONFINITE_TRANSFORM"), std::string("NONFINITE_FITNESS"),
           std::string("PCL_NOT_CONVERGED")}) {
    if (std::find(failure_flags.begin(), failure_flags.end(), candidate) !=
        failure_flags.end()) {
      reason = candidate;
      break;
    }
  }

  json output = {
      {"trial_id", trial_id},
      {"backend_name", "pcl_point_to_plane"},
      {"pcl_version", PCL_VERSION_PRETTY},
      {"has_converged_raw", has_converged_raw},
      {"has_converged", has_converged_raw},
      {"final_transform_finite", final_transform_finite},
      {"fitness_finite", fitness_finite},
      {"fitness_score", fitness_finite ? json(fitness) : json(nullptr)},
      {"final_transformation_4x4",
       final_transform_finite ? json(flatten(final)) : json(nullptr)},
      {"translation_update_norm_m", finite_or_null(translation_update)},
      {"rotation_update_norm_rad", finite_or_null(rotation_update)},
      {"source_point_count", source_xyz->size()},
      {"target_point_count", target_xyz->size()},
      {"finite_output", finite_output},
      {"qualification_pass", qualification_pass},
      {"iteration_count", icp.final_iteration_count()},
      {"correspondence_count", correspondence_count},
      {"point_cloud_rank", rank.point_cloud_rank},
      {"point_cloud_covariance_eigenvalues",
       rank.point_cloud_covariance_eigenvalues},
      {"point_cloud_rank_tolerance", rank.point_cloud_rank_tolerance},
      {"point_to_plane_jacobian_rank", rank.point_to_plane_jacobian_rank},
      {"point_to_plane_hessian_eigenvalues",
       rank.point_to_plane_hessian_eigenvalues},
      {"point_to_plane_rank_tolerance", rank.point_to_plane_rank_tolerance},
      {"diagnostic_correspondence_count", rank.diagnostic_correspondence_count},
      {"rank_deficient", rank.rank_deficient},
      {"condition_status", rank.condition_status},
      {"runtime_ms", runtime_ms},
      {"failure_reason", reason},
      {"failure_flags", failure_flags},
      {"exception_message", nullptr},
      {"source_checksum", config.at("source_checksum")},
      {"target_checksum", config.at("target_checksum")},
      {"reference_pose_checksum", config.at("reference_pose_checksum")},
      {"snapshot_checksum", config.at("snapshot_checksum")},
  };
  add_normal_statistics(output, "source", source_estimated.statistics);
  add_normal_statistics(output, "target", target_estimated.statistics);
  return output;
}

}  // namespace

int main(int argc, char** argv) {
  std::string trial_id = "unknown";
  try {
    require(argc == 3 && std::string(argv[1]) == "--config",
            "usage: pcl_point_to_plane_cli --config CONFIG.json");
    const std::filesystem::path config_path = std::filesystem::absolute(argv[2]);
    std::ifstream preview(config_path);
    if (preview.good()) {
      json value;
      preview >> value;
      trial_id = value.value("trial_id", "unknown");
    }
    std::cout << run(config_path).dump() << std::endl;
    return 0;
  } catch (const std::exception& error) {
    std::cout << failure_result(trial_id, error.what()).dump() << std::endl;
    return 2;
  }
}
