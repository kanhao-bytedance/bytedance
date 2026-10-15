"""Exercise the hosted startup and persistent-feedback workflow locally.

Run: python scripts/check_deployment.py [--python /path/to/python]
Uses a temporary database and never reads or changes the real feedback database.
"""
import argparse
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="signal-deployment-") as directory:
        env = os.environ.copy()
        password = secrets.token_urlsafe(32)
        env.update(PATH=f"{Path(args.python).absolute().parent}{os.pathsep}{env.get('PATH', '')}",
                   PORT=str(port), DATABASE_URL=f"sqlite:///{directory}/feedback.db",
                   DASHBOARD_USER="admin", DASHBOARD_PASSWORD=password,
                   REQUIRE_DASHBOARD_AUTH="true", OPENAI_API_KEY="", REDDIT_BEARER_TOKEN="")
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
            def check_run(restarting=False):
                with open(Path(directory) / "server.log", "w") as log:
                    server = subprocess.Popen(["sh", "scripts/start.sh"], cwd=root, env=env,
                                              stdout=log, stderr=log)
                    try:
                        for _ in range(100):
                            if server.poll() is not None:
                                raise RuntimeError("Production startup failed. Inspect the temporary server log.")
                            try:
                                if client.get("/health").status_code == 200:
                                    break
                            except httpx.ConnectError:
                                pass
                            time.sleep(.1)
                        else:
                            raise RuntimeError("Production server never became ready.")
                        auth = ("admin", password)
                        assert client.get("/").status_code == 401
                        assert client.get("/", auth=auth).status_code == 200
                        assert client.get("/static/app.js", auth=auth).status_code == 200
                        if not restarting:
                            body = {"source":"deployment-check", "external_id":"persistence-check",
                                    "content_type":"comment", "text":"Keep the timer visible while bidding."}
                            result = client.post("/ingest", json=body, auth=auth)
                            assert result.status_code == 200, result.status_code
                            assert result.json()["created"] is True
                        summary = client.get("/summary", auth=auth).json()
                        assert summary["total"] == 1
                        rows = client.get("/feedback", params={"q":"timer visible"}, auth=auth).json()
                        assert len(rows) == 1
                        assert rows[0]["external_id"] == "persistence-check"
                        assert rows[0]["classification_status"] == "unclassified"
                    finally:
                        server.terminate()
                        server.wait(timeout=10)
            check_run()
            check_run(restarting=True)
        env["DASHBOARD_PASSWORD"] = ""
        result = subprocess.run(["sh", "scripts/start.sh"], cwd=root, env=env, capture_output=True, timeout=20)
        assert result.returncode != 0
        assert b"DASHBOARD_PASSWORD must be configured" in result.stderr
    print("Production startup passed: assigned port, authentication, dashboard assets, ingestion, search, persistence after restart, and missing-password refusal.")


if __name__ == "__main__":
    main()
