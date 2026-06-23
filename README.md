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

| Argument                  | Description                                                                        |
| ------------------------- | ---------------------------------------------------------------------------------- |
| `--delay`                 | Delay script start by 60 seconds                                                   |
| `--whitelist <path>`      | Path to a custom service whitelist file                                            |
| `--log <path>`            | Path to a custom log file                                                          |
| `--groups <g1,g2>`        | Service groups / types to scan (see below). Defaults to `homekit`. Repeatable.     |
| `--service-type <_type>`  | Explicit mDNS service type(s) to scan, e.g. `_http._tcp`. Repeatable.              |
| `--verbose`               | Enable live console logging                                                         |

### Choosing what to scan

For each whitelisted name the script tries a list of mDNS service types in order and re-broadcasts under the first one that resolves.

- **By default only the `homekit` group is scanned** (`_hap._tcp`, `_homekit._tcp`, and the Matter types). This is the fast path for the tool's main job — re-broadcasting HomeKit bridges — and keeps a run quick.
- `--groups` takes a comma-separated, repeatable list. Each token is a **group name** (expanded to its types), the special token **`all`** (every group), or a **literal service type** starting with `_`. Available groups: `homekit`, `enumeration`, `web`, `files`, `printing`, `apple`, `google`, `iot`, `media`, `dev`, `p2p`.
- `--service-type` adds explicit service type(s) and combines with any `--groups` selection.

> ⚠️ `--groups all` scans ~70 service types. Because `dns-sd -L` only stops when it hits the resolve timeout, every type that doesn't resolve costs ~2s per whitelisted service, so a broad scan can be slow. Stick to the default or a narrow group list unless you specifically need the wide net.

```bash
# Default: HomeKit only (fast)
python3 mdns_broadcaster.py --verbose

# Scan a couple of groups plus one extra service type
python3 mdns_broadcaster.py --groups web,iot --service-type _custom._tcp

# Scan everything (slow)
python3 mdns_broadcaster.py --groups all
```

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

   You must use the exact "Instance Name" of the service you see when running `dns-sd -B` (service_type is required after `-B`, e.g. for HomeKit Bridges you should run `dns-sd -B _hap._tcp`) otherwise the services will not be resolved.

   If you can't see your service when running `dns-sd -B ...` then it means your host OS cannot see the mDNS service and this script cannot help you. Fix the first part and then come back to the script. (For HomeAssitant, using `network_mode: host` in the compose.yaml file seems to do the trick to expose the services to your host)

3. Run the script.

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
