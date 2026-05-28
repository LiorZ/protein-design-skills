# SDK — Biohub Platform (formerly Forge) clients

`esm.sdk` is the cloud API surface. Endpoint: **`https://biohub.ai`**
(formerly `https://forge.evolutionaryscale.ai` — many class names still say
"Forge", they mean the same service).

Auth: an API token from
[https://biohub.ai/developer-console/api-keys](https://biohub.ai/developer-console/api-keys).
By convention, export it as `ESM_API_KEY` — the SDK will read it
automatically if you don't pass `token=...` explicitly.

```bash
export ESM_API_KEY=biohub-...
```

## Factory functions

```python
from esm.sdk import client, esmc_client, esmfold2_client, batch_executor

esm3   = client(model="esm3-sm-open-v1", token=os.environ["ESM_API_KEY"])
esmc   = esmc_client(model="esmc-600m-2024-12", token=os.environ["ESM_API_KEY"])
folder = esmfold2_client(model="esmfold2-fast-2026-05", token=os.environ["ESM_API_KEY"])
```

All three accept the same kwargs:

| Kwarg | Type | Default | Meaning |
|-------|------|---------|---------|
| `model` | `str` | one per factory | Model id. Must start with `"esm3"`/`"esmc"`/`"esmfold2"` for the matching factory; otherwise `ValueError`. |
| `url` | `str` | `"https://biohub.ai"` | Override for staging / on-prem. |
| `token` | `str` | `os.environ.get("ESM_API_KEY", "")` | API token. |
| `request_timeout` | `float \| None` | `None` (wait indefinitely) | Per-request timeout, seconds. |

The factories instantiate the right concrete client class:

| Factory | Returns |
|---------|---------|
| `client(...)` | `ESM3ForgeInferenceClient` |
| `esmc_client(...)` | `ESMCForgeInferenceClient` |
| `esmfold2_client(...)` | `SequenceStructureForgeInferenceClient` |

All three implement the relevant abstract base classes
(`ESM3InferenceClient`, `ESMCInferenceClient`, …), which means **the same
high-level code (`encode` / `decode` / `logits` / `generate`) works
locally and on the platform**. Pick the right client, the rest is
identical.

## `SequenceStructureForgeInferenceClient` — folding + inverse folding

Used for both ESMFold (legacy) and ESMFold2 (`esmfold2_client(...)`).
Top-level verbs:

| Method | Purpose | Input | Output |
|--------|---------|-------|--------|
| `fold(sequence, ...)` | Fold a *single chain* (legacy ESMFold) | `str` | `ESMProtein` |
| `fold_all_atom(spi, config=FoldingConfig(...))` | ESMFold2 multi-entity fold | `StructurePredictionInput` | `MolecularComplexResult` |
| `inverse_fold(coordinates, config=InverseFoldingConfig(...))` | Sequence from a backbone | `(L, 37, 3)` tensor | `ESMProtein` |
| `async_*` versions | Same, awaitable | — | — |

```python
from esm.sdk.api import FoldingConfig, InverseFoldingConfig
from esm.utils.structure.input_builder import ProteinInput, StructurePredictionInput

# Legacy single-chain ESMFold
folded = folder.fold("MKTLLILAVL...", potential_sequence_of_concern=False)
folded.to_pdb("folded.pdb")

# ESMFold2 multi-entity
spi = StructurePredictionInput(sequences=[ProteinInput(id="A", sequence="MKTLL...")])
result = folder.fold_all_atom(spi, config=FoldingConfig(num_loops=3, num_sampling_steps=32))
open("pred.cif","w").write(result.complex.to_mmcif())

# Inverse fold
invf = folder.inverse_fold(coords, config=InverseFoldingConfig(temperature=0.1))
print(invf.sequence)
```

`FoldingConfig`:

```python
@define
class FoldingConfig:
    include_distogram: bool = False
    include_pae: bool = False
    include_pair_chains_iptm: bool = False
    num_sampling_steps: int = 100
    num_loops: int = 10
    include_embeddings: bool = False
```

`InverseFoldingConfig`:

```python
@define
class InverseFoldingConfig:
    invalid_ids: Sequence[int] = []
    temperature: float = 0.1
```

## `ESM3ForgeInferenceClient`

Implements the full `ESM3InferenceClient` interface:

| Method | Purpose |
|--------|---------|
| `encode(protein: ESMProtein) -> ESMProteinTensor` | Tokenize, run structure encoder if `coordinates` present |
| `decode(tensor: ESMProteinTensor) -> ESMProtein` | Detokenize, run structure decoder for coords |
| `generate(input, config: GenerationConfig)` | Iterative-sampling generation (encode → sample → decode) |
| `batch_generate(inputs, configs)` | Same, parallelized server-side |
| `forward_and_sample(tensor, SamplingConfig(...))` | One model forward + sample |
| `logits(tensor, LogitsConfig(...))` | One forward pass, return logits / hiddens / embeddings |

All have `async_*` siblings.

`generate` is the easiest path — pass an `ESMProtein` with the track you
want filled in left to `None`, ESM3 fills it in iteratively.

## `ESMCForgeInferenceClient`

A subset of the ESM3 interface — `encode` / `decode` / `logits`
(`generate` is not meaningful for an encoder-only model). The big extra is
`SAEConfig` support inside `LogitsConfig` (see `references/sae.md`).

## `batch_executor` — parallel HTTP requests

```python
with batch_executor(max_attempts=10, show_progress=True) as ex:
    results = ex.execute_batch(
        user_func=fn,           # callable taking (client=..., **kwargs)
        client=esmc,            # passed to every call
        sequence=["A","B","C"], # list arg → fanned out per call
        # any other args are broadcast as-is
    )
```

`execute_batch` interprets **list-valued kwargs** as the axis to fan over.
The callable receives **scalar** values for those args per call. Returns a
list aligned with the longest list-valued kwarg.

Failures: each result is either the function's return value or an
`Exception` (or `ESMProteinError`). The executor does its own retries with
exponential backoff up to `max_attempts`.

A common pattern:

```python
def _embed(client, sequence):
    pt = client.encode(ESMProtein(sequence=sequence))
    return client.logits(pt, LogitsConfig(return_mean_embedding=True))

with batch_executor() as ex:
    out = ex.execute_batch(_embed, client=esmc, sequence=many_seqs)

emb = torch.stack([o.mean_embedding[0] for o in out])  # (N, d)
```

## Error handling

The SDK's responses **never raise on per-call failures** — they return an
`ESMProteinError`:

```python
@define
class ESMProteinError(Exception, ProteinType):
    error_code: int        # HTTP-like: 404 NotFound, 500 InternalError, ...
    error_msg: str
```

(It also inherits from `Exception`, so `raise` and `isinstance` both
work.)

Always type-check:

```python
out = esmc.encode(ESMProtein(sequence=s))
if isinstance(out, ESMProteinError):
    print(f"failed: {out.error_code} {out.error_msg}")
else:
    use(out)
```

For `batch_generate` specifically, expect a mix of `ESMProtein` and
`ESMProteinError` — see `references/esm3.md`.

## Retries / timeouts

- `request_timeout=None` means wait forever (the default). For batch jobs
  set a finite value, e.g. `request_timeout=600`, so a stuck request
  doesn't hang the whole batch.
- `batch_executor(max_attempts=10)` retries with exponential backoff. The
  retry logic is in `esm.sdk.retry`.
- HTTP-level timeouts use `httpx` under the hood (transitive dep).

## `SamplingConfig` — for `forward_and_sample`

```python
@define
class SamplingTrackConfig:
    temperature: float = 1.0
    top_p: float = 1.0
    only_sample_masked_tokens: bool = True
    invalid_ids: Sequence[int] = []
    topk_logprobs: int = 0          # also return topk alternatives if > 0

@define
class SamplingConfig:
    sequence: SamplingTrackConfig | None = None
    structure: SamplingTrackConfig | None = None
    secondary_structure: SamplingTrackConfig | None = None
    sasa: SamplingTrackConfig | None = None
    function: SamplingTrackConfig | None = None
    residue_annotations: SamplingTrackConfig | None = None
```

Pass `None` for tracks you don't want sampled.

## Pseudoperplexity recipe (cookbook)

Uses `batch_executor` to mask each position in parallel and sum log-probs.
See `references/esmc.md::Recipe — pseudo-perplexity`. The same recipe
works locally by swapping the client for an `ESMC` model and the executor
for a plain loop.

## Forge vs Biohub naming

The API URL was renamed from `forge.evolutionaryscale.ai` to `biohub.ai`,
but the class names still mention "Forge":

- `ESM3ForgeInferenceClient`
- `ESMCForgeInferenceClient`
- `SequenceStructureForgeInferenceClient` (covers ESMFold2)
- `ForgeBatchExecutor` (alias under `batch_executor`)
- `forge_context_manager` (the retry/timeout module)

That's intentional / historical — the canonical URL is `https://biohub.ai`
and the default `url=` in every factory points there.

## SageMaker / AWS

`esm.sdk.sagemaker.ESM3SageMakerClient` provides the same surface against
an AWS-hosted endpoint. **Not imported by default** — depends on `boto3`
and an AWS account. Don't import from `esm.sdk.__init__` (the file says
`# Note: please do not import ESM3SageMakerClient here since that requires
AWS SDK.`); import explicitly:

```python
from esm.sdk.sagemaker import ESM3SageMakerClient
```

The Biohub Platform path is what 99% of users want — this is here for
enterprise deployments.
