<p align="center">
  <img src="docs/images/MOTUS-top.png" alt="MOTUS" width="800">
</p>

<h3 align="center"><em>Molecular Dynamics Automation Agent — From Atoms to Insights, in One Command</em></h3>

<p align="center">
  <strong>Version 0.0.2</strong> &nbsp;|&nbsp;
  Desmond MD ✅ &bull; GROMACS ✅ &bull; LAMMPS ✅
</p>

---

## What is MOTUS?

**MOTUS** is a unified molecular simulation analysis platform that transforms raw MD trajectory data into **publication-ready figures and quantitative insights** — automatically, across three industry-standard engines.

### Why Molecular Dynamics Matters

Molecular dynamics simulations are a cornerstone of modern science and engineering. By tracking every atom's motion at femtosecond resolution, MD reveals the invisible machinery behind:

- **⚡ Energy Storage** — electrolyte structure, ion transport mechanisms, and electrode-electrolyte interfaces in next-generation batteries
- **🧬 Drug Discovery** — protein-ligand binding free energies, conformational selection, and solvation effects that govern drug efficacy
- **🧪 Catalysis** — reaction pathways, transition states, and solvent effects in homogeneous and heterogeneous catalysis
- **🛡️ Materials Design** — polymer mechanics, membrane permeability, and self-assembly of functional nanomaterials
- **🌍 Climate & Geochemistry** — CO₂ capture solvents, mineral dissolution kinetics, and atmospheric aerosol chemistry

Across all these fields, the bottleneck is the same: **turning terabytes of simulation data into interpretable, publication-quality results**. MOTUS eliminates this bottleneck.

### What MOTUS Does

One command. Three engines. Fifteen analysis types. Zero manual plotting.

```bash
# From raw trajectory to complete analysis package
./desmond/desmond-analysis.sh desmond_md_job_my-system --plot
# → energy, Hbonds, RDF, density, dipole, clustering, PCA, SIMA...
# → all figures in PDF (vector) + PNG (300 DPI)
# → < 2 minutes on GPU
```

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

## Figure Gallery

All figures below were generated **fully automatically** by MOTUS from a single Desmond MD trajectory of a urea + phosphate aqueous solution. Click any engine name for the complete per-engine gallery with detailed figure descriptions.

| Engine | Gallery | Figures |
|--------|---------|---------|
| **Desmond** | [`docs/images/desmond/`](docs/images/desmond/README.md) | 23 figures · 15 analysis types |
| **GROMACS** | [`docs/images/gromacs/`](docs/images/gromacs/README.md) | 8 figures · 7 analysis types |
| **LAMMPS** | [`docs/images/lammps/`](docs/images/lammps/README.md) | 5 figures · 4 analysis types |

---

### Conformational Landscape — PCA Projection with Convex Hulls

Hierarchical RMSD clustering + PCA projection. Each cluster gets a **convex hull outline** and a **diamond centroid marker**. Point size grows with simulation time — small dots = early frames, large = late. Legend placed outside the plot frame.

<p align="center">
  <img src="docs/images/desmond/cluster_pca_scatter.png" alt="PCA Scatter" width="650">
</p>

---

### Thermodynamic Monitoring — Energy & Ensemble Stability

Multi-panel time series: Temperature (K), Pressure (bar), Potential Energy (kcal/mol), Volume (Å³). Dashed lines mark ensemble averages. Validates thermostat/barostat convergence at a glance.

<p align="center">
  <img src="docs/images/desmond/energy_timeseries.png" alt="Energy Timeseries" width="650">
</p>

---

### Solvent Structure — Water Shell Classification & RDF

**Left:** Three-layer water classification — bound (<3.5 Å), 2nd shell (3.5–5 Å), free (>5 Å) — as stacked area chart + pie chart. **Right:** Radial distribution function g(r) with coordination number n(r) on dual Y-axes for every element pair.

<p align="center">
  <img src="docs/images/desmond/water_shells.png" alt="Water Shells" width="400">
  <img src="docs/images/desmond/rdf_elements.png" alt="Element-Pair RDF" width="400">
</p>

---

### Molecular Properties — Dipole, Free Volume, and Ligand Behavior

**Left:** Total dipole moment components (X/Y/Z) over time — reveals charge redistribution and polarization dynamics. **Right:** SIMA ligand properties dashboard — RMSD, SASA, PSA, MolSA, and intramolecular H-bonds with ±1σ bands.

<p align="center">
  <img src="docs/images/desmond/dipole_components.png" alt="Dipole Components" width="400">
  <img src="docs/images/desmond/sima_properties_L-Properties.png" alt="SIMA Properties" width="400">
</p>

---

### Density Mapping — 1D Profiles & 2D Cross-Sections

**Left:** 1D relative density profiles along X/Y/Z axes — flat profiles confirm well-equilibrated homogeneous systems. **Right:** 2D density heatmap in the XY plane — identifies anisotropic packing, phase separation, or interfacial structure.

<p align="center">
  <img src="docs/images/desmond/density_1d_all.png" alt="1D Density" width="400">
  <img src="docs/images/desmond/density_2d_all_XY.png" alt="2D Density XY" width="400">
</p>

---

### Cluster Populations & Timeline

**Left:** Bar + pie chart of RMSD-based conformational cluster populations. **Right:** Stacked color bands showing which conformational state the system occupies at each point in time — transitions appear as band boundaries.

<p align="center">
  <img src="docs/images/desmond/cluster_population.png" alt="Cluster Population" width="400">
  <img src="docs/images/desmond/cluster_timeline.png" alt="Cluster Timeline" width="400">
</p>

---

### Free Volume & Void Analysis

Free volume (Å³) probed by a rolling sphere + fractional free volume (FFV %). Essential for predicting gas permeability, ion conductivity, and mechanical properties of polymers and electrolytes.

<p align="center">
  <img src="docs/images/desmond/free_volume.png" alt="Free Volume" width="650">
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
├── docs/images/                   ← Documentation screenshots
│   ├── MOTUS-top.png              ← Banner
│   ├── MOTUS-middle.png           ← Overview diagram
│   ├── desmond/                   ← Desmond figure gallery (+ README)
│   ├── gromacs/                   ← GROMACS figure gallery (+ README)
│   └── lammps/                    ← LAMMPS figure gallery (+ README)
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
MOTUS: Molecular Dynamics Automation Agent. Version 0.0.2.
https://github.com/X-Hydrogen/motus
```

---

<p align="center">
  <sub>Built for computational chemists who value their time.</sub>
</p>
