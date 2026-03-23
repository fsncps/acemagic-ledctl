# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
