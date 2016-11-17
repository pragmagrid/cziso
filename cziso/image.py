import abc
import cziso
import logging
import os
import re


class Image:
	"""
	Convenience class for handling VM images
	"""
	def __init__(self, image):
		"""
		Base constructor for image.  Initializes logger and stores image uri

		:param image:  The URI of the image
		"""
		self.logger = logging.getLogger(self.__module__)
		self.image_uri = image

	def __str__(self):
		"""
		Returns the image URI

		:return: A string containing the image URI
		"""
		return self.image_uri

	@abc.abstractmethod
	def create(self, size):
		"""
		Create the image file

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
		mount = self.get_mount()
		out, rc = cziso.run_command("fdisk -l %s" % mount)
		if rc != 0:
			cziso.abort("Unable to run fdisk command")
		partitions = []
		for line in out:
			matcher = re.match("^(%s\S+).*\s+(\S+)$" % mount, line)
			if matcher:
				if matcher.group(2) == "Linux":
					partitions.append(matcher.group(1))
		for partition in partitions:
			out, rc = cziso.run_command("fsck -y %s" % partition)
			if rc != 0:
				cziso.abort("Problem running fsck -y on partition")
			self.logger.debug("fsck output: %s" % "\n".join(out))

	@abc.abstractmethod
	def get_image_id(self):
		"""
		Get a string representing the ID of the image.  Used to name new
		Clonezilla ISO image.

		:return: A string containing the ID of the image
		"""
		pass

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
		elif Raw.match(image):
			return Raw(image)
		else:
			cziso.abort("Image type of %s is not supported" % image)

	@abc.abstractmethod
	def get_mount(self):
		"""
		Get the mountpoint for image

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
	def mount(self):
		"""
		Mount the specified image to local host as block device.

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


class Raw(Image):
	"""
	Convenience class for handling RAW VM images
	"""
	URI_PATTERN = "file://(/\S+\.(img|raw))"

	def __init__(self, image):
		"""
		Constructor for a RAW image.

		:param image:  The URI of the image of file://path/to/file.[raw,img]
		"""
		Image.__init__(self, image)
		matcher = Raw.match(image)
		self.file = matcher.group(1)
		self.loop_device = None
		self.logger.debug("Creating Raw object for %s" % self.file)

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

	def get_mount(self):
		"""
		Get the mountpoint for image

		:return: A string containing the mountpoint of the image
		"""
		return self.loop_device

	@staticmethod
	def match(image):
		"""
		Static method to see if image URI matches this subclass

		:param image: A string containing an image URI

		:return: True if subclass; False otherwise
		"""
		return re.match(Raw.URI_PATTERN, image)

	def mount(self):
		"""
		Mount the specified image to local host as block device.

		:return: True if successful, otherwise False
		"""
		out, rc = cziso.run_command("losetup -f %s" % self.file)
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

	def unmount(self):
		"""
		Unmount the specified image from localhost

		:return: True if successful; otherwise False
		"""
		out, rc = cziso.run_command("losetup -d %s" % self.loop_device)
		if rc != 0:
			self.logger.error(
				"Unable to remove loop device %s" % self.loop_device)
			return False
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
		Image.__init__(self, image)
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

		:return: True if image created; otherwise False
		"""
		out, rc = cziso.run_command("rocks add host storagemap %s %s %s %s %s img_sync=false" % (
				self.nas, self.pool, self.vol, self.hostname, size))
		if rc != 0:
			self.logger.error("Unable to create zvol to %s: %s" % (
				self.vol, "\n".join(out)))
			return False
		self.mountpoint = out[1]
		print True

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

	def get_mount(self):
		"""
		Get the mountpoint for image

		:return: A string containing the mountpoint of the image
		"""
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

	def mount(self):
		"""
		Mount the specified image to local host as block device.

		:return: True if successful, otherwise False
		"""
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
		return True
