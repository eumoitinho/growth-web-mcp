"""Aggregate sanitized journey reports; missing journeys never count as coverage."""
import argparse
from collections import Counter
import json
from pathlib import Path
import yaml


def summarize(suite, reports):
    latest = {}
    for report in reports:
        latest[report['journey_id']] = report
    statuses = {j['id']:latest.get(j['id'],{}).get('status','NOT_TESTED') for j in suite['journeys']}
    counts = Counter(statuses.values())
    total = len(statuses)
    return {'journeys':statuses,'counts':dict(counts),'total':total,
            'pass_rate':counts['PASS']/total if total else 0,
            'coverage':sum(s not in ('NOT_TESTED','NOT_APPLICABLE') for s in statuses.values())/total if total else 0,
            'healthy':bool(total) and all(s in ('PASS','NOT_APPLICABLE') for s in statuses.values())}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',required=True)
    parser.add_argument('--reports',required=True,help='Directory searched recursively for report.json; newest file per journey wins')
    parser.add_argument('--out',default='artifacts/health.json')
    args=parser.parse_args()
    paths=sorted(Path(args.reports).rglob('report.json'),key=lambda p:p.stat().st_mtime_ns)
    result=summarize(yaml.safe_load(Path(args.suite).read_text()),[json.loads(p.read_text()) for p in paths])
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['healthy'] else 1)


if __name__=='__main__':main()
