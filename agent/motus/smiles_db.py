"""
MOTUS SMILES Knowledge Base — Common molecules for MD simulations.

Every molecule here has a validated SMILES string. The MOTUS pipeline:
  1. SMILES → OpenBabel gen3d + MMFF94 minimize → 3D PDB
  2. 3D PDBs → Packmol assembly → system.gro
  3. system.gro + topol.top → GROMACS / LAMMPS MD

NO hand-written coordinates. NO API network calls needed for common molecules.
Add new entries as needed.

Sources of truth:
  - PubChem
  - Wikipedia
  - Chemical intuition (verified by OpenBabel)

Format: "name" → {smiles, category, notes}
"""
MOLECULES = {
    # ===== Solvents =====
    "water":       {"smiles": "O",            "category": "solvent", "notes": "SPC/E, TIP3P, TIP4P"},
    "methanol":    {"smiles": "CO",           "category": "solvent", "notes": "Polar protic"},
    "ethanol":     {"smiles": "CCO",          "category": "solvent", "notes": "Polar protic"},
    "isopropanol": {"smiles": "CC(C)O",       "category": "solvent", "notes": "2-propanol, IPA"},
    "acetone":     {"smiles": "CC(=O)C",      "category": "solvent", "notes": "Polar aprotic"},
    "acetonitrile":{"smiles": "CC#N",         "category": "solvent", "notes": "MeCN, polar aprotic"},
    "dmso":        {"smiles": "CS(=O)C",      "category": "solvent", "notes": "Dimethyl sulfoxide"},
    "dmf":         {"smiles": "CN(C)C=O",     "category": "solvent", "notes": "Dimethylformamide"},
    "thf":         {"smiles": "C1CCOC1",      "category": "solvent", "notes": "Tetrahydrofuran"},
    "chloroform":  {"smiles": "ClC(Cl)Cl",    "category": "solvent", "notes": "CHCl3"},
    "dichloromethane": {"smiles": "ClCCl",    "category": "solvent", "notes": "DCM, CH2Cl2"},
    "hexane":      {"smiles": "CCCCCC",       "category": "solvent", "notes": "n-hexane"},
    "cyclohexane": {"smiles": "C1CCCCC1",     "category": "solvent", "notes": "Nonpolar"},
    "toluene":     {"smiles": "CC1=CC=CC=C1", "category": "solvent", "notes": "Methylbenzene"},
    "benzene":     {"smiles": "C1=CC=CC=C1",  "category": "solvent", "notes": "Aromatic"},
    "ethyl_acetate":{"smiles": "CC(=O)OCC",   "category": "solvent", "notes": "EtOAc"},
    "nmp":         {"smiles": "CN1CCCC1=O",   "category": "solvent", "notes": "N-Methyl-2-pyrrolidone"},
    "glycerol":    {"smiles": "C(C(CO)O)O",   "category": "solvent", "notes": "Glycerin, viscous"},

    # ===== Simple gases / small molecules =====
    "methane":     {"smiles": "C",            "category": "gas", "notes": "CH4, natural gas"},
    "ethane":      {"smiles": "CC",           "category": "gas", "notes": "C2H6"},
    "propane":     {"smiles": "CCC",          "category": "gas", "notes": "C3H8"},
    "butane":      {"smiles": "CCCC",         "category": "gas", "notes": "n-butane, C4H10"},
    "isobutane":   {"smiles": "CC(C)C",       "category": "gas", "notes": "2-methylpropane"},
    "ethylene":    {"smiles": "C=C",          "category": "gas", "notes": "Ethene, C2H4"},
    "acetylene":   {"smiles": "C#C",          "category": "gas", "notes": "Ethyne, C2H2"},
    "carbon_dioxide": {"smiles": "O=C=O",     "category": "gas", "notes": "CO2"},
    "ammonia":     {"smiles": "N",            "category": "gas", "notes": "NH3"},
    "nitrogen":    {"smiles": "N#N",          "category": "gas", "notes": "N2 (dummy, use gas model)"},
    "oxygen":      {"smiles": "O=O",          "category": "gas", "notes": "O2"},
    "hydrogen":    {"smiles": "[H][H]",       "category": "gas", "notes": "H2"},
    "hydrogen_sulfide": {"smiles": "S",       "category": "gas", "notes": "H2S"},
    "sulfur_dioxide": {"smiles": "O=S=O",     "category": "gas", "notes": "SO2"},

    # ===== Common organics =====
    "formaldehyde": {"smiles": "C=O",         "category": "organic", "notes": "Methanal"},
    "acetaldehyde": {"smiles": "CC=O",        "category": "organic", "notes": "Ethanal"},
    "formic_acid":  {"smiles": "C(=O)O",      "category": "organic", "notes": "Methanoic acid"},
    "acetic_acid":  {"smiles": "CC(=O)O",     "category": "organic", "notes": "Ethanoic acid"},
    "urea":         {"smiles": "C(=O)(N)N",   "category": "organic", "notes": "Carbamide, (NH2)2CO"},
    "thiourea":     {"smiles": "C(=S)(N)N",   "category": "organic", "notes": "Sulfur analog of urea"},
    "glycine":      {"smiles": "C(C(=O)O)N",  "category": "organic", "notes": "Amino acid, Gly"},
    "glucose":      {"smiles": "C(C1C(C(C(C(O1)O)O)O)O)O", "category": "organic", "notes": "D-glucose, open chain"},
    "fructose":     {"smiles": "C(C(C(C(=O)CO)O)O)O", "category": "organic", "notes": "D-fructose"},
    "sucrose":      {"smiles": "C(C1C(C(C(C(O1)OC2(C(C(C(O2)CO)O)O)CO)O)O)O)O", "category": "organic", "notes": "Table sugar"},
    "caffeine":     {"smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C", "category": "organic", "notes": "Stimulant"},
    "phenol":       {"smiles": "C1=CC=C(C=C1)O", "category": "organic", "notes": "Hydroxybenzene"},
    "aniline":      {"smiles": "C1=CC=C(C=C1)N", "category": "organic", "notes": "Aminobenzene"},
    "benzoic_acid": {"smiles": "C1=CC=C(C=C1)C(=O)O", "category": "organic", "notes": ""},
    "naphthalene":  {"smiles": "C1=CC=C2C=CC=CC2=C1", "category": "organic", "notes": "PAH"},
    "anthracene":   {"smiles": "C1=CC=C2C=C3C=CC=CC3=CC2=C1", "category": "organic", "notes": "3-ring PAH"},
    "pyrene":       {"smiles": "C1=CC2=C3C(=C1)C=CC4=CC=CC(=C43)C=C2", "category": "organic", "notes": "4-ring PAH"},

    # ===== Polymers / monomers =====
    "ethylene_oxide": {"smiles": "C1CO1",     "category": "polymer", "notes": "EO monomer, oxirane"},
    "propylene_oxide":{"smiles": "CC1CO1",    "category": "polymer", "notes": "PO monomer"},
    "styrene":       {"smiles": "C=CC1=CC=CC=C1", "category": "polymer", "notes": "Vinylbenzene"},
    "methyl_methacrylate": {"smiles": "CC(=C)C(=O)OC", "category": "polymer", "notes": "MMA monomer"},
    "acrylic_acid":  {"smiles": "C=CC(=O)O",  "category": "polymer", "notes": "AA monomer"},
    "acrylamide":    {"smiles": "C=CC(=O)N",  "category": "polymer", "notes": "AM monomer"},
    "caprolactam":   {"smiles": "C1CCC(=O)NCC1", "category": "polymer", "notes": "Nylon-6 monomer"},
    "lactic_acid":   {"smiles": "CC(C(=O)O)O", "category": "polymer", "notes": "PLA monomer"},

    # ===== Ionic liquids =====
    "bmim":         {"smiles": "CCCCN1C=[N+](C)C=C1", "category": "ionic_liquid", "notes": "BMIM cation"},
    "emim":         {"smiles": "CCN1C=[N+](C)C=C1",   "category": "ionic_liquid", "notes": "EMIM cation"},
    "bf4":          {"smiles": "[B-](F)(F)(F)F", "category": "ionic_liquid", "notes": "Tetrafluoroborate anion"},
    "pf6":          {"smiles": "[P-](F)(F)(F)(F)(F)F", "category": "ionic_liquid", "notes": "Hexafluorophosphate anion"},
    "tfsi":         {"smiles": "C(F)(F)(F)S(=O)(=O)[N-]S(=O)(=O)C(F)(F)F", "category": "ionic_liquid", "notes": "NTf2 anion, bistriflimide"},

    # ===== Hydrate promoters / inhibitors =====
    "thf_hydrate":  {"smiles": "C1CCOC1",     "category": "hydrate", "notes": "sII hydrate promoter (same as THF)"},
    "cyclopentane": {"smiles": "C1CCCC1",     "category": "hydrate", "notes": "sII hydrate former"},
    "propane_hydrate":{"smiles": "CCC",       "category": "hydrate", "notes": "sII hydrate former"},
    "pvp":          {"smiles": "C=CN1CCCC1=O", "category": "hydrate", "notes": "PVP monomer, KHI"},
    "pvc":          {"smiles": "C=CCl",        "category": "hydrate", "notes": "PVCap monomer, KHI"},

    # ===== Surfactants =====
    "sds":          {"smiles": "CCCCCCCCCCCCOS(=O)(=O)[O-]", "category": "surfactant", "notes": "Sodium dodecyl sulfate"},
    "ctab":         {"smiles": "CCCCCCCCCCCCCCCC[N+](C)(C)C", "category": "surfactant", "notes": "Cetyltrimethylammonium"},
    "decane":       {"smiles": "CCCCCCCCCC",  "category": "surfactant", "notes": "n-decane, oil phase"},
    "dodecane":     {"smiles": "CCCCCCCCCCCC","category": "surfactant", "notes": "n-dodecane"},

    # ===== Drugs / biomolecules =====
    "aspirin":      {"smiles": "CC(=O)OC1=CC=CC=C1C(=O)O", "category": "drug", "notes": "Acetylsalicylic acid"},
    "paracetamol":  {"smiles": "CC(=O)NC1=CC=C(C=C1)O", "category": "drug", "notes": "Acetaminophen"},
    "ibuprofen":    {"smiles": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O", "category": "drug", "notes": "NSAID"},
    "dopamine":     {"smiles": "C1=CC(=C(C=C1CCN)O)O", "category": "drug", "notes": "Neurotransmitter"},
    "serotonin":    {"smiles": "C1=CC2=C(C=C1O)C(=CN2)CCN", "category": "drug", "notes": "5-HT"},
    "testosterone": {"smiles": "C[C@]12CC[C@H]3[C@@H](CCC4=CC(=O)CC[C@]34C)[C@@H]1CC[C@@H]2O", "category": "drug", "notes": "Androgen steroid"},

    # ===== Explosives / energetic materials =====
    "tnt":          {"smiles": "CC1=C(C=C(C=C1[N+](=O)[O-])[N+](=O)[O-])[N+](=O)[O-]", "category": "energetic", "notes": "Trinitrotoluene"},
    "rdx":          {"smiles": "C1N(CN(CN1[N+](=O)[O-])[N+](=O)[O-])[N+](=O)[O-]", "category": "energetic", "notes": "Cyclotrimethylenetrinitramine"},
    "hmx":          {"smiles": "C1N(CN(CN(CN1[N+](=O)[O-])[N+](=O)[O-])[N+](=O)[O-])[N+](=O)[O-]", "category": "energetic", "notes": "Octogen"},
    "nitroglycerin":{"smiles": "C(C(CO[N+](=O)[O-])O[N+](=O)[O-])O[N+](=O)[O-]", "category": "energetic", "notes": "NG"},
    "nitromethane": {"smiles": "C[N+](=O)[O-]", "category": "energetic", "notes": "NM"},
    # ===== Battery electrolytes =====
    "dme":       {"smiles": "COCCOC",                         "category": "solvent", "notes": "1,2-dimethoxyethane, glyme, Li-battery solvent"},
    "li+":       {"smiles": "[Li+]",                          "category": "ion", "notes": "Lithium cation, charge +1"},
    "fsi-":      {"smiles": "N(S(=O)(=O)F)S(=O)(=O)F",       "category": "ion", "notes": "Bis(fluorosulfonyl)imide anion, charge -1"},

}

# Aliases — map common alternative names to canonical keys
ALIASES = {
    "h2o": "water",
    "ch4": "methane",
    "co2": "carbon_dioxide",
    "nh3": "ammonia",
    "meoh": "methanol",
    "etoh": "ethanol",
    "ipa": "isopropanol",
    "thf": "thf",
    "dmso": "dmso",
    "dmf": "dmf",
    "dcm": "dichloromethane",
    "etoac": "ethyl_acetate",
    "hoac": "acetic_acid",
    "acoh": "acetic_acid",
    "h2s": "hydrogen_sulfide",
    "so2": "sulfur_dioxide",
    "c2h4": "ethylene",
    "c2h2": "acetylene",
    "c3h8": "propane",
    "c4h10": "butane",
    "bmim+": "bmim",
    "emim+": "emim",
    "bf4-": "bf4",
    "pf6-": "pf6",
    "ntf2": "tfsi",
    "tfsi-": "tfsi",
    "sds": "sds",
    "tnt": "tnt",
    "rdx": "rdx",
    "hmx": "hmx",
    "nm": "nitromethane",
    "o2": "oxygen",
    "h2": "hydrogen",
    "n2": "nitrogen",
    "lifsi": "fsi-",
    "li": "li+",
    "lithium": "li+",
    "fsi": "fsi-",
    "1,2-dimethoxyethane": "dme",
    "glyme": "dme",

}


def get_smiles(name: str) -> str | None:
    """Look up SMILES for a molecule by name or alias."""
    key = name.lower().strip().replace(" ", "_")
    if key in ALIASES:
        key = ALIASES[key]
    mol = MOLECULES.get(key)
    return mol["smiles"] if mol else None


def get_info(name: str) -> dict | None:
    """Get full molecule info (smiles, category, notes)."""
    key = name.lower().strip().replace(" ", "_")
    if key in ALIASES:
        key = ALIASES[key]
    return MOLECULES.get(key)


def list_by_category(category: str) -> list[str]:
    """List all molecule names in a category."""
    return [name for name, info in MOLECULES.items() if info["category"] == category]


def list_all() -> list[str]:
    """List all known molecule names."""
    return sorted(MOLECULES.keys())


def search(query: str) -> list[str]:
    """Fuzzy search molecule names."""
    q = query.lower()
    results = []
    for name, info in MOLECULES.items():
        if q in name or q in info.get("notes", "").lower():
            results.append(name)
    return results


if __name__ == "__main__":
    print(f"MOTUS SMILES Knowledge Base: {len(MOLECULES)} molecules")
    print(f"Aliases: {len(ALIASES)}")
    print()
    print("Categories:")
    from collections import Counter
    cats = Counter(m["category"] for m in MOLECULES.values())
    for cat, count in cats.most_common():
        print(f"  {cat}: {count}")
