"""Importing this package registers all adapters. Add new adapters to the import list."""

from ingestion.sources import (  # noqa: F401
    brightsky,
    chips,
    eeg,
    energycharts,
    entsoe,
    gee,
    mastr,
    osm,
    smard,
    turbines,
)
