#!/usr/bin/env python3
"""
Benchmark Results Analyzer
- Аналізує логи бенчмарку
- Генерує звіти та рекомендації
- Порівнює голоси
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

RESULTS_DIR = Path("/opt/tts/benchmark/results")


def load_latest_results() -> Dict[str, Any]:
    """Load latest benchmark results"""
    summary_file = RESULTS_DIR / "latest_summary.json"
    if not summary_file.exists():
        print("❌ No benchmark results found!")
        print(f"   Run: python styletts2_benchmark.py")
        return None

    with open(summary_file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_rankings() -> List[Dict]:
    """Load voice rankings"""
    rankings_file = RESULTS_DIR / "voice_rankings.json"
    if not rankings_file.exists():
        return []

    with open(rankings_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("rankings", [])


def print_rankings(limit: int = None):
    """Print voice rankings"""
    rankings = load_rankings()
    if not rankings:
        print("❌ No rankings found!")
        return

    print(f"\n{'='*70}")
    print("VOICE RANKINGS")
    print(f"{'='*70}")
    print(f"{'Rank':<5}{'Voice':<35}{'Score':<8}{'Grade':<6}{'CPS':<8}{'Std':<6}")
    print("-" * 70)

    for r in rankings[:limit] if limit else rankings:
        print(f"{r['rank']:<5}{r['voice']:<35}{r['score']:<8.1f}{r['grade']:<6}{r['avg_cps']:<8.1f}{r['std_cps']:<6.2f}")

    print("-" * 70)
    print(f"Total voices: {len(rankings)}")


def print_recommendations():
    """Print voice recommendations by use case"""
    rankings = load_rankings()
    if not rankings:
        return

    # Best overall
    top5 = rankings[:5]

    # Most stable (lowest std)
    stable = sorted([r for r in rankings if r['std_cps'] > 0],
                   key=lambda x: x['std_cps'])[:5]

    # Fastest
    fastest = sorted(rankings, key=lambda x: x['avg_cps'], reverse=True)[:5]

    print(f"\n{'='*70}")
    print("RECOMMENDATIONS")
    print(f"{'='*70}")

    print("\n🏆 TOP 5 OVERALL (best balance):")
    for r in top5:
        print(f"   {r['rank']}. {r['voice']} - Score: {r['score']}, CPS: {r['avg_cps']:.1f}")

    print("\n⚡ FASTEST (highest CPS):")
    for r in fastest:
        print(f"   • {r['voice']} - {r['avg_cps']:.1f} CPS")

    print("\n🎯 MOST STABLE (consistent performance):")
    for r in stable:
        print(f"   • {r['voice']} - Std: {r['std_cps']:.2f}")

    print("\n💡 RECOMMENDED FOR PRODUCTION:")
    # Voice with good balance of score, stability and CPS
    production_candidates = [r for r in rankings if r['score'] >= 60 and r['std_cps'] < 3]
    if production_candidates:
        best = production_candidates[0]
        print(f"   ★ {best['voice']}")
        print(f"     Score: {best['score']} | CPS: {best['avg_cps']:.1f} | Stability: {best['std_cps']:.2f}")


def compare_voices(voice_names: List[str]):
    """Compare specific voices"""
    data = load_latest_results()
    if not data:
        return

    voice_stats = data.get("voice_stats", {})

    print(f"\n{'='*70}")
    print("VOICE COMPARISON")
    print(f"{'='*70}")

    for name in voice_names:
        if name not in voice_stats:
            print(f"\n❌ Voice '{name}' not found in results")
            continue

        stats = voice_stats[name]
        print(f"\n📊 {name}")
        print("-" * 40)

        if stats.get("status") != "ok":
            print("   Status: FAILED")
            continue

        print(f"   Score: {stats['score']}/100 ({stats['grade']})")
        print(f"   CPS: {stats['avg_cps']:.1f} (min: {stats['min_cps']:.1f}, max: {stats['max_cps']:.1f})")
        print(f"   Stability: {stats['std_cps']:.2f}")
        print(f"   Success rate: {stats['success_rate']*100:.1f}%")
        print(f"   Total time: {stats['total_time_sec']:.1f}s")

        if "by_category" in stats:
            print("\n   By category:")
            for cat, cat_stats in stats["by_category"].items():
                print(f"     • {cat}: {cat_stats['avg_cps']:.1f} CPS ({cat_stats['count']} phrases)")


def print_summary():
    """Print benchmark summary"""
    data = load_latest_results()
    if not data:
        return

    print(f"\n{'='*70}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*70}")
    print(f"Run ID: {data.get('run_id')}")
    print(f"Started: {data.get('started')}")
    print(f"Finished: {data.get('finished')}")
    print(f"Total voices tested: {data.get('total_voices')}")

    rankings = data.get("rankings", [])
    if rankings:
        scores = [r['score'] for r in rankings]
        cps_values = [r['avg_cps'] for r in rankings]

        print(f"\nScore statistics:")
        print(f"  Average: {sum(scores)/len(scores):.1f}")
        print(f"  Best: {max(scores):.1f}")
        print(f"  Worst: {min(scores):.1f}")

        print(f"\nCPS statistics:")
        print(f"  Average: {sum(cps_values)/len(cps_values):.1f}")
        print(f"  Best: {max(cps_values):.1f}")
        print(f"  Worst: {min(cps_values):.1f}")

        # Grade distribution
        grades = {}
        for r in rankings:
            g = r['grade']
            grades[g] = grades.get(g, 0) + 1

        print(f"\nGrade distribution:")
        for grade in ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F']:
            count = grades.get(grade, 0)
            if count > 0:
                bar = '█' * count
                print(f"  {grade}: {bar} ({count})")


def export_csv():
    """Export rankings to CSV"""
    rankings = load_rankings()
    if not rankings:
        return

    csv_file = RESULTS_DIR / "rankings.csv"

    lines = ["Rank,Voice,Score,Grade,Avg_CPS,Min_CPS,Max_CPS,Std_CPS,Success_Rate"]
    for r in rankings:
        lines.append(f"{r['rank']},{r['voice']},{r['score']},{r['grade']},{r['avg_cps']},{r.get('min_cps', '')},{r.get('max_cps', '')},{r['std_cps']},{r['success_rate']}")

    with open(csv_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✓ Exported to: {csv_file}")


def main():
    parser = argparse.ArgumentParser(description="Analyze benchmark results")
    parser.add_argument("--rankings", "-r", action="store_true", help="Show rankings")
    parser.add_argument("--top", "-t", type=int, help="Show top N voices")
    parser.add_argument("--recommendations", "-rec", action="store_true", help="Show recommendations")
    parser.add_argument("--compare", "-c", nargs="+", help="Compare specific voices")
    parser.add_argument("--summary", "-s", action="store_true", help="Show summary")
    parser.add_argument("--export", "-e", action="store_true", help="Export to CSV")
    parser.add_argument("--all", "-a", action="store_true", help="Show all reports")
    args = parser.parse_args()

    if args.all or (not any([args.rankings, args.recommendations, args.compare, args.summary, args.export])):
        print_summary()
        print_rankings(10)
        print_recommendations()
    else:
        if args.summary:
            print_summary()
        if args.rankings:
            print_rankings(args.top)
        if args.recommendations:
            print_recommendations()
        if args.compare:
            compare_voices(args.compare)
        if args.export:
            export_csv()


if __name__ == "__main__":
    main()
