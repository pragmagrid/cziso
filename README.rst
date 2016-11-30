.. highlight:: rest

cziso
===============
.. contents::

Introduction
---------------
Cziso is a convenience tool for doing VM image conversion (e.g., a RAW image to a ZFS volume) via Clonezilla_.  

.. _Clonezilla: http://clonezilla.org

Example
---------------

Suppose you have a RAW VM image called **myimage.img** and you want to convert it to a ZFS volume.

First you generate a special Clonezilla restore ISO image using the **create** command. ::

    # cziso create file:///path/to/myimage.img
  
This will launch a customized Clonezilla Live VM instance to generate a restore ISO image called **clonezilla-live-myimage.iso**.  You can then use that ISO to restore it to a new ZFS volume called **myvol**. ::

    # cziso restore clonezilla-live-myimage.iso zfs://mynas/mypool/myvol
  
After this command completes, **myvol** will now be ready for you to use.  To test the image, ensure you have X forwarding enabled and run the following command: ::
 
    # cziso test zfs://mynas/mypool/myvol
  
This will launch a temporary VM instance using the new image via libvirt and use vncviewer command to launch a VNC window to your local machine.  When you close the window, the VM will be destroyed so this should only be used for temporary testing of the image.  

Installation
---------------
To install cziso, do a git clone ::

    # git clone https://github.com/pragmagrid/cziso
    # cd cziso
    
Next, edit the config file in etc/cziso.cfg and specify a location for **temp_directory** and set the **private_iface** field.  The latter is needed because we are using a Clonezilla Live VM to generate the restore ISO and so mount a temporary directory from the physical host to the VM to output the restore ISO.  Because the libvirt version we typically use does not support direct directory mounts from the physical host, we mount the directory using NFS and so need to configure a private interface on the Clonezilla Live VM instance.  The value of the **private_iface** field should be the private interface of your physical host (e.g., eth0 or eth1).
