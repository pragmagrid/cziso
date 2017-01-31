import abc
import cziso
import logging
import math
import os
import re


class Image:
	"""
	Convenience class for handling VM images
	"""
	def __init__(self, image, disk_type=None, qemu_type=None):
		"""
		Base constructor for image.  Initializes logger and stores image uri

		:param image:  The URI of the image
		:param disk_type: The type of disk (file or block)
		:param qemu_type: The image format (raw or qcow2)
		"""
		self.logger = logging.getLogger(self.__module__)
		self.image_uri = image
		self.disk_type = disk_type
		self.qemu_type = qemu_type
		self.partitions = []
		self.size_gb = 0

	def __str__(self):
		"""
		Returns the image URI

		:return: A string containing the image URI
		"""
		return self.image_uri

	def _get_disk_info(self):
		"""
		Find the provided image partitions on local host and disk size

		:return: A tuple containing the disk size and string array containing
		location of image partitions
		"""
		mount = self.get_mount()
		if self.get_mount() is None:
			self.logger.error("Disk is not mounted")
			return None, None
		out, rc = cziso.run_command("fdisk -l %s" % mount)
		if rc != 0:
			cziso.abort("Unable to run fdisk command")

		for line in out:
			if self.size_gb == 0:
				matcher = re.search("^Disk \S+: ([\d\.]+) GB", line)
				if matcher is not None:
					size_gb_float = float(matcher.group(1))
					self.size_gb = int(math.ceil(size_gb_float))
					self.logger.info("Disk size is %i GB" % self.size_gb)
			matcher = re.match("^(%s\S+).*\s+(\S+)$" % mount, line)
			if matcher:
				if matcher.group(2) == "Linux":
					self.partitions.append(matcher.group(1))
		if self.size_gb == 0:
			cziso.abort("Unable to find disk size of %s" % self)
		return self.size_gb, self.partitions

	def add_to_libvirt(self, libvirt):
		"""
		Mount the image if necessary and add disk to libvirt config file

		:param libvirt: An object of type virtualmachine.LibvirtFile
		"""
		if not self.mount(libvirt=True):
			cziso.abort("Unable to mount image %s" % self)
		libvirt.add_disk(
			self.get_disk_type(),
			"disk",
			self.get_mount(libvirt=True),
			self.get_qemu_type()
		)

	@abc.abstractmethod
	def create(self, size):
		"""
		Create the image file

		:param size An integer containing the file size in GB

		:return: True if image created; otherwise False
		"""
		pass

	@abc.abstractmethod
	def delete(self):
		"""
		Remove the image file

		:return: True if image deleted; otherwise False
		"""
		pass

	@abc.abstractmethod
	def exists(self):
		"""
		Verifies specified VM image exists

		:return: True if image exists; otherwise False
		"""
		pass

	def fsck(self):
		"""
		Runs fsck on disk to repair any issues

		:return:  True if successful; otherwise False
		"""
		self.logger.info("Running fsck on disk partitions")
		self._get_disk_info()
		if not self.partitions:
			cziso.abort("Unable to find any partitions on disk")
		for partition in self.partitions:
			out, rc = cziso.run_command("fsck -y %s" % partition)
			if rc != 0:
				self.unmount()
				cziso.abort(
					"Problem running fsck -y on partition: %s" % "\n".join(out))
			self.logger.debug("fsck output: %s" % "\n".join(out))

	@abc.abstractmethod
	def get_image_id(self):
		"""
		Get a string representing the ID of the image.  Used to name new
		Clonezilla ISO image.

		:return: A string containing the ID of the image
		"""
		pass

	def get_disk_type(self):
		"""
		Get the disk type (i.e., file or block)

		:return: A string containing the disk type
		"""
		return self.disk_type

	def get_qemu_type(self):
		"""
		Get the type of qemu image (e.g., raw, qcow, qcow2, ...)

		:return: A string containing qemu type
		"""
		return self.qemu_type

	def get_size(self):
		"""
		Return the disk size

		:return: An integer representing the disk size in GB
		"""
		return self.size_gb

	@staticmethod
	def factory(image):
		"""
		Return the correct subclass instance for specific image type.
		Currently supports RAW and ZFS vol images.

		:param image: A string containing an image URI

		:return:
		"""
		if ZfsVol.match(image):
			return ZfsVol(image)
		elif QemuImg.match(image):
			return QemuImg(image)
		else:
			cziso.abort("Image type of %s is not supported" % image)

	@abc.abstractmethod
	def get_mount(self, libvirt=False):
		"""
		Get the mountpoint for image

		:param libvirt: Return mount for libvirt

		:return: A string containing the mountpoint of the image
		"""
		pass

	@staticmethod
	@abc.abstractmethod
	def match(image):
		"""
		Static method to see if image URI matches this subclass

		:param image: A string containing an image URI

		:return: True if subclass; False otherwise
		"""
		pass

	@abc.abstractmethod
	def mount(self, libvirt=False):
		"""
		Mount the specified image to local host as block device.

		:param libvirt: Only mount if needed for libvirt (i.e. if mount not
		supported by libvirt 0.12)

		:return: True if successful, otherwise False
		"""
		pass

	@abc.abstractmethod
	def unmount(self):
		"""
		Unmount the specified image from localhost

		:return: True if successful; otherwise False
		"""
		pass


class QemuImg(Image):
	"""
	Convenience class for handling RAW VM images
	"""
	URI_PATTERN = "file://(/\S+\.(img|raw|qcow2))"

	def __init__(self, image):
		"""
		Constructor for a RAW image.

		:param image:  The URI of the image of file://path/to/file.[raw,img]
		"""
		matcher = QemuImg.match(image)
		self.file = matcher.group(1)
		Image.__init__(self, image, "file", self._find_qemu_type())
		self.loop_device = None
		self.logger.debug("Creating Raw object for %s" % self.file)

	def _find_qemu_type(self):
		"""
		Return the qemu type based on the file name

		:return:  A string containing the qemu type (e.g., raw or qcow2)
		"""
		base, qemu_type = os.path.splitext(self.file)
		qemu_type = qemu_type.replace(".", "").lower()
		if qemu_type == "img":
			qemu_type = "raw"
		return qemu_type

	def _get_disk_info(self):
		"""
		Find the provided image partitions on local host

		:return: A tuple containing the disk size and string array containing
		location of image partitions
		"""
		Image._get_disk_info(self)
		mapper = os.path.join("dev", "mapper")
		self.partitions = [p.replace("dev", mapper) for p in self.partitions]
		return self.size_gb, self.partitions

	def create(self, size):
		"""
		Create the image file

		:param size An integer containing the file size in GB

		:return: True if image created; otherwise False
		"""
		out, rc = cziso.run_command(
			"qemu-img create -f %s %s %iG" % (self.qemu_type, self.file, size))
		if rc != 0:
			self.logger.error("Unable to create image: %s" % "\n".join(out))
			return False
		self.logger.info("Created image file %s (%i GB)" % (self.file, size))
		return True

	def exists(self):
		"""
		Verifies specified VM image file exists

		:return: True if image exists; otherwise False
		"""
		return os.path.exists(self.file)

	def get_image_id(self):
		"""
		Get a string representing the ID of the image.  Used to name new
		Clonezilla ISO image.

		:return: A string containing the ID basename of the image w/o its suffix
		"""
		return os.path.splitext(os.path.basename(self.file))[0]

	def get_mount(self, libvirt=False):
		"""
		Get the mountpoint for image

		:param libvirt: Return mount for libvirt

		:return: A string containing the mountpoint of the image
		"""
		if libvirt:
			return self.file
		else:
			return self.loop_device

	@staticmethod
	def match(image):
		"""
		Static method to see if image URI matches this subclass

		:param image: A string containing an image URI

		:return: True if subclass; False otherwise
		"""
		return re.match(QemuImg.URI_PATTERN, image)

	def mount(self, libvirt=False):
		"""
		Mount the specified image to local host as block device.

		:param libvirt: Only mount if needed for libvirt (i.e. if mount not
		supported by libvirt 0.12)

		:return: True if successful, otherwise False
		"""
		# Files can be mounted by libvirt
		if libvirt:
			return True

		out, rc = cziso.run_command("kpartx -a %s" % self.file)
		if rc != 0:
			self.logger.error("Unable to mount %s as a control loop device")
			return False
		out, rc = cziso.run_command("losetup -a")
		for line in out:
			if line.find(self.file) >= 0:
				matcher = re.search("(/dev/loop\d+)", line)
				if matcher:
					self.loop_device = matcher.group(1)
					self.logger.info("Mounted image %s as %s" % (
						self.file, self.loop_device))
					return True
		if not self.loop_device:
			self.logger.error("Unable to find loop device for %s" % self.file)
			return False
		return True

	def unmount(self):
		"""
		Unmount the specified image from localhost

		:return: True if successful; otherwise False
		"""
		if self.loop_device is None:
			self.logger.debug("No loop device needs to be unmounted")
			return True

		out, rc = cziso.run_command("kpartx -d %s" % self.file)
		if rc != 0:
			self.logger.error(
				"Unable to remove loop device %s" % self.loop_device)
			return False
		self.loop_device = None
		return True


class ZfsVol(Image):
	"""
	Convenience class for handling ZFS vol backed VM images
	"""
	URI_PATTERN = "zfs://([^\/]+)/([^\/]+)/([^\/]+)"

	def __init__(self, image):
		"""
		Constructor for ZFS vol backed VM image.

		:param image:  The URI of the image of zfs://nas/pool/vol format
		"""
		Image.__init__(self, image, "block", "raw")
		matcher = ZfsVol.match(image)
		self.nas = matcher.group(1)
		self.pool = matcher.group(2)
		self.vol = matcher.group(3)
		self.logger.debug("Creating ZfsVol instance for vol %s in pool %s at %s"
		                  % (self.vol, self.pool, self.nas))
		out, rc = cziso.run_command(
			"rocks report host attr localhost attr=hostname")
		if rc != 0:
			cziso.abort("Unable to determine physical hostname")
		self.hostname = out[0]
		self.mountpoint = None

	def create(self, size):
		"""
		Create the image file

		:param size An integer containing the file size in GB

		:return: True if image created; otherwise False
		"""
		out, rc = cziso.run_command("rocks add host storagemap %s %s %s %s %i img_sync=false" % (
				self.nas, self.pool, self.vol, self.hostname, size))
		if rc != 0:
			self.logger.error("Unable to create zvol to %s: %s" % (
				self.vol, "\n".join(out)))
			return False
		self.logger.info("Created ZFS vol %s (%i GB)" % (self, size))
		self.mountpoint = out[1]
		return True

	def delete(self):
		"""
		Remove the image file

		:return: True if image deleted; otherwise False
		"""
		if self.is_mapped():
			self.unmount()
		out, rc = cziso.run_command("rocks remove host storageimg %s %s %s" % (
			self.nas, self.pool, self.vol))
		if rc != 0:
			self.logger.error("Unable to delete image: %s" % "\n".join(out))
			return False
		return True

	def exists(self):
		"""
		Verifies specified VM image zvol exists on NAS device

		:return: True if image exists; otherwise False
		"""
		out, rc = cziso.run_command("ssh %s zfs list %s/%s" % (
			self.nas, self.pool, self.vol))
		return rc == 0

	def get_image_id(self):
		"""
		Get a string representing the ID of the image.  Used to name new
		Clonezilla ISO image.

		:return: A string containing the vol name of the image
		"""
		return "%s-%s" % (self.pool, self.vol)

	def get_mount(self, libvirt=False):
		"""
		Get the mountpoint for image

		:param libvirt: Return mount for libvirt

		:return: A string containing the mountpoint of the image
		"""
		# always the same whether libvirt or regular host mount
		return self.mountpoint

	def is_mapped(self):
		out, rc = cziso.run_command("rocks list host storagemap %s" % self.nas)
		if rc != 0:
			cziso.abort("Unable to list current storagemap")
		mapped_pattern = "^%s\s+%s.*\s+(\S*mapped)\s+.*" % (self.vol, self.pool)
		self.logger.debug("Looking for pattern '%s'" % mapped_pattern)
		for line in out:
			matcher = re.search(mapped_pattern, line)
			if matcher is not None:
				mapped_status = matcher.group(1)
				self.logger.debug("Status of vol %s is %s" % (self.vol, mapped_status))
				return mapped_status == "mapped"
		return False

	@staticmethod
	def match(image):
		"""
		Static method to see if image URI matches this subclass

		:param image: A string containing an image URI

		:return: True if subclass; False otherwise
		"""
		return re.match(ZfsVol.URI_PATTERN, image)

	def mount(self, libvirt=False):
		"""
		Mount the specified image to local host as block device.

		:param libvirt: Only mount if needed for libvirt (i.e. if mount not
		supported by libvirt 0.12)

		:return: True if successful, otherwise False
		"""
		# ZFS mounts not supported by our libvirt version so always mount
		# check if already mounted
		if self.mountpoint is not None:
			return True

		out, rc = cziso.run_command(
			"rocks add host storagemap %s %s %s %s 10 img_sync=false" % (
				self.nas, self.pool, self.vol, self.hostname))
		if rc != 0:
			self.logger.error("Unable to mount zvol to %s" % self.hostname)
			return False
		self.mountpoint = out[1]
		self.logger.info("Mounted zvol %s to %s" % (self.vol, self.mountpoint))
		return True

	def unmount(self):
		"""
		Unmount the specified image from localhost

		:return: True if successful; otherwise False
		"""
		out, rc = cziso.run_command(
			"rocks remove host storagemap %s %s" % (self.nas, self.vol))
		if rc != 0:
			self.logger.error("Unable to unmount zvol at %s" % self.mount)
			return False
		self.mountpoint = None
		return True
