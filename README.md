<p align="center">
  <img src="docs/images/MOTUS-top.png" alt="MOTUS" width="800">
</p>

<h3 align="center"><em>Molecular Dynamics Automation Agent — Post-Processing &amp; Publication-Ready Figures</em></h3>

<p align="center">
  <strong>Version 0.0.1</strong> &nbsp;|&nbsp;
  Desmond MD ✅ &bull; GROMACS ✅ &bull; LAMMPS ✅
</p>

---

## What is MOTUS?

**MOTUS** is a unified, automated post-processing pipeline for molecular dynamics (MD) simulations. It supports **three MD engines** — **Schrödinger Desmond**, **GROMACS**, and **LAMMPS** — with a consistent CLI interface. Each engine gets its own MD launcher, analysis orchestrator, and publication-quality figure generator.

The long-term vision: a **fully automated MD agent** that handles analysis and figure generation across Desmond, GROMACS, and LAMMPS with a single, consistent interface.

<p align="center">
  <img src="docs/images/MOTUS-middle.png" alt="MOTUS Overview" width="700">
</p>

---

## Quick Start

### Desmond

```bash
# MD production run
./desmond/desmond-md.sh desmond_setup_my-system -w

# Full analysis + figures
./desmond/desmond-analysis.sh desmond_md_job_my-system --plot

# Figures only (re-plot from existing CSV)
./desmond/desmond-analysis.sh desmond_md_job_my-system --fig-only
```

### GROMACS

```bash
# MD production run (EM → NVT → NPT → Prod)
./gromacs/gromacs-md.sh my-system.gro my-system.top

# Full analysis + figures
./gromacs/gromacs-analysis.sh md_output/ --plot

# Enhanced sampling
./gromacs/gromacs-metadynamics.sh md_output/
./gromacs/gromacs-umbrella.sh md_output/ -d 0.05 -w 12 -s 0.3
```

### LAMMPS

```bash
# MD production run
./lammps/lammps-md.sh system.data

# Analysis + figures
./lammps/lammps-analysis.sh md_output/

# Metadynamics with COLVARS
./lammps/lammps-metadynamics.sh md_output/
```

**Requirements:**
- Linux; Schrödinger Suite (for Desmond), GROMACS, LAMMPS
- Python 3.8+ with `numpy`, `matplotlib`, `scipy`
- GPU recommended

---

## Features Matrix

| Feature | Desmond | GROMACS | LAMMPS |
|:--------|:-------:|:-------:|:------:|
| **MD Production** (EM + Equil + Prod) | ✅ | ✅ | ✅ |
| **Metadynamics** (Well-Tempered / Standard) | ✅ (native) | ✅ (PLUMED) | ✅ (COLVARS) |
| **Umbrella Sampling + WHAM** | — | ✅ | — |
| Energy / T / P / Vol / Density | ✅ | ✅ | ✅ |
| H-Bond Analysis | ✅ | ✅ | — |
| RMSD / RMSF | ✅ | ✅ | ✅ |
| RDF g(r) + Coordination Number n(r) | ✅ | ✅ | ✅ |
| Radius of Gyration (Rg) | ✅ | ✅ | — |
| SASA | ✅ | ✅ | — |
| SIMA (Simulation Interactions Diagram) | ✅ | — | — |
| 1D / 2D Density Cross-Sections | ✅ | ✅ | — |
| Distance Monitoring | ✅ | — | — |
| Water Residence Time | ✅ | — | — |
| **Conformational Clustering + PCA** | ✅ | ✅ | ✅ |
| Molecular Dipole Moment | ✅ | — | — |
| Free Volume / Void Analysis | ✅ | — | — |
| Dihedral / Angle Analysis | — | ✅ | — |
| Contact Matrix | — | ✅ | — |
| **CMS↔GROMACS/LAMMPS Converter** | `cms2gmx.py` | `cms2lmp.py` | — |

---

## Conformational Clustering — ML-Style PCA Scatter

Hierarchical RMSD clustering + PCA projection with **convex hulls**, **diamond cluster centroids**, and **time-evolution coloring** — journal-quality visualization.

<p align="center">
  <img src="docs/images/cluster_pca_scatter.png" alt="PCA Scatter" width="650">
</p>

Multi-panel dashboard: **bar chart + pie chart** for cluster populations.

<p align="center">
  <img src="docs/images/cluster_population.png" alt="Cluster Population" width="650">
</p>

---

## Figure Output

All figures saved in `<md_output>/analysis/figures/`:

| Format | Resolution | Purpose |
|--------|-----------|---------|
| **`.pdf`** | Vector | Journal submission, LaTeX inclusion |
| **`.png`** | 300 DPI | Quick preview, presentations, GitHub |

**Styling:**
- Arial / DejaVu Sans font family
- Nature-inspired 8-color palette
- Dual Y-axis with color coding (RDF, dipole)
- Convex hulls + centroids for clustering
- Legend outside the plot frame (clean look)
- Tight bounding boxes for direct LaTeX inclusion

---

## Repository Structure

```
motus/
├── README.md                      ← You are here
├── LICENSE                        ← MIT
├── .gitignore
├── docs/images/                   ← Screenshots for documentation
│
├── desmond/                       ← Desmond engine scripts
│   ├── desmond-md.sh              ← MD job submission & monitoring
│   ├── desmond-analysis.sh        ← Post-processing pipeline (15 modules)
│   ├── desmond-metadynamics.sh    ← MetaD enhanced sampling
│   └── functions/
│       ├── desmond_plot.py        ← Publication-quality figure generator
│       ├── sima_gen.py            ← SIMA data generator
│       ├── sima_plot.py           ← SIMA figure generator
│       ├── rdf_gen.py             ← RDF + coordination number
│       ├── density_gen.py         ← 1D/2D density cross-sections
│       ├── rg_gen.py              ← Radius of gyration
│       ├── dist_gen.py            ← Distance monitoring
│       ├── water_res_gen.py       ← Water residence time
│       ├── cluster_gen.py         ← Conformational clustering + PCA
│       ├── dipole_gen.py          ← Molecular dipole moment
│       ├── freevol_gen.py         ← Free volume / void analysis
│       ├── meta_gen.py            ← Metadynamics CV setup helper
│       └── esp_gen.py             ← Electrostatic potential (WIP)
│
├── gromacs/                       ← GROMACS engine scripts
│   ├── gromacs-md.sh              ← MD production (EM→NVT→NPT→Prod)
│   ├── gromacs-analysis.sh        ← Post-processing pipeline (9 modules)
│   ├── gromacs-metadynamics.sh    ← PLUMED MetaD pipeline
│   ├── gromacs-umbrella.sh        ← Umbrella sampling
│   ├── gromacs-wham.sh            ← WHAM PMF reconstruction
│   ├── gromacs-cluster.sh         ← GROMOS conformational clustering
│   ├── gromacs-pca.sh             ← PCA / essential dynamics
│   ├── gromacs-dihedral.sh        ← Dihedral angle analysis
│   ├── gromacs-contacts.sh        ← Distance contact maps
│   └── functions/
│       ├── gromacs_plot.py        ← Figure generator (13 plot types)
│       └── gromacs_meta_gen.py    ← PLUMED input generator
│
├── lammps/                        ← LAMMPS engine scripts
│   ├── lammps-md.sh               ← MD production
│   ├── lammps-analysis.sh         ← Post-processing pipeline
│   ├── lammps-metadynamics.sh     ← COLVARS MetaD pipeline
│   └── functions/
│       ├── lammps_plot.py         ← Figure generator (6 plot types)
│       └── lammps_colvars_gen.py  ← COLVARS input generator
│
└── converters/                    ← Cross-engine CMS converters
    ├── cms2gmx.py                 ← Desmond CMS → GROMACS topology
    └── cms2lmp.py                 ← Desmond CMS → LAMMPS data file
```

---

## Roadmap

| Milestone | Status |
|-----------|--------|
| Desmond post-processing (15 analyses) | ✅ |
| PCA clustering scatter with convex hulls | ✅ |
| GROMACS MD pipeline + 9 analysis scripts | ✅ |
| LAMMPS MD pipeline + 3 scripts | ✅ |
| CMS → GROMACS/LAMMPS topology converter | ✅ |
| PLUMED MetaD (GROMACS) | ✅ |
| COLVARS MetaD (LAMMPS) | ✅ |
| Umbrella sampling + WHAM (GROMACS) | ✅ |
| Cross-engine cluster plots (Desmond-style) | ✅ |
| Solvent structure analysis (sorient/spatial/h2order) | 🚧 Planned |
| Electrostatic Potential (ESP) | 🚧 Planned |
| Unified MOTUS CLI | 🚧 Planned |
| AI-driven analysis & interpretation | 🚧 Planned |

---

## License

MIT — see [LICENSE](LICENSE) file.

---

## Citation

If you use MOTUS in your research, please cite:

```
MOTUS: Molecular Dynamics Automation Agent. Version 0.0.1.
https://github.com/X-Hydrogen/motus
```

---

<p align="center">
  <sub>Built for computational chemists who value their time.</sub>
</p>
