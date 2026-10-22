"""M4: build blind-rating manifest.json — A_full vs random (B/C/D), blind L/R.

Usage:
  python3 manifest_gen.py runs/ rating/manifest.json --n-trials 20 --seed 7
  then serve the rating page over http (fetch needs it):
  cd rating && python3 -m http.server 8940
  open http://127.0.0.1:8940/?manifest=manifest.json&rater=alice
"""
import argparse
import json
import os
import random


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs_dir")
    ap.add_argument("out")
    ap.add_argument("--n-trials", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--replay-ext", default=".mp4",
                    help="extension of exported replay files (webm or mp4)")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    # replays exported by m4/replay/index.html are expected at runs_dir/../replays/
    # naming: {config}_{seed}_replay{ext}; fall back to jsonl names if no replays yet
    replays_dir = os.path.join(os.path.dirname(args.runs_dir.rstrip("/")), "replays")
    have_replays = os.path.isdir(replays_dir) and any(
        f.endswith(args.replay_ext) for f in os.listdir(replays_dir))
    ext = args.replay_ext if have_replays else ".jsonl"
    base = "../replays/" if have_replays else os.path.relpath(args.runs_dir, os.path.dirname(args.out)) + "/"

    pool = {}
    suffix = "_replay" if have_replays else ""
    for fn in sorted(os.listdir(args.runs_dir)):
        if fn.endswith(".jsonl") and "_" in fn:
            cfg = fn.rsplit("_", 1)[0]
            name = fn[:-6] + suffix + ext
            if have_replays and not os.path.exists(os.path.join(replays_dir, name)):
                continue  # replay not rendered yet; don't pair unrendered runs
            pool.setdefault(cfg, []).append(name)

    a_runs = pool.get("A_full", [])
    others = {k: v for k, v in pool.items() if k != "A_full"}
    if not a_runs or not others:
        raise SystemExit(f"need A_full runs and at least one ablation; got {sorted(pool)}")
    flats = [f for v in others.values() for f in v]

    trials = []
    for i in range(args.n_trials):
        a = rng.choice(a_runs)
        x = rng.choice(flats)
        pair = [(a, "A_full"), (x, x.rsplit("_", 1)[0])]
        rng.shuffle(pair)
        trials.append({
            "left": base + pair[0][0],
            "right": base + pair[1][0],
            "truth": {"left": pair[0][1], "right": pair[1][1]},
        })
    manifest = {"experiment": "FlyLaya M4 blind rating (plan section 4, criterion 2)",
                "n_trials": args.n_trials, "trials": trials}
    with open(args.out, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"wrote {args.out}: {args.n_trials} trials; sources ext={ext} base={base}")


if __name__ == "__main__":
    main()
