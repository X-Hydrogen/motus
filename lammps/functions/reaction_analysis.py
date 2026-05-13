#!/usr/bin/env python3
"""
reaction_analysis.py — Unified reaction analysis engine for LAMMPS MD.
MOTUS v0.0.1

Supports both ReaxFF (fix reaxff/species) and fix bond/react modules.
Provides species counting, concentration computation, and rate constant fitting.

Key functions:
  count_species_from_dump    — Parse LAMMPS dump, count molecules/species per frame
  compute_concentration      — Convert species counts to mol/L
  fit_first_order            — First-order decay:  A → products
  fit_second_order           — Second-order:         A + B → products
  compute_initial_rate       — Linear-fit initial slope over first N frames
  arrhenius_fit              — Extract Ea and A from k(T) data
  parse_reaxff_species       — Read fix reaxff/species output file
  parse_lammps_dump_molecules— Read bond/react-style dump with molecule IDs

Usage:
  import reaction_analysis as ra
  df = ra.count_species_from_dump("dump.lammpstrj")
  conc = ra.compute_concentration(df, volume_A3=100000.0)
  k, r2 = ra.fit_first_order(conc["Time_ps"], conc["H2O"])
"""

import sys
import re
import math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Union, Callable

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NA = 6.02214076e23          # Avogadro's number
R_KCAL = 1.987204258e-3     # Gas constant in kcal/(mol·K)
A3_TO_L = 1.0e-27           # 1 Å³ = 1e-27 L

# ---------------------------------------------------------------------------
# Low-level dump parser
# ---------------------------------------------------------------------------

def _read_dump_frames(
    dump_file: str,
    columns: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Parse a LAMMPS dump file into a list of per-frame dicts.

    Each dict contains:
        'timestep'  : int
        'natoms'    : int
        'box'       : (xlo,xhi, ylo,yhi, zlo,zhi)  or None if absent
        'atoms'     : list of dicts, one per atom line, keyed by column names

    Parameters
    ----------
    dump_file : str
        Path to the LAMMPS dump file.
    columns : list of str, optional
        Column names for the ATOMS section.  If None, auto-detected from the
        ITEM: ATOMS header line.

    Returns
    -------
    list of dict
    """
    frames = []
    current = None
    in_atoms = False
    atom_lines = []

    with open(dump_file, "r") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue

            if line.startswith("ITEM: TIMESTEP"):
                # commit previous frame
                if current is not None and atom_lines:
                    current["atoms"] = _parse_atom_lines(atom_lines, current.get("columns"))
                frames.append(current or {})
                current = {"timestep": None, "natoms": None, "box": None, "columns": None}
                in_atoms = False
                atom_lines = []

            elif line.startswith("ITEM: NUMBER OF ATOMS"):
                in_atoms = False

            elif line.startswith("ITEM: BOX BOUNDS"):
                in_atoms = False
                bounds = []
                for _ in range(3):
                    b = fh.readline().strip().split()
                    bounds.append((float(b[0]), float(b[1])))
                current["box"] = tuple(bounds)

            elif line.startswith("ITEM: ATOMS"):
                in_atoms = True
                # auto-detect columns
                parts = line.split()
                # "ITEM: ATOMS" is first two tokens; rest are column names
                col_names = parts[2:] if len(parts) > 2 else []
                current["columns"] = col_names
                continue

            else:
                if in_atoms:
                    atom_lines.append(line)
                elif current is not None and current.get("timestep") is None:
                    try:
                        current["timestep"] = int(line)
                    except ValueError:
                        pass
                elif current is not None and current.get("natoms") is None:
                    try:
                        current["natoms"] = int(line)
                    except ValueError:
                        pass

    # Don't forget the last frame
    if current is not None:
        if atom_lines:
            current["atoms"] = _parse_atom_lines(atom_lines, current.get("columns"))
        frames.append(current)

    # Remove the empty placeholder first element if needed
    if frames and frames[0].get("timestep") is None and frames[0].get("natoms") is None:
        frames = frames[1:]

    return frames


def _parse_atom_lines(lines: List[str], columns: List[str]) -> List[Dict]:
    """Convert raw atom text lines to list of dicts keyed by column name."""
    atoms = []
    for line in lines:
        vals = line.split()
        if len(vals) < len(columns):
            continue
        atom = {}
        for i, col in enumerate(columns):
            try:
                atom[col] = float(vals[i]) if "." in vals[i] or "e" in vals[i].lower() else int(vals[i])
            except ValueError:
                atom[col] = vals[i]
        atoms.append(atom)
    return atoms


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def count_species_from_dump(
    dump_file: str,
    atom_to_molecule: Optional[Union[Dict[int, int], Callable[[Dict], int]]] = None,
    species_name_map: Optional[Dict[int, str]] = None,
    time_step_fs: float = 1.0,
) -> pd.DataFrame:
    """
    Count molecules / species per frame from a LAMMPS dump file.

    Parameters
    ----------
    dump_file : str
        Path to LAMMPS dump trajectory.
    atom_to_molecule : dict or callable, optional
        If None: the dump file must contain a "mol" column (as written by
        fix bond/react).  Each unique mol ID is counted as one molecule.
        If dict: maps atom_id → molecule_id.
        If callable: called as f(atom_dict) → molecule_id for each atom.
    species_name_map : dict, optional
        Map integer species/type ID → human-readable name (e.g. {1:"H2O", 2:"CO2"}).
        If None, species are labelled "species_N".
    time_step_fs : float
        Timestep size in femtoseconds.  Used to convert timestep → Time_ps.

    Returns
    -------
    pd.DataFrame
        Columns: [Frame, Time_ps, <species_1>, <species_2>, ...]
        Each row is one frame.
    """
    frames = _read_dump_frames(dump_file)
    if not frames:
        raise ValueError(f"No frames found in dump file: {dump_file}")

    rows = []
    for i, frame in enumerate(frames):
        ts = frame.get("timestep", 0)
        time_ps = ts * time_step_fs / 1000.0

        # --- determine molecule assignment ---
        mol_ids: Dict[int, int] = {}  # atom_id → mol_id

        if atom_to_molecule is None:
            # Must have "mol" column in dump
            if frame.get("columns") is None or "mol" not in frame["columns"]:
                raise ValueError(
                    "Dump file has no 'mol' column and no atom_to_molecule mapping "
                    "was provided.  Use a dump that includes molecule IDs, or pass "
                    "atom_to_molecule."
                )
            for atom in frame.get("atoms", []):
                aid = int(atom["id"])
                mol_ids[aid] = int(atom["mol"])
        elif isinstance(atom_to_molecule, dict):
            for atom in frame.get("atoms", []):
                aid = int(atom["id"])
                mol_ids[aid] = atom_to_molecule.get(aid, aid)
        elif callable(atom_to_molecule):
            for atom in frame.get("atoms", []):
                aid = int(atom["id"])
                mol_ids[aid] = atom_to_molecule(atom)
        else:
            raise TypeError("atom_to_molecule must be None, dict, or callable")

        # --- assign species to each molecule ---
        # Species is determined by the atom type of the *first atom* seen
        # for each molecule.  species_name_map maps atom type → name.
        mol_species: Dict[int, str] = {}
        species_counts: Dict[str, int] = defaultdict(int)
        seen_mols: set = set()

        for atom in frame.get("atoms", []):
            mid = mol_ids[int(atom["id"])]

            # First time we encounter this molecule, record its species
            if mid not in mol_species:
                if "type" in atom:
                    tid = int(atom["type"])
                    if species_name_map is not None and tid in species_name_map:
                        sp = species_name_map[tid]
                    else:
                        sp = f"species_{tid}"
                else:
                    sp = f"mol_{mid}"
                mol_species[mid] = sp

            # Count each molecule only once per frame
            if mid not in seen_mols:
                seen_mols.add(mid)
                species_counts[mol_species[mid]] += 1

        row = {"Frame": i + 1, "Time_ps": time_ps}
        row.update(dict(species_counts))
        rows.append(row)

    df = pd.DataFrame(rows)
    # Fill missing species with 0
    df = df.fillna(0)
    # Ensure integer types for species columns
    for col in df.columns:
        if col not in ("Frame", "Time_ps"):
            df[col] = df[col].astype(int)

    return df


def compute_concentration(
    species_df: pd.DataFrame,
    volume_A3: float,
) -> pd.DataFrame:
    """
    Convert species counts to concentrations in mol/L.

    conc (mol/L) = count / (NA * volume_in_L)
    where volume_in_L = volume_A3 * 1e-27

    Parameters
    ----------
    species_df : pd.DataFrame
        Output of count_species_from_dump().  Must have 'Frame' and 'Time_ps'
        columns; all other columns are treated as species counts.
    volume_A3 : float
        Simulation box volume in Å³.

    Returns
    -------
    pd.DataFrame
        Same structure but with species counts replaced by mol/L concentrations.
    """
    vol_L = volume_A3 * A3_TO_L
    factor = 1.0 / (NA * vol_L)

    df = species_df.copy()
    for col in df.columns:
        if col not in ("Frame", "Time_ps"):
            df[col] = df[col].astype(float) * factor
    return df


# ---------------------------------------------------------------------------
# Kinetic fitting
# ---------------------------------------------------------------------------

def _r_squared(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Coefficient of determination R²."""
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if ss_tot == 0:
        return 1.0
    return float(1.0 - ss_res / ss_tot)


def fit_first_order(
    time_ps: Union[np.ndarray, pd.Series],
    conc: Union[np.ndarray, pd.Series],
) -> Tuple[float, float]:
    """
    Fit first-order kinetics:  A → products,  d[A]/dt = -k[A].

    Uses linear regression on ln([A]) vs time.
    ln([A]) = ln([A]₀) - k·t    →    slope = -k

    Parameters
    ----------
    time_ps : array-like
        Time in picoseconds.
    conc : array-like
        Concentration of reactant A in mol/L.

    Returns
    -------
    k_per_ps : float
        Rate constant in ps⁻¹.
    R_squared : float
        Goodness of fit.
    """
    t = np.asarray(time_ps, dtype=float)
    c = np.asarray(conc, dtype=float)

    # Remove zero/negative concentrations (log undefined)
    mask = c > 0
    if np.sum(mask) < 2:
        raise ValueError("Need at least 2 positive concentration values for fit")
    t_fit = t[mask]
    ln_c = np.log(c[mask])

    # Linear fit: ln(c) = a + b*t,  where b = -k
    b, a = np.polyfit(t_fit, ln_c, 1)
    k = -b
    ln_c_pred = a + b * t_fit
    r2 = _r_squared(ln_c, ln_c_pred)

    return float(k), r2


def fit_second_order(
    time_ps: Union[np.ndarray, pd.Series],
    conc_A: Union[np.ndarray, pd.Series],
    conc_B: Union[np.ndarray, pd.Series],
) -> Tuple[float, float]:
    """
    Fit second-order kinetics:  A + B → products,  d[A]/dt = -k[A][B].

    Handles both equal and unequal initial concentrations.

    - If [A]₀ ≈ [B]₀ (within 1%):  use  1/[A] = 1/[A]₀ + k·t
    - Otherwise:  use  ln([B][A]₀ / ([A][B]₀)) = ([B]₀ - [A]₀)·k·t

    Parameters
    ----------
    time_ps : array-like
        Time in picoseconds.
    conc_A : array-like
        Concentration of reactant A in mol/L.
    conc_B : array-like
        Concentration of reactant B in mol/L.

    Returns
    -------
    k_L_per_mol_per_ps : float
        Rate constant in L·mol⁻¹·ps⁻¹.
    R_squared : float
        Goodness of fit.
    """
    t = np.asarray(time_ps, dtype=float)
    a = np.asarray(conc_A, dtype=float)
    b = np.asarray(conc_B, dtype=float)

    # Filter valid data
    mask = (a > 0) & (b > 0)
    if np.sum(mask) < 2:
        raise ValueError("Need at least 2 valid data points for fit")

    t_fit = t[mask]
    a_fit = a[mask]
    b_fit = b[mask]

    a0 = a_fit[0]
    b0 = b_fit[0]

    # Check if equal initial concentrations (within 1%)
    if abs(a0 - b0) / max(a0, b0) < 0.01:
        # 1/[A] vs t  →  slope = k
        inv_a = 1.0 / a_fit
        slope, intercept = np.polyfit(t_fit, inv_a, 1)
        k = slope
        inv_a_pred = intercept + slope * t_fit
        r2 = _r_squared(inv_a, inv_a_pred)
    else:
        # ln([B][A]₀ / ([A][B]₀)) = ([B]₀ - [A]₀)·k·t
        y = np.log(b_fit * a0 / (a_fit * b0))
        slope, intercept = np.polyfit(t_fit, y, 1)
        k = slope / (b0 - a0)
        y_pred = intercept + slope * t_fit
        r2 = _r_squared(y, y_pred)

    return float(k), r2


def compute_initial_rate(
    time_ps: Union[np.ndarray, pd.Series],
    conc: Union[np.ndarray, pd.Series],
    window_frames: int = 10,
) -> Tuple[float, float]:
    """
    Compute initial reaction rate from the first `window_frames` data points.

    Uses linear regression on the early-time window.
    rate = -d[conc]/dt  (mol·L⁻¹·ps⁻¹)

    Parameters
    ----------
    time_ps : array-like
        Time in picoseconds.
    conc : array-like
        Concentration in mol/L.
    window_frames : int
        Number of initial data points to use for the fit.

    Returns
    -------
    rate_mol_per_L_per_ps : float
        Initial rate (positive = consumption).
    R_squared : float
        Goodness of the linear fit.
    """
    t = np.asarray(time_ps, dtype=float)
    c = np.asarray(conc, dtype=float)

    n = min(window_frames, len(t))
    if n < 2:
        raise ValueError("Need at least 2 data points to compute initial rate")

    t_win = t[:n]
    c_win = c[:n]

    slope, intercept = np.polyfit(t_win, c_win, 1)
    rate = -slope  # positive for consumption
    c_pred = intercept + slope * t_win
    r2 = _r_squared(c_win, c_pred)

    return float(rate), r2


def arrhenius_fit(
    temps_K_list: Union[List[float], np.ndarray],
    rates_list: Union[List[float], np.ndarray],
) -> Tuple[float, float, float]:
    """
    Fit Arrhenius parameters from k(T) data.

    k = A · exp(-Ea / (R·T))
    ln(k) = ln(A) - Ea/(R·T)

    Linear regression of ln(k) vs 1/T yields:
        slope = -Ea / R   →   Ea = -slope · R
        intercept = ln(A) →   A = exp(intercept)

    Parameters
    ----------
    temps_K_list : array-like
        Temperatures in Kelvin.
    rates_list : array-like
        Rate constants at each temperature.

    Returns
    -------
    Ea_kcal_per_mol : float
        Activation energy in kcal/mol.
    A_prefactor : float
        Pre-exponential factor (same units as input rates).
    R_squared : float
        Goodness of fit.
    """
    T = np.asarray(temps_K_list, dtype=float)
    k = np.asarray(rates_list, dtype=float)

    if len(T) < 2:
        raise ValueError("Need at least 2 temperature points for Arrhenius fit")

    mask = (T > 0) & (k > 0)
    T_fit = T[mask]
    k_fit = k[mask]

    if len(T_fit) < 2:
        raise ValueError("Need at least 2 valid (T>0, k>0) points for Arrhenius fit")

    inv_T = 1.0 / T_fit
    ln_k = np.log(k_fit)

    slope, intercept = np.polyfit(inv_T, ln_k, 1)

    Ea = -slope * R_KCAL        # kcal/mol
    A = math.exp(intercept)

    ln_k_pred = intercept + slope * inv_T
    r2 = _r_squared(ln_k, ln_k_pred)

    return float(Ea), float(A), r2


# ---------------------------------------------------------------------------
# File-format-specific parsers
# ---------------------------------------------------------------------------

def parse_reaxff_species(species_file: str) -> pd.DataFrame:
    """
    Parse a fix reaxff/species output file.

    Handles TWO formats:
    Format A (log-style):
        # Timestep  No_specs  Spec1  Count1  Spec2  Count2 ...
         0          3          H2O   100      H2     50 ...
    Format B (header+data):
        # Timestep  No_Moles  No_Specs  species1  species2 ...
        timestep    total     num_spec  count1    count2   ...

    Parameters
    ----------
    species_file : str
        Path to the species output file.

    Returns
    -------
    pd.DataFrame
        Columns: [Timestep, <species_name_1>, <species_name_2>, ...]
        Each row is one timestep snapshot.
    """
    rows = []
    species_names: List[str] = []
    pending_header = None  # Format B: header line with species names

    with open(species_file, "r") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            
            # Format B: header line
            if line.startswith('#'):
                parts = line.lstrip('#').strip().split()
                if len(parts) >= 3:
                    # Check if this looks like Format B (No_Moles or No_Specs in header)
                    header_parts = [p for p in parts if p not in ('Timestep', 'No_Moles', 'No_Specs')]
                    if header_parts and parts[0] in ('Timestep', 'timestep'):
                        pending_header = header_parts
                continue
            
            parts = line.split()
            if len(parts) < 2:
                continue

            try:
                timestep = int(parts[0])
            except ValueError:
                continue
            
            # Try to determine format
            row = {"Timestep": timestep}
            
            if pending_header is not None:
                # Format B: species names from header, counts from data
                num_specs = int(parts[2]) if len(parts) > 2 else len(pending_header)
                for i, name in enumerate(pending_header[:num_specs]):
                    if i + 3 < len(parts):
                        try:
                            count = int(parts[i + 3])
                            row[name] = count
                            if name not in species_names:
                                species_names.append(name)
                        except (ValueError, IndexError):
                            pass
                pending_header = None
            else:
                # Format A: name-count pairs on same line
                num_specs = int(parts[1])
                idx = 2
                for _ in range(num_specs):
                    if idx + 1 >= len(parts):
                        break
                    name = parts[idx]
                    try:
                        count = int(parts[idx + 1])
                    except (ValueError, IndexError):
                        break
                    row[name] = count
                    if name not in species_names:
                        species_names.append(name)
                    idx += 2

            rows.append(row)

    df = pd.DataFrame(rows)
    # Ensure all known species columns exist
    for sp in species_names:
        if sp not in df.columns:
            df[sp] = 0
    df = df.fillna(0)
    for sp in species_names:
        if sp in df.columns:
            df[sp] = df[sp].astype(int)
    return df


def parse_lammps_dump_molecules(
    dump_file: str,
    type_to_species: Optional[Dict[int, str]] = None,
    time_step_fs: float = 1.0,
) -> pd.DataFrame:
    """
    Parse a LAMMPS dump file with molecule IDs (e.g. from fix bond/react).

    This is a convenience wrapper around `count_species_from_dump` that:
      1. Uses the "mol" column from the dump for molecule assignment.
      2. Maps atom types to species names (via type_to_species).
      3. The species of a molecule is determined by the type of its first atom.

    Parameters
    ----------
    dump_file : str
        Path to the dump file (must contain "mol" and "type" columns).
    type_to_species : dict, optional
        Map LAMMPS atom type → species name, e.g. {1: "H2O", 2: "CO2"}.
        If None, species are labelled "species_N".
    time_step_fs : float
        Timestep size in femtoseconds.

    Returns
    -------
    pd.DataFrame
        Columns: [Frame, Time_ps, <species_1>, ...]
    """
    frames = _read_dump_frames(dump_file)
    if not frames:
        raise ValueError(f"No frames found in dump file: {dump_file}")

    rows = []
    for i, frame in enumerate(frames):
        ts = frame.get("timestep", 0)
        time_ps = ts * time_step_fs / 1000.0

        cols = frame.get("columns", [])
        if "mol" not in cols:
            raise ValueError(
                "Dump file must contain a 'mol' column. "
                "Use fix bond/react with 'dump id mol type ...' or similar."
            )
        if "type" not in cols:
            raise ValueError(
                "Dump file must contain a 'type' column for species mapping."
            )

        # Map atom_id → mol_id and determine mol → species from first atom
        mol_to_species: Dict[int, str] = {}
        seen_mols: set = set()
        species_counts: Dict[str, int] = defaultdict(int)

        for atom in frame.get("atoms", []):
            mid = int(atom["mol"])
            tid = int(atom["type"])

            # First time we see this molecule, assign its species
            if mid not in mol_to_species:
                if type_to_species is not None and tid in type_to_species:
                    sp = type_to_species[tid]
                else:
                    sp = f"species_{tid}"
                mol_to_species[mid] = sp

            if mid not in seen_mols:
                seen_mols.add(mid)
                species_counts[mol_to_species[mid]] += 1

        row = {"Frame": i + 1, "Time_ps": time_ps}
        row.update(dict(species_counts))
        rows.append(row)

    df = pd.DataFrame(rows).fillna(0)
    for col in df.columns:
        if col not in ("Frame", "Time_ps"):
            df[col] = df[col].astype(int)
    return df


# ---------------------------------------------------------------------------
# __main__ demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile
    import os

    print("=" * 65)
    print("  MOTUS Reaction Analysis Engine — Self-Test")
    print("=" * 65)

    # ---- 1. Build a synthetic LAMMPS dump file ----
    print("\n[1] Creating synthetic LAMMPS dump (bond/react style)...")
    dump_content = []
    box_size = 50.0
    ts_values = [0, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000]
    # Simulate: 100 H2O → 50 H2 + 25 O2  (first-order-like decay of H2O)
    h2o_counts = [100, 90, 81, 73, 66, 59, 53, 48, 43, 39, 35]
    h2_counts  = [0,   5,  9,  13, 17, 20, 23, 26, 28, 30, 32]
    o2_counts  = [0,   2,  4,   6,  8, 10, 12, 13, 14, 15, 16]

    for frame_idx, ts in enumerate(ts_values):
        dump_content.append("ITEM: TIMESTEP")
        dump_content.append(str(ts))
        dump_content.append("ITEM: NUMBER OF ATOMS")
        # 3 atoms per H2O, 2 per H2, 2 per O2
        natoms = h2o_counts[frame_idx] * 3 + h2_counts[frame_idx] * 2 + o2_counts[frame_idx] * 2
        dump_content.append(str(natoms))
        dump_content.append("ITEM: BOX BOUNDS pp pp pp")
        dump_content.append(f"0.0 {box_size}")
        dump_content.append(f"0.0 {box_size}")
        dump_content.append(f"0.0 {box_size}")
        dump_content.append("ITEM: ATOMS id mol type x y z")
        aid = 1
        # H2O molecules: type 1
        for m in range(h2o_counts[frame_idx]):
            for _ in range(3):  # 3 atoms per H2O
                dump_content.append(f"{aid} {m+1} 1 0.0 0.0 0.0")
                aid += 1
        # H2 molecules: type 2
        offset = h2o_counts[frame_idx]
        for m in range(h2_counts[frame_idx]):
            for _ in range(2):
                dump_content.append(f"{aid} {offset+m+1} 2 0.0 0.0 0.0")
                aid += 1
        # O2 molecules: type 3
        offset = h2o_counts[frame_idx] + h2_counts[frame_idx]
        for m in range(o2_counts[frame_idx]):
            for _ in range(2):
                dump_content.append(f"{aid} {offset+m+1} 3 0.0 0.0 0.0")
                aid += 1

    with tempfile.NamedTemporaryFile(mode="w", suffix=".lammpstrj", delete=False) as f:
        f.write("\n".join(dump_content))
        dump_path = f.name

    try:
        # ---- 2. Test count_species_from_dump ----
        print("[2] Testing count_species_from_dump ...")
        type_map = {1: "H2O", 2: "H2", 3: "O2"}
        sp_df = count_species_from_dump(dump_path, species_name_map=type_map)
        print(f"    Found {len(sp_df)} frames, species: {list(sp_df.columns)}")
        print(sp_df.to_string(index=False))

        # ---- 3. Test compute_concentration ----
        print("\n[3] Testing compute_concentration ...")
        volume = box_size ** 3  # 125000 Å³
        conc_df = compute_concentration(sp_df, volume)
        print(f"    Volume = {volume:.1f} Å³")
        print(conc_df.to_string(index=False, float_format=lambda x: f"{x:.6f}"))

        # ---- 4. Test fit_first_order ----
        print("\n[4] Testing fit_first_order (H2O decay) ...")
        k1, r2_1 = fit_first_order(conc_df["Time_ps"], conc_df["H2O"])
        half_life = math.log(2) / k1 if k1 > 0 else float("inf")
        print(f"    k = {k1:.6f} ps⁻¹,  R² = {r2_1:.4f},  t½ = {half_life:.1f} ps")

        # ---- 5. Test fit_second_order ----
        print("\n[5] Testing fit_second_order (A + B → products) ...")
        k2, r2_2 = fit_second_order(conc_df["Time_ps"], conc_df["H2O"], conc_df["H2O"])
        print(f"    k = {k2:.6f} L·mol⁻¹·ps⁻¹,  R² = {r2_2:.4f}")

        # ---- 6. Test compute_initial_rate ----
        print("\n[6] Testing compute_initial_rate ...")
        rate0, r2_r0 = compute_initial_rate(conc_df["Time_ps"], conc_df["H2O"], window_frames=4)
        print(f"    initial rate = {rate0:.6f} mol·L⁻¹·ps⁻¹,  R² = {r2_r0:.4f}")

        # ---- 7. Test arrhenius_fit ----
        print("\n[7] Testing arrhenius_fit ...")
        temps = [300, 350, 400, 450, 500]
        # Generate k values from Ea=15 kcal/mol, A=1e12
        Ea_true = 15.0
        A_true = 1e12
        rates = [A_true * math.exp(-Ea_true / (R_KCAL * T)) for T in temps]
        # Add tiny noise
        np.random.seed(42)
        rates_noisy = [r * (1 + 0.01 * np.random.randn()) for r in rates]
        Ea_fit, A_fit, r2_arr = arrhenius_fit(temps, rates_noisy)
        print(f"    True  Ea = {Ea_true:.2f} kcal/mol,  A = {A_true:.2e}")
        print(f"    Fit   Ea = {Ea_fit:.2f} kcal/mol,  A = {A_fit:.2e},  R² = {r2_arr:.4f}")

        # ---- 8. Test parse_reaxff_species ----
        print("\n[8] Testing parse_reaxff_species ...")
        species_content = """# Timestep  No_specs  Species_name  Count  ...
 0          3          H2O           100    H2            0      O2            0
 1000       3          H2O           90     H2            5      O2            2
 2000       3          H2O           81     H2            9      O2            4
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".species", delete=False) as f:
            f.write(species_content)
            spec_path = f.name
        spec_df = parse_reaxff_species(spec_path)
        print(spec_df.to_string(index=False))
        os.unlink(spec_path)

        # ---- 9. Test parse_lammps_dump_molecules ----
        print("\n[9] Testing parse_lammps_dump_molecules ...")
        mol_df = parse_lammps_dump_molecules(dump_path, type_to_species=type_map)
        print(mol_df.to_string(index=False))

        print("\n" + "=" * 65)
        print("  All tests passed.")
        print("=" * 65)

    finally:
        os.unlink(dump_path)
