"""Run or resume one end-to-end journey, preserving pending ingestion explicitly."""
import argparse
import asyncio
import json
from pathlib import Path

import yaml
from growth_qa.browser import run_browser
from growth_qa.collect import collect
from growth_qa.reconcile import reconcile, write_report


async def execute(args):
    output = Path(args.out)
    output.mkdir(parents=True,exist_ok=True)
    path = output/'evidence.json'
    suite = yaml.safe_load(Path(args.suite).read_text())
    if args.resume:
        evidence = json.loads(path.read_text())
    else:
        if path.exists():
            raise ValueError('Evidence already exists. Use --resume or a new output directory.')
        if not args.settings or not args.journey:
            raise ValueError('--settings and --journey are required for new runs')
        evidence = await run_browser(suite,args.journey,yaml.safe_load(Path(args.settings).read_text()),args.allow_submissions,str(path))
    if args.collectors:
        evidence = await collect(evidence,yaml.safe_load(Path(args.collectors).read_text()))
        path.write_text(json.dumps(evidence,indent=2)+'\n')
    report = reconcile(suite,evidence)
    write_report(report,output)
    print(f"{report['journey_id']}: {report['status']} ({output / 'report.md'})")
    return {'PASS':0,'FAIL':1,'ERROR':1,'PENDING':2,'NOT_APPLICABLE':3}[report['status']]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',required=True)
    parser.add_argument('--journey')
    parser.add_argument('--settings')
    parser.add_argument('--collectors')
    parser.add_argument('--out',required=True)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--allow-submissions',action='store_true')
    raise SystemExit(asyncio.run(execute(parser.parse_args())))


if __name__=='__main__':main()
