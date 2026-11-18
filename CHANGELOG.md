# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] - 2026-11-18

### Added
- The summary line now says roughly how long after the start the pause comes (for example
  "about 6h 40m into the print"), using OrcaSlicer's `M73` time estimate.

## [0.2.0] - 2026-11-18

### Added
- The plugin now always writes a summary comment as the second line of the G-code, even
  when no pause is needed, so you can see it ran.
- ruff lint and format checks, and a CI workflow running them plus the tests on Linux and
  Windows (Python 3.12 and 3.13).

### Changed
- Shorter plugin description; code reformatted with ruff (no behavior change).

## [0.1.0] - 2026-11-18

### Added
- OrcaSlicer 2.5+ slicing-pipeline plugin that inserts a pause before the spool runs out.
- Command-line mode for use as a classic post-processing script.
- Settings: `remaining_g` (default 1000), `reserve_g` (default 20), `pause_command`
  (default `M600`), `density_g_cm3`, `diameter_mm`.
