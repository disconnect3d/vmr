# vmr - a better vmware cli (vmrun)
vmware-cli is a minimal wrapper for vmware's vmrun command.

The motivation behind creating it was that I used to create aliases around `vmrun` commands as I think they are bad...

## Install

Clone the repo and run `python3 setup.py install`.

**NOTE that it requires custom pydhcpdparser installed - https://github.com/disconnect3d/pydhcpdparser - since the upstream hasn't made a release with Py3 support yet**

## Usage

To use vmr two environment variables must be set:
* `VMWARE_VMS_DIR` - it has to point to the directory that contains virtual machine's directories (the ones ending with `.vmwarevm`)
* `VMWARE_DHCPD_PATH` - it needs to point to vmware's dhcpd.conf file; it has a proper default for OS X

You can also set `VMWARE_VMRUN_PATH` but it defaults to `vmrun`, so just have it in your `$PATH`.

```
vmr

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
```

TLDR:
* you can list VMs that are on/off with their mac addresses and ips (if you set them as static)
* you can do all the basic stuff you could do with vmrun
* you ca generate dhpcd.conf and .ssh/config entries to speed up setting a static ip for your VMs

## Some screens

Note that:
* some sensitive(?) data has been censored
* there are some SYNTAX ERRORS comming from parsing dhcpd.conf via pydhcpdparser - I don't really care about those; feel free to send a PR to improve it if it bothers you

![vmr list screenshot](/github/vmr-list.png)
![vmr gennetcfg screenshot](/github/vmr-gennetcfg.png)
