<p align="center">
  <img src="docs/images/MOTUS-top.png" alt="MOTUS" width="800">
</p>

<h3 align="center"><em>Molecular Dynamics Automation — From Idea to Publication, in Natural Language</em></h3>

<p align="center">
  <strong>Version 1.0.0</strong> &nbsp;|&nbsp;
  Desmond MD ✅ &bull; GROMACS ✅ &bull; LAMMPS ✅ &bull; AI Agent ✅
</p>

---

## What is MOTUS?

**MOTUS** is a dual-purpose molecular dynamics platform:

1. **🧬 MOTUS Agent** — An AI scientist that designs, executes, and analyzes MD simulations through natural conversation. Just describe your research question in plain language.

2. **⚡ MOTUS Scripts** — A unified cross-engine analysis pipeline that transforms raw MD trajectory data into publication-ready figures — automatically, across Desmond, GROMACS, and LAMMPS.

### Why Molecular Dynamics Matters

Molecular dynamics simulations are a cornerstone of modern science and engineering. By tracking every atom's motion at femtosecond resolution, MD reveals the invisible machinery behind:

- **⚡ Energy Storage** — electrolyte structure, ion transport mechanisms, and electrode-electrolyte interfaces in next-generation batteries
- **🧬 Drug Discovery** — protein-ligand binding free energies, conformational selection, and solvation effects that govern drug efficacy
- **🧪 Catalysis** — reaction pathways, transition states, and solvent effects in homogeneous and heterogeneous catalysis
- **🛡️ Materials Design** — polymer mechanics, membrane permeability, and self-assembly of functional nanomaterials
- **🌍 Climate & Geochemistry** — CO₂ capture solvents, mineral dissolution kinetics, and atmospheric aerosol chemistry

Across all these fields, the bottleneck is the same: **turning terabytes of simulation data into interpretable, publication-quality results**. MOTUS eliminates this bottleneck.

---

## 🧬 MOTUS Agent — AI Scientist

### Quick Start

```bash
# One-shot research
motus "Study methane hydrate formation at 260K and 200 bar"

# Interactive mode
motus

# Web interface
motus-web --host 0.0.0.0

# Resume a session
motus --session 20260514_215205
```

The Agent will:
1. **Understand** your research question
2. **Build** the molecular system via Packmol (~90 molecule SMILES DB, PubChem fallback)
3. **Simulate** with GROMACS, LAMMPS, or Desmond (EM → NVT → NPT → Production)
4. **Model** for Desmond — auto-convert Packmol PDB → .cms via S-OPLS pipeline
5. **Analyze** — energy, RDF, RMSD, H-bonds, density, clustering, PCA, MSD...
6. **Render** publication-quality structure images with VMD
7. **Generate** LaTeX PDF reports with figures, tables, and quantitative conclusions
8. **Interpret** results and suggest next research steps
9. **Teach** — ask MD fundamentals and get interactive explanations

### Features

- **Natural Language Interface** — no scripting, no config files
- **Triple Engine Support** — GROMACS, LAMMPS, and Desmond (build + MD + analysis)
- **Desmond Modeling Pipeline** — Packmol PDB → .cms in ~46s via S-OPLS
- **Dual Role** — research scientist + passionate professor
- **Auto-detect** — knows GROMACS, LAMMPS, VMD, GPU, Schrödinger paths
- **Session Memory** — all conversations saved, resumable
- **Web Dashboard** — sci-fi themed, mobile-responsive, SSE real-time streaming
- **LLM Backend** — DeepSeek (configurable)

### Architecture

```
Hello World
       │
       ▼
  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐
  │ Build   │───▶│ Run MD   │───▶│ Analyze  │───▶│ Interpret │
  │ System  │    │ 500ps    │    │ + Plots  │    │ + Report  │
  └─────────┘    └──────────┘    └──────────┘    └───────────┘
       │              │               │               │
       ▼              ▼               ▼               ▼
  gmx solvate    gmx mdrun      RDF, RMSD,      LaTeX Paper
  insert-mol     GPU CUDA       H-bonds, E      PDF Output
```

### Agent Demo

<p align="center">
  <img src="docs/images/agent/MOTUS-demo.png" alt="MOTUS Agent Demo" width="750">
</p>
<p align="center">
  <em>Agent Web Interface — Real-time streaming, dark sci-fi theme, multi-tool orchestration</em>
</p>

<p align="center">
  <img src="docs/images/agent/MOTUS-demo2.png" alt="MOTUS Agent Demo 2" width="750">
</p>
<p align="center">
  <em>Research Workflow — Automatic analysis, publication-quality figures, and PDF report generation</em>
</p>

### Web Interface

<p align="center">
  <em>Dark sci-fi themed dashboard · Real-time tool call streaming · Mobile responsive · Canvas particle animations</em>
</p>

Access MOTUS from anywhere:
```bash
# Start web server
motus-web --host 0.0.0.0 --port 8848

# Public tunnel (Cloudflare)
cloudflared tunnel --url http://localhost:8848
```

---

## ⚡ MOTUS Scripts — Cross-Engine Analysis

One command. Three engines. Fifteen analysis types. Zero manual plotting.

```bash
# From raw trajectory to complete analysis package — run from within the job folder
cd desmond_md_job_my-system
../motus/desmond/desmond-analysis.sh --plot
# → energy, Hbonds, RDF, density, dipole, clustering, PCA, SIMA...
# → all figures in PDF (vector) + PNG (300 DPI)
# → < 2 minutes
```

**New in v1.0.0:** Autonomous AI scientist — describe your research in natural language and MOTUS does everything. Gold-standard 16-page LaTeX publication template. Also: LAMMPS reactive MD, Desmond one-click publishing, CWD auto-detection for all engines.

---

## Quick Start — Engine Scripts

### Desmond

**Recommended workflow:** Set up your system in Maestro (Windows or Linux), write the job files, then run on your GPU server.

```bash
# 1. Copy the Maestro-generated folder to your Linux server
#    Maestro produces: desmond_md_job_my-system/{.cms, .msj, .cfg}

# 2. Enter the folder and launch MD
cd desmond_md_job_my-system
bash ../motus/desmond/desmond-md.sh                     # Use Maestro settings as-is
bash ../motus/desmond/desmond-md.sh -t 5000 -i 2.5     # Or override time & interval

#    Real-time output: Stage progress + production progress bar
#      Stage 1 completed.  Stage 2 completed.  ...
#      [=========-----] 65% | 32500/50000 ps | 2513 ns/day

# 3. Full analysis + figures (same folder)
bash ../motus/desmond/desmond-analysis.sh --plot

# 4. One-click publication paper (16pp, ~8000 words)
bash ../motus/desmond/desmond-publish.sh

# 5. Re-plot from existing data (seconds)
bash ../motus/desmond/desmond-analysis.sh --fig-only
```

**Key features:**
- **Windows & Linux Maestro** — auto-detects and fixes CRLF line endings (`\r\n` → `\n`)
- **CWD auto-detection** — no folder path needed; just `cd` into the job folder
- **Real-time progress bar** — shows `Chemical time`, `ns/day`, and percentage during MD runs
- **Dynamic server paths** — auto-discovers Schrödinger scratch directory (works across different cluster configurations)
- **Stage-by-stage monitoring** — shows `_multisim.log` output during equilibration phases

**Legacy mode** (`--mode 2`): Build from a `desmond_setup_XXXXX` folder (generates `.msj` and `.cfg` from CLI parameters):
```bash
./desmond/desmond-md.sh --mode 2 desmond_setup_my-system -t 2000 -i 1

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
# Standard MD production run
./lammps/lammps-md.sh system.data

# Analysis + figures
./lammps/lammps-analysis.sh md_output/

# Enhanced sampling
./lammps/lammps-metadynamics.sh md_output/

# Reactive MD — ReaxFF (high-temperature reaction kinetics)
./lammps/lammps-reaxff.sh system.data -T 2500 -t 500
./lammps/lammps-reaxff-analysis.sh md_output/

# Reactive MD — fix bond/react (template-driven at any temperature)
./lammps/lammps-bond-react.sh system.data -m reaction.yaml -T 400 -t 2000
```

**LAMMPS Reaction Kinetics** (`lammps-reaxff.sh`, `lammps-bond-react.sh`, `lammps-reaxff-analysis.sh`):
- **ReaxFF** — reactive force field MD with automatic species tracking; suitable for high-T pyrolysis and combustion
- **fix bond/react** — template-driven reaction MD for ambient-temperature kinetics (e.g., hydrolysis, polymerization)
- **`reaction_analysis.py`** — shared analysis engine: species counting, concentration profiles, first/second-order rate fitting, Arrhenius parameter extraction across multiple temperatures
- **`bond_react_gen.py`** — YAML → LAMMPS native molecule template + reaction map file generator
- **Plot types** — species timeseries (stacked area + line), reaction rate (ln[C] vs t with R²), product formation (mole fraction evolution)

**Requirements:**
- Linux; Schrödinger Suite (for Desmond), GROMACS, LAMMPS
- Python 3.10+ with `numpy`, `matplotlib`, `scipy`
- GPU recommended

---

## Features Matrix

| Feature | Desmond | GROMACS | LAMMPS |
|:--------|:-------:|:-------:|:------:|
| **MD Production** (EM + Equil + Prod) | ✅ | ✅ | ✅ |
| **Automated Modeling** (Packmol → .cms) | ✅ | — | — |
| **AI Agent** (Natural Language → Simulation) | ✅ | ✅ | ✅ |
| **Cross-Platform Maestro** (Win/Linux CRLF auto-fix) | ✅ | — | — |
| **CWD Auto-Detection** (no folder args) | ✅ | ✅ | ✅ |
| **Real-Time Progress Bar** | ✅ | — | — |
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
| **ReaxFF Reactive MD** | — | — | ✅ |
| **fix bond/react Kinetics** | — | — | ✅ |
| **Arrhenius Rate Fitting** | — | — | ✅ |
| **CMS↔GROMACS/LAMMPS Converter** | `cms2gmx.py` | `cms2lmp.py` | — |

---

## Figure Gallery

All figures below were generated **fully automatically** by MOTUS from a single Desmond MD trajectory of a urea + phosphate aqueous solution. Click any engine name for the complete per-engine gallery with detailed descriptions.

| Engine | Gallery | Figures |
|--------|---------|---------|
| **Desmond** | [`docs/images/desmond/`](docs/images/desmond/README.md) | 31 figures · 15 analysis types |
| **GROMACS** | [`docs/images/gromacs/`](docs/images/gromacs/README.md) | 8 figures · 7 analysis types |
| **LAMMPS** | [`docs/images/lammps/`](docs/images/lammps/README.md) | 8 figures · 5 analysis types |

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
├── agent/                         ← 🧬 MOTUS Agent (AI Scientist)
│   ├── AGENT.md                   ← Developer guide
│   ├── pyproject.toml             ← v1.0.0 package
│   ├── motus_cli.py               ← CLI entry point
│   ├── motus/                     ← Core agent package
│   │   ├── __init__.py            ← Version info
│   │   ├── loop.py                ← LLM conversation loop
│   │   ├── registry.py            ← Tool registry
│   │   ├── memory/store.py        ← Session persistence
│   │   ├── tools/                 ← MD tools
│   │   │   ├── md_build.py        ← build_system
│   │   │   ├── md_run.py          ← run_md
│   │   │   ├── md_desmond.py      ← model_desmond (Packmol → .cms)
│   │   │   ├── md_analyze.py      ← analyze
│   │   │   ├── md_comprehensive.py ← comprehensive_analysis (9 modules)
│   │   │   ├── md_render.py       ← render_system
│   │   │   ├── md_report.py       ← generate_report (gold-standard template)
│   │   │   ├── md_read.py         ← read_data
│   │   │   └── md_system.py       ← terminal, file ops
│   │   ├── templates/             ← Paper templates (16pp gold standard)
│   │   │   ├── paper-template-desmond.tex  ← Desmond LaTeX template
│   │   │   └── paper-reference.pdf         ← Reference output (16pp, ~8000 words)
│   │   └── web/                   ← Web interface
│   │       ├── app.py             ← Flask server (port 8848)
│   │       └── tunnel.py          ← Public tunnel helper
│   └── scripts/
│       ├── build_hydrate_system.py
│       └── tunnel.sh
├── desmond/                       ← Desmond engine scripts
│   ├── desmond-md.sh              ← MD job submission & monitoring
│   ├── desmond-analysis.sh        ← Post-processing pipeline (15 modules)
│   ├── desmond-publish.sh         ← One-click LaTeX paper generation (16pp)
│   ├── desmond-metadynamics.sh    ← MetaD enhanced sampling
│   ├── templates/                 ← Paper templates
│   │   ├── paper-template.tex     ← Gold-standard LaTeX template (579 lines)
│   │   └── paper-reference.pdf    ← Reference output (16pp, ~8000 words)
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
│   ├── lammps-md.sh               ← Standard MD production
│   ├── lammps-analysis.sh         ← Post-processing pipeline
│   ├── lammps-metadynamics.sh     ← COLVARS MetaD pipeline
│   ├── lammps-reaxff.sh           ← ReaxFF reactive MD
│   ├── lammps-reaxff-analysis.sh  ← ReaxFF species + kinetics analysis
│   ├── lammps-bond-react.sh       ← fix bond/react template-driven MD
│   └── functions/
│       ├── lammps_plot.py         ← Figure generator (9 plot types incl. reaction)
│       ├── lammps_colvars_gen.py  ← COLVARS input generator
│       ├── reaction_analysis.py   ← Species counting, rate fitting, Arrhenius
│       ├── bond_react_gen.py      ← YAML → LAMMPS template + map generator
│       └── gen_urea_data.py       ← Urea+water test system builder
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
| Cross-platform Maestro (Win/Linux, CWD auto-detect, progress bar) | ✅ v0.0.3 |
| LAMMPS reactive MD — ReaxFF + fix bond/react + Arrhenius fitting | ✅ v0.0.3 |
| **🧬 MOTUS Agent — Autonomous AI Scientist** | ✅ v1.0.0 |
| **🌐 Web Interface — Sci-fi dashboard with SSE streaming** | ✅ v1.0.0 |
| Solvent structure analysis (sorient/spatial/h2order) | 🚧 Planned |
| Electrostatic Potential (ESP) | 🚧 Planned |
| Multi-agent collaborative research | 🚧 Planned |
| LLM-driven iterative experiment design | 🚧 Planned |

---

## License

MIT — see [LICENSE](LICENSE) file.

---

## Citation

If you use MOTUS in your research, please cite:

```
MOTUS: Molecular Dynamics Automation Agent. Version 1.0.0.
https://github.com/X-Hydrogen/motus
```

---

<p align="center">
  <sub>Built for computational chemists who value their time.</sub>
</p>
