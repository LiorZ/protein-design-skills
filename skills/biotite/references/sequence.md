# `biotite.sequence` — sequences, alignment, search

`import biotite.sequence as seq` and
`import biotite.sequence.align as align`. Like structures, sequences are
NumPy-backed: a `Sequence` stores an integer **code** array over an `Alphabet`;
`.symbols` decodes it back to letters.

## 1. Sequence types

```python
dna  = seq.NucleotideSequence("ATGGCCATTGTA")
prot = seq.ProteinSequence("MAIV")                 # accepts 1- or 3-letter input
gen  = seq.GeneralSequence(my_alphabet, "....")    # any custom alphabet
```

`NucleotideSequence`:
- `.complement()`, `.reverse()` (→ `.reverse_complement()` = `reverse().complement()`).
- `.translate(complete=True)` → `ProteinSequence`; `complete=False` →
  `(list_of_proteins, positions)` for all ORFs between start/stop codons.
- `is_valid()`, static `unambiguous_alphabet()` / `ambiguous_alphabet()`
  (the ambiguous one adds `R Y W S M K H B V D N`).

`ProteinSequence`:
- static `convert_letter_3to1("ALA") -> "A"`, `convert_letter_1to3("A") -> "ALA"`.
- `.remove_stops()`, `.get_molecular_weight()`.
- alphabet has 20 + `B Z X *` (ambiguous + stop).

```python
seq.CodonTable.default_table()                 # NCBI standard genetic code
seq.CodonTable.load_table("Vertebrate Mitochondrial")
```

Sequences support `len()`, indexing/slicing (returns symbols/subsequences),
`+` concatenation, boolean-mask indexing, `.copy()`, `.reverse()`.

## 2. Pairwise alignment

```python
matrix = align.SubstitutionMatrix.std_protein_matrix()      # BLOSUM62
# matrix = align.SubstitutionMatrix.std_nucleotide_matrix()
# matrix = align.SubstitutionMatrix(alph, alph, "PAM250")   # by name; list_db() to enumerate

alns = align.align_optimal(
    seq1, seq2, matrix,
    gap_penalty=(-10, -1),     # (open, extend); a single int = linear
    terminal_penalty=True,
    local=False,               # False = Needleman-Wunsch (global); True = Smith-Waterman (local)
)
aln = alns[0]
print(aln)                                       # pretty gapped view
print("identity:", align.get_sequence_identity(aln))
print("score:", aln.score)
gapped = aln.get_gapped_sequences()              # ['MA-IV', 'MALIV']
```

Other aligners: `align_ungapped` (equal length, no gaps), `align_banded` (long
similar sequences, banded DP), `align_local_gapped` / `align_local_ungapped`
(seed extension with X-drop). Stats helpers: `get_codes`, `get_symbols`,
`get_pairwise_sequence_identity`, `score`, `remove_terminal_gaps`.

## 3. Multiple sequence alignment

Two routes — Biotite's own progressive aligner, or an external tool wrapper.

```python
# (a) built-in progressive MSA (no external binary):
aln, order, guide_tree, dist = align.align_multiple(
    [s1, s2, s3, s4], matrix, gap_penalty=-10
)

# (b) external tools (need the binary — see applications.md):
from biotite.application.muscle import Muscle5App
from biotite.application.mafft  import MafftApp
from biotite.application.clustalo import ClustalOmegaApp
aln = MafftApp.align([s1, s2, s3], matrix=matrix)        # classmethod -> Alignment
```

For real datasets prefer MAFFT/MUSCLE5; `align_multiple` is convenient for a few
short sequences and has no dependency.

## 4. Fast homology search — k-mer tables

For "find where this query matches in a big reference set" without an O(n·m)
alignment, use a `KmerTable` (the engine behind seed-and-extend search):

```python
table = align.KmerTable.from_sequences(k=5, sequences=[ref1, ref2, ...], ref_ids=[0, 1, ...])
matches = table.match(query)            # (n_matches, 3): query_pos, ref_id, ref_pos
# then extend seeds with align_local_ungapped / align_local_gapped
```

Reduce the seed set on large genomes with selectors:
`MinimizerSelector(kmer_alphabet, window)`, `SyncmerSelector`, `MincodeSelector`.
`KmerAlphabet(base_alphabet, k, spacing=...)` supports spaced k-mers.

## 5. Profiles & consensus

```python
prof = align.SequenceProfile.from_alignment(aln)
consensus = prof.to_consensus()                  # Sequence
pwm = prof.log_odds_matrix()                     # position weight matrix
ppm = prof.probability_matrix(pseudocount=1.0)
```

## 6. Annotations (features)

`Feature`, `Location` (with `Strand` FORWARD/REVERSE and `Defect` flags),
`Annotation`, and `AnnotatedSequence` model GenBank-style feature tables. Parse
them from GenBank with `genbank.get_annotation` (see `file-io.md`), then slice
an `AnnotatedSequence` by feature.

## 7. Phylogenetics (`biotite.sequence.phylo`)

```python
from biotite.sequence.phylo import upgma, neighbor_joining, Tree
tree = upgma(distance_matrix)              # ndarray (n,n) symmetric; or neighbor_joining (n>=4)
newick = tree.to_newick(labels=names)
tree2 = Tree.from_newick(newick)
d = tree.get_distance(i, j)                # leaf-to-leaf distance
```

Build the distance matrix from pairwise identities (e.g.
`1 - get_pairwise_sequence_identity(msa)`), then cluster.

## Common recipes

- **% identity between two designs/predictions:**
  `align.get_sequence_identity(align.align_optimal(a, b, matrix)[0])`.
- **Translate a CDS:** `NucleotideSequence(cds).translate(complete=True)`.
- **Cluster a set of hits:** k-mer/identity distance → `neighbor_joining` →
  Newick → inspect.
- **Score a sequence against a motif:** `SequenceProfile` →
  `log_odds_matrix()` → score windows.

## See also

- Reading FASTA/FASTQ/GenBank/A3M → `file-io.md`
- External aligners + BLAST → `applications.md`
- Fetching sequences from UniProt/Entrez → `database.md`
