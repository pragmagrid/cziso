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
		try:
			self.clonezilla_vm_obj.destroy()
		except:
			self.logger.debug("VM already shutdown")
		self.clonezilla_vm_obj.undefine()

	def get_vnc_port(self):
		"""
		Get the VNC port assigned to VM

		:return:  A string containing the VNC port
		"""
		# get the XML description of the VM
		vm_xml = self.clonezilla_vm_obj.XMLDesc(0)
		root = ET.fromstring(vm_xml)
		# get the VNC port
		graphics = root.find('./devices/graphics')
		port = graphics.get('port')
		return port

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

	def add_disk(self, disk_type, device_type, disk):
		xml_type = "%s_%s" % (disk_type, device_type)
		if xml_type in self.disk_ids:
			self.disk_ids[xml_type] += 1
		else:
			self.disk_ids[xml_type] = ord('a')

		f = os.path.join(self.config_dir, "%s-%s-%s" % (
			disk_type, device_type, LibvirtFile.TEMPLATE_FILE))
		if not os.path.exists(f):
			cziso.abort("Unable to find libvirt file %s" % f)

		values = {'id': chr(self.disk_ids[xml_type]), xml_type: disk}
		self.disk_xmls.append(cziso.fill_template(f, **values))

	def get_name(self):
		return self.name

	def get_xml(self):
		return cziso.fill_template(self.libvirt, vm_name = self.name,
		    disks="\n".join(self.disk_xmls), interface=self.iface_xml)

	def set_interface(self, iface):
		f = os.path.join(self.config_dir, "iface-%s" % LibvirtFile.TEMPLATE_FILE)
		self.iface_xml = cziso.fill_template(f, iface=iface)



