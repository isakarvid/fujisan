# fujisan.py
# ----------
# FDIA clone by isak.asia
#
# dependencies: pymssql, pillow

import os
import time
import shutil
import pymssql
from collections import namedtuple
from PIL import Image # Pillow library
import fujirawimage # custom Pillow decoder

# configuration
tmp = "/tmp/fuji/" # working path for mounts, trailing slash please
outdir = "/Users/Svartlab/Documents/Frontier/Ready" # output path

win2000host = "10.0.1.15" # mssql / smb share host

mssqluser = "svartlab"
mssqlpass = "1234"

datestr = time.strftime("%Y%m%d") # today's date

# windows to OS X path conversion
def osxpath(win2000path):
	return win2000path.replace("\\", "/").replace("//WIN2000/", "")

# mount inspool if not mounted	
inspool = tmp + "InSpool"
if not os.path.ismount(inspool):
	if not os.path.isdir(inspool):
		os.makedirs(inspool)
	os.system("mount_smbfs //FRONTIER:FRONTIER@" + win2000host + "/InSpool " + inspool);

# mount outspool if not mounted
outspool = tmp + "OutSpool"
if not os.path.ismount(outspool):
	if not os.path.isdir(outspool):
		os.makedirs(outspool)
	os.system("mount_smbfs //FRONTIER:FRONTIER@" + win2000host + "/OutSpool " + outspool);

# create output directory if not existing
if not os.path.isdir(outdir):
	os.makedirs(outdir)

# create working directory if not existing
if not os.path.isdir(tmp):
	os.makedirs(tmp)

def exportimages(images, ordername, extension = ".tif", path = outdir):
	newdir = path + "/" + datestr + "-" + ordername + "/"
	if not os.path.isdir(newdir):
		os.makedirs(newdir)

	for image in images:
		try:
			im = Image.open(tmp + image.imgfile)
		except IOError as e:
			print "I/O error({0}): {1}".format(e.errno, e.strerror)

		filename = newdir + datestr + "-" + ordername + "-" + image.frame

		# rotate according to setting in scanner
		out = im.rotate(image.rotation, expand = True)

		print "exporting " + filename + extension

		# check if file already exists
		if os.path.isfile(filename + extension):
			filename += "-" + image.id.zfill(2)

		out.save(filename + extension)

# connect to MS SQL database
with pymssql.connect(win2000host, mssqluser, mssqlpass, "FDIA_DB") as conn:
		
	# reset list of orders waiting to be converted
	orderclass = namedtuple("order", ["id", "name", "status", "inffile", "cdorder"])
	imageclass = namedtuple("image", ["id", "imgfile", "inffile", "rotation", "frame"])
	orders = []

	with conn.cursor(as_dict = True) as c:

		# retrieve all orders
		c.execute("SELECT o.FDIAManageID as id, o.OrderID as name, o.Status as status, o.InfFileName as inffile, other.FilePath as cdorder FROM dbo.OrderTable o, dbo.OtherTable other")

		# loop through rows
		for row in c:
			# append to order list
			orders.append(orderclass(str(row["id"]), row["name"], row["status"], osxpath(row["inffile"]), osxpath(row["cdorder"])))


		# loop through orders
		for order in orders:
			print order

			# is there a CdOrder.INF file? use it to fetch rotation and actual frame numbers
			cdorder = []
			if order.cdorder:
				f = file(tmp + order.cdorder, "rU")
				lines = f.read().split("\n")[1:-3]
				for l in lines:
					l = l.replace("[", "").replace("]", "").split(" ")[1::]
					cdorder.append((int(l[0]), int(l[1]), l[2]))
				
			c.execute(	"SELECT	o.ImageID as id, o.FileName as imgfile, i.InfFileName as inffile "
						"FROM dbo.OutputImageTable o, dbo.InputImageTable i "
						"WHERE o.FDIAManageID = " + order.id + " "
						"AND i.FDIAManageID = o.FDIAManageID "
						"AND i.ImageID = o.ImageID" )

			images = []
			for row in c:
				rotation = None
				frame = None
				for cd in cdorder:
					if cd[0] == row["id"]:
						rotation = [0, 270, 0, 0, 180][cd[1]]
						frame = cd[2]
				images.append(imageclass(str(row["id"]), osxpath(row["imgfile"]), osxpath(row["inffile"]), rotation, frame))

			print images

			# (0 = Error, 2 = Waiting to convert)
			# (4 = Waiting to write, 5 = Completed)
	
			# if waiting to convert
			if order.status == 2:
				exportimages(images, order.name, ".tif")

				# change status of order to completed in DB
				c.execute("UPDATE dbo.OrderTable SET Status = 5 WHERE FDIAManageID = '" + order.id + "'")

			# if completed, remove
			elif order.status == 25:

				exportimages(images, order.name, ".tif", "/tmp/BACKUP")

				# find unique folders associated with current order
				orderdirs = set()

				# add each path name to image or .INF file, set() eliminates duplicates
				for image in images:
					orderdirs.add(os.path.dirname(image.imgfile))
					orderdirs.add(os.path.dirname(image.inffile))

				# loop through & remove the folders
				for d in orderdirs:
					print "rm -rf " + tmp + d
					if os.path.isdir(tmp + d):
						shutil.rmtree(tmp + d)

				# remove images associated with order in DB
				c.execute("DELETE FROM dbo.ImageTable WHERE FDIAManageID = '" + order.id + "'")
				c.execute("DELETE FROM dbo.InputImageTable WHERE FDIAManageID = '" + order.id + "'")
				c.execute("DELETE FROM dbo.OutputImageTable WHERE FDIAManageID = '" + order.id + "'")
				c.execute("DELETE FROM dbo.OutputEzTable WHERE FDIAManageID = '" + order.id + "'")
				c.execute("DELETE FROM dbo.OtherTable WHERE FDIAManageID = '" + order.id + "'")
				c.execute("DELETE FROM dbo.Old_convertInformationTable WHERE FDIAManageID = '" + order.id + "'")
				print "DELETE FROM dbo.xxxTable WHERE FDIAManageID = " + order.id

				# remove order in DB
				c.execute("DELETE FROM dbo.OrderTable WHERE FDIAManageID = '" + order.id + "'")

				# remove order .INF file
				if os.path.isfile(tmp + order.inffile):
					print "os.remove(" + tmp + order.inffile + ")"
					os.remove(tmp + order.inffile)

			# commit SQL changes to database
			conn.commit()
