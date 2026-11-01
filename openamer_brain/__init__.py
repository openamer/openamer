"""OpenAmer CPU brain — a small, local, CPU-only language model.

Modules:
    openamer_prototype  the network (SpectralMix + ConceptBottleneck)
    openamer_train      training loop over the collected brain corpus
    brain_scan          evaluation / latency scan
    openamer_unified    in-process service used by `openamer brain say`

torch is the only non-stdlib dependency and is imported lazily; importing
this package itself costs nothing.
"""

__all__ = ["openamer_prototype", "openamer_train", "brain_scan", "openamer_unified"]
