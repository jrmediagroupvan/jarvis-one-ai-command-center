# Contributing

Thanks for helping improve JARVIS ONE. Open an issue describing the bug or proposed feature before substantial changes. Send focused pull requests with clear tests and documentation.

## Local checks

```bash
python3 -m compileall -q app setup.py apply_update.py update_worker.py
python3 -m pip install -r requirements.txt pytest
python3 -m pytest -q
```

Never commit real `.env`, `data/`, `config/printers.json`, API keys, passwords, screenshots of private camera feeds or other personal data. Review the [security notes](SECURITY.md) before making changes to auth, browser or update handlers.
