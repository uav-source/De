import csv
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DAY29_SCRIPT = ROOT / "scripts/22_day29_safe_figures.py"
F01_SCRIPT = ROOT / "scripts/paper_figures/generate_f01_benchmark_geometry.py"
F03_SCRIPT = ROOT / "scripts/paper_figures/generate_f03_bias_audit.py"


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day29"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_day29_generates_real_figures_and_safety_artifacts(tmp_path):
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data/minibench"
    config_root = repo_root / "configs/minibench"
    out_root = repo_root / "results/day30"
    reports_root = repo_root / "reports"
    docs_root = repo_root / "docs/paper"
    prepare_day29_inputs(repo_root, data_root, config_root, out_root, reports_root)
    protected = snapshot_files(out_root)
    protected.update(snapshot_files(reports_root))
    config = write_day29_config(tmp_path)
    report = reports_root / "day29_safe_figures_report.md"

    result = run_script(
        [
            sys.executable,
            str(DAY29_SCRIPT),
            "--config",
            str(config),
            "--data-root",
            str(data_root),
            "--config-root",
            str(config_root),
            "--out-root",
            str(out_root),
            "--reports-root",
            str(reports_root),
            "--docs-root",
            str(docs_root),
            "--report",
            str(report),
        ],
        tmp_path,
    )

    assert result.returncode == 0
    for path, content in protected.items():
        assert path.read_bytes() == content

    for name in [
        "F01_benchmark_geometry_overview.png",
        "F01_benchmark_geometry_overview.pdf",
        "F03_bias_audit_legacy_vs_unbiased.png",
        "F03_bias_audit_legacy_vs_unbiased.pdf",
    ]:
        path = docs_root / "figures" / name
        assert path.exists()
        assert path.stat().st_size > 2000

    notes = (docs_root / "generated_tables/table_interpretation_notes.md").read_text(encoding="utf-8")
    caption_bank = (docs_root / "caption_bank_day29.md").read_text(encoding="utf-8")
    assert "valid means computable, not substantive validity" in notes
    for text in [caption_bank, notes, report.read_text(encoding="utf-8")]:
        assert "ODI " + "robustly predicts drift" not in text
        assert "weak-subspace update is authorized" not in text

    inventory = list(csv.DictReader((out_root / "tables/day29_generated_figure_inventory.csv").open()))
    safety = list(csv.DictReader((out_root / "tables/day29_table_safety_notes.csv").open()))
    caption_audit = list(csv.DictReader((out_root / "tables/day29_caption_safety_audit.csv").open()))
    manifest = json.loads((out_root / "manifests/day29_safe_figures_manifest.json").read_text())
    assert {row["figure_id"] for row in inventory} == {"F01", "F03"}
    assert all(row["real_generation_status"] == "generated_from_source_artifacts" for row in inventory)
    assert all(row["fake_figure_detected"] == "false" for row in inventory)
    assert any(row["unsafe_or_ambiguous_text"] == "held_out_validity_status = valid" for row in safety)
    assert any(row["unsafe_or_ambiguous_text"] == "exploratory_not_validated rows" for row in safety)
    assert all(row["status"] == "pass" for row in caption_audit)
    assert manifest["status"] == "OK"
    assert manifest["generated_figure_count"] >= 2
    assert manifest["fake_figures_created"] is False
    assert manifest["table_safety_notes_created"] is True
    assert manifest["caption_safety_passed"] is True
    assert manifest["method_update_authorized"] is False
    assert manifest["weak_update_authorized"] is False
    assert "No fake figures are generated." in report.read_text(encoding="utf-8")
    assert "Weak-subspace update remains unauthorized." in report.read_text(encoding="utf-8")


def test_day29_figure_scripts_fail_clearly_when_sources_are_missing(tmp_path):
    out_dir = tmp_path / "figures"
    result = run_script(
        [
            sys.executable,
            str(F01_SCRIPT),
            "--data-root",
            str(tmp_path / "missing_data"),
            "--config-root",
            str(tmp_path / "missing_configs"),
            "--out-dir",
            str(out_dir),
        ],
        tmp_path,
        check=False,
    )
    assert result.returncode == 2
    assert "Missing minibench data root" in result.stderr
    assert not (out_dir / "F01_benchmark_geometry_overview.png").exists()
    assert not (out_dir / "F01_benchmark_geometry_overview.pdf").exists()

    result = run_script(
        [
            sys.executable,
            str(F03_SCRIPT),
            "--day30-root",
            str(tmp_path / "missing_day30"),
            "--out-dir",
            str(out_dir),
        ],
        tmp_path,
        check=False,
    )
    assert result.returncode == 2
    assert "Missing required F03 source artifact" in result.stderr
    assert not (out_dir / "F03_bias_audit_legacy_vs_unbiased.png").exists()
    assert not (out_dir / "F03_bias_audit_legacy_vs_unbiased.pdf").exists()


def prepare_day29_inputs(repo_root: Path, data_root: Path, config_root: Path, out_root: Path, reports_root: Path) -> None:
    (out_root / "tables").mkdir(parents=True, exist_ok=True)
    (out_root / "manifests").mkdir(parents=True, exist_ok=True)
    reports_root.mkdir(parents=True, exist_ok=True)
    sequences = [
        ("OC-L0-S01-M1", "open_control", 0.0, 0.0, "low"),
        ("ST-L3-S01-M1", "straight_tunnel", 0.022, 0.0, "high"),
        ("CT-L2-S01-M2", "curved_tunnel", 0.016, 0.0, "medium"),
        ("RT-L4-S01-M1", "repetitive_tunnel", 0.026, 0.0, "high"),
    ]
    for idx, (sequence_id, scene_family, _legacy, _applied, _risk) in enumerate(sequences):
        write_minibench_sequence(data_root, config_root, sequence_id, scene_family, idx)
    write_text(
        out_root / "tables/day15_bias_audit.csv",
        "sequence_id,scene_family,legacy_axis_bias,final_axis_error,ODI_median,axis_drift_rate_median,confound_risk_level,interpretation\n"
        + "\n".join(
            f"{seq},{family},{legacy:.3f},0.1,0.5,0.01,{risk},diagnostic only"
            for seq, family, legacy, _applied, risk in sequences
        )
        + "\n",
    )
    write_text(
        out_root / "tables/day16_unbiased_toy_lio_summary.csv",
        "sequence_id,scene_family,axis_bias_mode,perturbation_profile,legacy_axis_bias,applied_axis_bias,final_axis_error,axis_drift_rate_median,ODI_median,AIS_median,lambda_min_clamped_median,condition_number_median,is_unbiased_protocol\n"
        + "\n".join(
            f"{seq},{family},none,unbiased_day16,{legacy:.3f},{applied:.3f},0.08,0.009,0.4,1.0,0.2,10.0,true"
            for seq, family, legacy, applied, _risk in sequences
        )
        + "\n",
    )
    write_text(
        out_root / "tables/day27_figure_table_readiness.csv",
        "item_id,source_artifact,output_target,readiness_status,next_action,must_not_claim\n"
        "F01,configs/minibench,docs/paper/figures/F01.png,pending,write script,real-world coverage\n"
        "F03,day15/day16,docs/paper/figures/F03.png,pending,write script,real LIO validation\n"
        "T03,results/day30/tables/day19_loso_selection_results.csv,docs/paper/generated_tables/T03.md,ready_for_conversion,convert,generalized validity\n"
        "T05,results/day30/tables/day21_joint_risk_comparison.csv,docs/paper/generated_tables/T05.md,ready_for_conversion,convert,validated joint-risk detector\n",
    )
    write_text(out_root / "tables/day28_generated_table_inventory.csv", "item_id,generated\nT03,true\nT05,true\n")
    write_text(out_root / "tables/day28_pending_figure_plan.csv", "item_id,must_not_fake\nF01,true\nF03,true\n")
    write_text(out_root / "tables/day28_caption_bank.csv", "item_id,caption_draft\nF01,diagnostic geometry overview\n")
    write_json(out_root / "manifests/day27_release_cleanup_manifest.json", {"status": "OK", "method_update_authorized": False, "weak_update_authorized": False})
    write_json(out_root / "manifests/day28_figure_table_generation_manifest.json", {"status": "OK", "method_update_authorized": False, "weak_update_authorized": False})
    write_text(reports_root / "day27_release_cleanup_report.md", "Day27 diagnostic benchmark report\n")
    write_text(reports_root / "day28_figure_table_generation_report.md", "Day28 no fake figures\n")


def write_minibench_sequence(data_root: Path, config_root: Path, sequence_id: str, scene_family: str, offset: int) -> None:
    seq_dir = data_root / sequence_id
    seq_dir.mkdir(parents=True, exist_ok=True)
    config_root.mkdir(parents=True, exist_ok=True)
    write_text(config_root / f"{sequence_id}.yaml", f"sequence_id: {sequence_id}\nscene_family: {scene_family}\n")
    write_json(seq_dir / "scene_metadata.json", {"sequence_id": sequence_id, "scene_family": scene_family})
    feature_rows = ["x,y,z"]
    for i in range(18):
        x = offset * 3.0 + i * 0.18
        y = ((i % 6) - 2.5) * 0.18
        z = ((i % 3) - 1.0) * 0.12
        feature_rows.append(f"{x:.4f},{y:.4f},{z:.4f}")
    write_text(seq_dir / "feature_points.csv", "\n".join(feature_rows) + "\n")
    write_text(
        seq_dir / "axis.csv",
        "timestamp,axis_x,axis_y,axis_z,reliable\n"
        "0.0,1.0,0.0,0.0,1\n"
        "0.1,0.98,0.05,0.0,1\n",
    )
    write_text(
        seq_dir / "planes.csv",
        "plane_id,frame_start,frame_end,nx,ny,nz,qx,qy,qz,semantic\n"
        "0,0,10,0.0,1.0,0.0,0.2,0.1,0.0,wall\n"
        "1,0,10,0.0,-1.0,0.0,0.8,-0.1,0.0,wall\n",
    )


def write_day29_config(tmp_path: Path) -> Path:
    path = tmp_path / "day29_safe_figures.yaml"
    path.write_text(
        "\n".join(
            [
                "source_days: [day15_bias_audit, day16_unbiased_protocol, day27_release_cleanup, day28_figure_table_generation]",
                "route: safe_figure_generation_and_table_safety",
                "figures: [F01_benchmark_geometry_overview, F03_bias_audit_legacy_vs_unbiased]",
                "table_safety_items: [T03_day19_grouped_loso_summary, T05_day21_joint_risk_summary]",
                "forbidden_actions: [weak_subspace_update, estimator_method_implementation, robust_ODI_claim, fake_figure_generation, overwrite_previous_artifacts]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def snapshot_files(root: Path):
    return {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}


def run_script(command, tmp_path: Path, check: bool = True):
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        env=child_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if check and result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
    if check:
        result.check_returncode()
    return result
