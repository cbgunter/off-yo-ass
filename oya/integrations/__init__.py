"""Thin clients for external data sources: garmin, google, concept2, peloton,
usda, openfoodfacts, nws, webpush. Each source's failure is isolated here and
must never break a sync run for the others. Built out starting phase 1."""
