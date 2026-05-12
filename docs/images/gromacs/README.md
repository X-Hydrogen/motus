# GROMACS — Figure Gallery

All figures generated from a **urea + H₂PO₄⁻ / NH₄⁺ aqueous solution** (239 atoms, 15 Å box) using MOTUS with GROMACS + OPLS-AA. Each figure type is engine-agnostic.

---

## Energy & Thermodynamics

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `energy_timeseries.png` | Energy Time Series | Multi-panel: Temperature (K), Pressure (bar), Potential Energy (kJ/mol), Volume (nm³), Density (kg/m³). Dashed line = mean. |
| `energy_distribution.png` | Energy Distribution | Histograms of T and E_pot with mean markers. Validates NVT/NPT equilibration quality. |

## Structure & Dynamics

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `rmsd.png` | RMSD | Root-mean-square deviation (Å) from starting structure. Measures overall structural drift. Plateau = equilibrated. |
| `rgyr.png` | Radius of Gyration | R_g (nm) over time. Compactness indicator — flat trace = stable conformation. |
| `sasa.png` | Solvent Accessible Surface Area | SASA (nm²) over time. Changes indicate exposure/burial of surface area. |
| `rdf.png` | Radial Distribution Function | g(r) for the system. First peak = nearest-neighbor distance. Integration → coordination number. |

## Hydrogen Bonds

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `hbonds.png` | Hydrogen Bond Count | Total H-bond count over time with average line. |

## Dashboard

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `summary_dashboard.png` | Summary Dashboard | 2×2 overview: Temperature, H-bonds, RMSD, Density profile. Quick-look summary. |
