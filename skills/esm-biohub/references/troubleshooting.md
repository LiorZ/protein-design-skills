# Troubleshooting

Roughly in the order people hit them. Build errors first, then runtime.

## Build (apptainer build esm.sif esm.def)

### "Permission denied" / "could not switch to user namespace"

You don't have fakeroot set up. Either:

```bash
sudo apt-get install -y apptainer-suid             # provides setuid path
sudo apptainer build esm.sif esm.def               # …or build as root
```

Or configure fakeroot once: `sudo apptainer config fakeroot --add $USER`.

### "No space left on device" during the pip layer

The apptainer build cache (`~/.apptainer/cache` by default) holds the
intermediate OCI blobs and is enormous. Free it:

```bash
df -h .                                            # check what filled up
apptainer cache list                               # show OCI + net caches
apptainer cache clean -f                           # wipe all of it
```

If `/` itself is at 100 %, also check `~/.singularity/cache` (legacy
singularity uses a different path). Move the cache to a bigger disk:

```bash
export APPTAINER_CACHEDIR=/big/disk/apptainer-cache
```

### "ERROR: Could not find a version that satisfies the requirement torch"

The base image's pinned PyTorch URL went stale. The def file uses
`https://download.pytorch.org/whl/cu126` — if your local CUDA differs,
update `From: nvidia/cuda:12.6…` and the pip `--index-url` together to a
matching pair (e.g. both `cu121`). They must match.

### "pip ERROR: externally-managed-environment" (PEP 668)

Ubuntu 24.04 forbids system-pip installs. The def file creates a venv at
`/opt/venv` to side-step this — if you got this error, you edited the def
file and removed the venv setup. Put it back.

### "fatal: unable to access 'https://github.com/Biohub/transformers.git/'"

The Biohub `transformers` fork is a private(ish) repo. The pinned commit
hash in `pyproject.toml` (`@3a8956fb…`) must resolve. If it doesn't:

- Check the repo is still reachable (the `Biohub` org may have rotated).
- Pin to a different commit by editing `pyproject.toml` and rebuilding.

### `huggingface_hub` import errors at install time

Usually means a transitive dependency is incompatible with Python 3.12.
Check `pixi.lock` for the working version set; if you're not using pixi,
the `pyproject.toml` is enough to recover a clean env.

## Run (apptainer exec --nv esm.sif …)

### `ModuleNotFoundError: No module named 'esm'`

You ran `python` outside the container or against the host Python. The
container's venv is at `/opt/venv` and `/opt/venv/bin` is on PATH. Either
run with `apptainer exec --nv esm.sif python ...` or, if you really need
the host Python, `pip install` the repo there first.

### `RuntimeError: CUDA driver version is insufficient for CUDA runtime version`

The container ships CUDA 12.6 libs but `--nv` provides the host driver.
Run `nvidia-smi` on the host — if the driver is older than 525.x (CUDA
12.x) you need to upgrade it, or rebuild the SIF against a `cu121` /
`cu118` base.

### `--nv` was missing → CPU-only and slow

```
WARNING: Could not find CUDA
```
or just *unexpected slowness* + `torch.cuda.is_available()` → `False`
**inside the container**. Always pass `--nv`. If it's set and CUDA is
still off, the host driver is missing / broken.

### `OSError: We couldn't connect to 'https://huggingface.co'`

The container can't reach HF — common in air-gapped clusters. Either:

- Pre-download on a networked host (see `references/installation.md`
  "Pre-warming the cache"); copy the cache and use `HF_HUB_OFFLINE=1`.
- Allow egress to `huggingface.co` and `cdn-lfs.huggingface.co` from the
  cluster node.

### `403 Client Error: Forbidden for url: …Biohub/ESMC-6B/…`

ESMC-6B is **gated**. Steps:

1. Visit the model card on HF and accept the license.
2. `huggingface-cli login` on the host (writes a token).
3. Make sure `$HOME/.cache/huggingface/token` is readable inside the
   container — apptainer auto-mounts `$HOME`, so this just works as long
   as you didn't override the bind.

Alternative: `--env HF_TOKEN=hf_…` on the apptainer command.

### `PermissionError: [Errno 13] Permission denied: '/root/.cache/huggingface'`

You set `HF_HOME` to `/root/...` somewhere, or didn't unset it after a
manual install. The SIF's `%environment` defaults it to
`$HOME/.cache/huggingface`, which the container can write to via the
auto-mounted `$HOME`. Force-unset and rely on the default:

```bash
apptainer exec --nv --env HF_HOME= "$SINGULARITY_HOME"/esm.sif python ...
```

### `ImportError: cannot import name 'ESMFold2Model' from 'transformers.models.esmfold2.modeling_esmfold2'`

The container was built with stock HF transformers instead of the
**Biohub fork**. Rebuild — `pyproject.toml` pulls
`transformers @ git+https://github.com/Biohub/transformers.git@3a8956fb…`.

### `ValueError: Model esm3-medium-2024-08 not found in local model registry.`

You passed a Biohub-Platform-only model name to `ESM3.from_pretrained`.
Use the SDK client for it: `client(model="esm3-medium-2024-08",
token=os.environ["ESM_API_KEY"])`.

### `ValueError: Invalid model name: <something>` (from `client()` / `esmc_client()` / `esmfold2_client()`)

The factory checks the model name's prefix:

- `client(...)` requires names starting with `"esm3"`.
- `esmc_client(...)` requires `"esmc"`.
- `esmfold2_client(...)` requires `"esmfold2"`.

Match the prefix or use the right factory.

### `RuntimeError: CUDA out of memory`

- ESMC-6B at long sequence lengths is a 30+ GB job. Drop to ESMC-600M, or
  use `--env CUDA_VISIBLE_DEVICES=…` to pick a bigger GPU, or
  `device_map="auto"` (HF) to spill across GPUs.
- ESMFold2 with `num_loops=10, num_sampling_steps=200` on a long
  multi-chain complex is the worst case. Drop `num_loops` first, then
  `num_sampling_steps`, then fold each chain separately if needed.
- The model is in bf16 by default. fp16 is the same size; fp32 doubles
  memory.

### `AssertionError: ESMProtein must have a sequence to convert to ProteinComplex`

You're calling `.to_protein_complex()` or `.to_pdb()` on a structure-only
output. Generate the sequence track first
(`GenerationConfig(track="sequence", …)`) or set
`protein.sequence` from your input.

### `ESMProteinError` returned (not raised) from a client call

The Biohub Platform endpoint reported a per-request failure. Always
type-check after every SDK call:

```python
if isinstance(out, ESMProteinError):
    raise RuntimeError(f"{out.error_code} {out.error_msg}")
```

Common error codes:

- `404` — model name doesn't exist on the platform / your account.
- `401/403` — bad/missing API key (check `ESM_API_KEY`).
- `429` — rate-limited; let `batch_executor` retry.
- `500` — server error; retry, escalate if persistent.

### `flash_attn` not loading → ESMC silently slow

`is_flash_attn_available` evaluates to `False` if `flash_attn` isn't
installed (it's intentionally optional). No error is raised; you just lose
the speed-up. To add it to the SIF, install inside the venv:

```bash
apptainer exec --writable --fakeroot esm.sif bash -c '
  /opt/venv/bin/pip install flash-attn --no-build-isolation
'
```

Requires a `--writable` rebuild or building a sandbox first. For most
workloads dense attention is fine.

### `ESMC` loads in bf16, downstream code expects fp32

```python
m = ESMC.from_pretrained("esmc_300m")              # → cuda + bf16
out = m(inputs)
out.embeddings.dtype                                # torch.bfloat16
loss = some_fp32_layer(out.embeddings)              # mixed-dtype error
```

Either cast (`out.embeddings.float()`) or load on CPU first:

```python
m = ESMC.from_pretrained("esmc_300m", device=torch.device("cpu")).to("cuda")
```

The auto-bf16 is in the `from_pretrained` source — it only triggers when
`device.type != "cpu"`.

### `RuntimeError: ESMC SAEConfig normalize_features=True is not supported for ESMC 300M SAE models`

You passed a 300M SAE name with default normalization. Set
`normalize_features=False`:

```python
SAEConfig(models=["Biohub/ESMC-300M-sae-…"], normalize_features=False)
```

### "Covalent bonds are not supported when using chainbreaks"

You passed a `ProteinInput` with `|` / `:` chainbreaks *and* a non-empty
`covalent_bonds`. Split the chains into separate `ProteinInput`s:

```python
# instead of:
ProteinInput(id="A", sequence="AAA|BBB", ...)
# do:
ProteinInput(id="A", sequence="AAA")
ProteinInput(id="B", sequence="BBB")
```

The `clean_esmfold2_input` helper raises this `ValueError` because the
bond indices reference chain ids that wouldn't exist after splitting.

### `from_rcsb("…")` times out

The example flow `ProteinChain.from_rcsb("1utn")` hits the network. From
an air-gapped cluster, download the PDB to disk and use
`ProteinChain.from_pdb(path)` instead.

### Mixed `ESMProtein` / `ESMProteinError` in `batch_generate`

By design — one bad prompt doesn't kill the batch. Iterate and type-check:

```python
for p in client.batch_generate(prompts, configs):
    if isinstance(p, ESMProteinError):
        print("skip:", p.error_msg)
    else:
        p.to_pdb(...)
```

### Slow first call ("compiling kernels…")

If you installed flash-attn yourself it builds CUDA kernels on first use
and caches them in `$HOME/.cache/torch_extensions`. Subsequent runs hit
the cache. Make sure that path is writable and bind-mounted (same
treatment as `$HF_HOME`).

### Jupyter inside the SIF can't find a port

Bind the port the obvious way:

```bash
apptainer exec --nv "$SINGULARITY_HOME"/esm.sif \
  jupyter notebook --no-browser --ip 0.0.0.0 --port 8888 /opt/esm/cookbook
```

Apptainer shares the host network namespace, so `--ip 0.0.0.0` is
sufficient — no `--bind` needed for the port.
