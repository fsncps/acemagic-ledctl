# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.0] - 2026-04-18

### Fixed
- MODE.RAINBOW wire byte corrected from 0x05 to 0x01 (matches real hardware)
- `ledctl pattern <name>` now works — pattern registry was empty, causing ImportError
- `ledctl off` command added (was documented but missing)

### Added
- MODE.AUTO (0x05) — previously missing from core library
- `--mode auto` choice in `ledctl setmode`
- `ledctl off` subcommand and `ledctl-off` console script entry point
- `ledctl wiz` subcommand routing in `__main__.py`
- Pattern auto-discovery via `pkgutil.iter_modules()`
- Friendly error message when pattern name is unknown

### Changed
- License classifier corrected to GPL-3.0-or-later (was incorrectly MIT)
- Version synchronized between `__init__.py` and `pyproject.toml`

## [0.1.0] - 2025-03-23

### Added
- Initial release
- CLI commands: `off`, `setmode`, `setpattern`, `wiz`
- Built-in modes: rainbow, breathing, cycle, off, auto
- Custom patterns: stillred, stillblue, breathered, alarm
- CH340/CH341 auto-detection
- Serial tuning flags: port, baud, DTR, RTS, inter-byte delay
- Background pattern execution with `--background`
- Interactive curses wizard (ledctl wiz)
