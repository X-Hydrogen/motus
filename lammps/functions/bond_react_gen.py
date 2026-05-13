#!/usr/bin/env python3
"""Bond/React template generator for LAMMPS fix bond/react.

Generates:
  - Molecule template files (.moltemplate) in LAMMPS native format
  - Map files with InitiatorIDs, EdgeIDs, Equivalences sections

The generated files work with:
  molecule <id> <template_file>
  fix <id> all bond/react react <name> <group> <Nevery> <r_cut> <d_cut> <mol_pre> <mol_post> <map_file>
"""

import yaml
import sys
import os
from collections import defaultdict

# Atom type mapping (element -> LAMMPS type number, must match data file)
ELEM_TO_TYPE = {'C': 1, 'H': 2, 'O': 3, 'N': 4, 'P': 5, 'S': 6}
# Approximate charges per element for common functional groups
ELEM_CHARGES = {'C': 0.5, 'H': 0.3, 'O': -0.5, 'N': -0.7, 'P': 0.5, 'S': -0.3}
# Approximate bond lengths
BOND_LENGTHS = {('C','C'): 1.5, ('C','O'): 1.25, ('C','N'): 1.35, ('N','H'): 1.01, 
                ('O','H'): 0.96, ('C','H'): 1.09, ('O','O'): 1.48}
# Approximate angles
DEFAULT_ANGLE = 109.5


def _build_connectivity(atoms_dict, bonds_list):
    """Build bond/angle sets from atoms and bonds."""
    bonds = set()
    for a, b in bonds_list:
        bonds.add((min(a,b), max(a,b)))
    
    # Build adjacency for angle detection
    adjacency = defaultdict(set)
    for a, b in bonds:
        adjacency[a].add(b)
        adjacency[b].add(a)
    
    angles = set()
    for b in adjacency:
        neighbors = sorted(adjacency[b])
        for i, a in enumerate(neighbors):
            for c in neighbors[i+1:]:
                angles.add((a, b, c))
    
    return sorted(bonds), sorted(angles)


def generate_molecule_template(atoms_dict, bonds_list, molecule_name, charge_override=None):
    """Generate a LAMMPS molecule template file.
    
    Format matches LAMMPS native molecule template (not JSON).
    
    Parameters
    ----------
    atoms_dict : dict
        {atom_id: element_symbol} e.g. {1: 'C', 2: 'O', ...}
    bonds_list : list
        [[a, b], ...] pairs of atom IDs
    molecule_name : str
        Description string
    charge_override : dict, optional
        {atom_id: charge} overrides
    
    Returns
    -------
    str : molecule template content
    """
    bonds_sorted, angles_sorted = _build_connectivity(atoms_dict, bonds_list)
    atom_ids = sorted(atoms_dict.keys())
    n_atoms = len(atom_ids)
    n_bonds = len(bonds_sorted)
    n_angles = len(angles_sorted)
    
    lines = [molecule_name, "",
             f"     {n_atoms} atoms",
             f"     {n_bonds} bonds",
             f"     {n_angles} angles",
             f"     0 dihedrals",
             f"     0 impropers",
             "",
             "Coords", ""]
    
    # Generate approximate 3D coordinates
    coords = _generate_coords(atoms_dict, bonds_list, atom_ids)
    for aid in atom_ids:
        x, y, z = coords[aid]
        lines.append(f"{aid:4d}  {x:12.6f}  {y:12.6f}  {z:12.6f}")
    
    lines.extend(["", "Types", ""])
    for aid in atom_ids:
        elem = atoms_dict[aid]
        atype = ELEM_TO_TYPE.get(elem, 1)
        lines.append(f"{aid:4d}  {atype}")
    
    lines.extend(["", "Charges", ""])
    for aid in atom_ids:
        if charge_override and aid in charge_override:
            q = charge_override[aid]
        else:
            elem = atoms_dict[aid]
            q = ELEM_CHARGES.get(elem, 0.0)
        lines.append(f"{aid:4d}  {q:.6f}")
    
    lines.extend(["", "Molecules", ""])
    for aid in atom_ids:
        lines.append(f"{aid:4d}  1")
    
    lines.extend(["", "Bonds", ""])
    for i, (a, b) in enumerate(bonds_sorted):
        lines.append(f"{i+1:4d}  1  {a}  {b}")
    
    lines.extend(["", "Angles", ""])
    for i, (a, b, c) in enumerate(angles_sorted):
        lines.append(f"{i+1:4d}  1  {a}  {b}  {c}")
    
    return '\n'.join(lines)


def _generate_coords(atoms_dict, bonds_list, atom_ids):
    """Generate approximate 3D coordinates for molecule(s) based on bond topology.
    
    Handles disconnected components (multiple product molecules) by starting
    a new BFS tree for each unplaced atom.
    """
    from math import cos, sin, pi
    import numpy as np
    
    coords = {}
    if not atom_ids:
        return coords
    
    # Build adjacency
    adj = defaultdict(list)
    for a, b in bonds_list:
        adj[a].append(b)
        adj[b].append(a)
    
    offset = np.array([0.0, 0.0, 0.0])
    component_spacing = 5.0  # Å between disconnected components
    
    # Handle disconnected components
    for start_id in atom_ids:
        if start_id in coords:
            continue
        
        # Start new component
        coords[start_id] = offset.copy()
        queue = [start_id]
        
        while queue:
            parent = queue.pop(0)
            for child in adj[parent]:
                if child in coords:
                    continue
                e1 = atoms_dict.get(parent, 'C')
                e2 = atoms_dict.get(child, 'C')
                bl = BOND_LENGTHS.get((e1, e2), BOND_LENGTHS.get((e2, e1), 1.5))
                
                theta = np.random.uniform(0, 2*pi) if child % 2 == 0 else pi/3
                phi = np.random.uniform(0, pi) if child % 3 == 0 else pi/4
                direction = np.array([
                    sin(phi) * cos(theta),
                    sin(phi) * sin(theta),
                    cos(phi)
                ])
                coords[child] = coords[parent] + direction * bl
                queue.append(child)
        
        offset += np.array([component_spacing, 0.0, 0.0])
    
    return coords


def generate_map_file(reaction, pre_mol_atoms):
    """Generate a map file for fix bond/react.
    
    Parameters
    ----------
    reaction : dict
        Reaction definition from YAML
    pre_mol_atoms : dict
        {atom_id: element} for the educt
    
    Returns
    -------
    str : map file content
    """
    name = reaction['name']
    educt_atoms = reaction['educt']['atoms']
    products = reaction['products']
    constraints = reaction.get('constraints', [])
    
    # --- Determine edge bonds ---
    edge_ids = []
    initiator_atoms = set()
    
    # Look for distance constraints = bonds to break
    for c in constraints:
        # Support both list format [type, a, b] and dict format {type: [a, b]}
        if isinstance(c, dict):
            for key, val in c.items():
                if key == 'distance' and len(val) >= 2:
                    a, b = val[0], val[1]
                    bonds = reaction['educt'].get('bonds', [])
                    for bi, (ba, bb) in enumerate(bonds):
                        if (ba == a and bb == b) or (ba == b and bb == a):
                            edge_ids.append(bi + 1)
                            initiator_atoms.add(a)
                            initiator_atoms.add(b)
                            break
        elif isinstance(c, list) and len(c) >= 3:
            if c[0] == 'distance':
                a, b = c[1], c[2]
            # Find bond ID in the educt bonds list
            bonds = reaction['educt'].get('bonds', [])
            for bi, (ba, bb) in enumerate(bonds):
                if (ba == a and bb == b) or (ba == b and bb == a):
                    edge_ids.append(bi + 1)  # 1-based bond index
                    initiator_atoms.add(a)
                    initiator_atoms.add(b)
                    break
    
    if not edge_ids:
        # Default: use first bond as edge
        edge_ids = [1]
        bonds = reaction['educt'].get('bonds', [])
        if bonds:
            initiator_atoms.add(bonds[0][0])
            initiator_atoms.add(bonds[0][1])
    
    # --- Build equivalences ---
    # Map educt atoms to product atoms by element matching
    equivalences = {}
    used_products = defaultdict(set)  # product_mol_id -> set of used atom ids
    
    for educt_id, eelem in sorted(educt_atoms.items()):
        for pi, product in enumerate(products):
            patoms = product['atoms']
            for pid, pelem in patoms.items():
                if pelem == eelem and pid not in used_products.get(pi+1, set()):
                    equivalences[educt_id] = (pi + 1, pid)
                    used_products.setdefault(pi+1, set()).add(pid)
                    break
            if educt_id in equivalences:
                break
    
    # --- Write map file ---
    lines = [f"{name} map file", "",
             f"{len(edge_ids)} edgeIDs",
             f"{len(educt_atoms)} equivalences",
             "",
             "InitiatorIDs", ""]
    
    initiators = sorted(initiator_atoms)[:2]
    for init in initiators:
        lines.append(str(init))
    
    lines.extend(["", "EdgeIDs", ""])
    for eid in edge_ids:
        lines.append(str(eid))
    
    # Build global ID lookup: (product_index, local_patom_id) -> global_id
    global_id_map = {}
    atom_counter = 0
    for pi, product in enumerate(products):
        for local_id in sorted(product['atoms'].keys()):
            atom_counter += 1
            global_id_map[(pi, local_id)] = atom_counter
    
    lines.extend(["", "Equivalences", ""])
    for educt_id in sorted(educt_atoms.keys()):
        if educt_id in equivalences:
            mol_id, patom_id = equivalences[educt_id]
            global_pid = global_id_map.get((mol_id - 1, patom_id), patom_id)
            lines.append(f"{educt_id}  {global_pid}")
        else:
            lines.append(f"# {educt_id}  unmapped")
    
    return '\\n'.join(lines)


def generate_all_templates(yaml_path, output_dir):
    """Generate all template files from a reaction YAML."""
    os.makedirs(output_dir, exist_ok=True)
    
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    
    reactions = data.get('reactions', [])
    
    for reaction in reactions:
        rname = reaction['name']
        educt = reaction['educt']
        educt_atoms = educt['atoms']
        educt_bonds = educt.get('bonds', [])
        
        # Pre-reaction molecule template (educt)
        pre_content = generate_molecule_template(
            educt_atoms, educt_bonds,
            f"{rname} - pre-reaction template"
        )
        pre_path = os.path.join(output_dir, f"{rname}.pre.moltemplate")
        with open(pre_path, 'w') as f:
            f.write(pre_content)
        print(f"  ✓ {pre_path}")
        
        # Post-reaction molecule template (combined products)
        # Combine all product atoms into one template with sequential global IDs
        post_atoms = {}
        post_bonds = []
        post_mols = {}      # global_atom_id -> molecule_number
        local_to_global = {}  # (product_index, local_id) -> global_id
        atom_counter = 0
        
        for pi, product in enumerate(reaction['products']):
            patoms = product['atoms']
            pbonds = product.get('bonds', [])
            
            for local_id in sorted(patoms.keys()):
                atom_counter += 1
                local_to_global[(pi, local_id)] = atom_counter
                post_atoms[atom_counter] = patoms[local_id]
                post_mols[atom_counter] = pi + 1
            
            for a, b in pbonds:
                ga = local_to_global.get((pi, a), a)
                gb = local_to_global.get((pi, b), b)
                post_bonds.append([ga, gb])
        
        n_mols = len(reaction['products'])
        post_content = generate_molecule_template(
            post_atoms, post_bonds,
            f"{rname} - post-reaction template ({n_mols} molecules)",
        )
        
        # Fix molecule numbers in post template
        post_lines = post_content.split('\n')
        new_lines = []
        in_molecules = False
        for line in post_lines:
            if line.strip() == 'Molecules':
                in_molecules = True
                new_lines.append(line)
                new_lines.append('')
                continue
            if in_molecules and line.strip() == '':
                in_molecules = False
            if in_molecules and line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    aid = int(parts[0])
                    mol = post_mols.get(aid, 1)
                    new_lines.append(f'{aid:4d}  {mol}')
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        post_content = '\n'.join(new_lines)
        post_path = os.path.join(output_dir, f"{rname}.post.moltemplate")
        with open(post_path, 'w') as f:
            f.write(post_content)
        print(f"  ✓ {post_path}")
        
        # Map file
        map_content = generate_map_file(reaction, educt_atoms)
        map_path = os.path.join(output_dir, f"{rname}.map")
        with open(map_path, 'w') as f:
            f.write(map_content)
        print(f"  ✓ {map_path}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 bond_react_gen.py <reaction.yaml> [output_dir]")
        print("  Generates .pre.moltemplate, .post.moltemplate, and .map files")
        sys.exit(1)
    
    yaml_path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(yaml_path) or '.'
    
    print(f"Generating templates from: {yaml_path}")
    generate_all_templates(yaml_path, outdir)
    print("\nDone.")
