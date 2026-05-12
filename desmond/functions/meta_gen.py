"""
meta_gen.py — Metadynamics analysis for Desmond MD trajectories.  |  MOTUS v0.0.1

Parses .kerseq (kernel sequence) and .cvseq (CV sequence) to produce:
  - meta_cv_time.csv        — CV values over time
  - meta_height.csv         — Gaussian height decay over time
  - meta_fes_1d.csv         — 1D free energy surface (if 1 CV)
  - meta_fes_2d.csv         — 2D free energy surface (if 2+ CVs, uses first 2)
  - meta_summary.txt         — Summary statistics

Usage:
  $SCHRODINGER/run python3 meta_gen.py <cms_file> <trj_dir> [OUTDIR]

The script auto-detects .kerseq and .cvseq from the parent directory
of the trajectory directory. Also reads .cfg for CV metadata.
"""
import sys, os, argparse, csv
import numpy as np
from collections import defaultdict

from schrodinger.application.desmond import cms
from schrodinger.application.desmond.meta import MetaDynamicsAnalysis, parse_cvseq


def find_kerseq_cvseq(trj_dir):
    """Auto-detect kerseq and cvseq files from the job directory."""
    job_dir = os.path.dirname(os.path.abspath(trj_dir))
    kerseq = None
    cvseq = None
    
    for f in os.listdir(job_dir):
        fp = os.path.join(job_dir, f)
        if f.endswith('.kerseq') and os.path.isfile(fp):
            kerseq = fp
        elif f.endswith('.cvseq') and os.path.isfile(fp):
            cvseq = fp
    
    return kerseq, cvseq


def find_cfg(job_dir):
    """Find a .cfg file for meta metadata (prefer -out.cfg)."""
    # Prefer -out.cfg (has actual meta config from multisim)
    for f in sorted(os.listdir(job_dir)):
        if f.endswith('-out.cfg'):
            fp = os.path.join(job_dir, f)
            if os.path.isfile(fp):
                return fp
    # Fallback: any .cfg
    for f in os.listdir(job_dir):
        if f.endswith('.cfg') and not f.endswith('.cpt.cfg'):
            fp = os.path.join(job_dir, f)
            if os.path.isfile(fp):
                return fp
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Metadynamics analysis for Desmond trajectories')
    parser.add_argument('cms_file', help='CMS topology file')
    parser.add_argument('trj_dir', help='Trajectory directory')
    parser.add_argument('outdir', nargs='?', default=None,
                        help='Output directory (default: cwd)')
    args = parser.parse_args()

    outdir = args.outdir or '.'
    os.makedirs(outdir, exist_ok=True)

    # Find metadynamics output files
    trj_dir = os.path.abspath(args.trj_dir)
    kerseq, cvseq = find_kerseq_cvseq(trj_dir)
    
    if not kerseq:
        print("⚠  No .kerseq file found — metadynamics was not used in this simulation")
        return 1
    if not cvseq:
        print("⚠  No .cvseq file found — incomplete metadynamics output")
        return 1
    
    job_dir = os.path.dirname(trj_dir)
    cfg_file = find_cfg(job_dir)
    
    print(f"Kerseq: {kerseq}")
    print(f"Cvseq:  {cvseq}")
    if cfg_file:
        print(f"Config: {cfg_file}")

    # ---- Parse CV sequence ----
    print("\nParsing cvseq...")
    cv_data = parse_cvseq(cvseq)
    times = np.array(cv_data.get('time', []))
    n_frames = len(times)
    print(f"  Found {n_frames} CV snapshots")
    
    if n_frames == 0:
        print("⚠  No CV data found")
        return 1

    # Extract CV columns (cv_00, cv_01, ...)
    cv_columns = sorted([k for k in cv_data if k.startswith('cv_')])
    n_cvs = len(cv_columns)
    print(f"  Collective variables: {n_cvs}")
    for cvk in cv_columns:
        vals = cv_data[cvk]
        print(f"    {cvk}: range [{min(vals):.3f}, {max(vals):.3f}]")

    # ---- Parse kernel sequence ----
    print("\nParsing kerseq...")
    try:
        if cfg_file:
            meta = MetaDynamicsAnalysis(kerseq, inp_fname=cfg_file)
        else:
            # No cfg: try loading CMS for metadata
            meta = MetaDynamicsAnalysis(kerseq, key=None)
    except Exception as e:
        print(f"⚠  Could not parse kerseq with cfg: {e}")
        # Fallback: just output CV time data
        meta = None
    
    if meta:
        print(f"  Kernel depositions: {len(meta.time)}")
        print(f"  CV types: {meta.cv}")
        if len(meta.bins) > 0:
            print(f"  FES bins: {meta.bins}")
        if len(meta.ranges) > 0:
            print(f"  CV ranges: {meta.ranges}")

    # ---- Write CV time CSV ----
    cv_time_csv = os.path.join(outdir, 'meta_cv_time.csv')
    with open(cv_time_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        header = ['Time_ps'] + [f'CV_{i}' for i in range(n_cvs)]
        writer.writerow(header)
        for i in range(n_frames):
            row = [times[i]]
            for cvk in cv_columns:
                row.append(cv_data[cvk][i])
            writer.writerow(row)
    print(f"\n✓ {cv_time_csv}")

    # ---- Write height CSV ----
    height_csv = os.path.join(outdir, 'meta_height.csv')
    with open(height_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Time_ps', 'Height_kcal_mol'])
        if meta:
            for t, h in zip(meta.time, meta.height):
                writer.writerow([t, h])
    if meta and len(meta.time) > 0:
        print(f"✓ {height_csv}")

    # ---- Compute FES ----
    if meta and len(meta.time) > 10 and len(meta.bins) > 0:
        print("\nComputing Free Energy Surface...")
        try:
            data, units = meta.computeFES('', units='radians')
            if data:
                ndim = len(meta.bins)
                if ndim == 1:
                    fes_csv = os.path.join(outdir, 'meta_fes_1d.csv')
                    with open(fes_csv, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['CV_0', 'Free_Energy_kcal_mol'])
                        for row in data:
                            writer.writerow([row[0], row[-1]])
                    print(f"✓ {fes_csv}")
                else:
                    fes_csv = os.path.join(outdir, 'meta_fes_%dd.csv' % ndim)
                    with open(fes_csv, 'w', newline='') as f:
                        writer = csv.writer(f)
                        cv_headers = [f'CV_{i}' for i in range(ndim)]
                        writer.writerow(cv_headers + ['Free_Energy_kcal_mol'])
                        for row in data:
                            writer.writerow(row)
                    print(f"✓ {fes_csv}")
        except Exception as e:
            print(f"⚠  FES computation failed: {e}")

    # ---- Summary ----
    summary_txt = os.path.join(outdir, 'meta_summary.txt')
    with open(summary_txt, 'w') as f:
        f.write("── Metadynamics Summary ──\n")
        f.write(f"CV snapshots: {n_frames}\n")
        f.write(f"Number of CVs: {n_cvs}\n")
        for i, cvk in enumerate(cv_columns):
            vals = cv_data[cvk]
            f.write(f"  CV_{i}: mean={np.mean(vals):.4f}, std={np.std(vals):.4f}, "
                    f"range=[{np.min(vals):.4f}, {np.max(vals):.4f}]\n")
        if meta:
            f.write(f"Kernel depositions: {len(meta.time)}\n")
            if len(meta.height) > 0:
                f.write(f"  Height: start={meta.height[0]:.4f}, end={meta.height[-1]:.4f}\n")
            if meta.cv:
                f.write(f"  CV types: {', '.join(meta.cv)}\n")
    print(f"✓ {summary_txt}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
