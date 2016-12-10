import cziso.commands
from cziso.clonezilla import Clonezilla
import cziso.image
from cziso.commands import CommonArgs, Arg, ImageArg, Opt


class Command(cziso.commands.Command):
	usage = CommonArgs(
		"""
		Restore a Clonezilla VM ISO to image. 
		""",
		[
			Arg("iso", "Path to Clonezilla VM ISO"),
			ImageArg("image")

		],
		[
			Opt("overwrite", "Replace an existing image if exists", "false"),
			Opt(
				"size",
			    """Size of destination image (GB); default is original image
size but can be larger if desired""",
				"")
		]
	)

	def __init__(self):
		cziso.commands.Command.__init__(self)
		self.file = __file__

	def run(self, config, args):
		arg_vals = self.parse_args(args)

		out_img = cziso.image.Image.factory(arg_vals["image"])
		if out_img.exists() and not self.is_arg_true(arg_vals["overwrite"]):
			cziso.abort("""Image %s already exists; use overwrite=true to
replace existing image""" % out_img)
		if not out_img.exists():
			image_size = Clonezilla.parse_image_size_from_iso_filename(
				arg_vals["iso"])
			if arg_vals["size"] != "":
				if int(arg_vals["size"]) < image_size:
					cziso.abort("""Original image size is %i GB.  Please specify
an image size >= %i GB""" % (image_size, image_size))
				image_size = int(arg_vals["size"])
			if not out_img.create(image_size):
				cziso.abort("Unable to create image %s" % arg_vals["image"])

		cz = Clonezilla(config)
		cz.restore_clonezilla_iso(arg_vals["iso"], out_img)
