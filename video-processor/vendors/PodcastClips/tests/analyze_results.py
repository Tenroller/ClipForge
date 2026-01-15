#!/usr/bin/env python3
"""
Face Detection Testing Framework - Results Analyzer

Analyzes JSON outputs from run_all_tests.py and generates summary reports.

Usage:
    python analyze_results.py
    python analyze_results.py --html  # Generate HTML report
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class AnalysisSummary:
    """Summary of analysis across all tests."""
    total_videos: int = 0
    passed: int = 0
    failed: int = 0
    no_expected: int = 0
    
    avg_face_coverage: float = 0.0
    avg_face_tracks: float = 0.0
    avg_processing_time: float = 0.0
    
    common_issues: Dict[str, int] = None
    
    def __post_init__(self):
        if self.common_issues is None:
            self.common_issues = {}


def load_results(outputs_dir: Path) -> List[Dict]:
    """Load all JSON result files."""
    results = []
    
    # Try combined results first
    combined_path = outputs_dir / 'all_results.json'
    if combined_path.exists():
        with open(combined_path) as f:
            results = json.load(f)
        return results
    
    # Otherwise load individual files
    for json_file in outputs_dir.glob('*_data.json'):
        with open(json_file) as f:
            results.append(json.load(f))
    
    return results


def analyze_results(results: List[Dict]) -> AnalysisSummary:
    """Analyze all test results and compute summary statistics."""
    summary = AnalysisSummary(total_videos=len(results))
    
    coverages = []
    tracks = []
    times = []
    
    for r in results:
        # Count pass/fail
        if r.get('expected_mode') is None:
            summary.no_expected += 1
        elif r.get('mode_match', False):
            summary.passed += 1
        else:
            summary.failed += 1
        
        # Collect metrics
        coverages.append(r.get('frame_coverage_pct', 0))
        tracks.append(r.get('face_track_count', 0))
        times.append(r.get('processing_time_seconds', 0))
        
        # Count issues
        for issue in r.get('issues', []):
            issue_type = issue.split(':')[0]
            summary.common_issues[issue_type] = summary.common_issues.get(issue_type, 0) + 1
    
    if results:
        summary.avg_face_coverage = sum(coverages) / len(coverages)
        summary.avg_face_tracks = sum(tracks) / len(tracks)
        summary.avg_processing_time = sum(times) / len(times)
    
    return summary


def print_analysis(results: List[Dict], summary: AnalysisSummary):
    """Print detailed analysis to console."""
    print("\n" + "="*80)
    print("FACE DETECTION TEST ANALYSIS")
    print("="*80)
    
    # Overall stats
    print(f"\n📊 OVERALL STATISTICS")
    print(f"   Total videos tested: {summary.total_videos}")
    print(f"   Passed (mode match): {summary.passed} ✓")
    print(f"   Failed (mode mismatch): {summary.failed} ✗")
    print(f"   No expected mode: {summary.no_expected}")
    print(f"\n   Avg face coverage: {summary.avg_face_coverage:.1f}%")
    print(f"   Avg face tracks: {summary.avg_face_tracks:.1f}")
    print(f"   Avg processing time: {summary.avg_processing_time:.1f}s")
    
    # Per-video details
    print(f"\n📋 PER-VIDEO BREAKDOWN")
    print("-"*80)
    
    for r in results:
        video = r.get('video_name', 'Unknown')
        expected = r.get('expected_mode', 'N/A')
        detected = r.get('detected_mode', 'Unknown')
        match = r.get('mode_match', False)
        coverage = r.get('frame_coverage_pct', 0)
        tracks = r.get('face_track_count', 0)
        
        status = "✓" if match else "✗" if expected != 'N/A' else "?"
        print(f"\n{status} {video}")
        print(f"   Expected: {expected} → Detected: {detected}")
        print(f"   Face tracks: {tracks}, Coverage: {coverage:.1f}%")
        
        # Face details
        for fm in r.get('face_metrics', []):
            print(f"   Face {fm['face_id']}: size={fm['avg_size_ratio']*100:.3f}%, conf={fm['confidence_avg']:.2f}, speech={fm['speech_correlation']:.2f}")
        
        # Mode segments
        segments = r.get('mode_segments', [])
        if segments:
            print(f"   Segments: ", end="")
            seg_strs = [f"{s['mode']}({s['start']:.1f}-{s['end']:.1f}s)" for s in segments]
            print(", ".join(seg_strs))
        
        # Issues
        for issue in r.get('issues', []):
            print(f"   ⚠ {issue}")
    
    # Common issues
    if summary.common_issues:
        print(f"\n⚠ COMMON ISSUES")
        print("-"*40)
        for issue_type, count in sorted(summary.common_issues.items(), key=lambda x: -x[1]):
            print(f"   {issue_type}: {count} occurrence(s)")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS")
    print("-"*40)
    
    if summary.avg_face_coverage < 50:
        print("   • Low face coverage detected. Consider:")
        print("     - Lowering min_face_size_ratio for small faces")
        print("     - Using YOLO person detection fallback")
    
    if 'INSUFFICIENT_FACES' in summary.common_issues:
        print("   • Split-screen detection failing due to missing faces:")
        print("     - Check if faces are too small or occluded")
        print("     - Review face separation scoring")
    
    if 'LOW_CONFIDENCE' in summary.common_issues:
        print("   • Low confidence detections:")
        print("     - May indicate difficult lighting or angles")
        print("     - Consider face detector tuning")
    
    if summary.failed == 0 and summary.total_videos > 0:
        print("   ✓ All tests passed! No issues detected.")
    
    print("\n" + "="*80)


def generate_html_report(results: List[Dict], summary: AnalysisSummary, output_path: Path):
    """Generate HTML report with embedded visualization links."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Face Detection Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #1a1a1a; color: #fff; }}
        h1 {{ color: #4fc3f7; }}
        h2 {{ color: #81c784; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #444; padding: 12px; text-align: left; }}
        th {{ background: #2d2d2d; }}
        tr:nth-child(even) {{ background: #252525; }}
        .pass {{ color: #4caf50; }}
        .fail {{ color: #f44336; }}
        .metric {{ background: #2d2d2d; padding: 20px; margin: 10px 0; border-radius: 8px; }}
        .issue {{ color: #ff9800; margin: 5px 0; }}
        video {{ max-width: 100%; margin: 10px 0; }}
    </style>
</head>
<body>
    <h1>🎬 Face Detection Test Report</h1>
    
    <div class="metric">
        <h2>📊 Summary</h2>
        <table>
            <tr><td>Total Videos</td><td>{summary.total_videos}</td></tr>
            <tr><td>Passed</td><td class="pass">{summary.passed}</td></tr>
            <tr><td>Failed</td><td class="fail">{summary.failed}</td></tr>
            <tr><td>Avg Coverage</td><td>{summary.avg_face_coverage:.1f}%</td></tr>
            <tr><td>Avg Face Tracks</td><td>{summary.avg_face_tracks:.1f}</td></tr>
        </table>
    </div>
    
    <h2>📋 Test Results</h2>
    <table>
        <tr>
            <th>Video</th>
            <th>Expected</th>
            <th>Detected</th>
            <th>Status</th>
            <th>Coverage</th>
            <th>Faces</th>
        </tr>
"""
    
    for r in results:
        match = r.get('mode_match', False)
        status_class = 'pass' if match else 'fail'
        status_text = '✓ Pass' if match else '✗ Fail'
        
        html += f"""
        <tr>
            <td>{r.get('video_name', 'Unknown')}</td>
            <td>{r.get('expected_mode', 'N/A')}</td>
            <td>{r.get('detected_mode', 'Unknown')}</td>
            <td class="{status_class}">{status_text}</td>
            <td>{r.get('frame_coverage_pct', 0):.1f}%</td>
            <td>{r.get('face_track_count', 0)}</td>
        </tr>
"""
    
    html += """
    </table>
    
    <h2>⚠ Issues Detected</h2>
"""
    
    all_issues = []
    for r in results:
        for issue in r.get('issues', []):
            all_issues.append(f"[{r.get('video_name', 'Unknown')}] {issue}")
    
    if all_issues:
        for issue in all_issues:
            html += f'    <p class="issue">• {issue}</p>\n'
    else:
        html += '    <p class="pass">No issues detected!</p>\n'
    
    html += """
</body>
</html>
"""
    
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"HTML report saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Analyze face detection test results")
    parser.add_argument('--html', action='store_true', help='Generate HTML report')
    args = parser.parse_args()
    
    outputs_dir = Path(__file__).parent / 'outputs'
    
    if not outputs_dir.exists():
        print(f"No outputs directory found: {outputs_dir}")
        print("Run 'python run_all_tests.py' first to generate test results.")
        return
    
    # Load results
    results = load_results(outputs_dir)
    
    if not results:
        print("No test results found. Run 'python run_all_tests.py' first.")
        return
    
    # Analyze
    summary = analyze_results(results)
    
    # Print to console
    print_analysis(results, summary)
    
    # Generate HTML if requested
    if args.html:
        html_path = outputs_dir / 'report.html'
        generate_html_report(results, summary, html_path)


if __name__ == "__main__":
    main()
