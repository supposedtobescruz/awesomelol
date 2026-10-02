"""
AwesomeLoL - auto-accepts the "Match Found" popup in League of Legends.

No screen scraping, no fake mouse clicks. Talks straight to the local
League client API (LCU): grabs the port + auth token from the running
LeagueClientUx process (lockfile as fallback), polls the ready-check
endpoint and fires the accept request the moment a match shows up.

Start it with no arguments to get a menu, or pass a flag to skip it:
    --loop        accept every match, never exit
    --status      print what the client is doing, then exit
"""

import argparse
import os
import re
import sys
import time

import psutil
import requests
import urllib3

try:
    import msvcrt
except ImportError:
    msvcrt = None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

INTERVAL = 1      # seconds between polls
CLOSE_DELAY = 5   # seconds to stick around after accepting
VERSION = "v1.0.6"

DIM = "\x1b[90m"
BOLD = "\x1b[1m"
CYAN = "\x1b[96m"
GREEN = "\x1b[92m"
OFF = "\x1b[0m"

LOCKFILE_PATHS = [
    r"C:\Riot Games\League of Legends\lockfile",
    r"C:\Riot Games\League of Legends Game\lockfile",
]

MENU = [
    ("1", "Accept once", "accept 1 match, close after 5s"),
    ("2", "Accept every match", "stay open, accept all of them"),
    ("3", "Client status", "who am I, what is it doing right now"),
    ("0", "Quit", ""),
]

ARROWS = {"H": "up", "P": "down", "M": "enter"}


def banner():
    print(
        f"\n{GREEN}  AwesomeLoL {VERSION}{OFF}{DIM}  -  auto-accept for League of Legends\n"
        f"  https://github.com/supposedtobescruz/awesomelol{OFF}\n"
        f"{DIM}  --------------------------------------------------------{OFF}\n"
    )


def read_key():
    # single keypress, no echo; falls back to plain input off Windows
    if msvcrt is None:
        return input().strip().lower() or "enter"
    ch = msvcrt.getwch()
    if ch in ("\x00", "\xe0"):
        return ARROWS.get(msvcrt.getwch(), "ignore")
    if ch in ("\r", "\n"):
        return "enter"
    if ch == "\x03":
        raise KeyboardInterrupt
    if ch == "\x1b":
        return "esc"
    return ch.lower()


def draw_menu(selected):
    os.system("cls" if os.name == "nt" else "clear")
    print(f"{GREEN}  AwesomeLoL {VERSION}{OFF}{DIM}  -  auto-accept for League of Legends{OFF}\n")
    for index, (key, title, hint) in enumerate(MENU):
        marker = f"{CYAN}{BOLD} > {OFF}" if index == selected else "   "
        print(f"  {marker} {BOLD}[{key}]{OFF} {title:<20}{DIM}{hint}{OFF}")
    print(f"\n  {DIM}arrows or a number, Enter confirms{OFF}")


def ask_menu():
    selected = 0  # [1] accept once
    while True:
        draw_menu(selected)
        key = read_key()
        if key == "up":
            selected = (selected - 1) % len(MENU)
        elif key == "down":
            selected = (selected + 1) % len(MENU)
        elif key == "esc":
            return "0"
        elif key == "enter":
            return MENU[selected][0]
        else:
            for number, _, _ in MENU:
                if key == number:
                    return number


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
            # name:pid:port:token:protocol - we want fields 2 and 3
            if len(parts) >= 4 and parts[2].isdigit():
                return parts[2], parts[3]
        except OSError:
            continue
    return None


def open_session(port, token):
    base = f"https://127.0.0.1:{port}"
    session = requests.Session()
    session.auth = ("riot", token)
    session.verify = False
    return base, session


def wait_for_client():
    print("[*] Waiting for the League client", end="", flush=True)
    credentials = None
    while credentials is None:
        credentials = find_client()
        if credentials is None:
            print(".", end="", flush=True)
            time.sleep(INTERVAL)
    port, token = credentials
    print(f"\n[+] Connected (port {port})")
    return open_session(port, token)


def watch_and_accept(base, session):
    # while queued, /lol-matchmaking/v1/ready-check answers with the popup
    # state; outside a queue it may 404, which we treat as "nothing yet"
    print("[*] Searching for a match...", flush=True)
    try:
        while True:
            response = session.get(base + "/lol-matchmaking/v1/ready-check", timeout=3)
            if response.ok:
                check = response.json()
                state = check.get("state")
                answer = check.get("playerResponse")
                if state == "InProgress" and answer in (None, "", "None"):
                    if session.post(
                        base + "/lol-matchmaking/v1/ready-check/accept", timeout=3
                    ).ok:
                        print("\n[+] MATCH ACCEPTED!")
                        return "accepted"
                    print("\n[!] The client refused the accept request")
                elif state == "InProgress" and answer == "Declined":
                    print("\n[-] Ready check declined, back in the queue")
                    time.sleep(INTERVAL)
                    continue
            else:
                print(".", end="", flush=True)
            time.sleep(INTERVAL)
    except requests.RequestException:
        # client died or restarted, outer loop will wait for it again
        print("\n[!] Lost connection to the client")
        return "lost"


def show_status():
    base, session = wait_for_client()
    with session:
        summoner = session.get(base + "/lol-summoner/v1/current-summoner", timeout=3).json()
        print(f"    summoner : {summoner.get('displayName')} (level {summoner.get('summonerLevel')})")
        flow = session.get(base + "/lol-gameflow/v1/session", timeout=3).json()
        print(f"    phase    : {flow.get('phase')}")
        queue = flow.get("queue") or {}
        print(f"    queue    : {queue.get('queueType') or '-'}")


def countdown():
    for remaining in range(CLOSE_DELAY, 0, -1):
        print(f"\r[!] Closing in {remaining} seconds...", end="", flush=True)
        time.sleep(1)


def run(loop):
    while True:
        base, session = wait_for_client()
        with session:
            accepted = watch_and_accept(base, session) == "accepted"
        if not accepted:
            # the client restarted - go find it again
            continue
        if loop:
            print("[*] --loop mode: watching for the next match\n")
            time.sleep(CLOSE_DELAY)
            continue
        countdown()
        print("\rDone. Bye!" + " " * 30)
        return


def main():
    # force utf-8 so piped output can't crash on legacy codepages
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
    parser.add_argument(
        "--status",
        action="store_true",
        help="print what the client is doing, then exit",
    )
    options = parser.parse_args()

    os.system("")  # enable ANSI colors on the classic Windows console

    loop = options.loop

    if options.status:
        banner()
        show_status()
        return

    if options.loop:
        banner()
    else:
        choice = ask_menu()
        if choice == "0":
            print(f"\n{DIM}Bye!{OFF}")
            return
        if choice == "2":
            loop = True
        elif choice == "3":
            banner()
            show_status()
            return

    run(loop)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[-] Stopped.")