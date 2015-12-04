from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, make_response, abort
from flask import session as login_session
from flask.ext.seasurf import SeaSurf
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
from sqlalchemy import create_engine, MetaData, Table, desc
from sqlalchemy.orm import sessionmaker
from sqlalchemy_imageattach.stores.fs import FileSystemStore
from sqlalchemy_imageattach.context import store_context, push_store_context, pop_store_context
from urllib2 import urlopen
from werkzeug import secure_filename

import datetime
import os
import random
import string
import httplib2
import json
import requests

from database_setup import Base, User, UserImg, Antibody, Cytotoxin, AntibodyImg, AntibodyLot, CytotoxinImg, CytotoxinLot, Adc, AdcLot, AdcImg

UPLOAD_FOLDER = '/uploads'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif', 'bmp'])

app = Flask(__name__)
csrf = SeaSurf(app)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Biologics Catalog"

fs_store = FileSystemStore(
    path='static/images/',
    base_url='http://localhost:5000/static/images/')

engine = create_engine('sqlite:///biologicscatalog.db')
Base.metadata.bind = engine
meta = MetaData(bind=engine)
DBSession = sessionmaker(bind=engine)
session = DBSession()

# Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = ''.join(
        random.choice(string.ascii_uppercase + string.digits) for x in range(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)

@csrf.exempt
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code, now compatible with Python3
    request.get_data()
    code = request.data.decode('utf-8')

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    # Submit request, parse response - Python3 compatible
    h = httplib2.Http()
    response = h.request(url, 'GET')[1]
    str_response = response.decode('utf-8')
    result = json.loads(str_response)

    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    params = {'access_token': access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['email'])
    return output

# User Helper Functions

def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    attach_picture_url(User, user.id, login_session['picture'])
    return user.id

def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user

def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

# DISCONNECT - Revoke a current user's token and reset their login_session
@csrf.exempt
@app.route('/gdisconnect')
def gdisconnect():
        # Only disconnect a connected user.
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] == '200':
        # Reset the user's sesson.
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']

        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response

# Making an XML Endpoint
@app.route('/<dbtype>/xml')
def collections(dbtype):
    collections=session.query(eval(dbtype.capitalize())).all()
    return render_template('collections.xml', dbtype=dbtype, collections=collections)

@app.route('/<dbtype>/lot/xml')
def collectionLots(dbtype):
    collections=session.query(eval(dbtype.capitalize()+'Lot')).all()
    return render_template('collections-lot.xml', dbtype=dbtype, collections=collections)

# Making an JSON Endpoint (GET Request)
@app.route('/antibody/JSON')
def antibodyJSON():
    antibodies=session.query(Antibody).all()
    return jsonify(Antibodies=[i.serialize for i in antibodies])

@app.route('/cytotoxin/JSON')
def cytotoxinJSON():
    cytotoxins=session.query(Cytotoxin).all()
    return jsonify(Cytotoxins=[i.serialize for i in cytotoxins])

@app.route('/adc/JSON')
def adcJSON():
    adcs=session.query(Adc).all()
    return jsonify(Adcs=[i.serialize for i in adcs])

@app.route('/antibody/lot/JSON')
def antibodyLotJSON():
    lots=session.query(AntibodyLot).all()
    return jsonify(Antibody_Lots=[i.serialize for i in lots])

@app.route('/cytotoxin/lot/JSON')
def cytotoxinLotJSON():
    lots=session.query(CytotoxinLot).all()
    return jsonify(Cytotoxin_Lots=[i.serialize for i in lots])

@app.route('/adc/lot/JSON')
def adcLotJSON():
    lots=session.query(AdcLot).all()
    return jsonify(Adc_Lots=[i.serialize for i in lots])

@app.route('/')
@app.route('/home')
def home():
    email, loggedIn = None, False
    if 'email' in login_session:
        email=login_session['email']
        loggedIn=True
    return render_template('home.html', title='Home', email=email, loggedIn=loggedIn)

@app.route('/antibody/')
def antibody():
    email, userID, loggedIn = None, None, False
    if 'email' in login_session:
        email=login_session['email']
        userID=getUserID(login_session['email'])
        loggedIn=True
    antibodies=session.query(Antibody).order_by(Antibody.name).all()
    lots=session.query(AntibodyLot).all()
    lotdict={}
    for x in range(1,session.query(Antibody).count()+1):
        lotdict[x]=session.query(AntibodyLot).filter(AntibodyLot.antibody_id==x).order_by(AntibodyLot.date).all()
    return render_template('antibody.html', title='Antibody',
                           antibodies=antibodies, lotdict=lotdict, lots=lots,
                           userID=userID, email=email, loggedIn=loggedIn)

@app.route('/<dbtype>/img/<int:item_id>/')
def get_picture_url(dbtype, item_id):
    item=session.query(eval(dbtype.capitalize())).filter_by(id=item_id).one()
    with store_context(fs_store):
        try:
            picture_url = item.picture.locate()
        except IOError:
            print "No picture found for lot# %s" % str(item_id)
            picture_url=''
    return render_template('img.html',item=item, picture_url=picture_url, dbtype=dbtype)

@app.route('/cytotoxin/')
def cytotoxin():
    email, userID, loggedIn = None, None, False
    if 'email' in login_session:
        email=login_session['email']
        userID=getUserID(login_session['email'])
        loggedIn=True
    cytotoxins=session.query(Cytotoxin).order_by(Cytotoxin.name).all()
    lots=session.query(CytotoxinLot).all()
    lotdict={}
    for x in range(1,session.query(Cytotoxin).count()+1):
        lotdict[x]=session.query(CytotoxinLot).filter(CytotoxinLot.cytotoxin_id==x).order_by(CytotoxinLot.date).all()
    return render_template('cytotoxin.html', title='Cytotoxin',
                           cytotoxins=cytotoxins, lotdict=lotdict, lots=lots,
                           userID=userID, email=email, loggedIn=loggedIn)

@app.route('/adc/')
def adc():
    email, userID, loggedIn = None, None, False
    if 'email' in login_session:
        email=login_session['email']
        userID=getUserID(login_session['email'])
        loggedIn=True
    adcs=session.query(Adc).order_by(Adc.name).all()
    lots=session.query(AdcLot).all()
    lotdict={}
    for x in range(1,session.query(Adc).count()+1):
        lotdict[x]=session.query(AdcLot).filter(AdcLot.adc_id==x).order_by(AdcLot.date).all()
    return render_template('adc.html', title='ADC', adcs=adcs, lotdict=lotdict,
                           lots=lots, userID=userID, email=email, loggedIn=loggedIn)

@app.route('/<dbtype>/create', methods=['GET','POST'])
def createType(dbtype):
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. Please sign in first.')
        return redirect(url_for(dbtype))
    table=Table(dbtype, meta, autoload=True, autoload_with=engine)
    user_id=getUserID(login_session['email'])
    if request.method == 'POST':
        if dbtype == 'antibody':
            new=eval(dbtype.capitalize())(name=request.form['name'],
                                          weight=request.form['weight'],
                                          target=request.form['target'],
                                          user_id=user_id)
        elif dbtype == 'cytotoxin':
            new=eval(dbtype.capitalize())(name=request.form['name'],
                                          weight=request.form['weight'],
                                          drugClass=request.form['drugClass'],
                                          user_id=user_id)
        else:
            new=eval(dbtype.capitalize())(name=request.form['name'],
                                          chemistry=request.form['chemistry'],
                                          user_id=user_id)
        session.add(new)
        session.commit()
        flash('%s Created' % dbtype.capitalize())
        image=request.files['picture']
        if image and allowed_file(image.filename):
            with store_context(fs_store):
                new.picture.from_file(image)
            return redirect(url_for(dbtype))
        else:
            flash('Unsupported file detected. No image has been uploaded.')
            return redirect(url_for(dbtype))
    else:
        return render_template('create-type.html', columns=table.columns, dbtype=dbtype)

@app.route('/<dbtype>/<int:item_id>/create/', methods=['GET','POST'])
def createTypeLot(dbtype, item_id):
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. Please sign in first.')
        return redirect(url_for(dbtype))
    table=Table('%s_lot' %dbtype, meta, autoload=True, autoload_with=engine)
    maxablot=session.query(AntibodyLot).order_by(desc(AntibodyLot.id)).first().id
    maxtoxinlot=session.query(CytotoxinLot).order_by(desc(CytotoxinLot.id)).first().id
    originID=session.query(eval(dbtype.capitalize())).filter_by(id=item_id).one().user_id
    user_id=getUserID(login_session['email'])
    if request.method == 'POST':
        if dbtype == 'antibody':
            new=AntibodyLot(date=datetime.datetime.strptime(request.form['date'].replace('-',' '), '%Y %m %d'),
                            aggregate=request.form['aggregate'],
                            endotoxin=request.form['endotoxin'],
                            concentration=request.form['concentration'],
                            vialVolume=request.form['vialVolume'],
                            vialNumber=request.form['vialNumber'],
                            antibody_id=item_id,
                            user_id=user_id)
        elif dbtype == 'cytotoxin':
            new=CytotoxinLot(date=datetime.datetime.strptime(request.form['date'].replace('-',' '), '%Y %m %d'),
                             purity=request.form['purity'],
                             concentration=request.form['concentration'],
                             vialVolume=request.form['vialVolume'],
                             vialNumber=request.form['vialNumber'],
                             cytotoxin_id=item_id,
                             user_id=user_id)
        else:
            new=AdcLot(date=datetime.datetime.strptime(request.form['date'].replace('-',' '), '%Y %m %d'),
                       aggregate=request.form['aggregate'],
                       endotoxin=request.form['endotoxin'],
                       concentration=request.form['concentration'],
                       vialVolume=request.form['vialVolume'],
                       vialNumber=request.form['vialNumber'],
                       antibodylot_id=request.form['antibodylot_id'],
                       cytotoxinlot_id=request.form['cytotoxinlot_id'],
                       adc_id=item_id,
                       user_id=user_id)
        session.add(new)
        session.commit()
        flash('%s Lot Created' %dbtype.capitalize())
        return redirect(url_for(dbtype))
    else:
        return render_template('create-type-lot.html', dbtype=dbtype,
                               columns=table.columns, item_id=item_id,
                               maxablot=maxablot, maxtoxinlot=maxtoxinlot,
                               originID=originID,
                               userID=getUserID(login_session['email']))

@app.route('/<dbtype>/<int:item_id>/edit', methods=['GET','POST'])
def editType(dbtype, item_id):
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. Please sign in first.')
        abort(401)
    editedItem = session.query(eval(dbtype.capitalize())).filter_by(id=item_id).one()
    if login_session['user_id'] != editedItem.user_id:
        flash('You are not authorized to modify items you did not create. Please create your own item in order to modify it.')
        return redirect(url_for(dbtype))
    table=Table(dbtype, meta, autoload=True, autoload_with=engine)
    if request.method == 'POST':
        for column in table.columns:
            if column.name in ('id','user_id'):
                pass
            else:
                setattr(editedItem, column.name, request.form[column.name])
        session.add(editedItem)
        session.commit()
        flash('%s Edited' % dbtype.capitalize())
        image=request.files['picture']
        if image and allowed_file(image.filename):
            with store_context(fs_store):
                editedItem.picture.from_file(image)
            return redirect(url_for(dbtype))
        else:
            flash('Unsupported file detected. No image has been uploaded.')
            return redirect(url_for(dbtype))
    else:
        return render_template('edit-type.html', dbtype=dbtype,
                               columns=table.columns, item_id=item_id,
                               editedItem=editedItem)

@app.route('/<dbtype>/lot/<int:item_id>/edit', methods=['GET','POST'])
def editTypeLot(dbtype, item_id):
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. Please sign in first.')
        abort(401)
    editedItem = session.query(eval(dbtype.capitalize()+'Lot')).filter_by(id=item_id).one()
    if login_session['user_id'] != editedItem.user_id:
        flash('You are not authorized to modify items you did not create. Please create your own item in order to modify it.')
        return redirect(url_for(dbtype))
    table=Table('%s_lot' % dbtype, meta, autoload=True, autoload_with=engine)
    maxablot=session.query(AntibodyLot).order_by(desc(AntibodyLot.id)).first().id
    maxtoxinlot=session.query(CytotoxinLot).order_by(desc(CytotoxinLot.id)).first().id
    if request.method == 'POST':
        editedItem.date=datetime.datetime.strptime(request.form['date'].replace('-',' '), '%Y %m %d')
        for column in table.columns:
            if column.name in ('id', 'date', 'antibody_id', 'cytotoxin_id', 'adc_id','user_id'):
                pass
            else:
                setattr(editedItem, column.name, request.form[column.name])
        session.add(editedItem)
        session.commit()
        flash('%s Lot Edited'% dbtype.capitalize())
        return redirect(url_for(dbtype))
    else:
        return render_template('edit-type-lot.html', dbtype=dbtype,
                               columns=table.columns, item_id=item_id,
                               editedItem=editedItem, maxablot=maxablot,
                               maxtoxinlot=maxtoxinlot)

@app.route('/<dbtype>/<int:item_id>/delete/', methods=['GET','POST'])
def delete(dbtype, item_id):
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. Please sign in first.')
        abort(401)
        # if dbtype[-3:].lower() == 'lot':
        #     return redirect(url_for(dbtype[:-3]))
        # else:
        #     return redirect(url_for(dbtype))
    deleteItem=session.query(eval(dbtype[0].upper()+dbtype[1:])).filter_by(id=item_id).one()
    if login_session['user_id'] != deleteItem.user_id:
        flash('You are not authorized to modify items you did not create. Please create your own item in order to modify it.')
        return redirect(url_for(dbtype))
    if request.method == 'POST':
        session.delete(deleteItem)
        session.commit()
        if dbtype[-3:].lower() == 'lot':
            flash('%s Lot Deleted' % dbtype[:-3].capitalize())
            return redirect(url_for(dbtype[:-3]))
        else:
            flash('%s  Deleted' % dbtype.capitalize())
            return redirect(url_for(dbtype))
    else:
        pass

@app.errorhandler(401)
def access_denied(e):
    return render_template('401.html'), 401

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.before_request
def start_implicit_store_context():
    push_store_context(fs_store)

@app.teardown_request
def stop_implicit_store_context(exception=None):
    pop_store_context()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

def attach_picture(table, item_id, location):
    try:
        item=session.query(table).filter_by(id=item_id).one()
        with store_context(fs_store):
            with open(location,'rb') as f:
                item.picture.from_file(f)
                session.commit()
    except Exception:
        session.rollback()
        raise

def attach_picture_url(table, item_id, location):
    try:
        item=session.query(table).filter_by(id=item_id).one()
        with store_context(fs_store):
            item.picture.from_file(urlopen(location))
            session.commit()
    except Exception:
        session.rollback()
        raise

def delete_picture(table, item_id):
    item=session.query(table).filter_by(id=item_id).one()
    fs_store.delete(item.picture.original)
    session.commit()

if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
