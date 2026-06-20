"""Stock Drop-Driver Analysis — application package.

This backend identifies and *attributes* significant single-day stock drops:
not just "the market fell and volume spiked" (a restatement of the drop), but
*why* it fell — market/sector beta vs. a company-specific shock, the global
event that prevailed, and the catalyst (earnings, rates).

Why it is layered the way it is
-------------------------------
The package is split so each concern can be tested and reasoned about in
isolation, and so the network is quarantined behind one boundary:

* ``config``            — typed, env-overridable settings (one source of truth).
* ``exceptions``        — a small domain error hierarchy the API maps to HTTP codes.
* ``logging_config``    — structured logging instead of ``print``.
* ``core``              — the data/feature/attribution layer (the only place that
                          touches the network), all reducible to pure functions
                          over DataFrames so it is unit-testable offline.
* ``models``            — the four analysis sections plus per-company explanations.
* ``services``          — thin orchestration between the API and the models.
* ``main``              — the FastAPI app and the exception→HTTP mapping.

A recurring rule across the code: same-day, outcome-derived quantities (the
return decomposition, macro/earnings/event context) are **attribution only** and
never enter the model feature set, because using them to *predict* the drop would
be leakage.
"""
