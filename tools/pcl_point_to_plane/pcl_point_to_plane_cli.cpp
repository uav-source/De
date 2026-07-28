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
#include <vector>

namespace {

using json = nlohmann::json;
using PointXYZ = pcl::PointXYZ;
using PointNormal = pcl::PointNormal;
using CloudXYZ = pcl::PointCloud<PointXYZ>;
using CloudNormal = pcl::PointCloud<PointNormal>;

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

CloudNormal::Ptr estimate_normals(const CloudXYZ::Ptr& xyz) {
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
  for (const auto& point : *result) {
    require(std::isfinite(point.normal_x) && std::isfinite(point.normal_y) &&
                std::isfinite(point.normal_z),
            "normal estimation produced a non-finite normal");
  }
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
  return {
      {"trial_id", trial_id},
      {"backend_name", "pcl_point_to_plane"},
      {"pcl_version", PCL_VERSION_PRETTY},
      {"has_converged", false},
      {"fitness_score", nullptr},
      {"final_transformation_4x4", nullptr},
      {"translation_update_norm_m", nullptr},
      {"rotation_update_norm_rad", nullptr},
      {"source_point_count", 0},
      {"target_point_count", 0},
      {"finite_output", false},
      {"runtime_ms", 0.0},
      {"failure_reason", reason},
  };
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
  const auto source = estimate_normals(source_xyz);
  const auto target = estimate_normals(target_xyz);

  pcl::IterativeClosestPointWithNormals<PointNormal, PointNormal> icp;
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
  icp.align(aligned, initial);
  const Eigen::Matrix4f final = icp.getFinalTransformation();
  const double fitness = icp.getFitnessScore(kMaximumCorrespondenceDistanceM);
  const auto finished = std::chrono::steady_clock::now();
  const double runtime_ms =
      std::chrono::duration<double, std::milli>(finished - started).count();
  const bool finite = finite_transform(final) && std::isfinite(fitness);
  const bool converged = icp.hasConverged() && finite;

  Eigen::Matrix4f delta = initial.inverse() * final;
  const double translation_update = static_cast<double>(delta.block<3, 1>(0, 3).norm());
  const Eigen::Matrix3f rotation = delta.block<3, 3>(0, 0);
  const double cosine = std::clamp(
      (static_cast<double>(rotation.trace()) - 1.0) * 0.5, -1.0, 1.0);
  const double rotation_update = std::acos(cosine);
  const std::string reason = converged ? "" : "pcl_icp_did_not_converge_or_nonfinite";

  return {
      {"trial_id", trial_id},
      {"backend_name", "pcl_point_to_plane"},
      {"pcl_version", PCL_VERSION_PRETTY},
      {"has_converged", converged},
      {"fitness_score", finite ? json(fitness) : json(nullptr)},
      {"final_transformation_4x4", finite ? json(flatten(final)) : json(nullptr)},
      {"translation_update_norm_m",
       std::isfinite(translation_update) ? json(translation_update) : json(nullptr)},
      {"rotation_update_norm_rad",
       std::isfinite(rotation_update) ? json(rotation_update) : json(nullptr)},
      {"source_point_count", source_xyz->size()},
      {"target_point_count", target_xyz->size()},
      {"finite_output", finite && std::isfinite(translation_update) &&
                            std::isfinite(rotation_update)},
      {"runtime_ms", runtime_ms},
      {"failure_reason", reason},
      {"source_checksum", config.at("source_checksum")},
      {"target_checksum", config.at("target_checksum")},
      {"reference_pose_checksum", config.at("reference_pose_checksum")},
      {"snapshot_checksum", config.at("snapshot_checksum")},
  };
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
