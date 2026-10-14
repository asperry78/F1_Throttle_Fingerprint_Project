# F1 Throttle/Brake Fingerprint

Explore and compare Formula 1 drivers' speed, throttle, brake, RPM, and gear traces on the same lap of a session. The dashboard uses OpenF1 data and aligns each driver's telemetry by approximate lap progress.

## Run locally

Use Python 3.11+ and an internet connection. From the repository root:

```bash
cd f1_fingerprint
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run main.py
```

For Windows PowerShell commands, configuration options, and usage notes, see the [app README](f1_fingerprint/README.md). The [project walkthrough](f1_fingerprint/PROJECT_WALKTHROUGH.md) explains the code, build sequence, and technical limits.
