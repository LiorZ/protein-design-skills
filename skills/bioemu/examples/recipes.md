# BioEmu recipes

Copy-paste snippets for common ensemble-sampling patterns. All
examples assume `pip install 'bioemu[cuda]'` and a GPU.

## Smallest possible run (chignolin sanity check)

```bash
python -m bioemu.sample \
    --sequence GYDPETGTWG --num_samples 10 \
    --output_dir ~/chignolin-test
```

~30 s on A100. Produces `samples.xtc` with up to 10 backbone frames.

## Large ensemble for free-energy / stability work

```bash
python -m bioemu.sample \
    --sequence "$(awk 'NR>1' my_protein.fasta | tr -d '\n')" \
    --num_samples 1000 \
    --output_dir ~/my_protein \
    --base_seed 42 \
    --batch_size_100 5
```

Reproducible (`base_seed` pinned), resumable (same `output_dir`),
batch sized down for safety on a non-A100 GPU.

## Long / disordered sequence — turn on physical steering

```bash
python -m bioemu.sample \
    --sequence "$(awk 'NR>1' long_protein.fasta | tr -d '\n')" \
    --num_samples 500 \
    --output_dir ~/long_protein-steered \
    --batch_size_100 3 \
    --denoiser_config src/bioemu/config/steering/physical_steering.yaml
```

The `physical_steering.yaml` uses SMC with 5 particles and the
`CaCaDistance` + `PairwiseClash` umbrella potentials — fewer samples
get filtered out for clashes / chain breaks.

## Target a specific conformation (FKC RMSD steering)

```bash
python -m bioemu.sample \
    --sequence GYDPETGTWG --num_samples 100 \
    --output_dir ~/chignolin-folded \
    --denoiser_config src/bioemu/config/steering/cv_steer.yaml \
    +denoiser_config.fk_potentials.0.cv.reference_pdb=/abs/path/folded.pdb
```

Biases the ensemble toward RMSD ≈ 0.5 nm to the reference. Result is
**not** Boltzmann-distributed — use this when you want the ensemble
*in* a basin, not the ratio *between* basins.

## Bring your own MSA

If you have a good MSA already (e.g. from `colabfold_search` or a
custom DB), skip the public ColabFold server:

```bash
# my_alignment.a3m's first row is the query sequence
python -m bioemu.sample \
    --sequence ~/my_alignment.a3m \
    --num_samples 100 \
    --output_dir ~/my_protein-byomsa
```

`msa_host_url` is ignored when an `.a3m` is passed.

## Custom MMseqs2 server

```bash
python -m bioemu.sample \
    --sequence GYDPETGTWG --num_samples 100 \
    --output_dir ~/chignolin-custom-msa \
    --msa_host_url https://my-mmseqs2-server.example.com/api
```

## Reconstruct side chains, then short MD relax

```bash
# After bioemu.sample finishes:
python -m bioemu.sidechain_relax \
    --pdb-path ~/my_protein/topology.pdb \
    --xtc-path ~/my_protein/samples.xtc \
    --outpath  ~/my_protein/relaxed \
    --md-protocol local_minimization
```

Outputs `samples_sidechain_rec.{pdb,xtc}` and
`samples_md_equil.{pdb,xtc}` under `--outpath`.

## Sub-sample first, then relax (fast)

Side-chain reconstruction is the slow step. For a 1000-frame ensemble,
relax every 10th frame:

```bash
python - <<'PY'
import mdtraj
t = mdtraj.load_xtc("~/my_protein/samples.xtc",
                    top="~/my_protein/topology.pdb")
sub = t[::10]
sub.save_xtc("~/my_protein/samples_sub.xtc")
sub[0].save_pdb("~/my_protein/topology_sub.pdb")
PY

python -m bioemu.sidechain_relax \
    --pdb-path ~/my_protein/topology_sub.pdb \
    --xtc-path ~/my_protein/samples_sub.xtc \
    --outpath  ~/my_protein/relaxed_sub
```

## Estimate folded fraction + ΔG_fold

```python
import mdtraj, numpy as np
t = mdtraj.load_xtc("samples.xtc", top="topology.pdb")
ref = mdtraj.load_pdb("reference_folded.pdb")
rmsd_to_ref = mdtraj.rmsd(t, ref)

folded_frac = (rmsd_to_ref < 0.3).mean()         # < 3 Å = folded
unfolded_frac = 1 - folded_frac

kT_kcal = 0.593                                   # at 298 K
dG_fold = -kT_kcal * np.log(folded_frac / unfolded_frac)

print(f"folded:  {folded_frac:.2%}")
print(f"ΔG_fold: {dG_fold:+.2f} kcal/mol")
```

For rigorous benchmark protocol, see
[bioemu-benchmarks/BIOEMU_RESULTS.md](https://github.com/microsoft/bioemu-benchmarks/blob/main/bioemu_benchmarks/BIOEMU_RESULTS.md).

## Cryptic-pocket discovery — load + cluster ensemble

```python
import mdtraj, numpy as np
from sklearn.cluster import KMeans

t = mdtraj.load_xtc("samples.xtc", top="topology.pdb")
t.superpose(t, frame=0)

# Per-frame pocket volume / SASA / dihedral signature → cluster
# (For pocket-detection-specific tools see fpocket / FTMap / GHECOM.)
ca = t.top.select("name CA")
xyz = t.xyz[:, ca].reshape(t.n_frames, -1)
clusters = KMeans(n_clusters=5, n_init=10).fit_predict(xyz)
for c in range(5):
    members = np.where(clusters == c)[0]
    t[members].save_xtc(f"cluster_{c}.xtc")
    t[members[0]].save_pdb(f"cluster_{c}_rep.pdb")
print("Inspect each cluster_<i>_rep.pdb for distinct pocket conformations.")
```

## Resume a partial run

If your job got killed at, say, 600 / 1000 samples:

```bash
# Same command. BioEmu detects the existing batch_*.npz files
# and only generates the remaining ~400 samples.
python -m bioemu.sample \
    --sequence "$(awk 'NR>1' my_protein.fasta | tr -d '\n')" \
    --num_samples 1000 \
    --output_dir ~/my_protein \
    --base_seed 42 \
    --batch_size_100 5
```

To **forget** and start from scratch with the same output dir:

```bash
rm ~/my_protein/batch_*.npz ~/my_protein/samples.xtc ~/my_protein/topology.pdb
# (keep sequence.fasta unless changing sequence)
```

## Compare bioemu-v1.1 vs v1.2

```bash
for v in bioemu-v1.1 bioemu-v1.2; do
    python -m bioemu.sample \
        --sequence "$SEQ" --num_samples 200 \
        --output_dir ~/compare/$v \
        --model_name $v \
        --base_seed 42
done
```

v1.2 should differ most on stability-sensitive proteins.

## Inline-dict denoiser config (no YAML file)

```python
from bioemu.sample import main as sample

denoiser = {
    "_target_": "bioemu.steering.dpm_smc.dpm_solver_smc",
    "_partial_": True,
    "eps_t": 0.001, "max_t": 0.99, "N": 100, "noise": 0.5,
    "fk_potentials": [
        {"_target_": "bioemu.steering.UmbrellaPotential",
         "cv": {"_target_": "bioemu.steering.CaCaDistance"},
         "target": 0.38, "flatbottom": 0.1, "slope": 10.0,
         "order": 1, "linear_from": 0.1, "weight": 1.0},
        {"_target_": "bioemu.steering.UmbrellaPotential",
         "cv": {"_target_": "bioemu.steering.PairwiseClash",
                "min_dist": 0.41, "offset": 3},
         "target": 0.0, "flatbottom": 0.0, "slope": 30.0, "weight": 1.0},
    ],
    "steering_config": {
        "num_particles": 5, "ess_threshold": 0.5,
        "start": 0.1, "end": 0.0,
    },
}

sample(sequence='GYDPETGTWG', num_samples=100,
       output_dir='~/inline-steered', denoiser_config=denoiser)
```

## Design-then-validate pattern (cross-skill)

```bash
# 1. Design with BindCraft / BoltzGen / etc.  (see those skills)
# 2. Pick top accepted designs.
# 3. For each design, sample the equilibrium ensemble:
for pdb in accepted/*.pdb; do
    seq=$(python -c "import biotite.structure.io.pdb as pdb; \
        s = pdb.PDBFile.read('$pdb').get_structure(model=1); \
        ca = s[s.atom_name == 'CA']; \
        import biotite.structure.info as info; \
        print(''.join(info.one_letter_code(r) for r in ca.res_name))")
    python -m bioemu.sample \
        --sequence "$seq" --num_samples 200 \
        --output_dir ~/design-ensembles/$(basename $pdb .pdb) \
        --denoiser_config src/bioemu/config/steering/physical_steering.yaml
done
# 4. For each ensemble, check the folded fraction vs the designed PDB:
#    designs that are mostly unfolded at equilibrium probably won't work in vitro.
```
