'''
Created on 4 Jul 2018

@author: jleedham
'''
import logging
from simplejson.scanner import JSONDecodeError
from flask.helpers import send_from_directory
logging.basicConfig(level=logging.DEBUG)
from flask import Flask, render_template, make_response, redirect, url_for, request, abort

import requests
import json
import os
from arcapix.config import config

application = Flask("Signiant Interop")

signiantserver = config.get('arcapix.signitantinterop.server','https://api.mediashuttle.com/v1/portals/')

restserver = config.get('arcapix.management.server.url','http://localhost/')+"/files"

apikey = config.get('arcapix.signiantinterop.apikey', 'GET FROM CONFLUENCE')

portal = config.get('arcapix.signiantinterop.portalkey','GET FROM CONFLUENCE')

def makeurl(package=None, tail=''):
    base = signiantserver + "/" + portal + "/packages"
    if package:
        base = base + "/" + package
    if tail:
        base = base + "/" + tail
    return base

def makefilejson(filenames):
    return [{
                "path" : x,
    #            "size" : os.lstat(filename).st_size # Also verifies that it can be seen by the user
                "isDirectory" : False
            } for x in filenames if os.path.exists(x)]
    

def get_existing_files(package):
    resp = requests.get(makeurl(package, "files"), headers=auth())
    if resp.status_code!=200:
        abort(resp.status_code, resp.json()['message'])
    return [x['path'] for x in resp.json()['files']]

def auth():
    return { "authorization" : apikey }

def abort_if_error(resp):
    if resp.status_code>=200 and resp.status_code<300:
        return
    logging.error(resp.text)
    try:
        message =   resp.json()['message']
    except JSONDecodeError:
        message = resp.text
    abort(resp.status_code, message)     

@application.route("/")
def documentation():
    return 'TODO'

@application.route("/signiantinterop/")
def process_clear():
    resp = make_response(render_template("cleared.html"))
    resp.set_cookie("signiantinterop.packagetoken",'')
    resp.set_cookie("signiantinterop.files",'')
    return resp

@application.route("/signiantinterop/<path:filename>", methods=['POST'])
def process_newpackage(filename):
    a = auth()
    resp = requests.post(makeurl(), headers=a, data= { 'portalId' : portal })
    abort_if_error(resp)
    package = resp.json()['id']
    files = "/"+filename
    resp = make_response(render_template("add_or_checkout.html", files=files))
    resp.set_cookie('signiantinterop.packagetoken', package)
    resp.set_cookie('signiantinterop.files',files)
    return resp
        
@application.route("/signiantinterop/<path:filename>")
def process(filename):
    # Steps
    # See if we have a package token in the cookie
    filename = os.path.join("/", filename)
    package = request.cookies.get('signiantinterop.packagetoken', None) # Default random package
    files = request.cookies.get('signiantinterop.files',"") # SHould pickle/unpickle/base64
    
    if package:
        files = ",".join(set(files.split(",") + [filename]))
        resp = make_response(render_template("add_or_checkout.html", files=([files] if len(files.split(","))==1 else files.split(","))))
        resp.set_cookie('signiantinterop.files',files)
        return resp
    # If so, POST the file to the package, and present "Add More or Checkout form"
    else:
    # If not, allow user to create new package with form.
        return render_template("new_package.html", filename=filename)

@application.route("/signiantinterop/checkout")
def process_checkout_page():
    package = request.cookies.get('signiantinterop.packagetoken','6OAv1SisnJJaQdHgZ8xa43') # Default random package
    files = request.cookies.get('signiantinterop.files',"") # SHould pickle/unpickle/base64
    return render_template("checkout.html", files=files.split(","), package=package)

@application.route("/signiantinterop/checkout", methods=['POST'])
def process_checkout():
    package = request.cookies.get('signiantinterop.packagetoken','6OAv1SisnJJaQdHgZ8xa43') # Default random package
    files = request.cookies.get('signiantinterop.files') # SHould pickle/unpickle/base64
    if not files:
        abort("Cannot checkout with no files")
    data={ 'portalId' : portal, 'packageId' : package, 'files' : makefilejson(files.split(","))}
    logging.info("Data about to send is %r" % data)
    resp = requests.put(makeurl(package,"files"), headers=auth(),json=data)
 #   abort_if_error(resp)
    data = {
        "user" : { "email" : request.form['email'] },
        "grants" : [ "download"],
        }
    logging.info("Data to be sent is %r" % data)
    resp = requests.post(makeurl(package, "tokens"), headers=auth(), json=data)
    abort_if_error(resp)
    resp = make_response(render_template("package_sent.html", url = resp.json()['url'], token=resp.json()['id']))
    resp.set_cookie("signiantinterop.packagetoken",'')
    resp.set_cookie("signiantinterop.files",'')
    return resp
    
@application.route("/signiantinterop/", methods=['POST', 'GET'])
def process_new_package():

    if request.type=='POST':
        r = requests.post(makeurl(), data={ 'portalId' : portal})
        
        cookie = r.json()['id']
        resp = make_response(redirect(url_for('process')))
        resp.set_cookie('signiantinterop.packagetoken',cookie)
        return resp
    else:
        render_template("new_package.html")
        

@application.route('/public/<path:path>')
def send_js(path):
    return send_from_directory('public', path)    
    
if __name__ == '__main__':
    application.run(debug=True, host="0.0.0.0", port=8000)