import cziso
import cziso.virtualmachine
import logging
import os
import re
import shutil
import subprocess
import time


class Clonezilla:
	CREATE_ISO_EXPECT = "create-iso.expect"
	CUSTOMIZATIONS = {
		"locales= ": "locales=en_US.UTF-8 ",
		"keyboard-layouts= ": "keyboard-layouts=us ",
		"ocs_live_run=\"ocs-live-general\"": "ocs_live_run=\"bash\" ",
		"ip= ": "console=ttyS0,115200n8 ip= "
	}

	def __init__(self, config):
		self.config = config
		self.clonezilla_custom = ClonezillaIso(config, "custom")
		self.clonezilla_regular = ClonezillaIso(config, "regular")
		self.launch_expect = config.get("cziso", "launch_expect_template")
		self.priv_interface = config.get("cziso", "private_iface")
		self.temp_dir = config.get("cziso", "temp_directory")
		self.genisoimage_command = config.get("cziso", "genisoimage_command")

		self.logger = logging.getLogger(self.__module__)
		self.unique_id = "%s-%d" % (time.strftime('%Y%m%d'), os.getpid())

	def convert_to_clonezilla_iso(self, image, out_file, network):
		"""
		Create a Clonezilla ISO file from specified image

		:param image:  Path to raw image file to convert
		:param ip: IP address to use for Clonezilla VM (default: from Rocks)
		:param netmask: Netmask to use for Clonezilla VM (default: from Rocks)

		:return:  Returns if successful; otherwise aborts
		"""
		if not image.exists():
			cziso.abort("Image file %s does not exist" % image)
		self.logger.info("Converting image %s to iso" % image)

		# mount raw image and check it
		if not image.mount():
			cziso.abort("Unable to mount input image %s" % image)
		image.fsck()

		# mount temp directory to place iso when complete
		tmp = self.create_temp_directory()
		if ip is None and netmask is None:
			ip, netmask = cziso.get_free_ip(self.priv_interface)
		cziso.create_nfs_export(tmp, ip)

		# launch Clonezilla
		libvirt_file = cziso.virtualmachine.LibvirtFile(self.config.config_dir)
		libvirt_file.add_disk(
			"file", "cdrom", self.clonezilla_custom.get_or_download())
		libvirt_file.add_disk("block", "disk", image.get_mount())
		libvirt_file.set_interface(self.priv_interface)
		vm = cziso.virtualmachine.VM()
		status = vm.launch(libvirt_file.get_xml())
		if status != 0:
			cziso.abort("Unable to launch Clonezilla Live VM")

		# run create iso script
		expect_path = self.write_create_expect_script(
			libvirt_file.get_name(), ip, tmp, netmask, image.get_image_id())
		self.logger.info("Running gen-rec-iso Clonezilla script")
		subprocess.call("expect %s" % expect_path, shell=True)

		# get ISO image
		iso_file = "clonezilla-live-%s.iso" % image.get_image_id()
		src_file = os.path.join(tmp, iso_file)
		dst_file = os.path.join(self.temp_dir, iso_file)
		if dst_file != "":
			dst_file = out_file
		if os.path.exists(src_file):
			os.rename(src_file, dst_file)
			self.logger.info("Moving ISO file to %s" % dst_file)
		else:
			self.logger.error("Clonezilla did not generate ISO file")

		# cleanup
		vm.clean()
		cziso.remove_nfs_export(tmp, ip)
		shutil.rmtree(tmp)
		image.unmount()

	def create_temp_directory(self):
		"""
		Create a temporary sub-directory relative to the config temp dir

		:return: The path to the temporary sub directory.
		"""
		tmp_dir = os.path.join(
			self.temp_dir, "clonezilla-temp-isodir-%s" % self.unique_id)
		os.mkdir(tmp_dir)
		return tmp_dir

	def modify_image(self, image):
		"""
		Modify image using regular Clonezilla

		:param image: An object of Image

		:return:  Returns if successful; otherwise aborts
		"""
		self.logger.info("Modifying image %s" % image)
		if not image.mount():
			cziso.abort("Unable to mount image %s" % image)

		libvirt_file = cziso.virtualmachine.LibvirtFile(self.config.config_dir)
		libvirt_file.add_disk("file", "cdrom",
		                      self.clonezilla_regular.get_or_download())
		libvirt_file.add_disk("block", "disk", image.get_mount())
		vm = cziso.virtualmachine.VM()
		vm.launch(libvirt_file.get_xml())
		vm.attach_vnc()
		vm.clean()
		image.unmount()

	def resize_image(self, in_image, out_image):
		"""
		Resize a current VM image

		:param in_image: input image to resize
		:param out_image: output image to place resized image

		:return:  Returns if successful; otherwise aborts
		"""
		self.logger.info("Resizing image %s to %s" % (in_image, out_image))

		# mount images
		if not in_image.mount():
			cziso.abort("Unable to mount input image %s" % in_image)
		if not out_image.mount():
			cziso.abort("Unable to mount output image %s" % out_image)

		# launch Clonezilla
		libvirt_file = cziso.virtualmachine.LibvirtFile(self.config.config_dir)
		libvirt_file.add_disk("file", "cdrom", self.clonezilla_regular.get_or_download())
		libvirt_file.add_disk("block", "disk", in_image.get_mount())
		libvirt_file.add_disk("block", "disk", out_image.get_mount())
		vm = cziso.virtualmachine.VM()
		status = vm.launch(libvirt_file.get_xml())
		if status != 0:
			cziso.abort("Unable to launch Clonezilla Live VM")
		vm.attach_vnc()

		# cleanup
		vm.clean()
		in_image.unmount()
		out_image.unmount()

	def restore_clonezilla_iso(self, iso_file, image):
		"""
		Restpre a Clonezilla VM ISO file

		:param iso_file:  Path to Clonezilla ISO file to restore
		:param image: Destination for restored image of type Image

		:return:  Returns if successful; otherwise aborts
		"""
		self.logger.info("Restoring image %s to image %s" % (iso_file, image))
		if not os.path.exists(iso_file):
			cziso.abort("ISO file %s does not exist" % iso_file)
		if not image.mount():
			cziso.abort("Unable to mount image %s" % image)

		# launch Clonezilla
		libvirt_file = cziso.virtualmachine.LibvirtFile(self.config.config_dir)
		libvirt_file.add_disk("file", "cdrom", iso_file)
		libvirt_file.add_disk("block", "disk", image.get_mount())
		vm = cziso.virtualmachine.VM()
		status = vm.launch(libvirt_file.get_xml())
		if status != 0:
			cziso.abort("Unable to launch Clonezilla Live VM")
		vm.attach_vnc()
		vm.clean()
		image.unmount()

	def test_image(self, image):
		"""
		Test image by starting up a VM

		:param image: A string containing the image URI

		:return:  Returns if successful; otherwise aborts
		"""
		self.logger.info("Testing image %s" % image)
		if not image.mount():
			cziso.abort("Unable to mount image %s" % image)

		libvirt_file = cziso.virtualmachine.LibvirtFile(self.config.config_dir)
		libvirt_file.add_disk("block", "disk", image.get_mount())
		vm = cziso.virtualmachine.VM()
		vm.launch(libvirt_file.get_xml())
		vm.attach_vnc()
		vm.clean()
		image.unmount()

	def update(self, zip_path, out_dir=os.getcwd()):
		self.logger.info("Generating custom ISO for %s" % zip_path)
		cz_version = os.path.splitext(os.path.basename(zip_path))[0]

		tmp = self.create_temp_directory()
		self.logger.debug("Created temporary directory %s" % tmp)

		# unpack zip
		zip_dir = os.path.join(tmp, "zip")
		out, rc = cziso.run_command("unzip %s -d %s" % (zip_path, zip_dir))
		if rc != 0:
			cziso.abort("Unable to unzip %s: %s" % (zip_path, "\n".join(out)))

		# generate regular ISO
		regular_iso = os.path.join(out_dir, "%s-regular.iso" % cz_version)
		cziso.generate_iso(self.genisoimage_command, zip_dir, regular_iso)

		# customize file
		isolinux_file = os.path.join(zip_dir, "syslinux", "isolinux.cfg")
		if not os.path.exists(isolinux_file):
			cziso.abort("Unable to find %s" % isolinux_file)
		self.logger.info("Editing %s" % isolinux_file)
		cziso.file_edit(isolinux_file, Clonezilla.CUSTOMIZATIONS)

		# generate custom ISO
		custom_iso = os.path.join(out_dir, "%s-custom.iso" % cz_version)
		cziso.generate_iso(self.genisoimage_command, zip_dir, custom_iso)

		# cleanup
		self.logger.debug("Removing temporary directory %s" % tmp)
		shutil.rmtree(tmp)

		return regular_iso, custom_iso

	def write_create_expect_script(self, vm_name, ip, iso_temp_dir, netmask, img_id):
		"""
		Fill in the correct parameters for expect script to drive automated
		Clonezilla ISO generation and write to disk.

		:param ip:  A string containing the IP address for Clonezilla VM
		:param iso_temp_dir:  Temporary directory to mount to /home/partimag
		:param netmask:  A string containing the netmask for Clonezilla VM
		:param img_id:  The identifier to use for ISO name

		:return:  Path to expect script
		"""
		msg = cziso.fill_template(self.launch_expect,
		                          vm_name=vm_name, ip=ip,
		                          netmask=netmask, temp_dir=iso_temp_dir,
		                          vm_id=img_id)
		expect_path = os.path.join(iso_temp_dir, Clonezilla.CREATE_ISO_EXPECT)
		self.logger.info("Writing expect template to %s" % expect_path)
		f = open(expect_path, "w")
		f.write(msg)
		f.close()
		self.logger.info(msg)
		return expect_path

class ClonezillaIso:
	""""
	Convenience class for working with Clonezilla Live ISO
	"""
	def __init__(self, config, iso_type):
		"""
		Read in config info from file and create instance.

		:param config:  A CzisoConfig object containing configuration
		:param iso_type:  A string containing the type of Clonezilla ISO as defined
		in config file.
		"""
		self.logger = logging.getLogger(self.__module__)
		self.temp_dir = config.get("cziso", "temp_directory")
		self.type = iso_type
		section_name = "clonezilla_%s" % iso_type
		self.google_drive_id = config.get(section_name, "google_drive_id")
		local_filename = config.get(section_name, "local_filename")
		self.iso_path = os.path.join(self.temp_dir, local_filename)

	def __str__(self):
		"""
		Return Clonezilla ISO type as defined in config file

		:return:  A string containing the type of the Clonezilla ISO
		"""
		return self.type

	def get_or_download(self):
		"""
		Return the path to the local Clonezilla Live ISO or download directlyt
		from Google drive if it doesn't exist yet

		:return:  Local path to Clonezilla Live VM
		"""
		if os.path.exists(self.iso_path):
			self.logger.info("Using clonezilla iso at %s" % self.iso_path)
			return self.iso_path
		self.logger.info("No local %s clonezilla iso found" % self.type)
		cziso.gdrive_download(self.google_drive_id, self.iso_path)
		return self.iso_path
