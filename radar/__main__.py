"""Default: weekly planning. Old daily renderer is available only with --legacy."""
import argparse
import sys
from datetime import date

from . import collect, deliver, rank, script, video, weekly, engine
from .common import run_dir

STAGES = {"collect": collect.run, "rank": rank.run, "script": script.run,
          "video": video.run, "deliver": deliver.run}


def main():
    if sys.argv[1:2] == ['run']:
        return engine.main(sys.argv[2:])
    if '--legacy' not in sys.argv[1:]:
        return weekly.main(sys.argv[1:])
    ap = argparse.ArgumentParser()
    ap.add_argument('--legacy', action='store_true', help='explicit compatibility mode; not the approved weekly workflow')
    ap.add_argument("--day", default=date.today().isoformat())
    ap.add_argument("--from", dest="start", default="collect", choices=STAGES)
    ap.add_argument("--smoke", action="store_true", help="short end-to-end briefing with bounded collection")
    args = ap.parse_args()
    d = run_dir(args.day)
    stages = {"collect": collect.run, "rank": rank.run, "script": script.run,
              "video": video.run, "deliver": deliver.run}
    if args.smoke:
        stages.update(collect=lambda d: collect.run(d, paper_days=14, max_pages=8),
                      rank=lambda d: rank.run(d, top=3),
                      script=lambda d: script.run(d, target_chars=(450, 650)))
    names = list(stages)
    for name in names[names.index(args.start):]:
        print(f"[{name}]")
        stages[name](d)


if __name__ == "__main__":
    main()
