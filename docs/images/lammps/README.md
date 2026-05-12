# LAMMPS — Figure Gallery

All figures generated from a **urea + H₂PO₄⁻ / NH₄⁺ aqueous solution** (239 atoms, 15 Å box) using MOTUS with LAMMPS + OPLS-AA. Each figure type is engine-agnostic.

---

## Energy & Thermodynamics

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `energy_timeseries.png` | Energy Time Series | Multi-panel: Temperature (K), Pressure (atm), Potential Energy (kcal/mol), Volume (Å³), Density (g/cm³). Dashed line = mean. |
| `energy_distribution.png` | Energy Distribution | Histograms of T and E_pot with mean markers. Validates equilibration convergence. |

## Structure & Dynamics

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `rmsd.png` | RMSD | Root-mean-square deviation (Å) from starting structure. Measures structural drift over the trajectory. |
| `rdf.png` | RDF + Coordination | Dual-axis g(r) + n(r). Solid blue = g(r) (left axis), dashed red = coordination number (right axis). |

## Dashboard

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `summary_dashboard.png` | Summary Dashboard | 2×2 overview: Temperature, Potential Energy, RDF, Volume. Quick-look summary. |
