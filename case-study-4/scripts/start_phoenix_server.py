"""
Starts the local Phoenix server/UI (localhost:6006) and blocks. Run
this from the SEPARATE .venv-phoenix environment, in its own terminal,
before running any dispute in the main app venv, and leave it running:

    ./.venv-phoenix/bin/python scripts/start_phoenix_server.py

Then in another terminal (main venv):

    ./.venv/bin/python cli.py run DSP-3001
    ... (run the other sample disputes) ...

Then back in the phoenix venv, export the evidence:

    ./.venv-phoenix/bin/python scripts/export_phoenix_traces.py
    ./.venv-phoenix/bin/python scripts/build_golden_signals.py
    ./.venv-phoenix/bin/python scripts/build_dashboard.py
"""

from __future__ import annotations

import time


def main() -> None:
    import phoenix as px

    session = px.launch_app()
    print(f"Phoenix UI running at {session.url if session else 'http://localhost:6006'}")
    print("Leave this running, then run disputes from the main venv in another terminal.")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Stopping Phoenix server.")


if __name__ == "__main__":
    main()
