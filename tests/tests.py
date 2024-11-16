#!/usr/bin/python3

# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright (c) 2023 Tesla Inc. All rights reserved.
#
# TTP (TTPoE) A reference implementation of Tesla Transport Protocol (TTP) that runs
#             directly over Ethernet Layer-2 Network. This is implemented as a Loadable
#             Kernel Module that establishes a TTP-peer connection with another instance
#             of the same module running on another Linux machine on the same Layer-2
#             network. Since TTP runs over Ethernet, it is often referred to as TTP Over
#             Ethernet (TTPoE). This is a test script.
#
#             This public release of the TTP software implementation is aligned with the
#             patent disclosure and public release of the main TTP Protocol
#             specification. Users of this software module must take into consideration
#             those disclosures in addition to the license agreement mentioned here.
#
# Authors:    Diwakar Tundlam <dntundlam@tesla.com>
#
# This software is licensed under the terms of the GNU General Public License version 2
# as published by the Free Software Foundation, and may be copied, distributed, and
# modified under those terms.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; Without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.

import os
import sys
import stat
import time
import json
import socket
import argparse
import unittest
import subprocess
from datetime import datetime

selfHost = ""
peerHost = ""
macUpper = "98:ed:5c"
peerMacL = ""
peerTgt  = ""
selfMac  = ""
selfTgt  = ""
selfDev  = ""
peerDev  = ""
selfLock = ""
peerLock = ""
verbose  = 0
connVCI  = "0"
tagSeqi  = "0"
nhmac    = ""
ipv4Arg  = 0
selfPfix = ""
peerPfix = ""
dropPct  = 0
sleepSec = 0.0
selfTgen = True
peerTgen = True

modpath  = "/sys/module/modttpoe/parameters"
procpath = "/proc/net/modttpoe"

ttpZones = [[0x1,  0x2,  0x3,  0x10],
            [0x4,  0x5,  0x6,  0x11],
            [0x7,  0x8,  0x9,  0x71],
            [0xa,  0xb,  0xc,  0x72],
            [0x21, 0x22, 0x23, 0x24]]

def getDefaultEthDev():
    return "vleth"

def getDefaultIP4Dev():
    return "vlip4"

def selfHostname():
    return subprocess.run (['uname', '-n'],
                           stdout=subprocess.PIPE).stdout.decode().strip()

def peerHostname (mac):
    if options.use_gw:
        str = selfHostname().split('-')
        selfhn = int(str[-1], 16)
        peerhn = int(options.target, 16)
        for zon in ttpZones:
            if selfhn in zon and peerhn in zon:
                print (f"Error: Unsupported in 'use-gw': target-node:'{options.target}'"
                       f" local-node:'{selfhn:02x}' in same zone:"
                       f"'{1 + ttpZones.index(zon)}'")
                sys.exit (-1)
    if mac[0] != '0' or mac[1] != '0' or mac[2] != ':' or \
       mac[3] != '0' or mac[4] != '0' or mac[5] != ':':
        print (f"Warning: Cannot resolve target={peerhn} to hostname")
        return "node-unknown"
    else:
        return f"node-{mac[-2:]}"

def setUpModule():
    global peerHost
    global macUpper
    global peerMacL
    global peerTgt
    global selfMac
    global selfTgt
    global selfDev
    global peerDev
    global selfLock
    global peerLock
    global verbose
    global connVCI
    global tagSeqi
    global nhmac
    global ipv4Arg
    global selfPfix
    global peerPfix
    global dropPct
    global sleepSec
    global selfTgen
    global peerTgen

    if "-vvv" in sys.argv[1:] or "--vvverbose" in sys.argv[1:]:
        verbose = 3
    elif "-vv" in sys.argv[1:] or "--vverbose" in sys.argv[1:]:
        verbose = 2
    elif "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]:
        verbose = 1

    selfHost = selfHostname()

    # command line options checking
    if not options.target:
        print (f"Error: Missing --target")
        sys.exit (-1)
    if options.ipv4 and options.use_gw:
        print (f"Error: Cannot combine option '--use-gw' with '--ipv4' option")
        sys.exit (-1)
    if not options.ipv4 and (options.prefix or options.self_prefix):
        print (f"Error: Require '--ipv4' option to specify '--prefix' option")
        sys.exit (-1)
    if options.prefix and (options.self_prefix or options.peer_prefix):
        print (f"Error: Cannot specify '--self/peer-prefix' with '--prefix' option")
        sys.exit (-1)
    if not options.ipv4 and (options.self_nhmac or options.peer_nhmac):
        print (f"Error: Require '--ipv4' option to specify '--nhmac'")
        sys.exit (-1)
    if (options.self_prefix and not options.peer_prefix) or \
       (options.peer_prefix and not options.self_prefix):
        print (f"Error: Require both '--self/peer-prefix' options")
        sys.exit (-1)
    if (options.self_nhmac and not options.peer_nhmac) or \
       (options.peer_nhmac and not options.self_nhmac):
        print (f"Error: Require both '--self/peer-nhmac' options")
        sys.exit (-1)
    if options.vci:
        connVCI = options.vci
    if connVCI != "0" and connVCI != "1" and connVCI != "2":
        print (f"Error: Invalid vci {connVCI}")
        sys.exit (-1)

    # command line options handling
    if options.drop_pct:
        dropPct = int(options.drop_pct)
    if options.sleep:
        sleepSec = float(options.sleep)
    elif options.drop_pct:
        sleepSec = 2.0
    if verbose:
        print (f"v---------------------------------------v")
        print (f" Start tests: {datetime.now()}")
        if verbose >= 2:
            print (f"     Verbose: {verbose}")
        if dropPct or verbose >= 2:
            print (f"Drop Percent: {dropPct}")
        if sleepSec != 0.0 or verbose >= 2:
            print (f" Sleep Delay: {sleepSec}")
    if options.ipv4:
        ipv4Arg = 1
        if verbose:
            print (f"   TTP Encap: ipv4 (etype: 0x0800)")
        if options.prefix:
            selfPfix = options.prefix
            peerPfix = options.prefix
        elif options.self_prefix: # peer_prefix required (checked earlier)
            selfPfix = options.self_prefix
            peerPfix = options.peer_prefix
        else:
            selfPfix = "10.0.0.0/8"
            peerPfix = "10.0.0.0/8"
        if not options.self_dev:
            selfDev = getDefaultIP4Dev()
    else:
        ipv4Arg = 0
        if verbose:
            print (f"   TTP Encap: ttpoe (etype: 0x9ac6)")
        if not options.self_dev:
            selfDev = getDefaultEthDev()
    if verbose:
        if options.vci:
            print (f"    Conn VCI: {connVCI} (override)")
        elif verbose >= 2:
            print (f"    Conn VCI: 0 (default)")
    if options.self_dev:
        selfDev = options.self_dev
        if verbose:
            print (f"     SelfDev: {selfDev} (override)")
    else:
        if verbose >= 2:
            print (f"     selfDev: {selfDev} (default)")

    # get src-mac from ip-link command
    cmd = f"ip -j link show dev {selfDev}"
    out = subprocess.run (str.split (cmd), stdout=subprocess.PIPE)
    if out.returncode:
        print (f"Error: {cmd} failed")
        sys.exit (-1)
    selfMac = json.loads (str(out.stdout, encoding='utf-8'))[0]["address"]
    if verbose:
        print (f"    Self MAC: {selfMac}")
    jstr = selfMac.split(':')
    selfTgt = f"{jstr[-3]}{jstr[-2]}{jstr[-1]}"

    if options.ipv4: # get src-ip from ip-addr command
        cmd = f"ip -j -4 addr show dev {selfDev}"
        out = subprocess.run (str.split (cmd), stdout=subprocess.PIPE)
        if out.returncode:
            print (f"Error: {cmd} failed")
            sys.exit (-1)
        ipa = json.loads (str(out.stdout, encoding='utf-8'))[0]["addr_info"][0]["local"]
        if verbose:
            print (f"     Self IP: {ipa} ['ip -4 addr': ipv4_sip]")
        jstr = ipa.split('.')
        selfTgt = f"{int(jstr[-1]):06x}"
    else: # check Tesla OUI only for ttpoe/ethernet mode (+gw mode): Skip for ipv4 encap
        if jstr[-6] != "98" and jstr[-5] != "ed" and jstr[-4] != "5c":
            print (f"Error: '{selfDev}' is not a TTP device: {selfMac}")
            sys.exit (-1)

    targ = options.target.split(':')
    if len(targ) == 1:
        peerMacL = ":00:00"
        peerTgt  = "0000"
    elif len(targ) == 2:
        peerMacL = ":00"
        peerTgt  = "00"
    elif len(targ) == 3:
        peerMacL = ""
        peerTgt  = ""
    else:
        print (f"Error: Bad --target='{options.target}'")
        sys.exit (-1)
    for tt in targ:
        if len(tt) == 1:
            peerMacL = f"{peerMacL}:0{tt}"
            peerTgt  = f"{peerTgt}0{tt}"
        elif len(tt) == 2:
            peerMacL = f"{peerMacL}:{tt}"
            peerTgt  = f"{peerTgt}{tt}"
        else:
            print (f"Error: Bad --target='{options.target}'")
            sys.exit (-1)
    peerMacL = peerMacL[1:]

    if not options.no_remote:
        peerHost = peerHostname (peerMacL)
    else:
        print (f"--no-remote: skipping ssh remote '{peerHost}'")
    if peerHost == selfHost:
        print (f"Error: Self --target='{options.target}'")
        sys.exit (-1)
    if os.path.exists ("/dev/noc_debug"):
        po = subprocess.run (['file', '/dev/noc_debug'],
                             stdout=subprocess.PIPE).stdout.decode().strip()
        if "character special (446/0)" not in po:
            os.system (f"ls -l /dev/noc_debug")
            print (f"Error: 'self' /dev/noc_debug not 'char' dev (446/0)\n"
                   "HINT: '/dev/noc_debug' may be a plain text file - remove it")
            sys.exit (-1)
    rv = os.system (f"which trafgen > /dev/null")
    if rv != 0:
        if verbose >= 2:
            print (f"Warning: no trafgen on self")
        selfTgen = False
    if peerHost:
        po = subprocess.run (['ssh', peerHost, 'ls', '/dev/noc_debug', '2>/dev/null'],
                             stdout=subprocess.PIPE).stdout.decode().strip()
        if "/dev/noc_debug" in po:
            po = subprocess.run (['ssh', peerHost, 'file', '/dev/noc_debug'],
                                 stdout=subprocess.PIPE).stdout.decode().strip()
            if "character special (446/0)" not in po:
                os.system (f"ssh {peerHost} 'ls -l /dev/noc_debug'")
                print (f"Error: 'peer' /dev/noc_debug not 'char' dev (446/0)\n"
                       "HINT: '/dev/noc_debug' may be a plain text file - remove it")
                sys.exit (-1)
        rv = os.system (f"ssh {peerHost} '/sbin/ifconfig {peerDev} 1>/dev/null'")
        if rv != 0:
            print (f"Error: Peer device '{peerDev}' not found")
            sys.exit (-1)
        rv = os.system (f"ssh {peerHost} 'which trafgen > /dev/null'")
        if rv != 0:
            if verbose >= 2:
                print (f"Warning: no trafgen on peer")
            peerTgen = False

    selfLock = f"/mnt/mac/.locks/ttp-host-lock-{selfHost}"
    try:
        os.open (selfLock, os.O_CREAT | os.O_EXCL, stat.S_IRUSR)
    except FileExistsError as e:
        print (f"Error: selfHost already locked ({selfLock} exists)")
        sys.exit (-1)
    if peerHost:
        peerLock = f"/mnt/mac/.locks/ttp-host-lock-{peerHost}"
        try:
            os.open (peerLock, os.O_CREAT | os.O_EXCL, stat.S_IRUSR)
        except FileExistsError as e:
            print (f"Error: {peerHost} already locked ({peerLock} exists)")
            os.remove (selfLock)
            sys.exit (-1)

    # all checks done, proceeding with tests
    if verbose:
        print (f" Self Target: {selfTgt}")
        print (f"   Self Host: {selfHost}")
    if options.peer_dev:
        peerDev = options.peer_dev
        if verbose:
            print (f"     PeerDev: {peerDev} (override)")
    else:
        if options.ipv4:
            peerDev = getDefaultIP4Dev()
        else:
            peerDev = getDefaultEthDev()
        if verbose >= 2:
            print (f"     PeerDev: {peerDev} (default)")
    if verbose:
        print (f"    Peer MAC: {macUpper}:{peerMacL}")
        print (f" Peer Target: {peerTgt}")
        print (f"   Peer Host: {peerHost}")
    if options.no_load:
        print (f"Skipping local module reload in setup:-")
    else:
        if options.ipv4:
            if options.self_nhmac:
                rv = os.system (f"sudo insmod /mnt/mac/modttpoe.ko"
                                f" verbose={verbose} dev={selfDev} drop_pct={dropPct}"
                                f" ipv4={ipv4Arg} prefix={selfPfix}"
                                f" nhmac={options.self_nhmac}")
            else:
                rv = os.system (f"sudo insmod /mnt/mac/modttpoe.ko"
                                f" verbose={verbose} dev={selfDev} drop_pct={dropPct}"
                                f" ipv4={ipv4Arg} prefix={selfPfix}")
        else:
            rv = os.system (f"sudo insmod /mnt/mac/modttpoe.ko"
                            f" verbose={verbose} dev={selfDev} drop_pct={dropPct}")
        if rv != 0:
            print (f"Error: 'insmod modttpoe' on 'self' failed")
            os.remove (selfLock)
            os.remove (peerLock)
            sys.exit (-1)
        if verbose:
            print (f" Use Gateway: {options.use_gw}")
        if verbose and options.ipv4:
            pf = open (f"/sys/module/modttpoe/parameters/prefix", "r")
            pfo = pf.read().strip()
            pf.close()
            print (f" IPv4 Prefix: {pfo} ({'override' if options.prefix else 'default'})")
        if options.ipv4: # set target to allow nhmac to resolve below
            if options.vci: # set 'vc' before setting 'target'
                rv = os.system (f"echo {connVCI} > {modpath}/vci 1")
                if rv != 0:
                    print (f"Error: Set vci on 'self' failed")
                    tearDownModule()
                    sys.exit (-1)
            rv = os.system (f"echo {peerTgt} > {modpath}/target")
            if rv != 0:
                print (f"Error: Set target on 'self' failed")
                tearDownModule()
                sys.exit (-1)
        if options.ipv4:
            pf = open (f"/sys/module/modttpoe/parameters/ipv4_sip", "r")
            pfo = pf.read().strip()
            pf.close()
            if verbose:
                print (f"     Self IP: {pfo} [param: ipv4_sip]")
        if options.ipv4:
            pf = open (f"/sys/module/modttpoe/parameters/ipv4_dip", "r")
            pfo = pf.read().strip()
            pf.close()
            if verbose:
                print (f"     Peer IP: {pfo} [param: ipv4_dip]")

        lct = 10
        while (options.use_gw or options.ipv4) and lct:
            pf = open (f"/sys/module/modttpoe/parameters/nhmac", "r")
            nhmac = pf.read().strip()
            pf.close()
            if verbose >= 2:
                print (f"?GW MAC addr: {nhmac}")
            if nhmac == "00:00:00:00:00:00":
                time.sleep (1)
                lct = lct - 1
                continue
            if not options.ipv4:
                rv = os.system (f"echo 1 > {modpath}/use_gw")
                if rv != 0:
                    print (f"Error: Set use_gw on 'self' failed")
                    tearDownModule()
                    sys.exit (-1)
            break
        if lct == 0:
            if options.ipv4:
                print (f"Error: Detect next-hop-mac on 'self' failed")
            else:
                print (f"Error: Detect gateway-mac on 'self' failed")
            tearDownModule()
            sys.exit (-1)
        if verbose:
            pf = open (f"/sys/module/modttpoe/parameters/nhmac", "r")
            nhmac = pf.read().strip()
            pf.close()
            if options.use_gw:
                print (f"   GW nh-mac: {nhmac}")
            elif options.ipv4:
                print (f" IPv4 nh-mac: {nhmac}")
        if not options.ipv4: # set target after nhmac resolve above
            if options.vci: # set 'vc' before setting 'target'
                rv = os.system (f"echo {connVCI} > {modpath}/vci 1")
                if rv != 0:
                    print (f"Error: Set vci on 'self' failed")
                    tearDownModule()
                    sys.exit (-1)
            rv = os.system (f"echo {peerTgt} > {modpath}/target")
            if rv != 0:
                print (f"Error: Set target on 'self' failed")
                tearDownModule()
                sys.exit (-1)

    tagSeqi = int(subprocess.run (["cat", f"{modpath}/tag_seq"],
                                  stdout=subprocess.PIPE).stdout.decode().strip())
    if tagSeqi != 1:
        if verbose:
            print (f"     Tag Seq: {tagSeqi} (override)")
    elif verbose >= 2:
        print (f"     Tag Seq: {tagSeqi} (default)")
    if options.no_load:
        print (f"Skipping peer module reload in setup:-")
    else:
        if peerHost:
            if options.ipv4:
                if options.peer_nhmac:
                    rv = os.system (f"ssh {peerHost} 'sudo insmod /mnt/mac/modttpoe.ko"
                                    f" verbose={verbose} dev={peerDev} drop_pct={dropPct}"
                                    f" ipv4={ipv4Arg} prefix={peerPfix}"
                                    f" nhmac={options.peer_nhmac}'")
                else:
                    rv = os.system (f"ssh {peerHost} 'sudo insmod /mnt/mac/modttpoe.ko"
                                    f" verbose={verbose} dev={peerDev} drop_pct={dropPct}"
                                    f" ipv4={ipv4Arg} prefix={peerPfix}'")
            else:
                rv = os.system (f"ssh {peerHost} 'sudo insmod /mnt/mac/modttpoe.ko"
                                f" verbose={verbose} dev={peerDev} drop_pct={dropPct}'")
            if rv != 0:
                print (f"Error: 'insmod modttpoe' on 'peer' failed")
                os.system ("sudo rmmod modttpoe 1>/dev/null")
                os.remove (selfLock)
                os.remove (peerLock)
                sys.exit (-1)
            time.sleep (0.5) # to allow peer module to settle down
    if 0: # exit early control (change 0 --> 1 to enable)
        if verbose:
            print (f"~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            tearDownModule()
            sys.exit (f"DEBUG: Exit early (disable condition to proceed..)")


def tearDownModule():
    if verbose == 3:
        print (f"**** Waiting 10 sec before tear-down:-\n"
               f" Hit ^C to stop and examine state before modules are unloaded")
        time.sleep (10)
    if options.no_unload:
        print (f"Skipping local and peer module unload in tear-down:-")
    else:
        os.system (f"sudo rmmod modttpoe 1>/dev/null")
        if peerHost:
            os.system (f"ssh {peerHost} 'sudo rmmod modttpoe 1>/dev/null'")
    os.remove (selfLock)
    if peerHost:
        os.remove (peerLock)


# This "Test0_Seq_IDs" test-suite needs to be the first test to run, as it checks RX
# and TX seq-IDs which depend on how many payloads were sent and received.
#@unittest.skip ("<comment>")
class Test0_Seq_IDs (unittest.TestCase):

    #@unittest.skip (f"skip close with EOF")
    def test1_seq_clr (self):
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"cat /dev/null > /dev/noc_debug")
        os.system (f"ssh {peerHost} 'cat /dev/null > /dev/noc_debug'")

    #@unittest.skip ("<comment>")
    def test2_tx1_seq (self):
        if options.no_load:
            self.skipTest (f"requires module reload")
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"cat /mnt/mac/tests/greet > /dev/noc_debug")
        time.sleep (1.0)
        if verbose >= 2:
            x = os.system (f"ssh {peerHost} 'diff /dev/noc_debug /mnt/mac/tests/greet'")
        else:
            x = os.system (f"ssh {peerHost}"
                           f" 'diff /dev/noc_debug /mnt/mac/tests/greet > /dev/null'")
        if x != 0:
            self.fail (f"received file did not match sent file 'greet'")
        pf = open (f"{procpath}/tags", "r")
        pfo = pf.read()
        pf.close()
        needle = f" {tagSeqi:7}  {(tagSeqi+2):7}  {(tagSeqi+1):7}  "
        if verbose >= 2:
            print()
            print (pfo)
        if needle not in pfo or peerMacL not in pfo:
            self.fail (f"did not find proper TX seq_ID (expected {needle})")
        os.system (f"cat /mnt/mac/tests/greet > /dev/noc_debug")
        time.sleep (0.1)
        pf = open (f"{procpath}/tags", "r")
        pfo = pf.read()
        pf.close()
        needle = f" {tagSeqi:7}  {(tagSeqi+3):7}  {(tagSeqi+2):7}"
        if verbose >= 2:
            print()
            print (pfo)
        if needle not in pfo or peerMacL not in pfo:
            self.fail (f"did not find proper TX seq_ID (expected 4)")
        pf = open (f"{modpath}/stats", "r")
        pfo = pf.read()
        pf.close()
        if verbose >= 2:
            print()
            for ll in pfo.split ("\n"):
                if "skb_" in ll:
                    print (ll)
        if "skb_ct: 0" not in pfo or "skb_rx: 3" not in pfo:
            self.fail (f"did not find proper [skb, rx] count (expected [0, 3])")

    #@unittest.skip ("<comment>")
    def test3_rx1_seq (self):
        if options.no_load:
            self.skipTest (f"requires module reload")
        if not peerHost:
            self.skipTest (f"--no-remote specified")
        if options.vci: # set 'vc' before setting 'target'
            rv = os.system (f"ssh {peerHost} 'echo {connVCI} > {modpath}/vci'")
            if rv != 0:
                self.fail (f"Error: Set vci {connVCI} on 'peer' failed")
        rv = os.system (f"ssh {peerHost} 'echo {selfTgt} > {modpath}/target'")
        if rv != 0:
            self.fail (f"Error: Set target {selfTgt} on 'peer' failed")

        os.system (f"cat /dev/null > /dev/noc_debug")
        os.system (f"ssh {peerHost} 'cat /mnt/mac/tests/greet > /dev/noc_debug'")
        time.sleep (0.1 + sleepSec)
        if verbose >= 2:
            os.system (f"diff /dev/noc_debug /mnt/mac/tests/greet")
        else:
            os.system (f"diff /dev/noc_debug /mnt/mac/tests/greet > /dev/null")
        pf = open (f"{procpath}/tags", "r")
        pfo = pf.read()
        pf.close()
        needle = f" {(tagSeqi+1):7}  {(tagSeqi+3):7}  {(tagSeqi+2):7}"
        if verbose >= 2:
            print()
            print (pfo)
        if needle not in pfo or peerMacL not in pfo:
            self.fail (f"did not find proper RX seq_ID (expected rx:2)")
        os.system (f"ssh {peerHost} 'cat /mnt/mac/tests/greet > /dev/noc_debug'")
        time.sleep (0.1 + sleepSec)
        pf = open (f"{procpath}/tags", "r")
        pfo = pf.read()
        pf.close()
        needle = f" {(tagSeqi+2):7}  {(tagSeqi+3):7}  {(tagSeqi+2):7}"
        if verbose >= 2:
            print()
            print (pfo)
        if needle not in pfo or peerMacL not in pfo:
            self.fail (f"did not find proper RX seq_ID (expected rx:3)")

    #@unittest.skip ("<comment>")
    def test4_tx2_seq (self):
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"cat /dev/null > /dev/noc_debug")
        os.system (f"ssh {peerHost} 'cat /dev/null > /dev/noc_debug'")
        os.system (f"cat /dev/null > /dev/noc_debug")
        time.sleep (0.1)
        os.system (f"ssh {peerHost} 'cat /mnt/mac/tests/4000 > /dev/noc_debug'")
        os.system (f"ssh {peerHost} 'echo -n expect-this-to-be-dropped > /dev/noc_debug'")
        time.sleep (0.1)
        os.system (f"ssh {peerHost} 'cat /dev/null > /dev/noc_debug'")
        os.system (f"cat /dev/null > /dev/noc_debug")


#@unittest.skip ("<comment>")
class Test1_Proc (unittest.TestCase):

    def test1_proc_stats (self):
        if verbose >= 2:
            print()
            pf = open (f"{modpath}/stats", "r")
            print (pf.read())
            pf.close()
        else:
            os.system (f"cat {modpath}/stats > /dev/null")

    #@unittest.skip ("<comment>")
    def test2_ttpoe_tags (self):
        if verbose >= 2:
            print()
            pf = open (f"{procpath}/tags", "r")
            print (pf.read())
            pf.close()
        else:
            os.system (f"cat {procpath}/tags > /dev/null")

    #@unittest.skip ("<comment>")
    def test3_debug__500 (self):
        if options.no_load:
            self.skipTest (f"requires module reload")
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"ssh {peerHost} 'cat /dev/null > /dev/noc_debug'")
        time.sleep (0.1 + sleepSec)
        os.system (f"cat /mnt/mac/tests/500 > /dev/noc_debug")
        time.sleep (0.1 + sleepSec)
        if verbose >= 2:
            x = os.system (f"ssh {peerHost} 'diff /dev/noc_debug /mnt/mac/tests/500'")
        else:
            x = os.system (f"ssh {peerHost}"
                           f" 'diff /dev/noc_debug /mnt/mac/tests/500 > /dev/null'")
        if x != 0:
            self.fail (f"received file did not match sent file '500'")

    #@unittest.skip ("<comment>")
    def test4_debug_1000 (self):
        if options.no_load:
            self.skipTest ("requires module reload")
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"ssh {peerHost} 'cat /dev/null > /dev/noc_debug'")
        time.sleep (0.1 + sleepSec)
        os.system (f"cat /mnt/mac/tests/1000 > /dev/noc_debug")
        time.sleep (0.1 + sleepSec)
        if verbose >= 2:
            x = os.system (f"ssh {peerHost} 'diff /dev/noc_debug /mnt/mac/tests/1000'")
        else:
            x = os.system (f"ssh {peerHost}"
                           f" 'diff /dev/noc_debug /mnt/mac/tests/1000 > /dev/null'")
        if x != 0:
            self.fail (f"received file did not match sent file '1000'")

    #@unittest.skip ("<comment>")
    def test5_debug_2000 (self):
        if options.no_load:
            self.skipTest (f"requires module reload")
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"ssh {peerHost} 'cat /dev/null > /dev/noc_debug'")
        time.sleep (0.1 + sleepSec)
        os.system (f"cat /mnt/mac/tests/2000 > /dev/noc_debug")
        time.sleep (0.1 + sleepSec)
        if verbose >= 2:
            x = os.system (f"ssh {peerHost} 'diff /dev/noc_debug /mnt/mac/tests/2000'")
        else:
            x = os.system (f"ssh {peerHost}"
                           f" 'diff /dev/noc_debug /mnt/mac/tests/2000 > /dev/null'")
        if x != 0:
            self.fail (f"received file did not match sent file '2000'")

    #@unittest.skip ("<comment>")
    def test6_debug_3000 (self):
        if options.no_load:
            self.skipTest (f"requires module reload")
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"ssh {peerHost} 'cat /dev/null > /dev/noc_debug'")
        time.sleep (0.1 + sleepSec)
        os.system (f"cat /mnt/mac/tests/3000 > /dev/noc_debug")
        time.sleep (0.1 + sleepSec)
        if verbose >= 2:
            x = os.system (f"ssh {peerHost} 'diff /dev/noc_debug /mnt/mac/tests/3000'")
        else:
            x = os.system (f"ssh {peerHost}"
                           f" 'diff /dev/noc_debug /mnt/mac/tests/3000 > /dev/null'")
        if x != 0:
            self.fail (f"received file did not match sent file '3000'")

    #@unittest.skip ("<comment>")
    def test7_debug_4000 (self):
        if options.no_load:
            self.skipTest (f"requires module reload")
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"ssh {peerHost} 'cat /dev/null > /dev/noc_debug'")
        time.sleep (0.1 + sleepSec)
        os.system (f"cat /mnt/mac/tests/4000 > /dev/noc_debug")
        time.sleep (1.1 + sleepSec)
        if verbose >= 2:
            x = os.system (f"ssh {peerHost} 'diff /dev/noc_debug /mnt/mac/tests/4000'")
        else:
            x = os.system (f"ssh {peerHost}"
                           f" 'diff /dev/noc_debug /mnt/mac/tests/4000 > /dev/null'")
        if x != 0:
            self.fail (f"received file did not match sent file '4000'")


#@unittest.skip ("<comment>")
class Test2_Packet (unittest.TestCase):

    def test1_get_open (self):
        if options.no_packet:
            self.skipTest (f"no packet tests")
        if not peerHost:
            self.skipTest (f"--no-remote specified")
        if not peerTgen:
            self.skipTest (f"no trafgen on peer")

        os.system (f"ssh {peerHost}"
                   f" 'cd /tmp; sudo trafgen -p -o {peerDev} "
                   f" -i /mnt/mac/tests/ttp_common.cfg -n 1"
                   f" -D DST_MAC=\"{selfMac}\""
                   f" -D SRC_MAC=\"{macUpper}:{peerMacL}\""
                   f" -D SVTR=5"
                   f" -D TOTLN=\"c16(46)\""
                   f" -D SRC_NODE=\"0,0,x{selfTgt}\""
                   f" -D DST_NODE=\"0,0,x{peerTgt}\""
                   f" -D NOCLN=\"c16(26)\""
                   f" -D CODE=0"
                   f" -D VCID=\"c8({connVCI})\""
                   f" -D TXID=\"c32(2)\" "
                   f" -D RXID=\"c32(1)\" "
                   f" -D PAYLOAD=\\\""
                   f"hello-tesla-OPEN"
                   f"\\\" > /dev/null'")
        time.sleep (0.1 + sleepSec)
        pf = open (f"{procpath}/tags", "r")
        pfo = pf.read()
        pf.close()
        if verbose >= 2:
            print()
            print (pfo)
        if "OP" not in pfo or peerMacL not in pfo:
            self.fail ("did not find proper tag")

    #@unittest.skip ("<comment>")
    def test2_snd_open (self):
        if options.no_packet:
            self.skipTest (f"no packet tests")
        if not peerHost:
            self.skipTest (f"--no-remote specified")
        if not selfTgen:
            self.skipTest (f"no trafgen on self")

        os.system (f"cd /tmp; sudo trafgen -p -o {selfDev}"
                   f" -i /mnt/mac/tests/ttp_common.cfg -n 1"
                   f" -D DST_MAC=\"{macUpper}:{peerMacL}\""
                   f" -D SRC_MAC=\"{selfMac}\""
                   f" -D SVTR=5"
                   f" -D TOTLN=\"c16(46)\""
                   f" -D SRC_NODE=\"0,0,x{selfTgt}\""
                   f" -D DST_NODE=\"0,0,x{peerTgt}\""
                   f" -D NOCLN=\"c16(26)\""
                   f" -D CODE=0"
                   f" -D VCID=\"c8({connVCI})\""
                   f" -D TXID=\"c32(2)\" "
                   f" -D RXID=\"c32(1)\" "
                   f" -D PAYLOAD=\\\""
                   f"hello-tesla-OPEN"
                   f"\\\" > /dev/null")
        time.sleep (0.1 + sleepSec)
        pf = open (f"{procpath}/tags", "r")
        pfo = pf.read()
        pf.close()
        if verbose >= 2:
            print()
            print (pfo)
        if "OP" not in pfo or peerMacL not in pfo:
            self.fail (f"did not find proper tag")

    #@unittest.skip ("<comment>")
    def test3_get_pyld (self):
        if options.no_packet:
            self.skipTest (f"no packet tests")
        if not peerHost:
            self.skipTest (f"--no-remote specified")
        if not peerTgen:
            self.skipTest (f"no trafgen on peer")

        os.system
        (f"ssh {peerHost}"
         f" 'cd /tmp; sudo trafgen -p -o {peerDev}"
         f" -i /mnt/mac/tests/ttp_common.cfg -n 5 -t 100ms"
         f" -D DST_MAC=\"{selfMac}\""
         f" -D SRC_MAC=\"{macUpper}:{peerMacL}\""
         f" -D SVTR=5"
         f" -D TOTLN=\"c16(690)\""
         f" -D SRC_NODE=\"0,0,x{selfTgt}\""
         f" -D DST_NODE=\"0,0,x{peerTgt}\""
         f" -D NOCLN=\"c16(670)\""
         f" -D CODE=6"
         f" -D VCID=\"c8({connVCI})\""
         f" -D TXID=\"c32(2)\" "
         f" -D RXID=\"c32(1)\" "
         f" -D PAYLOAD=\\\""
         f"Wikipedia\\ is\\ an\\ online\\ open-content\\ collaborative\\ encyclopedia,"
         f"\\ that\\ is,\\ a\\ voluntary\\ association\\ of\\ individuals\\ and\\ groups"
         f"\\ working\\ to\\ develop\\ a\\ common\\ resource\\ of\\ human\\ knowledge."
         f"\\ The\\ structure\\ of\\ the\\ project\\ allows\\ anyone\\ with\\ Internet"
         f"\\ connection\\ to\\ alter\\ its\\ content.\\ Please\\ be\\ advised\\ that"
         f"\\ nothing\\ found\\ here\\ has\\ necessarily\\ been\\ reviewed\\ by\\ people"
         f"\\ with\\ the\\ expertise\\ required\\ to\\ provide\\ you\\ with\\ complete,"
         f"\\ accurate\\ or\\ reliable\\ information.\\ That\\ is\\ not\\ to\\ say\\ that"
         f"\\ you\\ will\\ not\\ find\\ valuable\\ and\\ accurate\\ information\\ in"
         f"\\ Wikipedia,\\ much\\ of\\ the\\ time\\ you\\ will.\\ However,\\ Wikipedia"
         f"\\ cannot\\ guarantee\\ the\\ validity\\ of\\ the\\ information\\ found\\ here"
         f"\\\" > /dev/null'")
        time.sleep (0.1 + sleepSec)
        pf = open (f"{procpath}/tags", "r")
        pfo = pf.read()
        pf.close()
        if verbose >= 2:
            print()
            print (pfo)
        if "OP" not in pfo or peerMacL not in pfo:
            self.fail (f"did not find proper tag")

    #@unittest.skip ("<comment>")
    def test4_snd_pyld (self):
        if options.no_packet:
            self.skipTest (f"no packet tests")
        if not peerHost:
            self.skipTest (f"--no-remote specified")
        if not selfTgen:
            self.skipTest (f"no trafgen on self")

        os.system
        (f"cd /tmp; sudo trafgen -p -o {selfDev}"
         f" -i /mnt/mac/tests/ttp_common.cfg -n 5 -t 100ms"
         f" -D DST_MAC=\"{macUpper}:{peerMacL}\""
         f" -D SRC_MAC=\"{selfMac}\""
         f" -D SVTR=5"
         f" -D TOTLN=\"c16(690)\""
         f" -D SRC_NODE=\"0,0,x{selfTgt}\""
         f" -D DST_NODE=\"0,0,x{peerTgt}\""
         f" -D NOCLN=\"c16(670)\""
         f" -D CODE=6"
         f" -D VCID=\"c8({connVCI})\""
         f" -D TXID=\"c32(2)\" "
         f" -D RXID=\"c32(1)\" "
         f" -D PAYLOAD=\\\""
         f"Wikipedia\\ is\\ an\\ online\\ open-content\\ collaborative\\ encyclopedia,"
         f"\\ that\\ is,\\ a\\ voluntary\\ association\\ of\\ individuals\\ and\\ groups"
         f"\\ working\\ to\\ develop\\ a\\ common\\ resource\\ of\\ human\\ knowledge."
         f"\\ The\\ structure\\ of\\ the\\ project\\ allows\\ anyone\\ with\\ Internet"
         f"\\ connection\\ to\\ alter\\ its\\ content.\\ Please\\ be\\ advised\\ that"
         f"\\ nothing\\ found\\ here\\ has\\ necessarily\\ been\\ reviewed\\ by\\ people"
         f"\\ with\\ the\\ expertise\\ required\\ to\\ provide\\ you\\ with\\ complete,"
         f"\\ accurate\\ or\\ reliable\\ information.\\ That\\ is\\ not\\ to\\ say\\ that"
         f"\\ you\\ will\\ not\\ find\\ valuable\\ and\\ accurate\\ information\\ in"
         f"\\ Wikipedia,\\ much\\ of\\ the\\ time\\ you\\ will.\\ However,\\ Wikipedia"
         f"\\ cannot\\ guarantee\\ the\\ validity\\ of\\ the\\ information\\ found\\ here"
         f"\\\" > /dev/null")
        time.sleep (0.1 + sleepSec)
        pf = open (f"{procpath}/tags", "r")
        pfo = pf.read()
        pf.close()
        if verbose >= 2:
            print()
            print (pfo)
        if "OP" not in pfo or peerMacL not in pfo:
            self.fail (f"did not find proper tag")

    #@unittest.skip ("<comment>")
    def test5_get_clos (self):
        if options.ipv4:
            self.skipTest (f"--ipv4 specified")
        if options.no_packet:
            self.skipTest (f"--no-packet specified")
        if options.use_gw:
            self.skipTest (f"--use-gw specified")
        if options.drop_pct:
            self.skipTest (f"--drop-pct specified")
        if options.no_load:
            self.skipTest (f"requires module reload")
        if not peerHost:
            self.skipTest (f"--no-remote specified")
        if not peerTgen:
            self.skipTest (f"no trafgen on peer")

        os.system (f"ssh {peerHost}"
                   f" 'cd /tmp; sudo trafgen -p -o {peerDev}"
                   f" -i /mnt/mac/tests/ttp_common.cfg -n 1"
                   f" -D DST_MAC=\"{selfMac}\""
                   f" -D SRC_MAC=\"{macUpper}:{peerMacL}\""
                   f" -D SVTR=5"
                   f" -D TOTLN=\"c16(46)\""
                   f" -D SRC_NODE=\"0,0,x{peerTgt}\""
                   f" -D DST_NODE=\"0,0,x{selfTgt}\""
                   f" -D NOCLN=\"c16(26)\""
                   f" -D CODE=3"
                   f" -D VCID=\"c8({connVCI})\""
                   f" -D TXID=\"c32(2)\" "
                   f" -D RXID=\"c32(1)\" "
                   f" -D PAYLOAD=\\\""
                   f"hello-tesla-CLOSE"
                   f"\\\" > /dev/null'")
        time.sleep (0.1 + sleepSec)
        pf = open (f"{procpath}/tags", "r")
        pfo = pf.read()
        pf.close()
        if verbose >= 2:
            print()
            print (pfo)
        if "OP" in pfo and peerMacL in pfo:
            self.fail (f"found unexpected tag")

    #@unittest.skip ("<comment>")
    def test6_snd_clos (self):
        if options.ipv4:
            self.skipTest (f"--ipv4 specified")
        if options.no_packet:
            self.skipTest (f"--no-packet specified")
        if options.use_gw:
            self.skipTest (f"--use-gw specified")
        if options.drop_pct:
            self.skipTest (f"--drop-pct specified")
        if options.no_load:
            self.skipTest (f"requires module reload")
        if not peerHost:
            self.skipTest (f"--no-remote specified")
        if not selfTgen:
            self.skipTest (f"no trafgen on self")

        os.system (f"cd /tmp; sudo trafgen -p -o {selfDev}"
                   f" -i /mnt/mac/tests/ttp_common.cfg -n 1"
                   f" -D DST_MAC=\"{macUpper}:{peerMacL}\""
                   f" -D SRC_MAC=\"{selfMac}\""
                   f" -D SVTR=5"
                   f" -D TOTLN=\"c16(46)\""
                   f" -D SRC_NODE=\"0,0,x{selfTgt}\""
                   f" -D DST_NODE=\"0,0,x{peerTgt}\""
                   f" -D NOCLN=\"c16(26)\""
                   f" -D CODE=3"
                   f" -D VCID=\"c8({connVCI})\""
                   f" -D TXID=\"c32(2)\" "
                   f" -D RXID=\"c32(1)\" "
                   f" -D PAYLOAD=\\\""
                   f"hello-tesla-CLOSE"
                   f"\\\" > /dev/null")
        time.sleep (0.1 + sleepSec)
        pf = open (f"{procpath}/tags", "r")
        pfo = pf.read()
        pf.close()
        if verbose >= 2:
            print()
            print (pfo)
        if "OP" in pfo and peerMacL in pfo:
            self.fail (f"found unexpected tag")


#@unittest.skip ("<comment>")
class Test3_Noc_db (unittest.TestCase):

    def test1_show_tag (self):
        if not peerHost:
            self.skipTest (f"--no-remote specified")
        if verbose >= 2:
            print()
            os.system (f"cat {procpath}/tags")
            print()
            os.system (f"ssh {peerHost} 'cat {procpath}/tags'")

    #@unittest.skip ("<comment>")
    def test2_show_dbg (self):
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"cat /dev/null > /dev/noc_debug")
        os.system (f"cat /mnt/mac/tests/greet > /dev/noc_debug")
        os.system (f"ssh {peerHost} 'cat /dev/null > /dev/noc_debug'")
        os.system (f"ssh {peerHost} 'cat /mnt/mac/tests/greet > /dev/noc_debug'")
        if verbose >= 2:
            print()
            os.system (f"cat /dev/noc_debug")
            print()
            os.system (f"ssh {peerHost} 'cat /dev/noc_debug'")


#@unittest.skip ("<comment>")
class Test4_Traffic (unittest.TestCase):

    #@unittest.skip ("<comment>")
    def test1_traffic (self):
        if options.no_traffic:
            self.skipTest (f"no traffic")
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"ssh {peerHost} 'cat /dev/null > /dev/noc_debug'")
        os.system (f"cat /dev/null")
        os.system (f"cat /mnt/mac/tests/500 > /dev/noc_debug")

    def test2_traffic (self):
        if options.no_traffic:
            self.skipTest (f"no traffic")
        if options.traffic:
            ra = int(options.traffic)
            if ra < 0 or ra > 10:
                ra = 10
        else:
            ra = 10
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"ssh {peerHost} 'cat /dev/null > /dev/noc_debug'")
        for rep in range (1, ra):
            os.system (f"cat /dev/null > /dev/null")
            os.system (f"cat /mnt/mac/tests/1000 > /dev/noc_debug")

    #@unittest.skip ("<comment>")
    def test3_traffic (self):
        if options.no_traffic:
            self.skipTest (f"no traffic")
        if options.traffic:
            self.skipTest (f"no big traffic")
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"ssh {peerHost} 'cat /dev/null > /dev/noc_debug'")
        for rep in range (1, 100):
            os.system (f"cat /dev/null > /dev/null")
            os.system (f"cat /mnt/mac/tests/2000 > /dev/noc_debug")

    def test4_traffic (self):
        if options.no_traffic:
            self.skipTest (f"no traffic")
        if options.traffic:
            self.skipTest (f"no big traffic")
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"ssh {peerHost} 'cat /dev/null > /dev/noc_debug'")
        for rep in range (1, 20):
            os.system (f"cat /dev/null > /dev/null")
            os.system (f"cat /mnt/mac/tests/3000 > /dev/noc_debug")

    def test5_traffic (self):
        if options.no_traffic:
            self.skipTest (f"no traffic")
        if options.traffic:
            self.skipTest (f"no big traffic")
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"ssh {peerHost} 'cat /dev/null > /dev/noc_debug'")
        for rep in range (1, 100): # crashes when using 190
            os.system (f"cat /dev/null > /dev/null")
            os.system (f"cat /mnt/mac/tests/4000 > /dev/noc_debug")

#@unittest.skip ("<comment>")
class Test5_Cleanup (unittest.TestCase):

    def test1_cleanup (self):
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"ssh {peerHost} 'cat {procpath}/tags' > /tmp/peer_tags")
        time.sleep (0.1 + sleepSec)
        pf = open ("/tmp/peer_tags", "r")
        pfo = pf.read()
        pf.close()
        if verbose >= 2:
            print()
            print (pfo)
        if "OP" in pfo and peerMacL in pfo:
            self.fail (f"peer: found unexpected tag")

    #@unittest.skip ("<comment>")
    def test2_cleanup (self):
        time.sleep (0.1 + sleepSec)
        pf = open (f"{modpath}/stats", "r")
        pfo = pf.read()
        pf.close()
        if verbose >= 2:
            print()
            print (pfo)
        if "skb_ct: 0" not in pfo:
            self.fail (f"local skb_ct expected 0")

    def test3_cleanup (self):
        time.sleep (0.1 + sleepSec)
        if not peerHost:
            self.skipTest (f"--no-remote specified")

        os.system (f"ssh {peerHost} 'cat {modpath}/stats' > /tmp/peer_stats")
        pf = open (f"/tmp/peer_stats", "r")
        pfo = pf.read()
        pf.close()
        if verbose >= 2:
            print()
            print (pfo)
        if "skb_ct: 0" not in pfo:
            self.fail (f"peer: skb_ct expected 0")


if __name__ == '__main__':
    parser = argparse.ArgumentParser (add_help=False)
    parser.add_argument ('--self-dev')                         # [--self-dev=<dev>]
    parser.add_argument ('--peer-dev')                         # [--peer-dev=<dev>]
    parser.add_argument ('--vci')                              # [--vci=<vc>]
    parser.add_argument ('--use-gw',     action='store_true')  # [--use-gw]
    parser.add_argument ('--ipv4',       action='store_true')  # [--ipv4]
    parser.add_argument ('--prefix')                           # [--prefix=<A.B.C.D/L>]
    parser.add_argument ('--self-prefix')                      # [--prefix=<A.B.C.D/L>]
    parser.add_argument ('--peer-prefix')                      # [--prefix=<A.B.C.D/L>]
    parser.add_argument ('--self-nhmac')                       # [--nhmac=<a:b:c:d:e:f>]
    parser.add_argument ('--peer-nhmac')                       # [--nhmac=<a:b:c:d:e:f>]
    parser.add_argument ('--target')                           # [--target=<NN>]
    parser.add_argument ('--drop-pct')                         # [--drop-pct=<%val>]
    parser.add_argument ('--sleep')                            # [--sleep=<sec>]
    parser.add_argument ('--no-unload',  action='store_true')  # [--no-unload]
    parser.add_argument ('--no-load',    action='store_true')  # [--no-load]
    parser.add_argument ('--no-traffic', action='store_true')  # [--no-traffic]
    parser.add_argument ('--traffic')                          # [--traffic=<NN>]
    parser.add_argument ('--no-packet',  action='store_true')  # [--no-packet]
    parser.add_argument ('--no-remote',  action='store_true')  # [--no-remote]

    options, args = parser.parse_known_args()
    sys.argv[1:] = args

    unittest.main()
