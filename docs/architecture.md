# Architecture

## Purpose

`acemagic-ledctl` is a local Linux utility that sends serial byte sequences to an LED controller found in some ACEMAGIC mini PCs.

The project has three main layers:

1. device selection
2. command/frame generation
3. CLI and pattern orchestration

## Operating model

The host system talks to the LED microcontroller through a USB-to-UART bridge, usually CH340/CH341.

The tool does not control LEDs through a documented vendor API. It emits serial sequences derived from observed protocol behavior.

## Main components

### CLI layer

Commands exposed to the user include:

- `ledctl off`
- `ledctl setmode ...`
- `ledctl pattern ...`
- `ledctl wiz`

Responsibilities:

- parse user arguments
- resolve mode/pattern names
- pass serial options through cleanly
- keep hardware interaction visible rather than implicit

### Core protocol/frame layer

Responsibilities:

- map brightness/speed abstractions to wire values
- build frames and checksums
- enforce input validation before bytes are written
- keep protocol-specific logic centralized

This is the best place for pure unit tests.

### Serial transport layer

Responsibilities:

- open the selected serial device
- set baud and line state options
- write bytes with optional inter-byte delay
- fail clearly when the device is unavailable or misconfigured

### Pattern layer

Responsibilities:

- implement synthetic modes not offered by the vendor utility
- repeatedly send mode sequences to create apparent fixed-color or alert behavior
- manage background execution carefully

## Device selection strategy

Current strategy is heuristic:

1. `/dev/serial/by-path/*-if00-port0`
2. first `/dev/ttyUSB*`
3. first `/dev/ttyACM*`

This is convenient but not authoritative. On systems with multiple serial adapters, explicit `--port` is safer.

## Trust boundaries

The tool crosses these boundaries:

- user input -> CLI parsing
- CLI -> serial-device selection
- process -> local device node
- bytes -> external microcontroller behavior

Important implication: wrong-device writes are a more realistic risk than classic remote exploitation.

## Failure modes

Most important failure classes:

- wrong serial device selected
- unsupported UART bridge or LED firmware
- timing too fast or too slow for stable effect
- insufficient device permissions
- release/build metadata mismatch causing packaging confusion

## Safety posture

The design should prefer:

- explicit port selection over guesswork
- transparent serial settings over hidden defaults where failure matters
- clear error messages over silent fallback
- small, testable protocol helpers over large stateful control code

## Packaging architecture

Release artifacts are built from `pyproject.toml` metadata.

Current versioning model is static:

- the version used in the built package is the version declared in `pyproject.toml`
- Git tag and GitHub release names do not override that automatically

That is operationally important enough to be treated as architecture, not just release mechanics.

## Out of scope

This project is not trying to be:

- a general LED abstraction layer
- a vendor-neutral serial lighting framework
- a remote management service
- a background system daemon
