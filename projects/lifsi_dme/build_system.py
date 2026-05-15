#!/usr/bin/env python3
"""
Build 1M LiFSI/DME electrolyte system for GROMACS simulation.
Uses OPLS-AA force field with custom FSI- parameters.

1M LiFSI in DME:
  - DME density ~0.867 g/mL at 25°C
  - Molar mass DME = 90.12 g/mol
  - For 1M: 1 mol LiFSI + enough DME for 1 L solution
  - LiFSI Mw = 187.07 g/mol
  
  At 1M concentration:
  - 1 mol LiFSI + ~0.867 kg DME = 9.62 mol DME
  - Ratio: ~9.6 DME per LiFSI
  
  Target: ~8000 atoms for good statistics
  With 75 LiFSI + 720 DME: 75*1 + 75*9 + 720*16 = 75 + 675 + 11520 = 12270 atoms (too many)
  With 50 LiFSI + 480 DME: 50 + 450 + 7680 = 8180 atoms ✓
"""

import numpy as np
import os, sys, subprocess, shutil

# ============================================================
# Configuration
# ============================================================
N_LIFSI = 50          # Number of LiFSI ion pairs
N_DME = 480           # Number of DME molecules (~9.6 per LiFSI for 1M)
BOX_SIZE = 5.0        # nm initial box size

JOB_DIR = "/home/xenon/xhy/motus/projects/lifsi_dme"
FF_DIR = os.path.join(JOB_DIR, "forcefield")
os.makedirs(FF_DIR, exist_ok=True)

# ============================================================
# Generate FSI- molecule structure (N(SO2F)2-)
# ============================================================
def gen_fsi_gro():
    """Generate FSI- coordinates using idealized geometry"""
    atoms = []
    
    # Central N at origin
    atoms.append(("FSI", "N", 0, 0.000, 0.000, 0.000))
    
    # S1 and S2 - S-N-S angle ~126°
    theta = np.radians(63)
    d_sn = 0.157
    s1_x = d_sn * np.sin(theta)
    s1_z = d_sn * np.cos(theta)
    atoms.append(("FSI", "S1", 0, s1_x, 0.000, s1_z))
    atoms.append(("FSI", "S2", 0, -s1_x, 0.000, -s1_z))
    
    # O atoms on S1 (O=S=O ~118°, rotated ~45° from N-S plane)
    d_so = 0.143
    o_angle = np.radians(59)
    o_rot = np.radians(45)
    
    o1a_x = s1_x + d_so * np.sin(o_angle) * np.cos(o_rot)
    o1a_y = d_so * np.sin(o_angle) * np.sin(o_rot)
    o1a_z = s1_z + d_so * np.cos(o_angle)
    atoms.append(("FSI", "O1A", 0, o1a_x, o1a_y, o1a_z))
    
    o1b_x = s1_x + d_so * np.sin(o_angle) * np.cos(-o_rot)
    o1b_y = d_so * np.sin(o_angle) * np.sin(-o_rot)
    o1b_z = s1_z - d_so * np.cos(o_angle)
    atoms.append(("FSI", "O1B", 0, o1b_x, o1b_y, o1b_z))
    
    # F on S1
    d_sf = 0.158
    f_angle = np.radians(100)
    f1_x = s1_x + d_sf * np.sin(f_angle)
    f1_z = s1_z - d_sf * np.cos(f_angle)
    atoms.append(("FSI", "F1", 0, f1_x, 0.0, f1_z))
    
    # O atoms on S2
    o2a_x = -s1_x + d_so * np.sin(o_angle) * np.cos(o_rot)
    o2a_y = d_so * np.sin(o_angle) * np.sin(o_rot)
    o2a_z = -s1_z - d_so * np.cos(o_angle)
    atoms.append(("FSI", "O2A", 0, o2a_x, o2a_y, o2a_z))
    
    o2b_x = -s1_x + d_so * np.sin(o_angle) * np.cos(-o_rot)
    o2b_y = d_so * np.sin(o_angle) * np.sin(-o_rot)
    o2b_z = -s1_z + d_so * np.cos(o_angle)
    atoms.append(("FSI", "O2B", 0, o2b_x, o2b_y, o2b_z))
    
    # F on S2
    f2_x = -s1_x - d_sf * np.sin(f_angle)
    f2_z = -s1_z + d_sf * np.cos(f_angle)
    atoms.append(("FSI", "F2", 0, f2_x, 0.0, f2_z))
    
    return atoms

# ============================================================
# Generate DME molecule structure (CH3-O-CH2-CH2-O-CH3)
# ============================================================
def gen_dme_gro():
    """Generate DME coordinates - all-trans conformation"""
    atoms = []
    
    # C1 (methyl)
    c1 = np.array([-0.350, 0.000, 0.000])
    atoms.append(("DME", "C1", 0, c1[0], c1[1], c1[2]))
    atoms.append(("DME", "H1A", 0, c1[0]-0.089, 0.089, 0.063))
    atoms.append(("DME", "H1B", 0, c1[0]-0.089, -0.089, 0.063))
    atoms.append(("DME", "H1C", 0, c1[0]-0.089, 0.000, -0.126))
    
    # O1
    o1 = np.array([-0.140, 0.000, 0.000])
    atoms.append(("DME", "O1", 0, o1[0], o1[1], o1[2]))
    
    # C2
    c2 = np.array([0.070, 0.000, 0.000])
    atoms.append(("DME", "C2", 0, c2[0], c2[1], c2[2]))
    atoms.append(("DME", "H2A", 0, c2[0]+0.089, 0.089, 0.063))
    atoms.append(("DME", "H2B", 0, c2[0]+0.089, -0.089, 0.063))
    
    # C3
    c3 = np.array([0.280, 0.000, 0.000])
    atoms.append(("DME", "C3", 0, c3[0], c3[1], c3[2]))
    atoms.append(("DME", "H3A", 0, c3[0]+0.089, 0.089, 0.063))
    atoms.append(("DME", "H3B", 0, c3[0]+0.089, -0.089, 0.063))
    
    # O2
    o2 = np.array([0.490, 0.000, 0.000])
    atoms.append(("DME", "O2", 0, o2[0], o2[1], o2[2]))
    
    # C4 (methyl)
    c4 = np.array([0.700, 0.000, 0.000])
    atoms.append(("DME", "C4", 0, c4[0], c4[1], c4[2]))
    atoms.append(("DME", "H4A", 0, c4[0]+0.089, 0.089, 0.063))
    atoms.append(("DME", "H4B", 0, c4[0]+0.089, -0.089, 0.063))
    atoms.append(("DME", "H4C", 0, c4[0]+0.089, 0.000, -0.126))
    
    return atoms

# ============================================================
# Write GRO file
# ============================================================
def write_gro(filename, all_atoms, box_size):
    """Write GROMACS GRO format"""
    with open(filename, 'w') as f:
        f.write("1M LiFSI/DME electrolyte\n")
        f.write(f"{len(all_atoms)}\n")
        for i, (resname, atname, resid, x, y, z) in enumerate(all_atoms, 1):
            f.write(f"{resid:5d}{resname:<5s}{atname:>5s}{i:5d}{x:8.3f}{y:8.3f}{z:8.3f}\n")
        f.write(f"{box_size:10.5f}{box_size:10.5f}{box_size:10.5f}\n")

# ============================================================
# Write TOP file
# ============================================================
def write_top(filename, n_li, n_fsi, n_dme):
    """Write GROMACS topology"""
    with open(filename, 'w') as f:
        f.write("; Topology for 1M LiFSI/DME electrolyte\n")
        f.write("#include \"ff_lifsi_dme.itp\"\n\n")
        f.write("[ system ]\n")
        f.write("LiFSI/DME electrolyte\n\n")
        f.write("[ molecules ]\n")
        f.write(f"LI   {n_li}\n")
        f.write(f"FSI  {n_fsi}\n")
        f.write(f"DME  {n_dme}\n")

# ============================================================
# Main builder
# ============================================================
def main():
    print("=" * 60)
    print("Building 1M LiFSI/DME Electrolyte System")
    print("=" * 60)
    
    # Generate molecule structures
    fsi_atoms = gen_fsi_gro()
    dme_atoms = gen_dme_gro()
    
    print(f"\nFSI- atoms: {len(fsi_atoms)}")
    print(f"DME atoms:  {len(dme_atoms)}")
    print(f"Li+ atoms:  1")
    
    # Place molecules randomly in box
    np.random.seed(42)
    box = BOX_SIZE
    
    all_atoms = []
    
    # Place Li+ ions
    for i in range(N_LIFSI):
        x = np.random.uniform(-box/2 + 0.3, box/2 - 0.3)
        y = np.random.uniform(-box/2 + 0.3, box/2 - 0.3)
        z = np.random.uniform(-box/2 + 0.3, box/2 - 0.3)
        all_atoms.append(("LI", "LI", i+1, x, y, z))
    
    # Place FSI- ions
    for i in range(N_LIFSI):
        cx = np.random.uniform(-box/2 + 0.3, box/2 - 0.3)
        cy = np.random.uniform(-box/2 + 0.3, box/2 - 0.3)
        cz = np.random.uniform(-box/2 + 0.3, box/2 - 0.3)
        
        # Random rotation matrix
        theta = np.random.uniform(0, 2*np.pi)
        phi = np.random.uniform(0, np.pi)
        psi = np.random.uniform(0, 2*np.pi)
        
        for resname, atname, resid, x, y, z in fsi_atoms:
            # Rotation about z
            x1 = x * np.cos(theta) - y * np.sin(theta)
            y1 = x * np.sin(theta) + y * np.cos(theta)
            z1 = z
            # Rotation about x
            x2 = x1
            y2 = y1 * np.cos(phi) - z1 * np.sin(phi)
            z2 = y1 * np.sin(phi) + z1 * np.cos(phi)
            # Rotation about y
            x3 = x2 * np.cos(psi) + z2 * np.sin(psi)
            y3 = y2
            z3 = -x2 * np.sin(psi) + z2 * np.cos(psi)
            
            all_atoms.append(("FSI", atname, i+1, 
                            cx + x3, cy + y3, cz + z3))
    
    # Place DME molecules
    for i in range(N_DME):
        cx = np.random.uniform(-box/2 + 0.3, box/2 - 0.3)
        cy = np.random.uniform(-box/2 + 0.3, box/2 - 0.3)
        cz = np.random.uniform(-box/2 + 0.3, box/2 - 0.3)
        
        theta = np.random.uniform(0, 2*np.pi)
        phi = np.random.uniform(0, np.pi)
        psi = np.random.uniform(0, 2*np.pi)
        
        for resname, atname, resid, x, y, z in dme_atoms:
            x1 = x * np.cos(theta) - y * np.sin(theta)
            y1 = x * np.sin(theta) + y * np.cos(theta)
            z1 = z
            x2 = x1
            y2 = y1 * np.cos(phi) - z1 * np.sin(phi)
            z2 = y1 * np.sin(phi) + z1 * np.cos(phi)
            x3 = x2 * np.cos(psi) + z2 * np.sin(psi)
            y3 = y2
            z3 = -x2 * np.sin(psi) + z2 * np.cos(psi)
            
            all_atoms.append(("DME", atname, i+1,
                            cx + x3, cy + y3, cz + z3))
    
    total_atoms = len(all_atoms)
    print(f"\nTotal atoms: {total_atoms}")
    print(f"  Li+:  {N_LIFSI}")
    print(f"  FSI-: {N_LIFSI}")
    print(f"  DME:  {N_DME}")
    
    # Estimate concentration
    vol_nm3 = box**3
    vol_L = vol_nm3 * 1e-24
    conc = (N_LIFSI / 6.022e23) / vol_L
    print(f"  Box: {box} nm ({vol_nm3:.1f} nm³)")
    print(f"  Est. concentration: {conc:.3f} M")
    print(f"  DME:Li ratio: {N_DME/N_LIFSI:.1f}")
    
    # Write GRO
    gro_file = os.path.join(JOB_DIR, "system.gro")
    write_gro(gro_file, all_atoms, box)
    print(f"\nWrote: {gro_file}")
    
    # Write TOP
    top_file = os.path.join(JOB_DIR, "topol.top")
    write_top(top_file, N_LIFSI, N_LIFSI, N_DME)
    print(f"Wrote: {top_file}")
    
    # Copy force field if needed
    src_ff = "/home/xenon/tools/gromacs-2026/share/gromacs/top/oplsaa.ff"
    dst_ff = os.path.join(FF_DIR, "oplsaa.ff")
    if not os.path.exists(dst_ff):
        shutil.copytree(src_ff, dst_ff)
        print(f"Copied OPLS-AA to: {dst_ff}")
    
    print("\nDone! System ready for GROMACS.")
    return total_atoms

if __name__ == "__main__":
    main()
