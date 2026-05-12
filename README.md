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

All figures below were generated **fully automatically** by MOTUS from a single Desmond MD trajectory of a urea + phosphate aqueous solution. Click any engine name for the complete per-engine gallery with detailed descriptions.

| Engine | Gallery | Figures |
|--------|---------|---------|
| **Desmond** | [`docs/images/desmond/`](docs/images/desmond/README.md) | 23 figures · 15 analysis types |
| **GROMACS** | [`docs/images/gromacs/`](docs/images/gromacs/README.md) | 8 figures · 7 analysis types |
| **LAMMPS** | [`docs/images/lammps/`](docs/images/lammps/README.md) | 5 figures · 4 analysis types |

---

### 1. Energy & Thermodynamics

Before analyzing structure, verify the simulation is stable. These plots confirm the thermostat and barostat have converged — temperature, pressure, potential energy, and volume fluctuate around equilibrium values without drift.

<p align="center">
  <img src="docs/images/desmond/energy_timeseries.png" alt="Energy Timeseries" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/energy_distribution.png" alt="Energy Distribution" width="650">
</p>

---

### 2. Hydrogen Bonds & Solvation Shells

Hydrogen bonds are the primary interaction governing solvation, molecular recognition, and interfacial structure. MOTUS tracks total and solute-specific H-bond counts, classifies water into bound / 2nd-shell / free populations, measures water residence time, and monitors solute–water contacts.

<p align="center">
  <img src="docs/images/desmond/hbonds(all).png" alt="Hbonds All" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/hbonds(solute).png" alt="Hbonds Solute" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/water_shells.png" alt="Water Shells" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/solute_water_contacts.png" alt="Solute-Water Contacts" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/water_residence.png" alt="Water Residence" width="650">
</p>

---

### 3. Radial Distribution Functions — g(r) + Coordination Number n(r)

RDF reveals the short- and medium-range order of liquids. Every element-pair g(r) is computed, with coordination number n(r) on a dual Y-axis (dashed red). Water-shell RDFs distinguish bound vs free water populations around the solute.

<p align="center">
  <img src="docs/images/desmond/rdf_elements.png" alt="Element-Pair RDF" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/rdf_water.png" alt="Water Shell RDF" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/rdf_molecule_C1_H4_N2_O1.png" alt="Molecular RDF" width="650">
</p>

---

### 4. Density Cross-Sections — 1D Profiles & 2D Heatmaps

Density maps expose anisotropic packing, interfacial layering, or phase separation invisible in isotropic averages. 1D profiles along X/Y/Z validate homogeneity; 2D heatmaps reveal lateral structure.

<p align="center">
  <img src="docs/images/desmond/density_1d_all.png" alt="1D Density All" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/density_1d_solute.png" alt="1D Density Solute" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/density_1d_water.png" alt="1D Density Water" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/density_2d_all_XY.png" alt="2D Density XY" width="550">
</p>
<p align="center">
  <img src="docs/images/desmond/density_2d_all_XZ.png" alt="2D Density XZ" width="550">
</p>
<p align="center">
  <img src="docs/images/desmond/density_2d_all_YZ.png" alt="2D Density YZ" width="550">
</p>

---

### 5. Molecular Properties — Rg, Distances, Dipole Moments

Per-molecule characterization: radius of gyration (compactness), key interatomic distances (bond formation/breaking), total dipole magnitude and vector components (polarization dynamics).

<p align="center">
  <img src="docs/images/desmond/rg_C1_H4_N2_O1.png" alt="Radius of Gyration" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/distance_overview.png" alt="Distance Overview" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/dipole_total.png" alt="Dipole Total" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/dipole_components.png" alt="Dipole Components" width="650">
</p>

---

### 6. SIMA — Simulation Interactions Diagram

Fully automated SIMA — no Maestro GUI needed. Torsion radar plots show rotatable bond dynamics via time-colored angular distributions. Ligand properties dashboard tracks RMSD, SASA, PSA, MolSA, and intramolecular H-bonds. Torsion heatmaps reveal coupled conformational preferences.

<p align="center">
  <img src="docs/images/desmond/sima_radial_L_Torsions_1.png" alt="SIMA Radial Torsion 1" width="500">
</p>
<p align="center">
  <img src="docs/images/desmond/sima_radial_L_Torsions_2.png" alt="SIMA Radial Torsion 2" width="500">
</p>
<p align="center">
  <img src="docs/images/desmond/sima_properties_L-Properties.png" alt="SIMA Properties" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/sima_torsion_heatmap_L_Torsions.png" alt="SIMA Torsion Heatmap" width="550">
</p>

---

### 7. Conformational Clustering & PCA

Hierarchical RMSD clustering groups trajectory frames into conformational states. The RMSD matrix heatmap visualizes pairwise structural similarity. Cluster populations (bar + pie) quantify state occupancy; the timeline shows state transitions. PCA projection onto PC1–PC2 with **convex hulls** and **diamond centroids** maps the conformational landscape. Time-colored variant reveals chronological drift.

<p align="center">
  <img src="docs/images/desmond/cluster_rmsd_matrix.png" alt="RMSD Matrix" width="550">
</p>
<p align="center">
  <img src="docs/images/desmond/cluster_population.png" alt="Cluster Population" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/cluster_timeline.png" alt="Cluster Timeline" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/cluster_pca_scatter.png" alt="PCA Cluster Scatter" width="650">
</p>
<p align="center">
  <img src="docs/images/desmond/cluster_pca_timeline.png" alt="PCA Time Evolution" width="650">
</p>

---

### 8. Free Volume & Void Analysis

Free volume (Å³) probed by a rolling sphere + fractional free volume (FFV %). Critical for predicting gas permeability, ion conductivity, and mechanical properties in polymers, electrolytes, and porous materials.

<p align="center">
  <img src="docs/images/desmond/free_volume.png" alt="Free Volume" width="650">
</p>

---

### 9. Summary Dashboard

All key metrics at a glance — temperature, energy distribution, H-bonds, and water shell populations in a 2×2 panel. Perfect for supplementary information in publications.

<p align="center">
  <img src="docs/images/desmond/summary_dashboard.png" alt="Summary Dashboard" width="650">
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
