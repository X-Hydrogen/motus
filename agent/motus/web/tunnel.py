"""
Tunnel MOTUS web to public internet via serveo.net
Uses Python subprocess to handle the keyboard-interactive SSH prompt.
"""
import subprocess
import sys
import time

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8848
SUBDOMAIN = sys.argv[2] if len(sys.argv) > 2 else "motus-agent"

cmd = [
    "ssh", "-o", "StrictHostKeyChecking=no",
    "-o", "PubkeyAuthentication=no",
    "-o", "PreferredAuthentications=keyboard-interactive",
    "-o", "LogLevel=ERROR",
    "-R", f"{SUBDOMAIN}:80:localhost:{PORT}",
    "serveo.net",
]

print(f"Tunneling port {PORT} via serveo.net (subdomain: {SUBDOMAIN})...")
print(f"Public URL: https://{SUBDOMAIN}.serveo.net")
print("Press Ctrl+C to stop.\n")

proc = subprocess.Popen(
    cmd,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
)

# Serveo prompts for confirmation — send a newline
try:
    time.sleep(3)
    proc.stdin.write("\n")
    proc.stdin.flush()
except Exception:
    pass

# Print output
try:
    for line in proc.stdout:
        print(line, end="")
except KeyboardInterrupt:
    print("\nStopping tunnel...")
    proc.terminate()
    proc.wait()
