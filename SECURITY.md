# Security Policy

Only the latest released version on PyPI is considered supported for security fixes.
Older versions may receive fixes but no guarantees are made.

## Scope

Security issues include, but are not limited to:
- Incorrect or unsafe device auto-detection
- Interaction with unintended serial devices
- Privilege escalation or unsafe root usage patterns
- Unsafe command execution or argument handling
- Packaging or distribution compromise
- Malicious or unsafe default configuration
- udev rule guidance that could expose devices broadly
- Supply-chain risks affecting released artifacts

Functional bugs (e.g. LED patterns not working) are **not** security issues.


## Out of Scope

The following are not considered security vulnerabilities:
- Vendor firmware behavior
- Physical hardware modifications
- Misuse of the tool outside documented parameters
- Cosmetic or performance issues


## Reporting a Vulnerability

Please **do not disclose security vulnerabilities publicly first**.

Instead report privately:
- Open a GitHub security advisory (preferred), or
- Email: fsncps at eml dot cc

Include:
- A clear description of the issue
- Steps to reproduce
- Impact assessment if known

If you disclose a security exploit to the public before reporting it, you potentially propagate weaponized code.


## Disclosure Policy

After receiving a report:
1. Maintainer will acknowledge within a reasonable timeframe.
2. Issue will be investigated and severity assessed.
3. A fix will be developed and released, followed by public disclosure.
4. Reporter will be credited unless anonymity requested.

There is no formal SLA.


## Security Model

This tool:
- Interacts with hardware via serial interfaces
- May be executed with elevated privileges
- Assumes a trusted local system environment
- Does not attempt to sandbox or restrict device access

Users are responsible for:
- Ensuring correct device selection
- Applying appropriate udev permissions
- Avoiding execution on untrusted systems

This project is not intended for hostile multi-tenant environments.


## Supply Chain Integrity

Official releases are distributed via:
- PyPI
- GitHub Releases

Only these chennels are recommended for installation. No cryptographic signing policy is currently enforced.



