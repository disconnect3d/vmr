"""vmr

Usage:
  vmr list
  vmr start [--gui] <vm>
  vmr stop [--hard] <vm>
  vmr reset [--hard] <vm>
  vmr suspend [--hard] <vm>
  vmr pause <vm>
  vmr unpause <vm>
  vmr staticip
  vmr -h | --help

Options:
  -h --help     Show this screen.
"""
import subprocess
import argparse
import os
import sys
import ast

from docopt import docopt
from prettytable import PrettyTable, PLAIN_COLUMNS
from pydhcpdparser import parser
from pprint import pprint

VMWARE_VMS_DIR = os.getenv('VMWARE_VMS_DIR', '')
VMWARE_VMRUN_PATH = os.getenv('VMWARE_VMRUN_PATH', 'vmrun')
VMWARE_DHCPD_PATH = os.getenv('VMWARE_DHCPD_PATH', '/Library/Preferences/VMware Fusion/vmnet8/dhcpd.conf')

failed = False

if not os.path.exists(VMWARE_VMS_DIR):
    print("Set VMWARE_VMS_DIR to point to vmware's directory with virtual machines directories")
    print("(they end with .vmwarevm)")
    failed = True

if not VMWARE_VMRUN_PATH:
    print("Set VMWARE_VMRUN_PATH to point to vmware's vmrun tool")
    failed = True

if not os.path.exists(VMWARE_DHCPD_PATH):
    print("Set VMWARE_DHCPD_PATH to point to vmware's vmnet*/dhcpd.conf")
    failed = True

if failed:
    sys.exit(-1)

get_vmx = lambda dirname: os.path.join(dirname, next(j for j in os.listdir(os.path.join(VMWARE_VMS_DIR, dirname)) if j.endswith('vmx')))

all_vms = {
    i.rstrip('.vmwarevm'): get_vmx(i) for i in os.listdir(VMWARE_VMS_DIR) if '.vmwarevm' in i
}
max_len = max(map(len, all_vms.keys()))


def main():
    args = docopt(__doc__)

    softhard = 'hard' if args['--hard'] else 'soft'

    def get_vmx():
        vmx = all_vms.get(args['<vm>'])

        if not vmx:
            print(f"{c.FAIL}Can't find vmx for vm '{args['<vm>']}'{c.ENDC}")
            print(f'all_vms={all_vms}')
            sys.exit(-1)

        return os.path.join(VMWARE_VMS_DIR, vmx)

    out = None

    if args['list']:
        list_vms()

    elif args['start']:
        out = vmrun('start', get_vmx(), 'gui' if args['--gui'] else 'nogui')

    elif args['pause']:
        out = vmrun('pause', get_vmx(), softhard)

    elif args['unpause']:
        out = vmrun('unpause', get_vmx(), softhard)

    elif args['suspend']:
        out = vmrun('suspend', get_vmx(), softhard)

    elif args['staticip']:

        print(f'You can set static ip for your vms in "{dhcpd_path}"')

    if out:
        print(out)


def list_vms():
    running_vms = get_running_vms()
    net_cfg = get_vms_netcfg()

    print(f'VMWARE_VMS_DIR="{VMWARE_VMS_DIR}"')
    for vm, path in all_vms.items():
        status = vm in running_vms
        color = c.OKGREEN if status else c.FAIL
        
        net = net_cfg.get(vm, 'unknown/dhcp')
        print(f'{color}{vm:{max_len}s} : {path} (net: {net})')


def vmrun(*args):
    return subprocess.check_output([VMWARE_VMRUN_PATH, *args], stderr=subprocess.STDOUT)

def get_running_vms():
    name = lambda path: path.decode('ascii').rsplit(os.path.sep)[-1].rstrip('vmx')
    return {
        name(i): i for i in vmrun('list').splitlines()[1:]
    }

def get_vms_netcfg():
    """
    Get VMs network config as a dict of vmname:  {'mac': ..., 'ip': ...}

    Parses vmware's dhcpd.conf file and VMX file for each vm.
    """
    with open(VMWARE_DHCPD_PATH) as f:
        cfg = parser.parse(f.read())

    hosts = cfg[0].get('host')

    if not hosts:
        return {}

    # Workaround for https://github.com/jay-g-mehta/pydhcpdparser/issues/4
    for h in hosts:
        v = hosts.pop(h)
        hosts[h.rstrip()] = v
    
    # Read VMX files for all vms
    cfgs = {vm: read_vmx(vm) for vm in all_vms}

    vms_net_info = {}
    for vm, cfg in cfgs.items():
        for key, val in cfg.items():
            if key.startswith('ethernet') and key.endswith('generatedAddress'):
                vms_net_info[vm] = {'mac': val, 'ip': '<dhcp>'}

    for host, netcfg in hosts.items():
        try:
            mac = netcfg['hardware']['ethernet']
        except KeyError:
            continue

        try:
            vm = next(k for k, v in vms_net_info.items() if v['mac'] == mac)
        except StopIteration:
            # In this case the dhcpd.conf has an entry with mac which
            # we don't have a name for in vmx files
            # (there is no vm with corresponding network interface)
            #
            # Let's see if it is sth generic e.g. a dhcp server like:
            # host = 'vmnetX' (X = number)
            # netcfg = {'hardware': {'ethernet': <MAC>}, 'fixed-address': <IP>, 'option': {'domain-name-servers': '0.0.0.0', 'domain-name': '""', 'routers': '0.0.0.0'}}
            #
            # if so, let's ignore it; otherwise warn about the entry
            if 'option' not in netcfg or 'domain-name-servers' not in netcfg['option']:
                print(
                    c.WARNING + \
                    f"WARNING: the dhcpd conf has an entry of {host} with cfg {netcfg} "
                    "and we couldn't find a corresponding network interface in vms vmx files" + \
                    c.ENDC
                )
            continue

        # The default value should probably not happen?
        vms_net_info[vm]['ip'] = netcfg.get('fixed-address', '<missing-fixed-address-key-in-dhcpd>')

    return vms_net_info


def read_vmx(vm):
    data = {}
    with open(os.path.join(VMWARE_VMS_DIR, all_vms[vm])) as f:
        for line in f:
            key, value = line.split(' = ')
            
            # Unquote the string...
            data[key] = ast.literal_eval(value.rstrip('\n'))

    return data

class c:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


if __name__ == '__main__':
    main()
