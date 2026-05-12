# protein-design-skills

A collection of [Claude Code](https://claude.com/claude-code) skills for de novo protein design and biomolecular structure prediction. Drop this plugin into Claude Code and your agent gains expert-level operating knowledge of the major open-source tools in the field — installation, CLI flags, input schemas, output layouts, and how to chain them into full design campaigns.

## Skills

| Skill | What it does | Upstream |
|-------|-------------|----------|
| **[boltz](skills/boltz/SKILL.md)** | Boltz-1 / Boltz-2 — open foundation models for protein, complex, nucleic-acid, and protein-ligand structure + binding-affinity prediction. | [jwohlwend/boltz](https://github.com/jwohlwend/boltz) |
| **[boltzgen](skills/boltzgen/SKILL.md)** | All-atom diffusion model for universal binder design (proteins, peptides, cyclic peptides, nanobodies, Fabs) against protein / small-molecule / nucleic-acid targets. | [HannesStark/boltzgen](https://github.com/HannesStark/boltzgen) |
| **[chai-lab](skills/chai-lab/SKILL.md)** | Chai-1 — multi-modal foundation model for protein / ligand / nucleic-acid complex structure prediction, with restraints and MSAs. | [chaidiscovery/chai-lab](https://github.com/chaidiscovery/chai-lab) |
| **[disco](skills/disco/SKILL.md)** | DISCO — diffusion model that **co-designs** protein sequence and 3D structure conditioned on small molecules, metals, DNA, or RNA. | [DISCO-design/DISCO](https://github.com/DISCO-design/DISCO) |
| **[foundry](skills/foundry/SKILL.md)** | Foundry toolkit — RFdiffusion3, RosettaFold3, and the ProteinMPNN / LigandMPNN / SolubleMPNN / EnhancedMPNN / ThermalMPNN family under a shared CLI. Includes extension paths (registering checkpoints, adding architectures). | RC Foundry |
| **[genie3](skills/genie3/SKILL.md)** | Genie 3 — fast all-atom SE(3)-equivariant diffusion model for unconditional generation, motif scaffolding, and hotspot-guided binder design. | [aqlaboratory/genie3](https://github.com/aqlaboratory/genie3) |

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

1. **Generate backbones** with `genie3`, `boltzgen`, or `foundry` (RFdiffusion3).
2. **Assign sequences** with `foundry` (ProteinMPNN / LigandMPNN / SolubleMPNN) — or let `boltzgen` / `disco` co-design.
3. **Validate** with `boltz` or `chai-lab`.
4. **Rank** with ipSAE / pLDDT / iPTM filters described in each skill.

## Repo layout

```
.
├── .claude-plugin/
│   ├── plugin.json          # plugin manifest
│   └── marketplace.json     # marketplace entry
├── skills/
│   ├── boltz/
│   ├── boltzgen/
│   ├── chai-lab/
│   ├── disco/
│   ├── foundry/
│   └── genie3/
└── README.md
```

## Contributing

To add a new skill: create `skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`) and any supporting `references/` and `examples/`. Open a PR.

## License

Each skill's content tracks the upstream tool's license (noted in its frontmatter). The skill packaging in this repo is MIT.
