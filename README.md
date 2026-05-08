# multi-agentic-bft
Multi Agentic AI BFT System based on Aegean Protocol

## Python port scope

This repository now contains a Python port of the **currently implemented**
Nexus Agents Aegean logic only:

- Core Aegean types and quorum math
- Vote/proposal helper utilities
- Protocol execution loop (leader selection, proposal, voting, quorum evaluation)
- Event emission helpers
- Unit tests and basic E2E-style consensus tests

No new behavior beyond what is currently implemented in Nexus has been added.

## Run tests

```bash
python -m pip install -e ".[dev]"
pytest
```
