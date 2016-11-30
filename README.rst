.. highlight:: rest

cziso
===============
.. contents::

Introduction
---------------
Cziso is a convenience tool for doing VM image conversion (e.g., an RAW image to a ZFS volume) via Clonezilla_.  

.. _Clonezilla: http://clonezilla.org

Example
---------------

Suppose you have a RAW VM image called **myimage.img** and you want to convert it to a ZFS volume.

First you generate a special Clonezilla restore ISO image using the **create** command. ::

    # cziso create file:///path/to/myimage.img
  
After this command completes, a restore ISO image called **clonezilla-live-myimage.iso** will be generated.  You can then use that ISO to restore it to a new ZFS volume called **myvol**. ::

    # cziso restore clonezilla-live-myimage.iso zfs://mynas/mypool/myvol
  
After this command completes, **myvol** will now be ready for you to use.  To test the image, ensure you have X forwarding enabled and run the following command: ::
 
    # cziso test zfs://mynas/mypool/myvol
  
This will launch a temporary VM instance using the new image via libvirt and use vncviewer command to launch a VNC window to your local machine.  When you close the window, the VM will be destroyed so this should only be used for temporary testing of the image.  


