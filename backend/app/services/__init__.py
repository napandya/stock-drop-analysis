"""Service layer — orchestration between the API and the models.

Kept deliberately thin so the route handlers stay trivial and there is exactly
one place that assembles a full response (dataset summary + sections +
explanations). It also owns the cross-cutting policies that don't belong in any
single model: building a per-request ``Settings`` for a user ticker selection,
and degrading gracefully when one section can't run on a small selection (e.g.
clustering with too few drops becomes a warning rather than a failed request).
"""
