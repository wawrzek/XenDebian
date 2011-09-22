#!/usr/bin/env python
# -*- coding: UTF-8 -*-


import sys, time, getopt
import xmlrpclib 
import provision2 as provision

#
v = 'Value'

#Disk/Memory size definition
GB = 2**30
MB = 2**20


def get_pif(PIF, HOST, NET):
    """Find out PIF (Physical network InterFace) attached to the selected server"""
    
    # Choose the PIF with the alphabetically lowest device,
    # just because the example code does.
    #

    # Choose  PIFs attached to the host where VM should be install
    pifs = PIF.get_all_records(token)
    pifs_host = HOST.get_PIFs(token,host_ref)[v]
    
    pifs_attached = [pifs[v][id] for id in pifs_host if pifs[v][id]['currently_attached'] ]
    lowest = min([p['device'] for p in pifs_attached])
    pif = [p for p in pifs_attached if p['device'] == lowest][0]
    
    network_ref = pif['network']
    print ("  PIF is connected to: %s\n" %NET.get_name_label(token,network_ref)[v])

    return network_ref

    #print "Choosing PIF with device: ", pif

def set_vm(VM):
    """Set VM:
    - find requested template;
    - set VM name and description;
    - set kernel commands (non-interactive).
    """
    
    for vm, record in VM.get_all_records(token)[v].items():
        if record["name_label"] == distro:
            template = vm
            break
    print "  Selected template: %s\n" %(VM.get_name_label(token, template)[v])
    
    print ("Installing new VM from the template")
    new_vm = VM.clone(token, template, vmname)[v]
    
    print ("  New VM name is %s\n"% vmname)
    VM.set_name_description(token, new_vm, description)

    print ("Adding noninteractive to the kernel commandline\n")
    VM.set_PV_args(token, new_vm, "noninteractive")

    return new_vm
    
    
def set_cpu(VM):
    """Set CPU:
    - set max number;
    - set start number.
    """
    
    VM.set_VCPUs_max(token, vm, str(cpu))
    VM.set_VCPUs_at_startup(token, vm, str(cpu))
   
   
def set_mem(VM):
    """Set VM (static) memory"""
    
    mem_str = str(int(mem*GB))
    # It might be better to set dynamic values as well
    VM.set_memory_static_min(token, vm, mem_str)
    VM.set_memory_static_max(token, vm, mem_str)

def set_network(VIF):
    """Set VIF (Virtual network InterFace) based on
    - vm;
    - network_ref. (PIF)
    """
    
    print "Creating VIF\n"
    vif = { 'device': '0',
            'network': network_ref,
            'VM': vm,
            'MAC': "",
            'MTU': "1500",
            "qos_algorithm_type": "",
            "qos_algorithm_params": {},
            "other_config": {} }
    VIF.create(token, vif)


def get_local_disks(HOST, PBD, SR):
    """ Obtain info about all local disk attached to the selected server"""
    
    pbds = PBD.get_all_records(token)
    pbds_host = HOST.get_PBDs(token,host_ref)[v]
    
    # Choose  PBDs attached to the host where VM should be install
    sr_ref = [ PBD.get_record(token,i)[v]['SR'] for i in pbds_host ]
    sr = [ SR.get_record(token,d)[v] for d in sr_ref ]
    
    return [ s for s in sr if s['type'] in ['ext', 'lvm' ] and not s['shared'] ]


def set_disks(HOST, VM, PBD, SR, VBD, VDI):
    """ Prepare disks for VM:
    - HDD for main OS,
    - CD with XenTools
    """
    
    print ("Choosing an SR to initiate the VM's disks")

    # Find local disk - in future give a choice to find maybe share storage as well
    for sr in get_local_disks(HOST, PBD, SR):
        print ("  Found a local disk called '%s'" % sr['name_label'])
        print ("   Physical size: %s" % (sr['physical_size']))
        percentage = float(sr['physical_utilisation'])/(float(sr['physical_size']))*100
        print ("   Utilization: %5.2f %%" % (percentage))
        local_sr = sr

    print ("  Chosen SR: %s (uuid %s)" % (local_sr['name_label'], local_sr['uuid']))
    
    print ("Rewriting the disk provisioning XML\n")
    spec = provision.getProvisionSpec(VM, token, vm)
    local_sr_uuid = local_sr['uuid']
    spec.setSR(local_sr_uuid)

    print ("Asking server to provision storage from the template specification")
    provision.setProvisionSpec(VM, token, vm, spec)
    VM.provision(token, vm)

    print ("Setting up names for assign disks")
    names = {
        '0': 'Main disk for %s'%vmname,
        }
    for vbd_ref in VM.get_VBDs(token, vm)[v]:
        position = VBD.get_userdevice(token, vbd_ref)[v]
        vdi_ref = VBD.get_VDI(token, vbd_ref)[v]
        VDI.set_name_label(token, vdi_ref, names[position])

    print ("Creating CD-rom with XenTools\n")
    VBD.create(token, {'VM': vm,
                               'VDI': cd_ref,
                               'type': 'CD',
                               'mode': 'RO',
                               'userdevice': str(len(spec.disks)),
                               'bootable': False,
                               'empty': False,
                               'other_config': {},
                               'qos_algorithm_type': '',
                               'qos_algorithm_params': {}
                               })


def install_debian(VM):
    """Install selected version of Debian"""
    
    print ('Pointing the installation at a Debian repository \n')

    VM.remove_from_other_config(token, vm, 'install-methods')
    VM.add_to_other_config(token, vm, 'install-methods', 'http')
    VM.add_to_other_config(token, vm, 'install-repository', repo)
    VM.set_PV_args(token, vm, "auto=true "
                   " priority=critical "
                   " console-keymaps-at/keymap=us "
                   " preseed/locale=en_US "
                   " auto-install/enable=true "
                   " hostname=%s "
                   " domain=%s "
                   "%s" %(vmname, '', preseed))



###MAIN START HERE###
def main():
    
    # Define shourtcuts for all XAPI class in use
    VM = conn.VM
    HOST = conn.host
    VDI = conn.VDI
    PIF = conn.PIF
    VIF = conn.VIF
    NET = conn.network
    PBD = conn.PBD
    SR = conn.SR
    VBD = conn.VBD
    VDI = conn.VDI
    
    # These variabels are 'read only' used in various functions 
    # so I can define them global here and not bother to pass
    # to functions as argument later
    global cd_ref # Ref: CD with XS Tools
    cd_ref = VDI.get_by_name_label(token, 'xs-tools.iso')[v][0]    

    global host_ref # Ref: Host to install
    host_ref = HOST.get_by_name_label(token, hostname)[v][0]
    
    global network_ref # Ref: Network
    network_ref = get_pif(PIF, HOST, NET)

    global vm #Ref: to the new VM
    vm = set_vm(VM) # create VM

    set_cpu(VM) # set CPU
    set_mem(VM) # set memory (only static value)  
    set_network(VIF) # set network
    set_disks(HOST, VM, PBD, SR, VBD, VDI) #prepare disk and XenTools CDROM

    install_debian(VM)

    print ("Starting VM")
    VM.start(token, vm, False, True)
    print ("  VM is booting")
   

def usage():
    print """This is the tool to create a Debian based VM.
    It is controle by following options:
    -m --master= string: name of the pool master/server you want to connect to (no default);
    -u --username= string: username to connect to the pool master/server (default: root);
    -p --password= string: password used to login into  the pool master/server (no default)"
    -s --server= string: name of the server (host) you want to install your VM (no default);
    -v --vm= string: name of the new VM (default: new);
    -i --information= string: description of the new VM (default: New Debian VM);
    -d --distro= [5,6]: release number of Debian release (default: 6);
    -a --arch= [32,64]: VM architecture (default: 32);
    -c --config= [address] : address of preseed file to use - please remember not to add http:// (no default)"
    -r --repo= [address]: address of local mirror - please remember not to add http:// (default ftp.debian.org/debian)"
    -C --cpu= int: number of virtual CPU assign to vm (default 1);
    -M --memory= float: number of memory in GB (default 1.0);
    DOESN'T WORK YET:
    -D --disk= float: size of partition in GB (default 8.0);

    """
if __name__ == "__main__":
    	
    # Set DEFAULT VARIABLES
    username = 'root'
    vmname = 'new'
    description = 'New Debian VM'
    dist = '6'
    arch = '32'
    disk = 8.0
    mem = 1.0
    cpu = 1
    repo = 'http://ftp.debian.org/debian'
    
    # Get input from the command line
    try:
        opts, args = getopt.getopt(sys.argv[1:], "a:c:d:hi:m:p:r:s:u:v:C:D:M:", 
        ["arch=", "config=", "distro=", "help",  "info=", "master=", "password=", "repo=", "server=", "username=", "vm=", "cpu=", "disk=", "mem="])
    except getopt.GetoptError, err:
        # Print help information; error message and exit"
        usage()
        print str(err)
        sys.exit(2)
        
    # Set up variables based on commandline options
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-u", "--username"):
            username = a
        elif o in ("-p", "--password"):
            password= a
        elif o in ("-m", "--master"):
            url = 'http://'+a
        elif o in ("-s", "--server"):
            hostname = a
        elif o in ("-v", "--vm"):
            vmname = a
        elif o in ("-i", "--info"):
            description = a
        elif o in ("-d", "--distro"):
            dist = a
        elif o in ("-a", "--arch"):
            arch = a
        elif o in ("-c", "--configfile"):
            configfile = "http://"+a
        elif o in ("-r" "--repo"):
            repo = "http://"+a
        elif o in ("-C", "--cpu"):
            cpu = int(a)
        elif o in ("-D", "--disk"):
            disk = float(a)
        elif o in ("-M", "--memory"):
            mem = float(a)
        else:
            assert False, "unhandled option"   

    # Check if distro is supported #This can be done better, based on list from an actual box you try to connect to.
    if dist == '5' and arch == '32':
        distro = "Debian Lenny 5.0 ("+arch+"-bit)"
    elif dist == '6':
        if arch == '64':
            distro ="Debian Squeeze 6.0 ("+arch+"-bit) (experimental)"
        else:
            distro = "Debian Squeeze 6.0 ("+arch+"-bit)"
    else:
        print ("Unknown disto release")
        sys.exit(4)
        
    # Check if address to a preseed file has been provided
    try:
        preseed = (" url=%s" %  configfile)
    except NameError:
        preseed = ""
        print ("Preseed file not define. When script will finish please go to XenCenter to continue installation.")
        
    # Get password if not passed from the commandline
    try: 
        password
    except NameError:
        import getpass
        password = getpass.getpass()
        
    # First acquire a session by logging in
    conn = xmlrpclib.Server(url)
    connection = conn.session.login_with_password(username, password)
    
    #Test if session is valid
    if connection['Status'] == 'Success':
        token = connection[v]
        print ("\n Connection unique ref: %s\n" %token)
    else :
        for i in connection['ErrorDescription']:
            print i
        sys.exit(5)
        
    # With session Ref UUID start the main part
    try:
       main() # Not variables, as they are not going to be change in program
    except Exception, e:
        print str(e)
        raise
    
    # Close the session
    conn.logout(token)

