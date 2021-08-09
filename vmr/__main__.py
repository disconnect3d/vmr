"""vmr

Usage:
  vmr list
  vmr start [--gui] <vm>
  vmr stop [--hard] <vm>
  vmr reset [--hard] <vm>
  vmr suspend [--hard] <vm>
  vmr pause <vm>
  vmr unpause <vm>
  vmr gennetcfg <vm>
  vmr -h | --help

Options:
  -h --help     Show this screen.
"""
import ast
import os
import subprocess
import sys

from docopt import docopt
from pydhcpdparser import parser

VMWARE_VMS_DIR = os.getenv('VMWARE_VMS_DIR', '')
VMWARE_VMRUN_PATH = os.getenv('VMWARE_VMRUN_PATH', 'vmrun')
VMWARE_DHCPD_PATH = os.getenv('VMWARE_DHCPD_PATH', '/Library/Preferences/VMware Fusion/vmnet8/dhcpd.conf')

SSH_CONFIG_PATH = os.path.join(os.getenv('HOME'), '.ssh/config')

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


def get_vmx_path(dirname):
    return os.path.join(
        dirname,
        next(j for j in os.listdir(os.path.join(VMWARE_VMS_DIR, dirname)) if j.endswith('vmx'))
    )


all_vms = {
    i.rstrip('.vmwarevm'): get_vmx_path(i) for i in os.listdir(VMWARE_VMS_DIR) if '.vmwarevm' in i
}
max_len = max(max(map(len, all_vms.keys())), 6)


def main():
    args = docopt(__doc__)

    softhard = 'hard' if args['--hard'] else 'soft'

    def get_vmx():
        vmx = all_vms.get(args['<vm>'])

        if not vmx:
            print(f"{c.FAIL}Can't find vm '{args['<vm>']}' in VMWARE_VMS_DIR=\"{VMWARE_VMS_DIR}\" {c.ENDC}")
            print(f'all_vms={all_vms}')
            sys.exit(-1)

        return os.path.join(VMWARE_VMS_DIR, vmx)

    out = None

    if args['list']:
        list_vms()

    elif args['start']:
        out = vmrun('start', get_vmx(), 'gui' if args['--gui'] else 'nogui')

    elif args['stop']:
        out = vmrun('stop', get_vmx(), softhard)

    elif args['reset']:
        out = vmrun('pause', get_vmx(), softhard)

    elif args['suspend']:
        out = vmrun('suspend', get_vmx(), softhard)

    elif args['pause']:
        out = vmrun('pause', get_vmx())

    elif args['unpause']:
        out = vmrun('unpause', get_vmx())

    elif args['gennetcfg']:
        gen_network_cfgs(args['<vm>'])
        print(f'You can set static ip for your vms in "{VMWARE_DHCPD_PATH}"')

    if out:
        print(out)


def list_vms():
    running_vms = get_running_vms_vmx()
    net_cfg = get_vms_netcfg()

    print(f'{c.HEADER}Listing VMs from VMWARE_VMS_DIR="{VMWARE_VMS_DIR}":{c.ENDC}')
    for vm, path in all_vms.items():
        status = vm in running_vms
        color = c.OKGREEN if status else c.FAIL

        net = net_cfg.get(vm, 'unknown/dhcp')
        print(f'{color}{vm:{max_len}s} : {path}{c.ENDC}')
        print(f'{" "*max_len}   mac: {net["mac"]}')
        print(f'{" "*max_len}    ip: {net["ip"]}')
        print()


def gen_network_cfgs(vm):
    net_cfg = get_vms_netcfg()[vm]

    if net_cfg['ip'] == '<dhcp>':
        print(f'{c.OKGREEN}Generating "{VMWARE_DHCPD_PATH}" config{c.ENDC}')
        print(f'{c.WARNING}Please put the lines below in the ^ file{c.ENDC}')
        print()
        print(f'host {vm} {{')
        print(f'    hardware ethernet {net_cfg["mac"]};')
        print(f'    fixed-address <PUT-IP-HERE>;')
        print('}')
        print()
    else:
        print(f'{c.OKGREEN}"{VMWARE_DHCPD_PATH}" entry not generated: vm has static ip.')

    print(f'{c.WARNING}Generating ~/.ssh/config entry (note: it might already be there!){c.ENDC}')
    print(f'''
Host {vm}
  HostName {net_cfg["ip"]}
  Port 22
  User dc
  IdentityFile ~/.ssh/id_rsa
''')


def get_running_vms_vmx():
    def name(path):
        return path.rsplit(os.path.sep, 2)[-2].rstrip('.vmwarevm')

    return {
        name(i): i for i in vmrun('list').splitlines()[1:]
    }


def get_vms_netcfg():
    """
    Get VMs network config as {
        'vmname':  {'mac': ..., 'ip': ...},
        ...
    }

    Parses vmware's dhcpd.conf file and VMX file for each vm.
    """
    with open(VMWARE_DHCPD_PATH) as f:
        cfg = parser.parse(f.read())

    hosts = cfg[0].get('host')

    if not hosts:
        return {}

    # Workaround for https://github.com/jay-g-mehta/pydhcpdparser/issues/4
    for h in list(hosts.keys()):
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
            # netcfg = {
            #    'hardware': {'ethernet': <MAC>},
            #    'fixed-address': <IP>,
            #    'option': {'domain-name-servers': '0.0.0.0', 'domain-name': '""', 'routers': '0.0.0.0'}
            # }
            #
            # if so, let's ignore it; otherwise warn about the entry
            if 'option' not in netcfg or 'domain-name-servers' not in netcfg['option']:
                print(
                    c.WARNING +
                    f"WARNING: the dhcpd conf has an entry of {host} with cfg {netcfg} "
                    "and we couldn't find a corresponding network interface in vms vmx files" +
                    c.ENDC
                )
            continue

        # The default value should probably not happen?
        vms_net_info[vm]['ip'] = netcfg.get('fixed-address', '<missing-fixed-address-key-in-dhcpd>')

    return vms_net_info


def vmrun(*args):
    return subprocess.check_output([VMWARE_VMRUN_PATH, *args], stderr=subprocess.STDOUT).decode('ascii')


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
