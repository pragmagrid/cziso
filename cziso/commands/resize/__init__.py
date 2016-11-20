import cziso.commands
import cziso.clonezilla
import cziso.image
from cziso.commands import CommonArgs, Arg, ImageArg, Opt


class Command(cziso.commands.Command):
	usage = CommonArgs(
		"""
		Resize an image using regular Clonezilla Live VM
		""",
		[
			ImageArg("in_image"),
			ImageArg("out_image"),
			Arg("size", "Size of destination image (GB)")
		],
		[
			Opt("overwrite", "Overwite current out_image", "false")
		]
	)

	def __init__(self):
		cziso.commands.Command.__init__(self)
		self.file = __file__

	def run(self, config, args):
		arg_vals = self.parse_args(args)

		in_image = cziso.image.Image.factory(arg_vals["in_image"])
		out_image = cziso.image.Image.factory(arg_vals["out_image"])
		if not in_image.exists():
			cziso.abort("Input image %s does not exists" % in_image)
		if out_image.exists():
			if not self.is_arg_true(arg_vals["overwrite"]):
				cziso.abort(
					"Output image %s already exists; use option overwrite=true to replace" % out_image)
			out_image.delete()
		out_image.create(arg_vals["size"])
		cz = cziso.clonezilla.Clonezilla(config)
		cz.resize_image(in_image, out_image)