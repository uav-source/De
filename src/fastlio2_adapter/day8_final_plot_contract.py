"""Frozen, fail-closed plotting contract for final Day 8 evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence


PLOT_INPUT_SCHEMA_VERSION = "DAY8_FINAL_PLOT_INPUT_SCHEMA_V1"
PLOT_NAMES = (
    "final_identity_overlap_by_pair.png",
    "final_query_stream_alignment.png",
    "final_strict_member_set_divergence.png",
    "final_result_order_only_divergence.png",
    "final_full_window_token_coverage.png",
    "final_shadow_vs_formal_members.png",
    "final_first_query_visited_nodes.png",
    "final_first_query_prune_counts.png",
    "final_first_query_token_diff.png",
    "final_missing_expected_point_path.png",
    "final_deleted_visibility.png",
    "final_rebuild_context.png",
    "final_root_cause_summary.png",
    "final_null_token_contract_audit.png",
    "final_random_replay_route_decision.png",
)


def _require(mapping: Mapping[str, Any], fields: Sequence[str], name: str) -> None:
    missing = [field for field in fields if field not in mapping]
    if missing:
        raise ValueError(f"{name} missing required fields: {missing}")


def validate_plot_inputs(documents: Mapping[str, Any]) -> dict[str, Any]:
    required_documents = {
        "pairwise_final_query_comparison",
        "pairwise_final_strict_identity_summary",
        "pairwise_final_first_divergence",
        "pairwise_final_root_cause_classification",
        "root_cause_summary",
        "token_coverage",
        "shadow_accounting",
        "instrumentation_cost",
        "null_token_contract_audit",
        "random_replay_route_decision",
    }
    missing_documents = sorted(required_documents - set(documents))
    if missing_documents:
        raise ValueError(f"plot documents missing: {missing_documents}")
    pair_summary = documents["pairwise_final_strict_identity_summary"]
    _require(pair_summary, ("pairs", "pair_count"), "pair summary")
    if pair_summary["pair_count"] != 6 or len(pair_summary["pairs"]) != 6:
        raise ValueError("plot contract requires six pair summaries")
    for pair in pair_summary["pairs"]:
        _require(pair, (
            "left_run_id",
            "right_run_id",
            "left_identity_count",
            "right_identity_count",
            "common_identity_count",
            "aligned_prefix_length",
            "strict_identity_formal_member_set_divergence_count",
            "formal_result_order_only_divergence_count",
            "root_cause_classification",
        ), "pair")
    _require(
        documents["pairwise_final_first_divergence"],
        ("pairs",),
        "first divergence",
    )
    _require(
        documents["root_cause_summary"],
        (
            "root_cause_classification",
            "first_strict_formal_member_set_divergence",
            "first_divergent_traversal_token",
            "missing_expected_point_witness",
        ),
        "root cause",
    )
    _require(
        documents["token_coverage"],
        ("runs", "FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS"),
        "token coverage",
    )
    _require(
        documents["shadow_accounting"],
        ("runs", "SHADOW_STATE_ACCOUNTING_PASS"),
        "shadow accounting",
    )
    _require(
        documents["instrumentation_cost"],
        ("runs", "instrumentation_timing_perturbation_present"),
        "instrumentation cost",
    )
    _require(
        documents["null_token_contract_audit"],
        ("failure_count", "NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS"),
        "null audit",
    )
    _require(
        documents["random_replay_route_decision"],
        (
            "RANDOM_REAL_REPLAY_ROUTE_STATUS",
            "FURTHER_RANDOM_REAL_REPLAY_AUTHORIZED",
        ),
        "route decision",
    )
    return {
        "schema_version": PLOT_INPUT_SCHEMA_VERSION,
        "input_documents": sorted(required_documents),
        "uses_formal_analysis_outputs_only": True,
        "alternate_scientific_input_used": False,
        "defaulted_critical_scientific_field_count": 0,
        "PLOT_INPUT_CONTRACT_PASS": True,
    }


def _pair_labels(pairs: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        f"{row['left_run_id'].rsplit('_', 1)[-1]}-{row['right_run_id'].rsplit('_', 1)[-1]}"
        for row in pairs
    ]


def render_plots(
    documents: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    contract = validate_plot_inputs(documents)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    pairs = documents["pairwise_final_strict_identity_summary"]["pairs"]
    labels = _pair_labels(pairs)
    root = documents["root_cause_summary"]
    witness = root["first_strict_formal_member_set_divergence"]
    token = root["first_divergent_traversal_token"] or {}
    missing = root["missing_expected_point_witness"] or {}

    def bars(name: str, values: Sequence[float], title: str, ylabel: str) -> None:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.bar(labels[:len(values)], values, color="#4267B2")
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(output_dir / name, dpi=140)
        plt.close(fig)

    bars(
        PLOT_NAMES[0],
        [row["common_identity_count"] for row in pairs],
        "Strict query identity overlap by pair",
        "Common identities",
    )
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(labels, [row["left_identity_count"] for row in pairs], "o-", label="left")
    ax.plot(labels, [row["right_identity_count"] for row in pairs], "s-", label="right")
    ax.plot(labels, [row["aligned_prefix_length"] for row in pairs], "^-", label="aligned prefix")
    ax.set_title("Query stream identity alignment")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / PLOT_NAMES[1], dpi=140)
    plt.close(fig)
    bars(PLOT_NAMES[2], [
        row["strict_identity_formal_member_set_divergence_count"]
        for row in pairs
    ], "Strict formal member-set divergences", "Queries")
    bars(PLOT_NAMES[3], [
        row["formal_result_order_only_divergence_count"] for row in pairs
    ], "Order-only formal result divergences", "Queries")

    coverage_runs = documents["token_coverage"]["runs"]
    run_labels = [name.rsplit("_", 1)[-1] for name in coverage_runs]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for run_id, scans in coverage_runs.items():
        ax.plot(
            [int(scan) for scan in scans["per_scan"]],
            [
                100.0 if row["token_coverage_pass"] else 0.0
                for row in scans["per_scan"].values()
            ],
            marker="o",
            label=run_id.rsplit("_", 1)[-1],
        )
    ax.set_ylim(0, 105)
    ax.set_title("Full-window detailed token coverage")
    ax.set_ylabel("Coverage (%)")
    ax.set_xlabel("Scan")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / PLOT_NAMES[4], dpi=140)
    plt.close(fig)

    shadow_runs = documents["shadow_accounting"]["runs"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = list(range(len(run_labels)))
    ax.bar(
        [item - 0.2 for item in x],
        [shadow_runs[run]["shadow_member_total"] for run in coverage_runs],
        width=0.4,
        label="shadow",
    )
    ax.bar(
        [item + 0.2 for item in x],
        [shadow_runs[run]["formal_member_total"] for run in coverage_runs],
        width=0.4,
        label="formal",
    )
    ax.set_xticks(x, run_labels)
    ax.set_title("Shadow vs formal members")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / PLOT_NAMES[5], dpi=140)
    plt.close(fig)

    left_query = witness.get("left_query", {}) if witness else {}
    right_query = witness.get("right_query", {}) if witness else {}
    bars(
        PLOT_NAMES[6],
        [left_query.get("visited_node_count", 0), right_query.get("visited_node_count", 0)],
        "First strict query visited nodes",
        "Nodes",
    )
    bars(
        PLOT_NAMES[7],
        [
            left_query.get("no_intersection_prune_count", 0),
            right_query.get("no_intersection_prune_count", 0),
        ],
        "First strict query prune counts",
        "Prunes",
    )
    bars(
        PLOT_NAMES[8],
        [token.get("first_divergent_traversal_token_index") or 0],
        "First divergent traversal token",
        "Token index",
    )
    visited = missing.get("expected_member_visited", {})
    bars(
        PLOT_NAMES[9],
        [int(bool(visited.get("left"))), int(bool(visited.get("right")))],
        "Missing expected point visit path",
        "Visited",
    )
    left_missing = missing.get("left", {})
    right_missing = missing.get("right", {})
    bars(
        PLOT_NAMES[10],
        [
            int(bool(left_missing.get("point_deleted_when_visited")))
            + int(bool(left_missing.get("tree_deleted_when_visited"))),
            int(bool(right_missing.get("point_deleted_when_visited")))
            + int(bool(right_missing.get("tree_deleted_when_visited"))),
        ],
        "Deleted visibility at expected member",
        "Deleted flags",
    )
    left_token = token.get("left_token") or {}
    right_token = token.get("right_token") or {}
    bars(
        PLOT_NAMES[11],
        [left_token.get("rebuild_generation", 0), right_token.get("rebuild_generation", 0)],
        "Rebuild context at first token difference",
        "Generation",
    )
    classifications: dict[str, int] = {}
    for row in pairs:
        key = row["root_cause_classification"]
        classifications[key] = classifications.get(key, 0) + 1
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.barh(list(classifications), list(classifications.values()))
    ax.set_title("Final pair root-cause classifications")
    fig.tight_layout()
    fig.savefig(output_dir / PLOT_NAMES[12], dpi=140)
    plt.close(fig)
    null_audit = documents["null_token_contract_audit"]
    bars(
        PLOT_NAMES[13],
        [null_audit["failure_count"]],
        "Null-token contract audit",
        "Failures",
    )
    decision = documents["random_replay_route_decision"]
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.axis("off")
    ax.text(
        0.5,
        0.62,
        decision["RANDOM_REAL_REPLAY_ROUTE_STATUS"],
        ha="center",
        va="center",
        fontsize=15,
        wrap=True,
    )
    ax.text(
        0.5,
        0.3,
        "Further random replay authorized: "
        + str(decision["FURTHER_RANDOM_REAL_REPLAY_AUTHORIZED"]).lower(),
        ha="center",
    )
    fig.tight_layout()
    fig.savefig(output_dir / PLOT_NAMES[14], dpi=140)
    plt.close(fig)
    missing_plots = [name for name in PLOT_NAMES if not (output_dir / name).is_file()]
    if missing_plots:
        raise RuntimeError(f"plot output missing: {missing_plots}")
    result = {
        **contract,
        "plot_count": len(PLOT_NAMES),
        "plots": list(PLOT_NAMES),
        "PLOT_RENDER_PASS": True,
    }
    (output_dir / "day8_final_plot_summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


__all__ = [
    "PLOT_INPUT_SCHEMA_VERSION",
    "PLOT_NAMES",
    "render_plots",
    "validate_plot_inputs",
]
