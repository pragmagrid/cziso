import cziso
import cziso.commands
import cziso.clonezilla
import cziso.image
from cziso.commands import CommonArgs, ImageArg, ImageOpt


class Command(cziso.commands.Command):
	usage = CommonArgs(
		"""
		Modify an image using regular Clonezilla Live VM.  Attaches specified
		disks as vda and vdb (if target-image specified) and launches VNC
		console to Clonezilla Live VM instance.  Will shutdown and destroy
		VM once vncviewer window is closed.  Currently requires X
		forwarding enabled in order to run vncviewer.
		""",
		[
			ImageArg("image")
		],
		[
			ImageOpt("target-image", None)
		]
	)

	def __init__(self):
		cziso.commands.Command.__init__(self)
		self.file = __file__

	def run(self, config, args):
		arg_vals = self.parse_args(args)

		cziso.abort_if_no_x()
		image = cziso.image.Image.factory(arg_vals["image"])
		target_image = None
		if arg_vals["target-image"] is not None:
			target_image = cziso.image.Image.factory(arg_vals["target-image"])
		if not image.exists():
			cziso.abort("Image %s does not exists" % image)
		cz = cziso.clonezilla.Clonezilla(config)
		cz.modify_image(image, target_image)