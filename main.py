"""
AwesomeLoL - auto-accepts the "Match Found" popup in League of Legends.

No screen scraping, no fake mouse clicks. Talks straight to the local
League client API (LCU): grabs the port + auth token from the running
LeagueClientUx process (lockfile as fallback), polls the ready-check
endpoint and fires the accept request the moment a match shows up.
"""

import argparse
import os
import re
import sys
import time

import psutil
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

INTERVAL = 1      # seconds between polls
CLOSE_DELAY = 5   # seconds to stick around after accepting

LOCKFILE_PATHS = [
    r"C:\Riot Games\League of Legends\lockfile",
    r"C:\Riot Games\League of Legends Game\lockfile",
]

BANNER = """
\x1b[92m █████╗ ██╗    ██╗███████╗███████╗ ██████╗ ███╗   ███╗███████╗██╗      ██████╗ ██████╗ ██╗
██╔══██╗██║    ██║██╔════╝██╔════╝██╔═══██╗████╗ ████║██╔════╝██║     ██╔═══██╗██╔══██╗██║
███████║██║ █╗ ██║███████╗█████╗  ██║   ██║██╔████╔██║█████╗  ██║     ██║   ██║██████╔╝██║
██╔══██║██║███╗██║╚════██║██╔══╝  ██║   ██║██║╚██╔╝██║██╔══╝  ██║     ██║   ██║██╔═══╝ ██║
██║  ██║╚███╔███╔╝███████║███████╗╚██████╔╝██║ ╚═╝ ██║███████╗███████╗╚██████╔╝██║     ███████╗
╚═╝  ╚═╝ ╚══╝╚══╝ ╚══════╝╚══════╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝╚══════╝ ╚═════╝ ╚═╝     ╚══════╝\x1b[0m
        auto-accepts the Match Found popup so you can keep alt-tabbing
"""


def find_client():
    # the UX process carries --app-port and --remoting-auth-token on its
    # command line, that's all we need to talk to the local API
    for proc in psutil.process_iter(["name", "cmdline"]):
        if (proc.info["name"] or "").lower() != "leagueclientux.exe":
            continue
        cmdline = " ".join(proc.info["cmdline"] or [])
        port = re.search(r"--app-port=(\d+)", cmdline)
        token = re.search(r"--remoting-auth-token=([\w-]+)", cmdline)
        if port and token:
            return port.group(1), token.group(1)

    # process scan came up empty, try the usual install locations
    for path in LOCKFILE_PATHS:
        try:
            with open(path, encoding="utf-8") as f:
                parts = f.read().strip().split(":")
            if len(parts) >= 3:
                return parts[1], parts[2]
        except OSError:
            continue
    return None


def watch_and_accept(port, token):
    # while queued, /lol-matchmaking/v1/ready-check answers with the popup
    # state; outside a queue it may 404, which we treat as "nothing yet"
    base_url = f"https://127.0.0.1:{port}"
    session = requests.Session()
    session.auth = ("riot", token)
    session.verify = False

    print("[*] Searching for a match...", flush=True)
    try:
        while True:
            response = session.get(base_url + "/lol-matchmaking/v1/ready-check", timeout=3)
            if response.ok:
                check = response.json()
                found = check.get("state") == "InProgress"
                unanswered = check.get("playerResponse") != "Accepted"
                if found and unanswered:
                    if session.post(
                        base_url + "/lol-matchmaking/v1/ready-check/accept", timeout=3
                    ).ok:
                        print("\n[+] MATCH ACCEPTED!")
                        return True
            else:
                print(".", end="", flush=True)
            time.sleep(INTERVAL)
    except requests.RequestException:
        # client died or restarted, outer loop will wait for it again
        print("\n[!] Lost connection to the client")
        return False


def countdown():
    for remaining in range(CLOSE_DELAY, 0, -1):
        print(f"\r[!] Closing in {remaining} seconds...", end="", flush=True)
        time.sleep(1)


def main():
    # the banner uses box-drawing chars that older codepages (cp1254 etc.)
    # can't encode once output gets piped, so force utf-8 everywhere
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    parser = argparse.ArgumentParser(
        description="Auto-accepts the Match Found popup in League of Legends."
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="don't exit after the first accept, keep accepting every match",
    )
    options = parser.parse_args()

    os.system("")  # enable ANSI colors on the classic Windows console
    print(BANNER)

    while True:
        print("[*] Waiting for the League client", end="", flush=True)
        credentials = None
        while credentials is None:
            credentials = find_client()
            if credentials is None:
                print(".", end="", flush=True)
                time.sleep(INTERVAL)
        port, token = credentials
        print(f"\n[+] Connected (port {port})")

        accepted = watch_and_accept(port, token)
        if not accepted:
            continue
        if options.loop:
            print("[*] --loop mode: watching for the next match\n")
            time.sleep(CLOSE_DELAY)
            continue
        countdown()
        print("\rDone. Bye!" + " " * 30)
        return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[-] Stopped.")
