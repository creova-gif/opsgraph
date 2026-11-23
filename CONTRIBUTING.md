# Contributing to OpsGraph

Thanks for your interest in improving OpsGraph.

## Development setup

```bash
git clone https://github.com/creova-gif/opsgraph.git
cd opsgraph
python -m venv .venv && source .venv/bin/activate
pip install -e ".[drive]"
```

## Before opening a pull request

1. Branch from `main` and keep each pull request focused on one change.
2. Run the test suite and the offline smoke test:
   ```bash
   python -m unittest discover -s . -p 'test_*.py'
   python opsgraph_cli.py gap examples/seed-b2b-saas.json examples/sample-drive-inventory.json
   ```
3. Read [DESIGN.md](DESIGN.md) before changing the dashboard, certificate or any other visual output.
4. Keep to the project principles in the README: evidence before assertion, propose before destructive
   action, and never claim compliance. Delete operations are not allowed in v1.

## Reporting issues

Open a GitHub issue with steps to reproduce, the command you ran, and the output you expected.
Please do not include real company data or Google credentials in issues or fixtures.
