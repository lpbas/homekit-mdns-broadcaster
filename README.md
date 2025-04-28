# mDNS Broadcaster

![Python Version](https://img.shields.io/badge/python-3.x-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A small Python utility to **resolve**, **parse**, and **re-broadcast** mDNS services on your local network using dns-sd.

Are you tired of Docker/OrbStack on OSX not broadcasting your mDNS services?
Can you see your services when running dns-sd -B but the other devices on your network can't?
Don't want to run a full VM for a service just to use some proper host networking to be able to get mDNS from containers working?
Then this small script may be for you!

This is especially useful for custom setups using Docker in MacOS like running Home Assistant in a container, Docker containers, or self-hosted environments where mDNS service advertisements need to be recreated manually due to the way mDNS is handled by Docker/OrbStack in MacOS.

You can follow the progress of OrbStack fixing this issue [here](https://github.com/orbstack/orbstack/issues/342). Hopefully this script will not be needed in the future.

---

## Features

- Auto-resolves services from a whitelist file
- Extracts service TXT records and ports
- Re-broadcasts services using `dns-sd`
- Clean logging to a file (and optionally to console)
- Graceful shutdown on Ctrl+C
- Lightweight and dependency-free (uses only built-in Python modules)

---

## Requirements

- Python 3.x
- `dns-sd` command line tool (already built into macOS)

---

## Usage

```bash
python3 mdns_broadcaster.py [OPTIONS]
```

### Options

| Argument             | Description                              |
| -------------------- | ---------------------------------------- |
| `--delay`             | Delay script start by 90 seconds        |
| `--whitelist <path>`  | Path to a custom service whitelist file |
| `--log <path>`        | Path to a custom log file               |
| `--verbose`           | Enable live console logging             |

### Example Commands

Start with default `service_whitelist.txt` and `mdns_broadcaster.log` in the current directory:

```bash
python3 mdns_broadcaster.py --verbose
```

Start with a custom whitelist and log file:

```bash
python3 mdns_broadcaster.py --whitelist my_services.txt --log my_logfile.log
```

Delay startup by 60 seconds (useful if you want to run this script on system startup in order to wait for your containers to load):

```bash
python3 mdns_broadcaster.py --delay --verbose
```

---

## Setup

Before running the script:

1. Copy the example whitelist file:

```bash
cp example_service_whitelist.txt service_whitelist.txt
```

2. Edit `service_whitelist.txt` and add the names of the services you want to re-broadcast (one per line).

---

## Whitelist File Format

- Plain text file
- One service name per line
- Lines starting with `#` are ignored (comments)

Example:

```text
# My HomeKit Bridges
HASS Bridge SP B1234
Home Assistant Bridge 45A67F
```

## License

MIT License.  
Feel free to use, modify, and contribute!

---

## Notes

- The script will terminate and inform you if the default `service_whitelist.txt` is missing and no custom file is provided.
- Make sure your Python environment has permission to use `dns-sd`.
- To stop the script, press **Ctrl+C** — all running `dns-sd` processes it will be cleaned up automatically.
- You can add the script as a launch agent to run it on OSX when you login.
