from flask import Flask, flash, render_template
app = Flask(__name__)

@app.route("/")
def orderlist():
	# connect to DB
	# show orders

	# hmmm, store converted orders to be shown??

	# or look through images??? hmmm

	return render_template("orderlist.html")

@app.route("/log")
def log():
	return "looog"	

if __name__ == "__main__":
	app.debug = True
	app.run()
