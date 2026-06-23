#!/usr/bin/env python3

import subprocess
import signal
import re
import time
import sys
import logging
import argparse
import os
import threading

# Constants
# Service types grouped by category. By default every group is scanned (except
# the ones in NON_DEFAULT_GROUPS); --groups / --service-type narrow it.
SERVICE_GROUPS = {
    # Meta-query used to enumerate advertised service types. Not a resolvable
    # instance type, so it's excluded from the default scan, but it can still be
    # selected explicitly with --groups enumeration.
    "enumeration": [
        "_services._dns-sd._udp",
    ],
    "web": [
        "_http._tcp",
        "_https._tcp",
        "_ssh._tcp",
        "_telnet._tcp",
        "_rfb._tcp",
        "_rdp._tcp",
        "_webdav._tcp",
        "_workstation._tcp",
    ],
    "files": [
        "_ftp._tcp",
        "_smb._tcp",
        "_afpovertcp._tcp",
        "_nfs._tcp",
        "_adisk._tcp",
        "_esdevice._tcp",
        "_esfileshare._tcp",
    ],
    "printing": [
        "_ipp._tcp",
        "_ipps._tcp",
        "_printer._tcp",
        "_scanner._tcp",
        "_printer._sub._http._tcp",
    ],
    "apple": [
        "_airdrop._tcp",
        "_airplay._tcp",
        "_raop._tcp",
        "_airport._tcp",
        "_appletv-v2._tcp",
        "_companion-link._tcp",
        "_home-sharing._tcp",
        "_daap._tcp",
        "_dpap._tcp",
        "_atc._tcp",
        "_device-info._tcp",
        "_apple-mobdev2._tcp",
        "_apple-sasl._tcp",
        "_eppc._tcp",
        "_ica-networking._tcp",
        "_ichat._tcp",
    ],
    "homekit": [
        "_hap._tcp",
        "_homekit._tcp",
        "_matterc._udp",
        "_matter._tcp",
        "_matterd._udp",
    ],
    "google": [
        "_googlecast._tcp",
        "_googlezone._tcp",
        "_androidtvremote._tcp",
        "_amzn-wplay._tcp",
        "_amazonecho-remote._tcp",
    ],
    "iot": [
        "_shelly._tcp",
        "_philipshue._tcp",
        "_aqara._tcp",
        "_aqara-setup._tcp",
        "_tplink._tcp",
    ],
    "media": [
        "_spotify-connect._tcp",
        "_sonos._tcp",
        "_roku._tcp",
        "_rsp._tcp",
        "_plexmediasvr._tcp",
        "_xbmc-jsonrpc-h._tcp",
        "_bose._tcp",
    ],
    "dev": [
        "_hudson._tcp",
        "_jenkins._tcp",
        "_distcc._tcp",
        "_sketchmirror._tcp",
        "_bcbonjour._tcp",
        "_cloud._tcp",
        "_airdroid._tcp",
    ],
    "p2p": [
        "_bp2p._tcp",
        "_Friendly._sub._bp2p._tcp",
        "_invoke._sub._bp2p._tcp",
        "_webdav._sub._bp2p._tcp",
    ],
}

# Groups left out of the default "scan everything" set (still selectable by name).
NON_DEFAULT_GROUPS = {"enumeration"}

# Timeouts
RESOLVE_TIMEOUT=2
DELAY=60

# Default paths
DEFAULT_WHITELIST_FILE = "service_whitelist.txt"
DEFAULT_LOG_FILE = "mdns_broadcaster.log"

# Parse command line arguments
parser = argparse.ArgumentParser(
    description="mDNS service resolver and broadcaster.\n\n"
                "Example usage:\n"
                "  python3 mdns_broadcaster.py --verbose\n"
                "  python3 mdns_broadcaster.py --whitelist my_services.txt --log mdns_log.log\n",
    formatter_class=argparse.RawTextHelpFormatter
)

parser.add_argument("--delay", action="store_true", help=f"Delay start for {DELAY} seconds")
parser.add_argument("--whitelist", type=str, help="Path to the service whitelist file")
parser.add_argument("--log", type=str, help="Path to the log file")
parser.add_argument(
    "--groups",
    action="append",
    metavar="g1,g2",
    help="Comma-separated groups and/or service types to scan. Each token is a\n"
         "group name (expanded to its types) or a literal service type\n"
         "(anything starting with '_'). Repeatable.\n"
         "Available groups: " + ", ".join(SERVICE_GROUPS) + ".\n"
         "If omitted, all groups are scanned (except 'enumeration').",
)
parser.add_argument(
    "--service-type",
    action="append",
    metavar="_type._tcp",
    help="Explicit mDNS service type(s) to scan (e.g. _http._tcp). Repeatable and\n"
         "comma-separated; combined with any --groups selection.",
)
parser.add_argument("--verbose", action="store_true", help="Enable verbose output (log to console as well)")
args = parser.parse_args()


def _split_csv(values):
    """Flatten a list of (possibly comma-separated) CLI values into tokens."""
    tokens = []
    for value in values or []:
        tokens.extend(part.strip() for part in value.split(",") if part.strip())
    return tokens


# Resolve --groups / --service-type into the ordered list of service types to
# scan. A --groups token is either a group name (expanded) or a literal service
# type. Both flags combine; if neither is given, scan all default groups. For
# each whitelisted name the script tries each type in order and registers under
# whichever one resolves first.
selected = []
unknown_groups = []
for token in _split_csv(args.groups):
    if token in SERVICE_GROUPS:
        selected.extend(SERVICE_GROUPS[token])
    elif token.startswith("_"):
        selected.append(token)  # literal service type
    else:
        unknown_groups.append(token)

selected.extend(_split_csv(args.service_type))

if unknown_groups:
    print(f"Error: unknown group(s): {', '.join(unknown_groups)}")
    print(f"Available groups: {', '.join(SERVICE_GROUPS)}")
    print("(Pass a literal service type starting with '_' to scan one directly.)")
    sys.exit(1)

if selected:
    SERVICE_TYPES = list(dict.fromkeys(selected))
else:
    SERVICE_TYPES = list(dict.fromkeys(
        service_type
        for group, types in SERVICE_GROUPS.items()
        if group not in NON_DEFAULT_GROUPS
        for service_type in types
    ))

if args.delay:
    print(f"Delaying script execution for {DELAY} seconds...")
    logging.info(f"Delaying script execution for {DELAY} seconds...")
    time.sleep(DELAY)

# Use provided or default file paths
whitelist_file = args.whitelist if args.whitelist else DEFAULT_WHITELIST_FILE
log_file = args.log if args.log else DEFAULT_LOG_FILE

# Setup logging
log_handlers = [logging.FileHandler(log_file)]

if args.verbose:
    log_handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=log_handlers
)

# Load whitelisted services
if not os.path.isfile(whitelist_file):
    if args.whitelist:
        print(f"Error: Provided whitelist file '{whitelist_file}' does not exist.")
    else:
        print(f"Error: Default whitelist file '{DEFAULT_WHITELIST_FILE}' not found in the current directory.\n"
              f"Please provide a file using --whitelist <path_to_file>.")
    sys.exit(1)

try:
    with open(whitelist_file, "r") as f:
        WHITELISTED_SERVICES = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
except Exception as e:
    logging.error(f"Failed to load whitelist file: {e}")
    print(f"Failed to load whitelist file: {e}")
    sys.exit(1)

print(f"Will try to resolve {len(WHITELISTED_SERVICES)} services: {WHITELISTED_SERVICES}")
print(f"Scanning {len(SERVICE_TYPES)} service type(s) (in order): {SERVICE_TYPES}")

# Store subprocesses so we can clean them up later
running_processes = []

def cleanup(signum=None, frame=None):
    logging.info("Cleaning up spawned dns-sd processes...")
    for proc in running_processes:
        proc.terminate()
    logging.info("Script finished, all cleaned up! 🧹\n")
    sys.exit(0)

# Handle SIGINT (Ctrl+C) and SIGTERM
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def resolve_under_type(service_name, service_type):
    """Resolve a single service under one service type.

    Returns (hostname, port, txt_records) on success, or None if there is no
    matching instance for this service type.
    """
    proc = subprocess.Popen(
        ["dns-sd", "-L", service_name, service_type, "local"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # dns-sd -L never exits on its own, so it always hits the timeout; we then
    # terminate it and parse whatever it buffered.
    try:
        stdout, stderr = proc.communicate(timeout=RESOLVE_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.terminate()
        stdout, stderr = proc.communicate()

    hostname, port = None, None
    txt_records = []

    for line in stdout.splitlines():
        if "can be reached at" in line:
            match = re.search(r"at (.*?)\.(local|local.):(\d+)", line)
            if match:
                hostname = match.group(1) + ".local"
                port = match.group(3)
        elif "=" in line:
            # TXT record line. Replace escaped spaces and split on spaces.
            line = line.strip().replace("\\032", " ")
            parts = line.split()

            # Rebuild the key=value fields
            current_kv = ""
            for part in parts:
                if "=" in part:
                    if current_kv:
                        txt_records.append(current_kv)
                    current_kv = part
                else:
                    current_kv += " " + part
            if current_kv:
                txt_records.append(current_kv)

    if hostname and port:
        return hostname, port, txt_records

    return None


def extract_service_info(service_name, service_types):
    print(f"Resolving {service_name}...")
    for service_type in service_types:
        try:
            result = resolve_under_type(service_name, service_type)
        except Exception as e:
            logging.error(f"Error extracting service info for {service_name} ({service_type}): {e}")
            continue

        if result:
            hostname, port, txt_records = result
            return hostname, port, txt_records, service_type

    print(f"Failed to resolve {service_name}")
    logging.error(f"Failed to resolve {service_name}")

    return None

def main():
    successful_count = 0
    for name in WHITELISTED_SERVICES:
        info = extract_service_info(name, SERVICE_TYPES)
        if not info:
            logging.warning(f"Skipping {name}, unable to fetch info.")
            continue

        hostname, port, txt_records, service_type = info
        cmd = ["dns-sd", "-R", name, service_type, "local", port] + txt_records
        proc = subprocess.Popen(cmd)
        running_processes.append(proc)
        successful_count += 1
        logging.info(f"Registering {name} as {service_type}, {hostname}:{port} {txt_records} | PID: {proc.pid}")

    if successful_count == 0:
        logging.info("No services registered. Exiting.")
        print("No services registered. Exiting.")
        sys.exit(0)

    logging.info(f"{successful_count} services registered.")
    print(f"{successful_count} services registered. Press Ctrl+C to stop.")

    # Block until the process is killed by a signal.
    # threading.Event().wait() is used instead of signal.pause() because
    # signal.pause() on macOS returns when *any* signal arrives (EINTR),
    # which caused the script to re-enter the registration loop and spawn
    # duplicate dns-sd -R child processes.
    threading.Event().wait()

if __name__ == "__main__":
    main()
