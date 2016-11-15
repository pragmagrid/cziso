import apiclient.discovery
import cookielib
import cziso
import libvirt
import logging
import httplib2
import json
import os
import re
from oauth2client.service_account import ServiceAccountCredentials
import shutil
import subprocess
import time
import urllib2
from xml.etree import ElementTree as ET



class Clonezilla:
	SCOPE = "https://www.googleapis.com/auth/drive"
	CLONEZILLA_LOCAL_FILENAME = "clonezilla-live.iso"
	CLONEZILLA_VM_PREFIX = "cziso"
	CREATE_ISO_EXPECT = "create-iso.expect"

	def __init__(self, config):
		self.clonezilla_drive_id = config.get("google", "clonezilla_drive_id")
		self.service_account_credentials = config.get("google", "service_account_credentials")
		self.clonezilla_libvirt_template = config.get("cziso", "clonezilla_libvirt_template")
		self.launch_expect = config.get("cziso", "launch_expect_template")
		self.priv_interface = config.get("cziso", "private_iface")
		self.temp_dir = config.get("cziso", "temp_directory")

		self.clonezilla_vm_obj = None
		self.logger = logging.getLogger(self.__module__)
		self.unique_id = "%s-%d" % (time.strftime('%Y%m%d'), os.getpid())
		self.clonezilla_vm_name = "%s-%s" % (
			Clonezilla.CLONEZILLA_VM_PREFIX, self.unique_id)

	def clean_clonezilla_vm(self):
		"""
		Shutdown and remove Clonezilla VM

		:return: Returns if successful; otherwise aborts
		"""
		try:
			self.clonezilla_vm_obj.destroy()
		except:
			self.logger.debug("VM already shutdown")
		self.clonezilla_vm_obj.undefine()

	def convert_to_clonezilla_iso(self, image, ip=None, netmask=None):
		"""
		Create a Clonezilla ISO file from specified image

		:param image:  Path to raw image file to convert
		:param ip: IP address to use for Clonezilla VM (default: from Rocks)
		:param netmask: Netmask to use for Clonezilla VM (default: from Rocks)

		:return:  Returns if successful; otherwise aborts
		"""
		self.logger.info("Converting image %s to iso" % image)
		vm_id = os.path.splitext(os.path.basename(image))[0]

		if not os.path.exists(image):
			cziso.abort("Image file %s does not exist" % image)

		# mount raw image
		loop_device = cziso.create_loop_device(image)
		self.logger.info("Mounted image %s as %s" % (image, loop_device))

		# mount temp directory to place iso when complete
		tmp = self.create_temp_directory()
		if ip is None and netmask is None:
			ip, netmask = cziso.get_free_ip(self.priv_interface)
		cziso.create_nfs_export(tmp, ip)

		# launch Clonezilla
		status = self.launch_clonezilla_vm(loop_device)
		if status != 0:
			cziso.abort("Unable to launch Clonezilla Live VM")

		# run create iso script
		expect_path = self.write_create_expect_script(ip, tmp, netmask, vm_id)
		self.logger.info("Running gen-rec-iso Clonezilla script")
		subprocess.call("expect %s" % expect_path, shell=True)

		# get ISO image
		iso_file = "clonezilla-live-%s.iso" % vm_id
		dst_file = os.path.join(self.temp_dir, iso_file)
		os.rename(os.path.join(tmp, iso_file), dst_file)
		self.logger.info("Moving ISO file to %s" % dst_file)

		# cleanup
		self.clean_clonezilla_vm()
		cziso.remove_nfs_export(tmp, ip)
		shutil.rmtree(tmp)
		cziso.remove_loop_device(loop_device)

	def create_temp_directory(self):
		"""
		Create a temporary sub-directory relative to the config temp dir

		:return: The path to the temporary sub directory.
		"""
		dir = os.path.join(
			self.temp_dir, "clonezilla-temp-isodir-%s" % self.unique_id)
		os.mkdir(dir)
		return dir

	def get_or_download_clonezilla_live(self):
		"""
		Return the path to the local Clonezilla Live ISO or download directlyt
		from Google drive if it doesn't exist yet

		:return:  Local path to Clonezilla Live VM
		"""
		local_path = os.path.join(
			self.temp_dir, Clonezilla.CLONEZILLA_LOCAL_FILENAME)
		if os.path.exists(local_path):
			self.logger.info("Using clonezilla iso at %s" % local_path)
			return local_path
		self.logger.info("No local clonezilla iso found")
		cziso.download(self.clonezilla_drive_id, local_path)

	def get_vm_vnc_port(self):
		"""
		Get the VNC port assigned to Clonezilla VM

		:return:  A string containing the VNC port
		"""
		# get the XML description of the VM
		vm_xml = self.clonezilla_vm_obj.XMLDesc(0)
		root = ET.fromstring(vm_xml)
		# get the VNC port
		graphics = root.find('./devices/graphics')
		port = graphics.get('port')
		return port

	def launch_clonezilla_vm(self, loop_device):
		"""
		Launch Clonezilla Live VM with provided loop device as input image

		:param loop_device:  Input image to convert

		:return: Returns 0 on success; otherwise non-zero
		"""
		clonezilla_iso = self.get_or_download_clonezilla_live()

		# check for external display so we can launch vncviewer
		if "DISPLAY" not in os.environ:
			cziso.abort("Must have external display to launch vncviewer.  Please SSH in with -Y to forward X display")

		self.virConnect_obj = libvirt.open("qemu:///session")
		xml = cziso.fill_template(
			self.clonezilla_libvirt_template,
			vm_name=self.clonezilla_vm_name,
			clonezilla_iso=clonezilla_iso,
			loopback_device=loop_device,
			ethX=self.priv_interface)
		self.clonezilla_vm_obj = self.virConnect_obj.defineXML(xml)
		return self.clonezilla_vm_obj.create()

	def upload(self, image):
		self.logger.info("Uploading image %s to %s" % (image, "fill in later"))

		self.get_or_download_clonezilla_live()

		# mount
		# credentials = ServiceAccountCredentials.from_json_keyfile_name(
		#     self.service_credentials, Repository.SCOPE)
		#
		# http_auth = credentials.authorize(httplib2.Http())
		# drive = apiclient.discovery.build('drive', 'v3', http=http_auth, cache_discovery=False)
		#
		# results = drive.files().list(q="name contains 'clonezilla'").execute()
		# items = results.get('files', [])
		# if not items:
		#     print('No files found.')
		# else:
		#     print('Files:')
		#     for item in items:
		#         print('{0} ({1})'.format(item['name'], item['id']))

	def write_create_expect_script(self, ip, iso_temp_dir, netmask, vm_id):
		msg = cziso.fill_template(self.launch_expect,
		                         vm_name=self.clonezilla_vm_name, ip=ip,
		                         netmask=netmask, temp_dir=iso_temp_dir,
		                         vm_id=vm_id)
		expect_path = os.path.join(iso_temp_dir, Clonezilla.CREATE_ISO_EXPECT)
		self.logger.info("Writing expect template to %s" % expect_path)
		f = open(expect_path, "w")
		f.write(msg)
		f.close()
		self.logger.info(msg)
		return expect_path
