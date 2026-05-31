# protein-design-skills

A collection of [Claude Code](https://claude.com/claude-code) skills for de novo protein design and biomolecular structure prediction. Drop this plugin into Claude Code and your agent gains expert-level operating knowledge of the major open-source tools in the field — installation, CLI flags, input schemas, output layouts, and how to chain them into full design campaigns.

## Skills

| Skill | What it does | Upstream |
|-------|-------------|----------|
| **[biotite](skills/biotite/SKILL.md)** | Biotite — fast, NumPy-backed toolkit to read / manipulate / write structures + sequences, compute RMSD / lDDT / TM-score / SASA / SSE, and fetch from RCSB / AlphaFold DB / UniProt / Entrez / PubChem. The "glue" library for preparing inputs and scoring outputs of the other tools. | [biotite-dev/biotite](https://github.com/biotite-dev/biotite) |
| **[boltz](skills/boltz/SKILL.md)** | Boltz-1 / Boltz-2 — open foundation models for protein, complex, nucleic-acid, and protein-ligand structure + binding-affinity prediction. | [jwohlwend/boltz](https://github.com/jwohlwend/boltz) |
| **[boltzgen](skills/boltzgen/SKILL.md)** | All-atom diffusion model for universal binder design (proteins, peptides, cyclic peptides, nanobodies, Fabs) against protein / small-molecule / nucleic-acid targets. | [HannesStark/boltzgen](https://github.com/HannesStark/boltzgen) |
| **[caver](skills/caver/SKILL.md)** | CAVER 3.0/3.01 — Voronoi-based identification, geometric characterization, clustering, and visualization of transport tunnels in proteins (single PDB or MD ensembles). Packaged to run from an Apptainer/Singularity SIF. | [caver.cz](http://www.caver.cz/) |
| **[chai-lab](skills/chai-lab/SKILL.md)** | Chai-1 — multi-modal foundation model for protein / ligand / nucleic-acid complex structure prediction, with restraints and MSAs. | [chaidiscovery/chai-lab](https://github.com/chaidiscovery/chai-lab) |
| **[disco](skills/disco/SKILL.md)** | DISCO — diffusion model that **co-designs** protein sequence and 3D structure conditioned on small molecules, metals, DNA, or RNA. | [DISCO-design/DISCO](https://github.com/DISCO-design/DISCO) |
| **[esm-biohub](skills/esm-biohub/SKILL.md)** | Biohub's `esm` repo — **ESMC** language model, **ESMFold2** AF3-class structure prediction, **ESM3** generative model, and **ESMC SAEs** for interpretability. Packaged to run from an Apptainer/Singularity SIF. | [Biohub/esm](https://github.com/Biohub/esm) |
| **[fair-esm](skills/fair-esm/SKILL.md)** | Meta FAIR `fair-esm` — ESM-2 / ESM-1b / ESM-1v / MSA Transformer embeddings, ESMFold structure prediction, ESM-IF1 inverse folding, zero-shot variant scoring, and the ESM Metagenomic Atlas. | [facebookresearch/esm](https://github.com/facebookresearch/esm) |
| **[foundry](skills/foundry/SKILL.md)** | Foundry toolkit — RFdiffusion3, RosettaFold3, and the ProteinMPNN / LigandMPNN / SolubleMPNN / EnhancedMPNN / ThermalMPNN family under a shared CLI. Includes extension paths (registering checkpoints, adding architectures). | RC Foundry |
| **[genie3](skills/genie3/SKILL.md)** | Genie 3 — fast all-atom SE(3)-equivariant diffusion model for unconditional generation, motif scaffolding, and hotspot-guided binder design. | [aqlaboratory/genie3](https://github.com/aqlaboratory/genie3) |
| **[invrotzyme](skills/invrotzyme/SKILL.md)** | Build inverse-rotamer theozyme / active-site assemblies from Rosetta enzdes CST files (PyRosetta) — drop-in input for RFdiffusion All-Atom enzyme design. | [ikalvet/invrotzyme](https://github.com/ikalvet/invrotzyme) |
| **[placer](skills/placer/SKILL.md)** | PLACER — atom-level GNN for ligand pose refinement / docking-score, side-chain prediction, and conformational ensembles. Packaged to run from an Apptainer/Singularity SIF. | [baker-laboratory/PLACER](https://github.com/baker-laboratory/PLACER) |
| **[protenix](skills/protenix/SKILL.md)** | Protenix — open-source AlphaFold 3 reproduction for protein / nucleic-acid / ligand / ion complex structure prediction, with MSAs, templates, covalent bonds, and pocket/contact constraints. Packaged to run from an Apptainer/Singularity SIF. | [bytedance/Protenix](https://github.com/bytedance/Protenix) |
| **[protflow](skills/protflow/SKILL.md)** | ProtFlow — compose multi-step design pipelines (RFdiffusion, MPNN family, ESMFold, AF2/AF3, Boltz, Rosetta, GROMACS, …) behind a Poses + Runner API with first-class SLURM array jobs. | [mabr3112/ProtFlow](https://github.com/mabr3112/ProtFlow) |

Each skill ships its `SKILL.md` plus curated `references/` and `examples/` so Claude has the source material on hand when it builds your pipeline.

## Installation

### As a Claude Code plugin (recommended)

```text
/plugin marketplace add LiorZ/protein-design-skills
/plugin install protein-design-skills@protein-design-skills
```

Claude Code will auto-discover every skill under `skills/` and trigger them by name or description match. Verify with `/plugin list` and `/help`.

### Manual install (per-user)

Clone the repo and symlink the skills into your user skills directory:

```bash
git clone https://github.com/LiorZ/protein-design-skills.git
ln -s "$PWD/protein-design-skills/skills"/* ~/.claude/skills/
```

### Manual install (per-project)

```bash
cd your-project
mkdir -p .claude/skills
ln -s /path/to/protein-design-skills/skills/* .claude/skills/
```

## Using the skills

Skills are invoked automatically when your prompt matches their description. You can also invoke one explicitly:

```text
/boltzgen design a 80-residue binder against PD-L1 (PDB 5O45 chain A)
/boltz  predict the complex from this YAML
/genie3 generate 100 backbones of length 120
```

A typical binder-design campaign chains several:

1. **Generate backbones** with `genie3`, `boltzgen`, or `foundry` (RFdiffusion3). For enzymes, build a theozyme with `invrotzyme` first.
2. **Assign sequences** with `foundry` (ProteinMPNN / LigandMPNN / SolubleMPNN) — or let `boltzgen` / `disco` co-design. Score / rerank candidates with `fair-esm`.
3. **Validate** with `boltz`, `chai-lab`, `protenix` (open-source AlphaFold 3), or `fair-esm`'s ESMFold — cross-checking two AF3-class co-folders is a strong signal. For enzyme / ligand pockets, refine and score the ligand pose and side chains with `placer`.
4. **Rank** with ipSAE / pLDDT / iPTM filters described in each skill — and use `biotite` to parse the CIF/PDB outputs and compute the structural metrics (RMSD / lDDT / TM-score / SASA / clashes) you filter on, or to fetch and clean target structures feeding the design steps above.

For multi-step campaigns at cluster scale, drive the whole pipeline with `protflow` (SLURM array jobs, Poses DataFrame, motif tracking).

## Repo layout

```
.
├── .claude-plugin/
│   ├── plugin.json          # plugin manifest
│   └── marketplace.json     # marketplace entry
├── skills/
│   ├── biotite/
│   ├── boltz/
│   ├── boltzgen/
│   ├── caver/
│   ├── chai-lab/
│   ├── disco/
│   ├── esm-biohub/
│   ├── fair-esm/
│   ├── foundry/
│   ├── genie3/
│   ├── invrotzyme/
│   ├── placer/
│   ├── protenix/
│   └── protflow/
└── README.md
```

## Contributing

To add a new skill: create `skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`) and any supporting `references/` and `examples/`. Open a PR.

## License

Each skill's content tracks the upstream tool's license (noted in its frontmatter). The skill packaging in this repo is MIT.
