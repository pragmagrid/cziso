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
		"ip= ": "console=ttyS0,115200n8 ip= ",
		"timeout 300": "timeout 1"
	}

	def __init__(self, config):
		self.config = config
		self.clonezilla_custom = ClonezillaIso(config, "custom")
		self.clonezilla_regular = ClonezillaIso(config, "regular")
		self.create_expect = config.get_path("cziso", "create_expect_template")
		self.restore_expect = config.get_path(
			"cziso", "restore_expect_template")
		self.priv_interface = config.get("cziso", "private_iface")
		self.temp_dir = config.get("cziso", "temp_directory")
		self.genisoimage_command = config.get("cziso", "genisoimage_command")

		self.logger = logging.getLogger(self.__module__)
		self.unique_id = "%s-%d" % (time.strftime('%Y%m%d'), os.getpid())

	def convert_to_clonezilla_iso(self, image, out_dir, network):
		"""
		Create a Clonezilla ISO file from specified image

		:param image:  Path to raw image file to convert
		:param ip: IP address to use for Clonezilla VM (default: from Rocks)
		:param netmask: Netmask to use for Clonezilla VM (default: from Rocks)

		:return:  Returns if successful; otherwise aborts
		"""
		if not image.exists():
			cziso.abort("Image file %s does not exist" % image)
		if out_dir is not None and not os.path.exists(out_dir):
			cziso.abort("Output directory %s does not exist" % out_dir)
		self.logger.info("Converting image %s to iso" % image)

		# mount raw image and check it
		if not image.mount():
			cziso.abort("Unable to mount input image %s" % image)
		image.fsck()
		image.unmount()

		# mount temp directory to place iso when complete
		tmp = self.create_temp_directory()
		ip, netmask = None, None
		if network is None:
			ip, netmask = cziso.get_free_ip(self.priv_interface)
		else:
			ip, netmask = network.split(":")
		if netmask is None or ip is None:
			cziso.abort("Unable to create a NFS export.  No ip or netmask")
		cziso.create_nfs_export(tmp, ip)

		# check that we don't overwrite an existing ISO file
		generated_iso_filename = Clonezilla.get_cz_restore_iso_filename(image)
		generated_iso_path = os.path.join(tmp, generated_iso_filename)
		# insert the disk size into the file name
		new_iso_filename = Clonezilla.get_cziso_restore_iso_filename(image)
		candidate_dst_file = os.path.join(self.temp_dir, new_iso_filename)
		if out_dir is not None:
			candidate_dst_file = os.path.join(out_dir, new_iso_filename)
		dst_file = cziso.increment_filename(candidate_dst_file)

		# launch Clonezilla
		libvirt_file = cziso.virtualmachine.LibvirtFile(self.config.config_dir)
		libvirt_file.add_disk(
			"file", "cdrom", self.clonezilla_custom.get_or_download())
		image.add_to_libvirt(libvirt_file)
		libvirt_file.set_interface(self.priv_interface)
		vm = cziso.virtualmachine.VM()
		status = vm.launch(libvirt_file.get_xml())
		if status != 0:
			cziso.abort("Unable to launch Clonezilla Live VM")

		# run create iso script
		expect_path = cziso.fill_template(
			self.create_expect, tmp_dir=tmp, temp_dir=tmp,
			vm_name=libvirt_file.get_name(), ip=ip, netmask=netmask,
			vm_id=image.get_image_id())
		self.logger.info(
			"""Running expect script to execute gen-rec-iso script -- it may
take a few mins to boot the Clonezilla Live VM before you see any output""")
		subprocess.call("expect %s" % expect_path, shell=True)

		if os.path.exists(generated_iso_path):
			self.logger.debug(
				"Moving ISO file %s to %s" % (generated_iso_path, dst_file))
			os.rename(generated_iso_path, dst_file)
			self.logger.info(
				"Clonezilla restore ISO file is now ready at %s" % dst_file)
		else:
			self.logger.error("Clonezilla did not generate ISO file")

		# cleanup
		vm.clean()
		cziso.remove_nfs_export(tmp, ip)
		shutil.rmtree(tmp)
		image.unmount()

	@staticmethod
	def get_cziso_restore_iso_filename(image):
		"""
		Get the restore ISO filename that Clonezilla generates

		:param image: An object of type cziso.image.Image

		:return: A string containing the restore ISO filename
		"""
		iso_base, iso_ext = os.path.splitext(
			Clonezilla.get_cz_restore_iso_filename(image))
		new_iso_filename = "%s.%iG%s" % (iso_base, image.get_size(), iso_ext)
		return new_iso_filename

	@staticmethod
	def get_cz_restore_iso_filename(image):
		"""
		Get the restore ISO filename that cziso generates

		:param image: An object of type cziso.image.Image

		:return: A string containing the restore ISO filename
		"""
		return  "clonezilla-live-%s.iso" % image.get_image_id()

	def create_temp_directory(self):
		"""
		Create a temporary sub-directory relative to the config temp dir

		:return: The path to the temporary sub directory.
		"""
		tmp_dir = os.path.join(
			self.temp_dir, "clonezilla-temp-isodir-%s" % self.unique_id)
		os.mkdir(tmp_dir)
		return tmp_dir

	def modify_image(self, image, target_image):
		"""
		Modify image using regular Clonezilla

		:param image: An object of Image

		:return:  Returns if successful; otherwise aborts
		"""
		self.logger.info("Modifying image %s" % image)

		libvirt_file = cziso.virtualmachine.LibvirtFile(self.config.config_dir)
		libvirt_file.add_disk(
			"file", "cdrom", self.clonezilla_regular.get_or_download())
		image.add_to_libvirt(libvirt_file)
		if target_image is not None:
			target_image.add_to_libvirt(libvirt_file)

		vm = cziso.virtualmachine.VM()
		vm.launch(libvirt_file.get_xml())
		vm.attach_vnc()
		vm.clean()
		image.unmount()
		if target_image is not None:
			target_image.unmount()

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

		# launch Clonezilla
		libvirt_file = cziso.virtualmachine.LibvirtFile(self.config.config_dir)
		libvirt_file.add_disk("file", "cdrom", iso_file)
		image.add_to_libvirt(libvirt_file)

		vm = cziso.virtualmachine.VM()
		status = vm.launch(libvirt_file.get_xml())
		if status != 0:
			cziso.abort("Unable to launch Clonezilla Live VM")

		# run restore iso script
		expect_path = cziso.fill_template(
			self.restore_expect, tmp_dir=self.temp_dir,
			vm_name=libvirt_file.get_name())
		self.logger.info("""Running restore expect script -- it may take a few
mins to boot the Clonezilla Live VM before you see any output""")
		subprocess.call("expect %s" % expect_path, shell=True)

		# cleanup
		vm.clean()
		image.unmount()
		os.remove(expect_path)
		self.logger.info("Restored image %s is now ready" % image)

	@staticmethod
	def parse_image_size_from_iso_filename(filename):
		"""
		Parse and return the original image size from a restore ISO filename.

		:param filename: The restore ISO filename

		:return: An integer representing the original image size in GB
		"""
		matcher = re.search("\.(\d+)G\.", filename)
		if matcher is None:
			cziso.abort("Unable to parse image size from restore ISO filename")
		return int(matcher.group(1))

	def test_image(self, image):
		"""
		Test image by starting up a VM

		:param image: A string containing the image URI

		:return:  Returns if successful; otherwise aborts
		"""
		self.logger.info("Testing image %s" % image)

		libvirt_file = cziso.virtualmachine.LibvirtFile(self.config.config_dir)
		image.add_to_libvirt(libvirt_file)
		vm = cziso.virtualmachine.VM()
		vm.launch(libvirt_file.get_xml())
		vm.attach_vnc()
		vm.clean()
		image.unmount()

	def update(self, zip_path, out_dir=os.getcwd()):
		"""
		Generate new Clonezilla Live ISOs for both the custom and regular
		cases.

		:param zip_path: A string containing the path to a Clonezilla zip
		release
		:param out_dir: A string containing a path to where the ISOs should
		be written

		:return: A tuple containing the path to the regular and custom ISOs
		"""
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
		self.gdrive_id = config.get(section_name, "google_drive_id")
		self.filename = config.get(section_name, "filename")
		self.iso_path = os.path.join(self.temp_dir, self.filename)
		self.max_cache_age_days = int(config.get(section_name, "max_cache_age"))
		self.max_cache_age_secs = self.max_cache_age_days * 60 * 60 * 24

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
		if not os.path.exists(self.iso_path):
			self.logger.info("No local %s clonezilla iso found" % self.type)
			cziso.gdrive_download(self.gdrive_id, self.iso_path)
			return self.iso_path

		# check to see if we need to download a fresh copy
		local_age = time.time() - os.path.getmtime(self.iso_path)
		if local_age > self.max_cache_age_secs:
			self.logger.info("Local %s found is older than %i days" % (
				self.iso_path, self.max_cache_age_days))
			cziso.gdrive_download(self.gdrive_id, self.iso_path)

		self.logger.debug("Using clonezilla iso at %s" % self.iso_path)
		return self.iso_path
