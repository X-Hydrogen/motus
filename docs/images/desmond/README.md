# Desmond — Figure Gallery

All figures generated from a **urea + H₂PO₄⁻ / NH₄⁺ aqueous solution** (239 atoms, 15 Å box) using MOTUS with Schrödinger Desmond. Each figure type is **engine-agnostic** — the same analysis is available for GROMACS and LAMMPS where indicated.

---

## Energy & Thermodynamics

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `energy_timeseries.png` | Energy Time Series | Multi-panel: Temperature (K), Pressure (bar), Potential Energy (kcal/mol), Volume (Å³) over the full trajectory. Dashed horizontal line = mean. |
| `energy_distribution.png` | Energy Distribution | Histograms of Temperature and Potential Energy with mean (dashed) and ±1σ (dotted) markers. Validates thermostat/barostat convergence. |

## Hydrogen Bonds

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `hbonds(all).png` | H-Bond Count (System) | Total intermolecular H-bond count over time. Higher = more structured solvent network. |
| `hbonds(solute).png` | H-Bond Count (Solute) | H-bonds between solute and surrounding water/ions. Sensitive to solvation changes. |

## Solvent Structure

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `water_shells.png` | Water Shell Classification | Dual panel: **(left)** stacked area of water classified as Bound (<3.5 Å), 2nd shell (3.5–5 Å), and Free (>5 Å) over time; **(right)** average pie chart. |
| `solute_water_contacts.png` | Solute–Water Contacts | Number of water molecules within contact distance of solute atoms over time. Sensitive to solvation/desolvation events. |
| `water_residence.png` | Water Residence Time | Survival probability S(t) for water in the first solvation shell. Exponential decay fit yields residence time τ. |

## Radial Distribution Functions

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `rdf_elements.png` | Element-Pair RDF | g(r) + coordination number n(r) for **every element pair** in the system. Dual Y-axis: left = g(r) (solid), right = n(r) (dashed). |
| `rdf_molecule_C1_H4_N2_O1.png` | Molecular RDF (Intra/Inter) | Intra- and intermolecular g(r) + n(r) for a specific molecule. Separates internal structure from packing. |
| `rdf_water.png` | Water Shell RDF | g(r) for bound/free water vs solute and water-water pairs. First peak position = characteristic solvation distance. |

## Density Profiles

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `density_1d_all.png` | 1D Density (All Atoms) | Relative density along X, Y, Z axes. Flat profile (near 1.0) = well-equilibrated homogeneous system. |
| `density_1d_solute.png` | 1D Density (Solute) | Solute density profile along axes. Peaks reveal preferred solute positions or interfacial accumulation. |
| `density_1d_water.png` | 1D Density (Water) | Water density profile. Layering near interfaces manifests as oscillations. |
| `density_2d_all_XY.png` | 2D Density Map (XY) | Cross-sectional density heatmap in the XY plane. |
| `density_2d_all_XZ.png` | 2D Density Map (XZ) | Cross-sectional density heatmap in the XZ plane. |
| `density_2d_all_YZ.png` | 2D Density Map (YZ) | Cross-sectional density heatmap in the YZ plane. |

## Molecular Properties

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `rg_C1_H4_N2_O1.png` | Radius of Gyration (Rg) | Rg over time for each molecule. Measures compactness — lower Rg = more folded/compact conformation. Shaded band = ±1 std. |
| `distance_overview.png` | Distance Monitoring | User-specified atom-pair distances over time. Useful for tracking bond formation/breaking or key contacts. |
| `dipole_total.png` | Total Dipole Moment | System total dipole magnitude over time. Polarization changes indicate charge redistribution. |
| `dipole_components.png` | Dipole Components | X/Y/Z vector components of the total dipole. Oscillations reveal anisotropic polarization. |

## Conformational Clustering (ML-Style)

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `cluster_rmsd_matrix.png` | Pairwise RMSD Matrix | Heatmap of all-vs-all frame RMSD. Block-diagonal structure = well-separated clusters. |
| `cluster_population.png` | Cluster Populations | Bar chart + pie chart of RMSD-based conformational clusters. Largest cluster = dominant conformation. |
| `cluster_timeline.png` | Cluster Timeline | Stacked color bands showing which cluster each frame belongs to. Transitions visible as band boundaries. |
| `cluster_pca_scatter.png` | PCA Projection (Clusters) | PC1 vs PC2 scatter colored by cluster. **Convex hulls** enclose each cluster. **Diamond markers** = cluster centroids. Dot size increases with simulation time. |
| `cluster_pca_timeline.png` | PCA Projection (Time) | Same projection colored by time (viridis gradient). Reveals conformational drift — distinct color regions = distinct simulation epochs. |

## Free Volume

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `free_volume.png` | Free Volume Analysis | Dual panel: **(left)** free volume (Å³) excluded by probe sphere; **(right)** fractional free volume (FFV %). Void analysis for transport properties. |

## SIMA (Simulation Interactions Diagram)

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `sima_radial_L_Torsions_1.png` | Ligand Torsion Radar 1 | Time-colored radial plot of a rotatable torsion angle. Color gradient = early (purple) → late (yellow). Wide angular spread = flexible torsion. |
| `sima_radial_L_Torsions_2.png` | Ligand Torsion Radar 2 | Second rotatable torsion. Narrow angular spread = rigid torsion. |
| `sima_properties_L-Properties.png` | Ligand Properties | Multi-panel: RMSD, SASA, PSA, MolSA, intramolecular H-bonds. All as rolling averages with ±1σ bands. |
| `sima_torsion_heatmap_L_Torsions.png` | Torsion Heatmap | 2D probability density of torsion pairs. Hot spots = preferred conformations. Diagonal = correlated torsions. |

## Dashboard

| Figure | Analysis | What It Shows |
|--------|----------|---------------|
| `summary_dashboard.png` | Summary Dashboard | 2×2 multi-panel overview combining Temperature, H-bonds/Water shells, and one additional metric. Quick-look summary for SI. |
