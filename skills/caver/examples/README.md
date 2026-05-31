# caver examples

| File | What it does | How to use |
|------|--------------|-----------|
| `CAVER.def` | The Apptainer/Singularity definition file. Build with `apptainer build --fakeroot CAVER.sif CAVER.def` from `~/Repos/CAVER`. | `cd ~/Repos/CAVER && apptainer build --fakeroot "$SINGULARITY_HOME"/CAVER.sif CAVER.def` |
| `commandline_examples.sh` | Every common invocation: build, quickstart, static structure, MD ensemble, re-cluster, custom atom radii, PyMOL/VMD post-processing. | Skim and copy-paste — it has the build commented; pick the lines you need. |
| `config_static.txt` | Minimal config for a single static PDB. | Save as `./config.txt` next to your input PDB, edit `starting_point_*`. |
| `config_md.txt` | Full config for an MD ensemble with histograms + heat maps + VMD movies. | Save as `./config.txt`, edit `starting_point_*` and frame slicing. |
| `run_caver.sh` | Wrapper that resolves `$SINGULARITY_HOME` and forwards args + `JAVA_OPTS`. | `./run_caver.sh ./md_snapshots ./config.txt ./out -Xmx16g` |

Prerequisites:

```bash
export SINGULARITY_HOME=/path/to/dir/with/CAVER.sif
```

Quick test against the bundled examples (no project files needed):

```bash
mkdir -p /tmp/caver_test && cd /tmp/caver_test
apptainer exec "$SINGULARITY_HOME"/CAVER.sif \
    cp -r /opt/caver/examples/QUICK_START .
apptainer run "$SINGULARITY_HOME"/CAVER.sif \
    -home /opt/caver \
    -pdb  /tmp/caver_test/QUICK_START/md_snapshots \
    -conf /tmp/caver_test/QUICK_START/inputs/config.txt \
    -out  /tmp/caver_test/QUICK_START/out

cat /tmp/caver_test/QUICK_START/out/summary.txt
```

The container ships with the upstream `QUICK_START`,
`static_structures/{1AKD,1BL8,1MXT,2ACE,2BG9,2OAR}`, and `guided_example`
sets at `/opt/caver/examples/`. Reference results live alongside each.
