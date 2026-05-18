#!/usr/bin/env python3
"""Methane hydrate system builder — United-atom → now all-atom. See previous version."""
import os, sys, math, argparse, subprocess
from pathlib import Path

GMXRC = "/home/xenon/tools/gromacs-2026/bin/GMXRC"
METHANE_GRO = """Methane AA
    5
    1CH4      C    1   0.000   0.000   0.000
    1CH4     H1    2   0.000   0.000   0.109
    1CH4     H2    3   0.103   0.000  -0.036
    1CH4     H3    4  -0.051  -0.089  -0.036
    1CH4     H4    5  -0.051   0.089  -0.036
   2.00000   2.00000   2.00000
"""

def run_gmx(cmd, cwd=None):
    wrapped = f'source "{GMXRC}" 2>/dev/null && {cmd}'
    r = subprocess.run(["bash", "-c", wrapped], cwd=cwd or os.getcwd(), capture_output=True, text=True, timeout=120)
    return r.returncode == 0

def count_water(gro_path):
    with open(gro_path) as f: lines = f.readlines()
    return sum(1 for l in lines[2:-1] if "SOL" in l) // 3

def build_topology(outdir, n_methane, n_water):
    with open(outdir / "topol.top", "w") as f:
        f.write('#include "oplsaa.ff/forcefield.itp"\n#include "oplsaa.ff/spce.itp"\n#include "oplsaa.ff/methane.itp"\n\n[ System ]\nMethane + Water\n\n[ Molecules ]\n')
        f.write(f'CH4    {n_methane}\nSOL    {n_water}\n')

def build_dissolved(args):
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    nm, bx = args.n_methane, args.box_size
    run_gmx(f"gmx solvate -cs spc216.gro -o water.gro -box {bx} {bx} {bx}", str(out))
    (out / "ch4.gro").write_text(METHANE_GRO)
    for box_extra in [0.0, 0.5, 1.0]:
        if box_extra > 0:
            run_gmx(f"gmx solvate -cs spc216.gro -o water.gro -box {bx+box_extra} {bx+box_extra} {bx+box_extra}", str(out))
            (out / "system.gro").unlink(missing_ok=True)
        if run_gmx(f"gmx insert-molecules -f water.gro -ci ch4.gro -nmol {nm} -o system.gro -try 100 -radius 0.15", str(out)) and (out / "system.gro").exists():
            n_water = count_water(out / "system.gro")
            build_topology(out, nm, n_water)
            for f in ["water.gro", "ch4.gro"]: (out / f).unlink(missing_ok=True)
            print(f"Built: {nm} CH4 + {n_water} H2O  ->  {out}/")
            return True
    print("ERROR: insert-molecules failed")
    return False

def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="mode")
    s1 = sp.add_parser("dissolved"); s1.add_argument("--n_methane", type=int, default=30); s1.add_argument("--box_size", type=float, default=3.0); s1.add_argument("--out", required=True)
    args = p.parse_args()
    ok = build_dissolved(args) if args.mode == "dissolved" else False
    sys.exit(0 if ok else 1)

if __name__ == "__main__": main()
