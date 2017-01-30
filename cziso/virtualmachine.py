import cziso
import libvirt
import logging
import os
import subprocess
import time
from xml.etree import ElementTree as ET


class VM:
	"""
	Convenience class for booting Clonezilla VMs
	"""

	def __init__(self):
		self.clonezilla_vm_obj = None
		self.logger = logging.getLogger(self.__module__)
		self.virConnect_obj = None

	def attach_vnc(self):
		subprocess.call("vncviewer localhost::%s" % self.get_vnc_port(), shell=True)

	def clean(self):
		"""
		Shutdown VM if needed and and remove

		:return: Returns if successful; otherwise aborts
		"""
		self.logger.debug("Cleaning up VM instance %s" % self.get_name())
		dom0 = self.virConnect_obj.lookupByName(self.get_name())
		if dom0 is None:
			self.logger.debug("VM already destroyed")
			return True
		status = dom0.info()[0]
		if status == libvirt.VIR_DOMAIN_RUNNING:
			try:
				self.clonezilla_vm_obj.destroy()
			except Exception as e:
				self.logger.debug("Trouble shutting down VM: %s" % str(e))
				return False
		else:
			self.logger.debug("VM instance already shutdown")
		self.clonezilla_vm_obj.undefine()
		return True

	def get_name(self):
		"""
		Get the name of the VM instance

		:return: A string containing the name of the VM instance
		"""
		root = self.get_xml()
		return root.find("name").text

	def get_vnc_port(self):
		"""
		Get the VNC port assigned to VM

		:return:  A string containing the VNC port
		"""
		root = self.get_xml()
		# get the VNC port
		graphics = root.find('./devices/graphics')
		port = graphics.get('port')
		return port

	def get_xml(self):
		"""
		Get the XML from VM instance

		:return:  An ElementTree object
		"""
		# get the XML description of the VM
		vm_xml = self.clonezilla_vm_obj.XMLDesc(0)
		root = ET.fromstring(vm_xml)
		return root

	def launch(self, libvirt_xml, **kwargs):
		"""
		Launch VM with provided loop device as input image

		:param libvirt_template:  Libvirt template to use to launch VM
		:param kwargs: key/value names to fill in the template

		:return: Returns 0 on success; otherwise non-zero
		"""
		self.virConnect_obj = libvirt.open("qemu:///session")
		self.clonezilla_vm_obj = self.virConnect_obj.defineXML(libvirt_xml)
		return self.clonezilla_vm_obj.create()


class LibvirtFile:
	"""
	Convenience class for creating libvirt files for Clonezilla and test VMs
	"""
	CLONEZILLA_VM_PREFIX = "cziso"
	CONFIG_SUBDIR = "libvirt"
	TEMPLATE_FILE = "template.xml"

	def __init__(self, config_dir):
		"""
		Create LibvirtFile object using templates in config_dir/libvirt.

		:param config_dir: The config directory
		:param name:
		"""
		self.config_dir = os.path.join(config_dir, LibvirtFile.CONFIG_SUBDIR)
		self.libvirt = os.path.join(self.config_dir, LibvirtFile.TEMPLATE_FILE)
		self.logger = logging.getLogger(self.__module__)
		self.unique_id = "%s-%d" % (time.strftime('%Y%m%d'), os.getpid())
		self.name = "%s-%s" % (LibvirtFile.CLONEZILLA_VM_PREFIX, self.unique_id)

		self.disk_xmls = []
		self.disk_ids = {}
		self.iface_xml = ""

	def add_disk(self, disk_type, device_type, disk, qemu_type="raw"):
		"""
		Add a disk to the libvirt file

		:param disk_type: A string containing the type of disk (file, block)
		:param device_type: A string containing the type of device (disk, cdrom)
		:param disk: The path to the disk
		:param qemu_type: A string containing the format of disk (e.g., raw)
		:return:
		"""
		xml_type = "%s_%s" % (disk_type, device_type)
		if device_type in self.disk_ids:
			self.disk_ids[device_type] += 1
		else:
			self.disk_ids[device_type] = ord('a')

		f = os.path.join(self.config_dir, "%s-%s-%s" % (
			disk_type, device_type, LibvirtFile.TEMPLATE_FILE))
		if not os.path.exists(f):
			cziso.abort("Unable to find libvirt file %s" % f)

		values = {
			'id': chr(self.disk_ids[device_type]),
			xml_type: os.path.realpath(disk),
			'qemu_type': qemu_type
		}
		self.disk_xmls.append(cziso.fill_template(f, **values))

	def get_name(self):
		"""
		Return the name of the VM instance

		:return:  A string containing the name of the VM instance
		"""
		return self.name

	def get_xml(self):
		"""
		Return the virt file XML

		:return:  A string containing the libvirt file
		"""
		return cziso.fill_template(self.libvirt, vm_name = self.name,
		    disks="\n".join(self.disk_xmls), interface=self.iface_xml)

	def set_interface(self, iface):
		"""
		Add an interface to the libvirt file

		:param iface: The local interface that you want this vM to be bridged to
		"""
		f = os.path.join(self.config_dir, "iface-%s" % LibvirtFile.TEMPLATE_FILE)
		self.iface_xml = cziso.fill_template(f, iface=iface)



