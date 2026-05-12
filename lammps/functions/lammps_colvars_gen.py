#!/usr/bin/env python3
"""
Generate LAMMPS COLVARS config for metadynamics
Usage: python3 lammps_colvars_gen.py [args] -o colvars.meta
"""
import sys, argparse

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dist", nargs=2, type=int)
    p.add_argument("--angle", nargs=3, type=int)
    p.add_argument("--dihedral", nargs=4, type=int)
    p.add_argument("--height", type=float, default=0.5)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--biasfactor", type=float, default=0)
    p.add_argument("--temp", type=float, default=300.0)
    p.add_argument("--timestep", type=float, default=0.5)
    p.add_argument("-o", "--output", default="colvars.meta")
    args = p.parse_args()

    cv_blocks = []
    cv_names = []
    cv_sigmas = []

    if args.dist:
        cv_blocks.append(f"""colvar {{
  name d
  distance {{
    group1 {{ atomNumbers {args.dist[0]} }}
    group2 {{ atomNumbers {args.dist[1]} }}
  }}
}}""")
        cv_names.append("d")
        cv_sigmas.append("0.1")
    if args.angle:
        cv_blocks.append(f"""colvar {{
  name a
  angle {{
    group1 {{ atomNumbers {args.angle[0]} {args.angle[1]} {args.angle[2]} }}
  }}
}}""")
        cv_names.append("a")
        cv_sigmas.append("0.1")
    if args.dihedral:
        cv_blocks.append(f"""colvar {{
  name t
  dihedral {{
    group1 {{ atomNumbers {args.dihedral[0]} {args.dihedral[1]} {args.dihedral[2]} {args.dihedral[3]} }}
  }}
}}""")
        cv_names.append("t")
        cv_sigmas.append("0.1")

    if not cv_blocks:
        print("ERROR: No CVs specified", file=sys.stderr)
        sys.exit(1)

    hill_interval = int(args.interval * 1000 / args.timestep)
    traj_freq = hill_interval * 10
    restart_freq = hill_interval * 100

    if args.biasfactor > 0:
        # biasTemperature = T * (biasFactor - 1)
        bt = args.temp * (args.biasfactor - 1.0)
        wt = f"wellTempered on\n    biasTemperature {bt:.1f}"
    else:
        wt = ""

    config = f"""colvarsTrajFrequency {traj_freq}
colvarsRestartFrequency {restart_freq}

{chr(10).join(cv_blocks)}

metadynamics {{
    name meta
    colvars {" ".join(cv_names)}
    hillWeight {args.height}
    hillWidth {" ".join(cv_sigmas)}
    newHillFrequency {hill_interval}
    {wt}
}}"""

    with open(args.output, "w") as f:
        f.write(config)
    print(f"colvars.meta: {len(cv_blocks)} CV(s), height={args.height}, biasfactor={args.biasfactor}")

if __name__ == "__main__":
    main()
