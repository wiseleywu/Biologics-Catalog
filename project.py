import os
import random
import string
import httplib2
import json
import requests
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from flask import jsonify, send_from_directory, make_response, abort
from flask import session as login_session
from flask.ext.seasurf import SeaSurf

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError

from sqlalchemy import create_engine, MetaData, Table, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy_imageattach.stores.fs import FileSystemStore
from sqlalchemy_imageattach.context import store_context, push_store_context
from sqlalchemy_imageattach.context import pop_store_context

from urllib2 import urlopen

from werkzeug import secure_filename

from database_setup import Base, User, UserImg, Antibody, Cytotoxin
from database_setup import AntibodyImg, AntibodyLot
from database_setup import CytotoxinImg, CytotoxinLot, Adc, AdcLot, AdcImg

# Global variables
APPLICATION_NAME = "Biologics Catalog"
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif', 'bmp'])

app = Flask(__name__)
# Using SeaSurf, a flask extension, to implement protection against CSRF
csrf = SeaSurf(app)

# UPLOAD_FOLDER = '/uploads'
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']

# Location of where the pictures will be uploaded and their web url
fs_store = FileSystemStore(
    path='static/images/',
    base_url='http://localhost:5000/static/images/')

# Setting up postgres Database and SQL Alchemy's ORM
engine = create_engine(
    'postgresql://postgres:biologics@localhost/biologics-catalog')
# engine = create_engine('sqlite:///biologicscatalog.db')
Base.metadata.bind = engine
meta = MetaData(bind=engine)
DBSession = sessionmaker(bind=engine)
session = DBSession()


@app.route('/login')
def showLogin():
    """Create anti-forgery state token for the login session."""
    state = ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for x in range(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@csrf.exempt
@app.route('/gconnect', methods=['POST'])
def gconnect():
    """Implement Oauth 2.0 login method with user's Google account"""
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
        response = make_response(json.dumps(
                                'Current user is already connected.'),
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
    login_session['provider'] = 'google'

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
    flash("You are now signed in as %s" % login_session['email'])
    return output


@csrf.exempt
@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    """Implement Oauth 2.0 login method with user's Facebook account"""
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data
    print "access token received %s " % access_token

    app_id = json.loads(open('fb_client_secrets.json', 'r').read())[
        'web']['app_id']
    app_secret = json.loads(
        open('fb_client_secrets.json', 'r').read())['web']['app_secret']
    url = 'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' % (
        app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]

    # Use token to get user info from API
    userinfo_url = "https://graph.facebook.com/v2.5/me"
    # strip expire tag from access token
    token = result.split("&")[0]

    url = 'https://graph.facebook.com/v2.5/me?%s&fields=name,id,email' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    # print "url sent for API access:%s"% url
    # print "API JSON result: %s" % result
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # The token must be stored in the login_session in order to properly logout,
    # let's strip out the information before the equals sign in our token
    stored_token = token.split("=")[1]
    login_session['access_token'] = stored_token

    # Get user picture
    url = 'https://graph.facebook.com/v2.5/me/picture?%s&redirect=0&height=200&width=200' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)

    login_session['picture'] = data["data"]["url"]

    # see if user exists
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

    flash("You are now signed in as %s" % login_session['username'])
    return output


# DISCONNECT - Revoke a current user's token and reset their login_session
@csrf.exempt
@app.route('/gdisconnect')
def gdisconnect():
    """Disconnect user's Google account"""
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

        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


@csrf.exempt
@app.route('/fbdisconnect')
def fbdisconnect():
    """Disconnect user's Facebook account"""
    facebook_id = login_session['facebook_id']
    # The access token must me included to successfully logout
    access_token = login_session['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (facebook_id, access_token)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    return "you have been logged out"


# Disconnect based on provider
@csrf.exempt
@app.route('/disconnect')
def disconnect():
    """Disconnect User's Google/Facebook account and delete any remaining
       user info
    """
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash("You have been successfully logged out.")
        return ""
    else:
        flash("You were not logged in")
        return redirect(url_for('home'))


# User Helper Functions
def createUser(login_session):
    """Create a new user in the db using user info in the login_session"""
    newUser = User(name=login_session['username'], email=login_session[
                   'email'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    attach_picture_url(User, user.id, login_session['picture'])
    return user.id


def getUserInfo(user_id):
    """Get user object in the db using its user_id"""
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    """Get user's id in the db using its e-mail address"""
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


def login_info(login_session):
    email, userID, loggedIn = None, None, False
    if 'email' in login_session:
        email = login_session['email']
        userID = getUserID(login_session['email'])
        loggedIn = True
    return (email, userID, loggedIn)


@app.route('/')
@app.route('/home')
def home():
    """Define website's homepage with both guest/ logged-in user access"""
    # email, loggedIn = None, False
    # if 'email' in login_session:
    #     email = login_session['email']
    #     loggedIn = True
    (email, userID, loggedIn) = login_info(login_session)
    return render_template('home.html', title='Home',
                           email=email, loggedIn=loggedIn)


@app.route('/antibody/')
def antibody():
    """Define website's Antibody page with both guest/ logged-in user access"""
    # email, userID, loggedIn = None, None, False
    # if 'email' in login_session:
    #     email = login_session['email']
    #     userID = getUserID(login_session['email'])
    #     loggedIn = True
    (email, userID, loggedIn) = login_info(login_session)
    antibodies = session.query(Antibody).order_by(Antibody.name).all()
    lots = session.query(AntibodyLot).all()
    lotdict = {}
    for x in range(1, session.query(Antibody).count()+1):
        lotdict[x] = (session.query(AntibodyLot)
                      .filter(AntibodyLot.antibody_id == x)
                      .order_by(AntibodyLot.date).all())
    return render_template('antibody.html', title='Antibody',
                           antibodies=antibodies, lotdict=lotdict, lots=lots,
                           userID=userID, email=email, loggedIn=loggedIn)


@app.route('/<dbtype>/img/<int:item_id>/')
def get_picture_url(dbtype, item_id):
    """Redirect stored image url within the db to an organized url for
       Antibody/Cytotoxin/Adc.html to access
    """
    item = session.query(eval(dbtype.capitalize())).filter_by(id=item_id).one()
    with store_context(fs_store):
        try:
            picture_url = item.picture.locate()
        except IOError:
            print "No picture found for lot# %s" % str(item_id)
            picture_url = ''
    return render_template('img.html', item=item,
                           picture_url=picture_url, dbtype=dbtype)


@app.route('/cytotoxin/')
def cytotoxin():
    """Define website's Cytotoxin page with both guest/ logged-in user access"""
    # email, userID, loggedIn = None, None, False
    # if 'email' in login_session:
    #     email = login_session['email']
    #     userID = getUserID(login_session['email'])
    #     loggedIn = True
    (email, userID, loggedIn) = login_info(login_session)
    cytotoxins = session.query(Cytotoxin).order_by(Cytotoxin.name).all()
    lots = session.query(CytotoxinLot).all()
    lotdict = {}
    for x in range(1, session.query(Cytotoxin).count()+1):
        lotdict[x] = (session.query(CytotoxinLot)
                      .filter(CytotoxinLot.cytotoxin_id == x)
                      .order_by(CytotoxinLot.date).all())
    return render_template('cytotoxin.html', title='Cytotoxin',
                           cytotoxins=cytotoxins, lotdict=lotdict, lots=lots,
                           userID=userID, email=email, loggedIn=loggedIn)


@app.route('/adc/')
def adc():
    """Define website's ADC page with both guest/ logged-in user access"""
    email, userID, loggedIn = None, None, False
    # if 'email' in login_session:
    #     email = login_session['email']
    #     userID = getUserID(login_session['email'])
    #     loggedIn = True
    (email, userID, loggedIn) = login_info(login_session)
    adcs = session.query(Adc).order_by(Adc.name).all()
    lots = session.query(AdcLot).all()
    lotdict = {}
    for x in range(1, session.query(Adc).count()+1):
        lotdict[x] = (session.query(AdcLot)
                      .filter(AdcLot.adc_id == x)
                      .order_by(AdcLot.date).all())
    return render_template('adc.html', title='ADC', adcs=adcs, lotdict=lotdict,
                           lots=lots, userID=userID, email=email,
                           loggedIn=loggedIn)


@app.route('/<dbtype>/create', methods=['GET', 'POST'])
def createType(dbtype):
    """Create new category (within 3 pre-defined type) in the database"""
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. '
              'Please sign in first.')
        return redirect(url_for(dbtype))
    table = Table(dbtype, meta, autoload=True, autoload_with=engine)
    user_id = getUserID(login_session['email'])
    if request.method == 'POST':
        new = eval(dbtype.capitalize())()
        for field in request.form:
            if hasattr(new, field):
                setattr(new, field, request.form[field])
        setattr(new, 'user_id', user_id)

        session.add(new)
        session.commit()
        flash('%s Created' % dbtype.capitalize())
        image = request.files['picture']
        if image and allowed_file(image.filename):
            with store_context(fs_store):
                new.picture.from_file(image)
        elif image and not allowed_file(image.filename):
            flash('Unsupported file detected. No image has been uploaded.')
        return redirect(url_for(dbtype))
    else:
        return render_template('create-type.html',
                               columns=table.columns, dbtype=dbtype)


@app.route('/<dbtype>/<int:item_id>/create/', methods=['GET', 'POST'])
def createTypeLot(dbtype, item_id):
    """Create new item within the category in the database"""
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. '
              'Please sign in first.')
        return redirect(url_for(dbtype))
    table = Table('%s_lot' % dbtype, meta, autoload=True, autoload_with=engine)
    maxablot = (session.query(AntibodyLot)
                .order_by(desc(AntibodyLot.id)).first().id)
    maxtoxinlot = (session.query(CytotoxinLot)
                   .order_by(desc(CytotoxinLot.id)).first().id)
    originID = (session.query(eval(dbtype.capitalize()))
                .filter_by(id=item_id).one().user_id)
    user_id = getUserID(login_session['email'])
    if request.method == 'POST':
        new = eval(dbtype.capitalize()+'Lot')()
        for field in request.form:
            if field == 'date':
                try:
                    setattr(new, field, datetime.strptime(request.form[field].replace('-', ' '), '%Y %m %d'))
                except ValueError as detail:
                    print 'Handling run-time error: ', detail
                    flash('Invalid date detected. Please type the date in '
                          'format: MM/DD/YYYY')
                    return redirect(url_for(dbtype))
            if hasattr(new, field):
                setattr(new, field, request.form[field])
        setattr(new, dbtype+'_id', item_id)
        setattr(new, 'user_id', user_id)
        session.add(new)
        session.commit()
        flash('%s Lot Created' % dbtype.capitalize())
        return redirect(url_for(dbtype))
    else:
        return render_template('create-type-lot.html', dbtype=dbtype,
                               columns=table.columns, item_id=item_id,
                               maxablot=maxablot, maxtoxinlot=maxtoxinlot,
                               originID=originID,
                               userID=getUserID(login_session['email']))


@app.route('/<dbtype>/<int:item_id>/edit', methods=['GET', 'POST'])
def editType(dbtype, item_id):
    """Edit the category (within 3 pre-defined type) in the database"""
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. '
              'Please sign in first.')
        abort(401)
    editedItem = (session.query(eval(dbtype.capitalize()))
                  .filter_by(id=item_id).one())
    if login_session['user_id'] != editedItem.user_id:
        flash('You are not authorized to modify items you did not create. '
              'Please create your own item in order to modify it.')
        return redirect(url_for(dbtype))
    table = Table(dbtype, meta, autoload=True, autoload_with=engine)
    if request.method == 'POST':
        for column in table.columns:
            if column.name in ('id', 'user_id'):
                pass
            else:
                setattr(editedItem, column.name, request.form[column.name])
        session.add(editedItem)
        session.commit()
        flash('%s Edited' % dbtype.capitalize())
        image = request.files['picture']
        if image and allowed_file(image.filename):
            with store_context(fs_store):
                editedItem.picture.from_file(image)
        elif image and not allowed_file(image.filename):
            flash('Unsupported file detected. No image has been uploaded.')
        return redirect(url_for(dbtype))
    else:
        return render_template('edit-type.html', dbtype=dbtype,
                               columns=table.columns, item_id=item_id,
                               editedItem=editedItem)


@app.route('/<dbtype>/lot/<int:item_id>/edit', methods=['GET', 'POST'])
def editTypeLot(dbtype, item_id):
    """Edit item within the category in the database"""
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. '
              'Please sign in first.')
        abort(401)
    editedItem = (session.query(eval(dbtype.capitalize()+'Lot'))
                  .filter_by(id=item_id).one())
    if login_session['user_id'] != editedItem.user_id:
        flash('You are not authorized to modify items you did not create. '
              'Please create your own item in order to modify it.')
        return redirect(url_for(dbtype))
    table = Table('%s_lot' % dbtype, meta, autoload=True, autoload_with=engine)
    maxablot = (session.query(AntibodyLot)
                .order_by(desc(AntibodyLot.id)).first().id)
    maxtoxinlot = (session.query(CytotoxinLot)
                   .order_by(desc(CytotoxinLot.id)).first().id)
    if request.method == 'POST':
        try:
            editedItem.date = (datetime.strptime(request.form['date'].replace('-', ' '), '%Y %m %d'))
        except ValueError as detail:
            print 'Handling run-time error: ', detail
            flash('Invalid date detected. Please type the date in '
                  'format: MM/DD/YYYY')
            return redirect(url_for(dbtype))
        for column in table.columns:
            if column.name in ('id', 'date', 'antibody_id',
                               'cytotoxin_id', 'adc_id', 'user_id'):
                pass
            else:
                setattr(editedItem, column.name, request.form[column.name])
        session.add(editedItem)
        session.commit()
        flash('%s Lot Edited' % dbtype.capitalize())
        return redirect(url_for(dbtype))
    else:
        return render_template('edit-type-lot.html', dbtype=dbtype,
                               columns=table.columns, item_id=item_id,
                               editedItem=editedItem, maxablot=maxablot,
                               maxtoxinlot=maxtoxinlot)


@app.route('/<dbtype>/<int:item_id>/delete/', methods=['GET', 'POST'])
def delete(dbtype, item_id):
    """Delete either the item or category in the database"""
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. '
              'Please sign in first.')
        abort(401)
    deleteItem = (session.query(eval(dbtype[0].upper()+dbtype[1:]))
                  .filter_by(id=item_id).one())
    if login_session['user_id'] != deleteItem.user_id:
        flash('You are not authorized to modify items you did not create. '
              'Please create your own item in order to modify it.')
        return redirect(url_for(dbtype))
    if request.method == 'POST':
        try:
            session.delete(deleteItem)
            session.commit()
        except IntegrityError as detail:
            print 'Handling run-time error: ', detail
            session.rollback()
            flash('Delete Operation Failed')
            return redirect(url_for('home'))
        if dbtype.endswith('Lot'):
            flash('%s Lot Deleted' % dbtype[:-3].capitalize())
            return redirect(url_for(dbtype[:-3]))
        else:
            flash('%s  Deleted' % dbtype.capitalize())
            return redirect(url_for(dbtype))
    else:
        pass


@app.route('/<dbtype>/xml')
def collections(dbtype):
    """Create an XML endpoint with all categories"""
    collections = session.query(eval(dbtype.capitalize())).all()
    return render_template('collections.xml', dbtype=dbtype,
                           collections=collections)


@app.route('/<dbtype>/lot/xml')
def collectionLots(dbtype):
    """Create an XML endpoint with all items within the categories available"""
    collections = session.query(eval(dbtype.capitalize()+'Lot')).all()
    return render_template('collections-lot.xml', dbtype=dbtype,
                           collections=collections)


@app.route('/antibody/JSON')
def antibodyJSON():
    """Create an JSON endpoint with all antibody categories"""
    antibodies = session.query(Antibody).all()
    return jsonify(Antibodies=[i.serialize for i in antibodies])


@app.route('/cytotoxin/JSON')
def cytotoxinJSON():
    """Create an JSON endpoint with all cytotoxin categories"""
    cytotoxins = session.query(Cytotoxin).all()
    return jsonify(Cytotoxins=[i.serialize for i in cytotoxins])


@app.route('/adc/JSON')
def adcJSON():
    """Create an JSON endpoint with all ADC categories"""
    adcs = session.query(Adc).all()
    return jsonify(Adcs=[i.serialize for i in adcs])


@app.route('/antibody/lot/JSON')
def antibodyLotJSON():
    """Create an JSON endpoint with all items within the antibody categories"""
    lots = session.query(AntibodyLot).all()
    return jsonify(Antibody_Lots=[i.serialize for i in lots])


@app.route('/cytotoxin/lot/JSON')
def cytotoxinLotJSON():
    """Create an JSON endpoint with all items within the cytotoxin categories"""
    lots = session.query(CytotoxinLot).all()
    return jsonify(Cytotoxin_Lots=[i.serialize for i in lots])


@app.route('/adc/lot/JSON')
def adcLotJSON():
    """Create an JSON endpoint with all items within the ADC categories"""
    lots = session.query(AdcLot).all()
    return jsonify(Adc_Lots=[i.serialize for i in lots])


@app.errorhandler(401)
def access_denied(e):
    """Render a 401 error page when user tries to perform unauthorized access"""
    return render_template('401.html'), 401


@app.errorhandler(404)
def page_not_found(e):
    """
    Render a 404 error page when user tries to access page that doesn't exist
    """
    return render_template('404.html'), 404


@app.before_request
def start_implicit_store_context():
    push_store_context(fs_store)


@app.teardown_request
def stop_implicit_store_context(exception=None):
    pop_store_context()


def allowed_file(filename):
    """
    Determine whether the uploaded file has an allowed file extension.
    Arg:
        filename: the uploaded file's name
    Returns:
        Boolean. True if the file extension is one of those listed under
        ALLOWED_EXTENSIONS. False if otherwise.
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


def attach_picture(table, item_id, location):
    """
    A helper function used in populator.py to upload picture to the db
    Args:
        table: The category which the picture belongs to
        item_id: The category's id number which the picture should be
                 uploaded to
        location: local directory of where the picture is found
    Returns:
        None
    """
    try:
        item = session.query(table).filter_by(id=item_id).one()
        with store_context(fs_store):
            with open(location, 'rb') as f:
                item.picture.from_file(f)
                session.commit()
    except Exception:
        session.rollback()
        raise


def attach_picture_url(table, item_id, location):
    """
    A helper function used in populator.py to upload picture to the db from web
    Args:
        table: The category which the picture belongs to
        item_id: The category's id number which the picture should be
                 uploaded to
        location: a web url of where the picture is found
    Returns:
        None
    """
    try:
        item = session.query(table).filter_by(id=item_id).one()
        with store_context(fs_store):
            item.picture.from_file(urlopen(location))
            session.commit()
    except Exception:
        session.rollback()
        raise

if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
