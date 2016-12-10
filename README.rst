.. highlight:: rest

cziso
===============
.. contents::

Introduction
---------------
Cziso is a convenience tool for doing VM image conversion (e.g., a RAW image to a ZFS volume) via Clonezilla_.  

.. _Clonezilla: http://clonezilla.org

Suppose you have a RAW VM image called **myimage.img** that is 50 GB in size and you want to convert it to a ZFS volume.

First you generate a special Clonezilla restore ISO image using the **create** command. ::

    # cziso create file:///path/to/myimage.img
  
This will launch a customized Clonezilla Live VM instance to generate a restore ISO image called **clonezilla-live-myimage.50G.iso**.  You can then use that ISO to restore it to a new ZFS volume called **myvol**. ::

    # cziso restore clonezilla-live-myimage.50G.iso zfs://mynas/mypool/myvol
      
After this command completes, **myvol** will now be ready for you to use.  To test the image, ensure you have X forwarding enabled and run the following command: ::
 
    # cziso test zfs://mynas/mypool/myvol
  
This will launch a temporary VM instance using the new image via libvirt and use vncviewer command to launch a VNC window to your local machine.  When you close the window, the VM will be destroyed so this should only be used for temporary testing of the image.  

Requirements
---------------
* libvirt (version 0.10.2 or later)
* tigervnc
* Python 2.6 or later

Installation
---------------
To install cziso, do a git clone ::

    # git clone https://github.com/pragmagrid/cziso
    # cd cziso
    
Next, edit the config file in etc/cziso.cfg and specify a location for **temp_directory** and set the **private_iface** field.  The latter is needed because we are using a Clonezilla Live VM to generate the restore ISO and so mount a temporary directory from the physical host to the VM to output the restore ISO.  Because the libvirt version we typically use does not support direct directory mounts from the physical host, we mount the directory using NFS and so need to configure a private interface on the Clonezilla Live VM instance.  The value of the **private_iface** field should be the private interface of your physical host (e.g., eth0 or eth1).

Getting started
---------------
To see all cziso commands run ::

    # cziso help
    
To view help information for a particular command, run ::

    # cziso <command> help
    
E.g., ::

    # cziso create help
    
Supported formats
---------------

The cziso tool supports the following image formats: ZFS vol, raw file, and qcow2 file.  

When specifying a ZFS image vol, use the format: **zfs://mynas/mypool/myvol**

When specifying a raw image file, use the format: **file:///abs/path/to/file.img** or **file:///abs/path/to/file.raw**

When specifying a qcow2 image file, use the format: **file:///abs/path/to/file.qcow2**

Increase image size
---------------

By default, the **cziso restore** command will create a new restore image using the original size of the image.  If you want to make a larger image, use the **size** option. For example, ::

    # cziso restore clonezilla-live-myimage.50G.iso zfs://mynas/mypool/myvol size=100
    
This will create a 100 GB image and use Clonezilla's advanced "-k1" option to resize the partition table in proportion to its original size. 

Upload to Google drive
---------------
The cziso tool contains a convenience command to upload image files to Google drive. To use this feature, you must do the following:

#. Install the `Google Python API Client <https://developers.google.com/drive/v3/web/quickstart/python>`_. :: 

#. Obtain `OAuth2 service account credentials <https://developers.google.com/identity/protocols/OAuth2ServiceAccount>`_. ::

Once you have your OAuth2 credentials, you can download them in JSON format (e.g., mycreds-4d8f69195c82.json) and copy them to the **/opt/cziso/etc** directory.  Then edit the **/opt/cziso/etc/cziso.cfg** file and insert the filename in the field **service_account_credentials**.  E.g., ::

    service_account_credentials = mycreds-4d8f69195c82.json

You will also need to allow your service account credentials to edit any folders you wish to upload too.  To give edit permissions on a Google drive folder, left click on the desired folder(s) via the Google drive web interface and click the **share** option.  If your project was called **myproject** and the service account name was **myservice**, then insert the email address of your service account as **myservice@myproject.iam.gserviceaccount.com** under the People box and click the **Done** button.

After this, you should be able to use the **cziso upload** command to upload, for example, a restore ISO **clonezilla-live-myimage.50G.iso** to Google drive folder **0B3cw74KWQ3fXcmd3RHBCTV9KaUU**. ::

    # cziso upload clonezilla-live-myimage.50G.iso 0B3cw74KWQ3fXcmd3RHBCTV9KaUU
    
To see more upload options, type ::
 
    # cziso upload help
    
Updating Clonezilla (for the cziso maintainer only)
---------------

The following is an advanced feature just for us cziso developers/maintainers.  This tool uses customized and regular Clonezilla Live VM ISO files that are stored in Google drive.  If there is a new version of Clonezilla Live and we want to update our ISO files, download the new Clonezilla zip file.  Then run the **cziso update** command as follows ::

     # cziso update clonezilla-live-2.5.0-9-amd64.zip upload=true 
     
This will generate to customized and regular ISO images and the **upload** option will also automatically upload them to the configured Google drive folder as updates to the existing files in Google drive.
