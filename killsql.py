# fujisan.py
# ----------
# FDIA clone by isak.asia
#
# dependencies: pymssql, pillow

import os
import time
import shutil # for rmtree
import pymssql # MS SQL connection support
from collections import namedtuple
from PIL import Image # Pillow library
import fujirawimage # custom Pillow decoder

# configuration
tmp = "/tmp/fuji/" # working path for mounts, trailing slash please
outdir = "/Users/Svartlab/Documents/Frontier/Ready" # output path

win2000host = "10.0.1.166" # mssql / smb share host

# user/pass for MS SQL server
mssqluser = "svartlab"
mssqlpass = "1234"

# generate today's date for folders
datestr = time.strftime("%Y%m%d")

# logging function, disable to be less verbose
def log(what):
	print time.strftime("%Y-%m-%d %H:%M:%S " + str(what))
	return

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

# image export function, takes list of "image" named tuples, ordername string, extension string and path string
def exportimages(exportimages, ordername, extension = ".tif", path = outdir):
	# generate path for order export
	newdir = path + "/" + datestr + "-" + ordername + "/"
	# check if existing, otherwise create
	if not os.path.isdir(newdir):
		os.makedirs(newdir)

	# loop through images
	for image in exportimages:
		# try to open the image file
		try:
			im = Image.open(tmp + image.imgfile)
		except IOError as e:
			log("I/O error({0}): {1}".format(e.errno, e.strerror))

		# backup frame number in case none was found
		frame = image.id.zfill(3)

		if image.frame:
			frame = image.frame
			if not frame.endswith("A"):
				frame += "F"
			frame = frame.zfill(3)

			
		# generate filename with date, order name and frame number (zero padded)
		filename = newdir + datestr + "-" + ordername + "-" + frame

		# rotate according to setting in scanner
		out = im.rotate(image.rotation, expand = True)

		log("exporting " + filename + extension)

		# check if file already exists, if it does add the id at the end (loop until unique filename created)
		while os.path.isfile(filename + extension):
			filename += "-" + image.id.zfill(2)

		# save file
		out.save(filename + extension, dpi=(300, 300))

	return

# connect to MS SQL database
sqlconn = pymssql.connect(win2000host, mssqluser, mssqlpass, "FDIA_DB")
	
# create named tuple classes for orders and images
orderclass = namedtuple("order", ["id", "name", "status", "inffile", "cdorder"])
imageclass = namedtuple("image", ["id", "imgfile", "inffile", "rotation", "frame"])

# reset list of orders waiting to be converted
orders = []

cursor = sqlconn.cursor(as_dict = True)

# retrieve all orders
cursor.execute("SELECT o.FDIAManageID as id, o.OrderID as name, o.Status as status, o.InfFileName as inffile, other.FilePath as cdorder FROM dbo.OrderTable o, dbo.OtherTable other WHERE o.FDIAManageID = other.FDIAManageID")

# loop through rows
for row in cursor:
	# append to order list
	log("appending " + str(row["id"]))
	orders.append(orderclass(str(row["id"]), row["name"], row["status"], osxpath(row["inffile"]), osxpath(row["cdorder"])))

# loop through orders
for order in orders:
	log(order)

	# is there a CdOrder.INF file? use it to fetch image rotation data and actual frame numbers (read from the film)
	cdorder = []
	if order.cdorder and os.path.isfile(tmp + order.cdorder):
		# open CdOrder.INF file
		f = file(tmp + order.cdorder, "rU") # universal newline mode for DOS file support
		# read the whole file and split into lines
		lines = f.read().split("\n") 
		for l in lines:
			# fetch all lines beginning with "Frame"
			if l.startswith("Frame"):
				# strip them of some aesthetics
				l = l.replace("[", "").replace("]", "").split(" ")[1::] 
				# ...and append to the list
				cdorder.append((int(l[0]), int(l[1]), l[2])) 
		f.close()

	# fetch SQL image data
	cursor.execute(	"SELECT	o.ImageID as id, o.FileName as imgfile, i.InfFileName as inffile "
				"FROM dbo.OutputImageTable o, dbo.InputImageTable i "
				"WHERE o.FDIAManageID = " + order.id + " "
				"AND i.FDIAManageID = o.FDIAManageID "
				"AND i.ImageID = o.ImageID" )

	# reset image list
	images = []

	# loop through SQL data att poll the list
	for row in cursor:
		# standard rotation and frame in case none was found
		rotation = 270
		frame = "00"

		# loop through data from CdOrder.inf
		for cd in cdorder:
			if cd[0] == int(os.path.basename(osxpath(row["inffile"])).replace(".INF", "")):
				rotation = [0, 270, 0, 180, 0][cd[1]]
				frame = cd[2]

		# add to image list
		images.append(imageclass(str(row["id"]), osxpath(row["imgfile"]), osxpath(row["inffile"]), rotation, frame))

	# for debugging
	log(images)

	# what status does the current order have? proceed accordingly
	#
	# (0 = Error, 2 = Waiting to convert)
	# (4 = Waiting to write, 5 = Completed)

	# if waiting to convert, export the files and change status into 5 (completed)
	if order.status == 2:
		exportimages(images, order.name, ".tif")

		# change status of order to completed in DB
		cursor.execute("UPDATE dbo.OrderTable SET Status = 5 WHERE FDIAManageID = '" + order.id + "'")

		# commit SQL changes to database
		log("sqlconn.commit()")
		sqlconn.commit()

	# if completed, remove the order and files
	elif order.status > 3:

		# find unique folders associated with current order (reset the set of directories first)
		orderdirs = set()

		# add each path name to image or .INF file, set() eliminates duplicates
		for image in images:
			orderdirs.add(os.path.dirname(image.imgfile))
			orderdirs.add(os.path.dirname(image.inffile))

		orderdirs.add(os.path.dirname(order.cdorder))

		# remove images associated with order in DB
		cursor.execute("DELETE FROM dbo.ImageTable WHERE FDIAManageID = '" + order.id + "'")
		cursor.execute("DELETE FROM dbo.InputImageTable WHERE FDIAManageID = '" + order.id + "'")
		cursor.execute("DELETE FROM dbo.OutputImageTable WHERE FDIAManageID = '" + order.id + "'")
		cursor.execute("DELETE FROM dbo.OutputEzTable WHERE FDIAManageID = '" + order.id + "'")
		cursor.execute("DELETE FROM dbo.OtherTable WHERE FDIAManageID = '" + order.id + "'")
		cursor.execute("DELETE FROM dbo.Old_convertInformationTable WHERE FDIAManageID = '" + order.id + "'")

		log("DELETE FROM dbo.*Table WHERE FDIAManageID = " + order.id)

		# remove order in DB
		cursor.execute("DELETE FROM dbo.OrderTable WHERE FDIAManageID = '" + order.id + "'")

		# commit SQL changes to database
		log("sqlconn.commit()")
		sqlconn.commit()

		# remove order .INF file
		if os.path.isfile(tmp + order.inffile):
			log("os.remove(" + tmp + order.inffile + ")")
			os.remove(tmp + order.inffile)

		# loop through & remove the folders in InSpool and OutSpool
		for d in orderdirs:
			if os.path.isdir(tmp + d):
				log("shutil.rmtree(" + tmp + d + ")")
				shutil.rmtree(tmp + d)

	# end of orders loop

sqlconn.close()		
