from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).parents[1]
SCRIPTS = REPO / "skills" / "llm-wiki" / "scripts"


class LauncherIntegrationTests(unittest.TestCase):
    def test_bootstrap_launch_health_security_duplicate_and_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "blank wiki"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "bootstrap_wiki.py"),
                    str(root),
                    "--preset",
                    "mixed",
                    "--title",
                    "Synthetic Test Wiki",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            fake_key = "integration-placeholder"
            (root / ".env").write_text(
                "LLMWIKI_PROVIDER=openai\n"
                "LLMWIKI_AI_ENABLED=1\n"
                f"OPENAI_API_KEY={fake_key}\n",
                "utf-8",
            )

            occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            first_port = occupied.getsockname()[1]
            launcher = root / "tools" / "launch_wiki.py"
            started = None
            try:
                started = subprocess.run(
                    [
                        sys.executable,
                        str(launcher),
                        "--root",
                        str(root),
                        "--port",
                        str(first_port),
                        "--no-browser",
                        "--json",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                info = json.loads(started.stdout)
                self.assertNotEqual(info["port"], first_port)

                base = f"http://127.0.0.1:{info['port']}"
                with urllib.request.urlopen(f"{base}/health", timeout=3) as response:
                    health = json.loads(response.read())
                self.assertEqual(health["host"], "127.0.0.1")
                self.assertEqual(health["ai"]["provider"], "openai")
                self.assertEqual(health["ai"]["keyStatus"], "configured (****)")
                self.assertNotIn(fake_key, json.dumps(health))

                with urllib.request.urlopen(
                    f"{base}/constellation.html", timeout=3
                ) as response:
                    self.assertEqual(response.status, 200)

                duplicate = subprocess.run(
                    [
                        sys.executable,
                        str(launcher),
                        "--root",
                        str(root),
                        "--port",
                        str(first_port),
                        "--no-browser",
                        "--json",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.assertTrue(json.loads(duplicate.stdout)["alreadyRunning"])

                with self.assertRaises(urllib.error.HTTPError) as traversal:
                    urllib.request.urlopen(f"{base}/%2e%2e/purpose.md", timeout=3)
                self.assertEqual(traversal.exception.code, 403)

                request = urllib.request.Request(
                    f"{base}/search",
                    data=b'{"question":"test"}',
                    headers={
                        "Content-Type": "application/json",
                        "Origin": "https://example.invalid",
                    },
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as cors:
                    urllib.request.urlopen(request, timeout=3)
                self.assertEqual(cors.exception.code, 403)

                log = (root / ".llmwiki" / "bridge.log").read_text(
                    "utf-8", errors="replace"
                )
                self.assertNotIn(fake_key, log)
            finally:
                occupied.close()
                if started is not None:
                    subprocess.run(
                        [sys.executable, str(launcher), "--root", str(root), "--stop"],
                        check=False,
                        capture_output=True,
                        text=True,
                    )


if __name__ == "__main__":
    unittest.main()
