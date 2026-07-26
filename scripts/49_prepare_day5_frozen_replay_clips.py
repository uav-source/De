#!/usr/bin/env python3
"""Create one-time, read-only two-topic Day 5 startup-sync replay clips."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping


TOPICS = ("/livox/lidar", "/livox/imu")
CLIP_IDENTITY = {
    "usage": "ENGINEERING_REPLAY_DERIVATIVE",
    "scientific_sequence": "NOT_A_NEW_SCIENTIFIC_SEQUENCE",
    "data_namespace": "NOT_INCLUDED_IN_DATA_NAMESPACE",
}
SEQUENCES = {
    "avia_quick_shack": {
        "source_name": "2020-09-16-quick-shack.bag",
        "output_name": "avia_quick_shack.replay.bag",
        "source_sha256": "05a56e75898f952766f136d1e5db64a35d202e990e3b1052558369d8384d7ffe",
        "locked_duration_sec": 50.001004,
    },
    "avia_outdoor_run_100hz": {
        "source_name": "outdoor_run_100Hz_2020-12-27-17-12-19.bag",
        "output_name": "avia_outdoor_run_100hz.replay.bag",
        "source_sha256": "13bde5d88ce054d88904873e924e2619153efdf5b63df7f3bbab4f16eb72a253",
        "locked_duration_sec": 63.857759,
    },
}


class ClipError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_source(path: Path, expected_sha256: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise ClipError(f"source bag missing or empty: {path}")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ClipError(f"source bag SHA mismatch: expected {expected_sha256}, got {actual}")


def ensure_new_output(path: Path) -> None:
    if path.exists():
        raise ClipError(f"refusing to regenerate frozen clip: {path}")


def validate_clip_metadata(metadata: Mapping[str, Any]) -> None:
    topics = set(metadata.get("topics", []))
    if topics != set(TOPICS):
        raise ClipError(f"clip topics must be exactly {TOPICS}, got {sorted(topics)}")
    counts = metadata.get("topic_counts", {})
    if int(counts.get(TOPICS[0], 0)) <= 0:
        raise ClipError("clip has no LiDAR messages")
    if int(counts.get(TOPICS[1], 0)) <= 0:
        raise ClipError("clip has no IMU messages")
    if int(metadata.get("message_count", 0)) <= 0:
        raise ClipError("clip is empty")


def clip_is_read_only(path: Path) -> bool:
    return stat.S_IMODE(path.stat().st_mode) == 0o444


def _analyze_clip(path: Path) -> dict[str, Any]:
    import rosbag  # type: ignore

    topic_times: dict[str, list[float]] = {topic: [] for topic in TOPICS}
    first_topic = None
    first_time = None
    count = 0
    with rosbag.Bag(str(path), "r") as bag:
        for topic, _message, timestamp in bag.read_messages():
            current = timestamp.to_sec()
            if first_topic is None:
                first_topic, first_time = topic, current
            if topic not in topic_times:
                raise ClipError(f"unexpected topic in clip: {topic}")
            topic_times[topic].append(current)
            count += 1
    metadata = {
        "topics": sorted(topic_times),
        "topic_counts": {topic: len(values) for topic, values in topic_times.items()},
        "message_count": count,
        "first_message_topic": first_topic,
        "first_message_time": first_time,
        "first_lidar_time": topic_times[TOPICS[0]][0] if topic_times[TOPICS[0]] else None,
        "last_lidar_time": topic_times[TOPICS[0]][-1] if topic_times[TOPICS[0]] else None,
        "first_imu_time": topic_times[TOPICS[1]][0] if topic_times[TOPICS[1]] else None,
        "last_imu_time": topic_times[TOPICS[1]][-1] if topic_times[TOPICS[1]] else None,
    }
    validate_clip_metadata(metadata)
    metadata["clip_duration_sec"] = max(
        metadata["last_lidar_time"], metadata["last_imu_time"]
    ) - min(metadata["first_lidar_time"], metadata["first_imu_time"])
    return metadata


def create_clip(source: Path, output: Path, duration: float) -> dict[str, Any]:
    import rosbag  # type: ignore

    ensure_new_output(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with rosbag.Bag(str(source), "r") as input_bag:
        start = float(input_bag.get_start_time())
        end = start + duration
        with rosbag.Bag(str(output), "w") as output_bag:
            for topic, message, timestamp in input_bag.read_messages(topics=list(TOPICS)):
                current = timestamp.to_sec()
                if start <= current < end:
                    output_bag.write(topic, message, timestamp)
    metadata = _analyze_clip(output)
    metadata.update(
        {
            "original_start_time": start,
            "locked_window_end_exclusive": end,
            "locked_duration_sec": duration,
        }
    )
    os.chmod(output, 0o444)
    if not clip_is_read_only(output):
        raise ClipError("clip mode is not 0444")
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--manifest-output", required=True, type=Path)
    parser.add_argument("--sha-output", required=True, type=Path)
    parser.add_argument("--info-output-root", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.info_output_root.mkdir(parents=True, exist_ok=True)
    records = []
    for sequence_id, definition in SEQUENCES.items():
        source = args.source_root / str(definition["source_name"])
        output = args.output_root / str(definition["output_name"])
        verify_source(source, str(definition["source_sha256"]))
        metadata = create_clip(source, output, float(definition["locked_duration_sec"]))
        clip_sha = sha256_file(output)
        info_path = args.info_output_root / f"{sequence_id}.rosbag_info.yaml"
        with info_path.open("w", encoding="utf-8") as stream:
            subprocess.run(
                ["rosbag", "info", "--yaml", str(output)],
                check=True,
                stdout=stream,
                text=True,
            )
        records.append(
            {
                "sequence_id": sequence_id,
                "source_name": definition["source_name"],
                "source_sha256": definition["source_sha256"],
                "source_size_bytes": source.stat().st_size,
                "clip_name": definition["output_name"],
                "clip_sha256": clip_sha,
                "clip_size_bytes": output.stat().st_size,
                "clip_read_only": clip_is_read_only(output),
                "generated_once": True,
                **CLIP_IDENTITY,
                **metadata,
            }
        )
    manifest = {
        "schema_version": "day5_startup_sync_replay_clips_v1",
        "filter_topics": list(TOPICS),
        "window_rule": "original_start_time <= message_time < original_start_time + locked_duration",
        "clips": records,
    }
    args.manifest_output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.sha_output.write_text(
        "".join(f"{record['clip_sha256']}  {record['clip_name']}\n" for record in records),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
