"""
evaluate_study_monitor.py — Accuracy & Performance Evaluation Benchmark.
Evaluates the AI Study Focus Monitor across multi-session test datasets.
Reports:
  - Per-class Precision, Recall, and F1-score
  - Complete Confusion Matrix
  - False Alarms per Hour
  - Detection Latency (seconds to alarm onset)
  - Recovery Latency (seconds to alarm clearing upon study resumption)
  - Separate metrics for Ordinary Reading vs Book Occlusion
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import config
from state_machine import DetectorSignals, StudyState, StudyStateMachine


# Ground truth test scenario classes
EVAL_CLASSES = [
    StudyState.STUDYING,
    StudyState.STUDYING_READING,
    StudyState.STUDYING_WRITING,
    StudyState.LOOKING_AWAY,
    StudyState.STUDY_ACTIVITY_UNCONFIRMED,
    StudyState.INACTIVITY_WARNING,
    StudyState.DISTRACTED,
    StudyState.POSSIBLE_DROWSINESS,
    StudyState.FACE_OCCLUDED,
    StudyState.OCCLUSION_UNCERTAIN,
    StudyState.STUDENT_ABSENT,
    StudyState.CAMERA_ERROR,
    StudyState.LOW_VISIBILITY,
    StudyState.RECOVERING,
]


def create_synthetic_test_sessions() -> List[Dict[str, Any]]:
    """
    Generate independent test sessions with realistic event sequences,
    mimicking diverse student sessions (different persons & sessions to prevent data leakage).
    """
    sessions = []

    # ── Session 1: Student A — Reading intensive session ───────────────
    # Sequence: Initial baseline -> Ordinary reading -> Book partly occludes face -> Resume reading
    s1_steps = []
    t = 0.0
    # 0s to 5s: Baseline studying
    for _ in range(50):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, face_detected=True, ear=0.30, head_pitch=5.0, motion_score=0.01)
        s1_steps.append((t, StudyState.STUDYING, sig))

    # 5s to 15s: Ordinary reading with book (face visible, pitch down 18 deg)
    for _ in range(100):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, face_detected=True, book_detected=True, head_pitch=18.0, ear=0.28, motion_score=0.008)
        s1_steps.append((t, StudyState.STUDYING_READING, sig))

    # 15s to 25s: Reading with book occluding lower face (face landmarks lost, but book detected & pitch down)
    for _ in range(100):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, face_detected=False, book_detected=True, head_pitch=22.0, motion_score=0.006)
        s1_steps.append((t, StudyState.STUDYING_READING, sig))

    # 25s to 35s: Writing in notebook
    for _ in range(100):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, face_detected=True, laptop_detected=True, head_pitch=12.0, ear=0.29, motion_score=0.015)
        s1_steps.append((t, StudyState.STUDYING_WRITING, sig))

    sessions.append({"session_id": "session_01_student_A", "steps": s1_steps})

    # ── Session 2: Student B — Distraction, phone, and camera staring ─
    s2_steps = []
    t = 0.0
    # 0s to 4s: Normal studying
    for _ in range(40):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, face_detected=True, ear=0.31, head_pitch=4.0, motion_score=0.01)
        s2_steps.append((t, StudyState.STUDYING, sig))

    # 4s to 12s: Phone off-task distraction (phone present >= 4s triggers DISTRACTED)
    for i in range(80):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, face_detected=True, phone_detected=True, ear=0.30, head_pitch=15.0, motion_score=0.01)
        target = StudyState.DISTRACTED if i >= 40 else StudyState.STUDYING
        s2_steps.append((t, target, sig))

    # 12s to 14s: Put phone away -> RECOVERING
    for i in range(20):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, face_detected=True, ear=0.31, head_pitch=5.0, motion_score=0.01)
        target = StudyState.RECOVERING if i < 12 else StudyState.STUDYING
        s2_steps.append((t, target, sig))

    # 14s to 30s: Staring blankly at camera (yaw 0, pitch 0, motionless, no book)
    for i in range(160):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, face_detected=True, head_pitch=0.0, head_yaw=0.0, motion_score=0.001)
        if i >= 120:  # >= 12s of staring
            target = StudyState.INACTIVITY_WARNING
        elif i >= 35: # >= 3.5s of staring
            target = StudyState.STUDY_ACTIVITY_UNCONFIRMED
        else:
            target = StudyState.STUDYING
        s2_steps.append((t, target, sig))

    sessions.append({"session_id": "session_02_student_B", "steps": s2_steps})

    # ── Session 3: Student C — Absence, Face Concealment, and Drowsiness ─
    s3_steps = []
    t = 0.0
    # 0s to 5s: Studying
    for _ in range(50):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, face_detected=True, ear=0.30, motion_score=0.01)
        s3_steps.append((t, StudyState.STUDYING, sig))

    # 5s to 14s: Student absent from camera view (> 6.0s triggers STUDENT_ABSENT)
    for i in range(90):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=False, face_detected=False)
        target = StudyState.STUDENT_ABSENT if i >= 60 else StudyState.MONITORING
        s3_steps.append((t, target, sig))

    # 14s to 16s: Student returns -> RECOVERING -> STUDYING
    for i in range(20):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, face_detected=True, ear=0.30, motion_score=0.01)
        target = StudyState.RECOVERING if i < 12 else StudyState.STUDYING
        s3_steps.append((t, target, sig))

    # 16s to 24s: Deliberate face occlusion with hands (> 3.5s triggers FACE_OCCLUDED)
    for i in range(80):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, face_detected=False, hands_near_face=True, book_detected=False)
        target = StudyState.FACE_OCCLUDED if i >= 35 else StudyState.OCCLUSION_UNCERTAIN
        s3_steps.append((t, target, sig))

    # 24s to 26s: Remove hands -> RECOVERING -> STUDYING
    for i in range(20):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, face_detected=True, ear=0.30, motion_score=0.01)
        target = StudyState.RECOVERING if i < 12 else StudyState.STUDYING
        s3_steps.append((t, target, sig))

    # 26s to 32s: Drowsiness with prolonged eye closure (> 1.8s triggers POSSIBLE_DROWSINESS)
    for i in range(60):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, face_detected=True, ear=0.12, head_pitch=8.0, motion_score=0.002)
        target = StudyState.POSSIBLE_DROWSINESS if i >= 18 else StudyState.STUDYING
        s3_steps.append((t, target, sig))

    sessions.append({"session_id": "session_03_student_C", "steps": s3_steps})

    # ── Session 4: Student D — Camera fault and poor lighting ──────────
    s4_steps = []
    t = 0.0
    for _ in range(30):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, face_detected=True, ear=0.30)
        s4_steps.append((t, StudyState.STUDYING, sig))

    # 3s to 8s: Camera frame corrupted / frozen
    for _ in range(50):
        t += 0.1
        sig = DetectorSignals(timestamp=t, camera_valid=False)
        s4_steps.append((t, StudyState.CAMERA_ERROR, sig))

    # 8s to 15s: Low visibility / underexposed
    for _ in range(70):
        t += 0.1
        sig = DetectorSignals(timestamp=t, person_detected=True, low_visibility=True)
        s4_steps.append((t, StudyState.LOW_VISIBILITY, sig))

    sessions.append({"session_id": "session_04_student_D", "steps": s4_steps})

    return sessions


def run_benchmark_evaluation(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Execute state machine on test sessions, calculate metrics,
    confusion matrix, false alarms, and latencies.
    """
    confusion: Dict[StudyState, Dict[StudyState, int]] = {
        gt: {pred: 0 for pred in EVAL_CLASSES} for gt in EVAL_CLASSES
    }

    # Tracking detection latencies for alert states
    # onset_time -> first alert trigger time
    detection_latencies: Dict[StudyState, List[float]] = defaultdict(list)
    recovery_latencies: List[float] = []

    false_alarm_count = 0
    total_study_duration_sec = 0.0

    # Metrics for reading vs occlusion
    reading_total = 0
    reading_correct = 0
    reading_as_occluded = 0

    occlusion_total = 0
    occlusion_correct = 0
    occlusion_as_reading = 0

    for sess in sessions:
        sm = StudyStateMachine(logger=None)
        steps = sess["steps"]

        current_event_gt = None
        event_start_time = None
        alert_triggered_for_event = False

        recovery_start_time = None
        recovering_active = False

        for t, gt_state, signals in steps:
            eval_res = sm.update(signals)
            pred_state = eval_res.state

            # Record in confusion matrix if both in EVAL_CLASSES
            if gt_state in confusion and pred_state in confusion[gt_state]:
                confusion[gt_state][pred_state] += 1

            # Count study time for false alarm rate calculation
            if gt_state in (StudyState.STUDYING, StudyState.STUDYING_READING, StudyState.STUDYING_WRITING):
                total_study_duration_sec += 0.1
                # If predicted state is an alert state during clean study -> False Alarm
                if pred_state in (StudyState.DISTRACTED, StudyState.INACTIVITY_WARNING, StudyState.POSSIBLE_DROWSINESS, StudyState.FACE_OCCLUDED, StudyState.STUDENT_ABSENT):
                    false_alarm_count += 1

            # Track Reading vs Occlusion specifically
            if gt_state == StudyState.STUDYING_READING:
                reading_total += 1
                if pred_state == StudyState.STUDYING_READING:
                    reading_correct += 1
                elif pred_state == StudyState.FACE_OCCLUDED:
                    reading_as_occluded += 1

            if gt_state == StudyState.FACE_OCCLUDED:
                occlusion_total += 1
                if pred_state == StudyState.FACE_OCCLUDED:
                    occlusion_correct += 1
                elif pred_state in (StudyState.STUDYING, StudyState.STUDYING_READING):
                    occlusion_as_reading += 1

            # Latency tracking:
            if gt_state != current_event_gt:
                current_event_gt = gt_state
                event_start_time = t
                alert_triggered_for_event = False

            if gt_state in (StudyState.DISTRACTED, StudyState.POSSIBLE_DROWSINESS, StudyState.FACE_OCCLUDED, StudyState.STUDENT_ABSENT, StudyState.INACTIVITY_WARNING):
                if pred_state == gt_state and not alert_triggered_for_event:
                    latency = t - event_start_time
                    detection_latencies[gt_state].append(latency)
                    alert_triggered_for_event = True

            # Recovery latency tracking:
            if gt_state == StudyState.RECOVERING:
                if not recovering_active:
                    recovery_start_time = t
                    recovering_active = True
            elif gt_state in (StudyState.STUDYING, StudyState.STUDYING_READING) and recovering_active:
                if pred_state in (StudyState.STUDYING, StudyState.STUDYING_READING):
                    rec_lat = t - recovery_start_time
                    recovery_latencies.append(rec_lat)
                    recovering_active = False

    # Compute Precision, Recall, F1 for each class
    per_class_metrics = {}
    for st in EVAL_CLASSES:
        tp = confusion[st][st]
        fp = sum(confusion[other][st] for other in EVAL_CLASSES if other != st)
        fn = sum(confusion[st][other] for other in EVAL_CLASSES if other != st)

        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        per_class_metrics[st.name] = {
            "TP": tp,
            "FP": fp,
            "FN": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "support": tp + fn,
        }

    total_study_hours = total_study_duration_sec / 3600.0
    false_alarms_per_hour = (false_alarm_count / total_study_hours) if total_study_hours > 0 else 0.0

    avg_detection_latencies = {
        st.name: round(float(np.mean(lats)), 2) for st, lats in detection_latencies.items() if lats
    }
    avg_recovery_latency = round(float(np.mean(recovery_latencies)), 2) if recovery_latencies else 0.0

    reading_recall = round(reading_correct / reading_total, 4) if reading_total > 0 else 1.0
    occlusion_recall = round(occlusion_correct / occlusion_total, 4) if occlusion_total > 0 else 1.0

    results = {
        "per_class_metrics": per_class_metrics,
        "false_alarms_per_hour": round(false_alarms_per_hour, 2),
        "total_study_hours_evaluated": round(total_study_hours, 3),
        "average_detection_latencies_sec": avg_detection_latencies,
        "average_recovery_latency_sec": avg_recovery_latency,
        "reading_vs_occlusion_breakdown": {
            "ordinary_reading_samples": reading_total,
            "ordinary_reading_accuracy": reading_recall,
            "reading_misclassified_as_occluded": reading_as_occluded,
            "face_occlusion_samples": occlusion_total,
            "face_occlusion_accuracy": occlusion_recall,
            "occlusion_misclassified_as_reading": occlusion_as_reading,
        },
    }

    return results, confusion


def print_formatted_report(results: Dict[str, Any], confusion: Dict[StudyState, Dict[StudyState, int]]) -> None:
    """Print ASCII report table for display."""
    print("\n" + "=" * 78)
    print("  AI STUDY MONITOR — ACCURACY & PERFORMANCE EVALUATION REPORT")
    print("=" * 78)

    print("\n1. Per-Class Precision, Recall, and F1-Scores:")
    print("-" * 78)
    header = f"{'State Name':<28} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Support':<8}"
    print(header)
    print("-" * 78)

    for state_name, m in results["per_class_metrics"].items():
        if m["support"] > 0 or m["FP"] > 0:
            print(
                f"{state_name:<28} | {m['precision']:<10.3f} | {m['recall']:<10.3f} | "
                f"{m['f1_score']:<10.3f} | {m['support']:<8}"
            )

    print("-" * 78)

    print("\n2. False Alarms & Temporal Responsiveness:")
    print(f"  • Total Evaluated Study Duration: {results['total_study_hours_evaluated']:.3f} hours")
    print(f"  • Measured False Alarms per Hour: {results['false_alarms_per_hour']:.2f}")
    print(f"  • Average Recovery Latency:      {results['average_recovery_latency_sec']:.2f} seconds")

    print("\n3. Detection Latencies (Time from event onset to alert):")
    for st_name, lat in results["average_detection_latencies_sec"].items():
        print(f"  • {st_name:<26}: {lat:.2f} s")

    print("\n4. Ordinary Reading vs Book Occlusion Discrimination:")
    r_info = results["reading_vs_occlusion_breakdown"]
    print(f"  • Ordinary Reading Accuracy:     {r_info['ordinary_reading_accuracy']*100:.1f}% ({r_info['ordinary_reading_samples']} samples)")
    print(f"  • Reading false alarms (occluded): {r_info['reading_misclassified_as_occluded']}")
    print(f"  • Deliberate Occlusion Accuracy: {r_info['face_occlusion_accuracy']*100:.1f}% ({r_info['face_occlusion_samples']} samples)")
    print(f"  • Occlusion missed as reading:   {r_info['occlusion_misclassified_as_reading']}")

    print("\n5. Confusion Matrix (Active Classes):")
    active_classes = [st for st in EVAL_CLASSES if results["per_class_metrics"][st.name]["support"] > 0]
    header_title = "True \\ Pred"
    print(f"{header_title:<22}" + "".join([f"{st.name[:6]:>7}" for st in active_classes]))
    for gt in active_classes:
        row = f"{gt.name[:21]:<22}" + "".join([f"{confusion[gt][pred]:>7}" for pred in active_classes])
        print(row)

    print("=" * 78 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Evaluate AI Study Focus Monitor Accuracy")
    parser.add_argument("--save-json", type=str, default="evaluation_results.json", help="Path to save results JSON")
    args = parser.parse_args()

    sessions = create_synthetic_test_sessions()
    results, confusion = run_benchmark_evaluation(sessions)
    print_formatted_report(results, confusion)

    if args.save_json:
        with open(args.save_json, "w") as f:
            json.dump(results, f, indent=2)
        print(f"[Info] Full evaluation results saved to: {args.save_json}")


if __name__ == "__main__":
    main()
