<div align="center">

<img src="assets/icon.png" alt="AwesomeLoL icon" width="120"/>

# AwesomeLoL

**Auto-accepts the "Match Found" popup in League of Legends so you can keep alt-tabbing.**

[![Release](https://img.shields.io/github/v/release/supposedtobescruz/awesomelol?style=flat-square&color=blue)](../../releases/latest)
[![Build](https://img.shields.io/github/actions/workflow/status/supposedtobescruz/awesomelol/build.yml?style=flat-square&label=build)](../../actions/workflows/build.yml)
[![Platform](https://img.shields.io/badge/platform-Windows-blueviolet?style=flat-square&logo=windows&logoColor=white)](#getting-started)
[![Python](https://img.shields.io/badge/python-3.8%2B-informational?style=flat-square&logo=python&logoColor=white)](requirements.txt)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

</div>

---

No screen scraping, no fake mouse clicks, nothing injected into the game. AwesomeLoL talks directly to the League client's own local API (LCU) and accepts your match the instant the popup appears. By default it accepts **one match and exits within 5 seconds** — pass `--loop` if you want it to stay open and accept every match.

## What it looks like

```
  AwesomeLoL v1.0  -  auto-accept for League of Legends
  https://github.com/supposedtobescruz/awesomelol

  tip: run with --loop to keep accepting every match
--------------------------------------------------------

[*] Waiting for the League client....
[+] Connected (port 33096)
[*] Searching for a match...
.......................................................
[+] MATCH ACCEPTED!

[!] Closing in 1 seconds...
Done. Bye!
```

## How it works

1. Reads the connection details (port + auth token) from the running `LeagueClientUx` process — lockfile as fallback
2. Polls `/lol-matchmaking/v1/ready-check` once per second over localhost HTTPS
3. Fires `POST /lol-matchmaking/v1/ready-check/accept` the moment the popup state flips to `InProgress`
4. Counts down for 5 seconds and exits (single-shot mode)

Everything happens on `127.0.0.1` between this tool and your own client. The game process is never touched.

## Getting started

No coding required:

1. Head to the [latest release](../../releases/latest)
2. Download `AwesomeLoL.exe`
3. Open your LoL client, then run the exe
4. Queue up and forget about it

> Windows SmartScreen may warn about an unsigned executable. That's expected for any open-source tool without a code-signing certificate — review the source here or build it yourself below.

### Options

| Flag | Behavior |
|------|----------|
| *(none)* | Accept one match, close after 5 seconds |
| `--loop` | Keep running and accept every match |

## Building it yourself

```bash
pip install -r requirements.txt pyinstaller
pyinstaller --onefile --console --icon assets/icon.ico --name AwesomeLoL main.py
```

Or don't bother building anything: every `v*` tag triggers a GitHub Actions workflow that compiles the `.exe` (with the icon baked in) on a clean Windows runner and attaches it to the release automatically. Each release binary is also uploaded to VirusTotal and the scan report link is added to the release notes.

## FAQ

<details>
<summary><b>Will I get banned?</b></summary>

The tool never touches game files or the match itself — it only calls endpoints your own client already exposes locally. That said, use at your own risk; Riot's stance on third-party tools can change.

</details>

<details>
<summary><b>Why does my antivirus flag the exe?</b></summary>

The binary is unsigned and packed with PyInstaller, so machine-learning detectors make educated guesses instead of finding actual malware. The current release scans **63/71 engines clean** on VirusTotal — every engine that flags it reports a generic ML verdict, not a real signature:

| Engine | Verdict | What it actually is |
|---|---|---|
| Microsoft | Trojan:Win32/Wacatac.**B!ml** | ML heuristic (`!ml` = machine learned) |
| SentinelOne | Static AI - Suspicious PE | ML model on the PyInstaller structure |
| Elastic | malicious (moderate confidence) | ML model |
| APEX | Malicious | ML model |
| K7 (x2) | Password-Stealer | Behavioral guess: the tool reads the client's command line to get its auth token |
| Bkav | W32.Malware.* | Generic name, Bkav is a known false-positive machine |

No engine reports a specific, verifiable threat — because there isn't one. Don't take our word for it:

- Every release ships with a VirusTotal link in the notes — read the report yourself
- Every build gets a [build provenance attestation](../../attestations) proving it was compiled by this repo's workflow
- The entire source is one ~150 line file: build it yourself with the two commands above and compare

Help everyone out: if your antivirus flags it, [report the false positive to Microsoft](https://www.microsoft.com/en-us/wdsi/filesubmission) (the only major engine affected) — it takes a minute.

</details>

<details>
<summary><b>I ran it while the client was closed and nothing happened.</b></summary>

That's by design. It waits until the League client is running.

</details>

<details>
<summary><b>Does it work in champion select / during a game?</b></summary>

There's nothing left to do once the match is accepted — that's the whole point.

</details>

## License

[MIT](LICENSE)
