import cziso.commands
import cziso.clonezilla
import cziso.image
import cziso.virtualmachine
from cziso.commands import CommonArgs, ImageArg


class Command(cziso.commands.Command):
	usage = CommonArgs(
		"""
		Start a VM with selected image and open up a VNC console to the
		VM instance.  Will destroy VM instance once VNC console is closed so
		should only be used for verification of the VM.
		Currently requires X forwarding enabled in order to run vncviewer.
		""",
		[
			ImageArg("image")
		],
		[

		]
	)

	def __init__(self):
		cziso.commands.Command.__init__(self)
		self.file = __file__

	def run(self, config, args):
		arg_vals = self.parse_args(args)

		cziso.abort_if_no_x()
		image = cziso.image.Image.factory(arg_vals["image"])
		if not image.exists():
			cziso.abort("Input image %s does not exists" % in_image)
		cz = cziso.clonezilla.Clonezilla(config)
		cz.test_image(image)