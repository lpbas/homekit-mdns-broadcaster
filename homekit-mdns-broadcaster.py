#!/usr/bin/env python3

import subprocess
import signal
import re
import time
import sys
import logging
import argparse
import os

# Constants
SERVICE_TYPE="_hap._tcp"

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
parser.add_argument("--verbose", action="store_true", help="Enable verbose output (log to console as well)")
args = parser.parse_args()

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

def extract_service_info(service_name):
    print(f"Resolving {service_name}...")
    try:
        proc = subprocess.Popen(
            ["dns-sd", "-L", service_name, SERVICE_TYPE, "local"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        try:
            stdout, stderr = proc.communicate(timeout=2)
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
            elif "md=" in line:
                # Replace escaped spaces and split on spaces
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

        if hostname and port and txt_records:
            return hostname, port, txt_records

    except Exception as e:
        logging.error(f"Error extracting service info for {service_name}: {e}")

    print(f"Failed to resolve {service_name}")
    logging.error(f"Failed to resolve {service_name}")

    return None

def main():
    successful_count = 0
    for name in WHITELISTED_SERVICES:
        info = extract_service_info(name)
        if not info:
            logging.warning(f"Skipping {name}, unable to fetch info.")
            continue

        hostname, port, txt_records = info
        cmd = ["dns-sd", "-R", name, SERVICE_TYPE, "local", port] + txt_records
        proc = subprocess.Popen(cmd)
        running_processes.append(proc)
        successful_count += 1
        logging.info(f"Registering {name}, {hostname}:{port} {txt_records} | PID: {proc.pid}")

    if successful_count == 0:
        logging.info("No services registered. Exiting.")
        print("No services registered. Exiting.")
        sys.exit(0)

    logging.info(f"{successful_count} services registered.")
    print(f"{successful_count} services registered. Press Ctrl+C to stop.")
    signal.pause()

if __name__ == "__main__":
    main()
