import os
import random
import string
import httplib2
import json
import requests
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from flask import jsonify, make_response, abort
from flask import session as login_session
from flask.ext.seasurf import SeaSurf

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError

from sqlalchemy import Table, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy_imageattach.context import store_context, push_store_context
from sqlalchemy_imageattach.context import pop_store_context

from database_setup import Base, User, Antibody, Cytotoxin, Adc
from database_setup import AntibodyLot, CytotoxinLot, AdcLot
from database_setup import UserImg, AntibodyImg, CytotoxinImg, AdcImg

from helper import allowed_file
from helper import create_user, get_user_id, login_info, set_category

from init_db import engine, meta, session

from settings import app_path, fs_store
from settings import google_client_secrets, facebook_client_secrets

# Global variables
APPLICATION_NAME = "Biologics Catalog"

app = Flask(__name__)
app.wsgi_app = fs_store.wsgi_middleware(app.wsgi_app)
# Using SeaSurf, a flask extension, to implement protection against CSRF
csrf = SeaSurf(app)


@app.route('/login')
def show_login():
    """Create anti-forgery state token for the login session."""
    state = ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for x in range(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@csrf.exempt
@app.route('/gconnect', methods=['POST'])
def google_login():
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
        oauth_flow = flow_from_clientsecrets(
            os.path.join(app_path, 'client_secrets.json'), scope='')
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
    if result['issued_to'] != google_client_secrets['web']['client_id']:
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
    user_id = get_user_id(login_session['email'])
    if not user_id:
        user_id = create_user(login_session)
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
def facebook_login():
    """Implement Oauth 2.0 login method with user's Facebook account"""
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data
    print "access token received %s " % access_token

    app_id = facebook_client_secrets['web']['app_id']
    app_secret = facebook_client_secrets['web']['app_secret']
    url = 'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' % (
        app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]

    # Use token to get user info from API
    # userinfo_url = "https://graph.facebook.com/v2.5/me"
    # strip expire tag from access token
    token = result.split("&")[0]

    url = 'https://graph.facebook.com/v2.5/me?%s&fields=name,id,email' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    print result
    # print "url sent for API access:%s"% url
    # print "API JSON result: %s" % result
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # The token must be stored in login_session in order to properly logout
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
    user_id = get_user_id(login_session['email'])
    if not user_id:
        user_id = create_user(login_session)
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
def google_logout():
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
def facebook_logout():
    """Disconnect user's Facebook account"""
    facebook_id = login_session['facebook_id']
    # The access token must me included to successfully logout
    access_token = login_session['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (
                                                facebook_id,
                                                access_token)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    print result
    return "you have been logged out"


# Disconnect based on provider
@csrf.exempt
@app.route('/disconnect')
def logout():
    """
    Disconnect User's Google/Facebook account and delete any
    remaining user info
    """
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            google_logout()
        if login_session['provider'] == 'facebook':
            facebook_logout()
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


@app.route('/')
@app.route('/home')
def home():
    """
    Define website's homepage with both guest/ logged-in user
    access
    """
    (email, user_id, logged_in) = login_info(login_session)
    return render_template('home.html', title='Home',
                           email=email, logged_in=logged_in)


@app.route('/antibody/')
def antibody():
    """
    Define website's Antibody page with both guest/ logged-in
    user access
    """
    (email, user_id, logged_in) = login_info(login_session)
    (antibodies, lot_dict, lots) = set_category('antibody')
    return render_template('antibody.html', title='Antibody',
                           antibodies=antibodies, lot_dict=lot_dict, lots=lots,
                           user_id=user_id, email=email, logged_in=logged_in)


@app.route('/<dbtype>/img/<int:item_id>/')
def get_picture_url(dbtype, item_id):
    """
    Redirect stored image url within the db to an organized url for
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
    """
    Define website's Cytotoxin page with both guest/ logged-in user
    access
    """
    (email, user_id, logged_in) = login_info(login_session)
    (cytotoxins, lot_dict, lots) = set_category('cytotoxin')
    return render_template('cytotoxin.html', title='Cytotoxin',
                           cytotoxins=cytotoxins, lot_dict=lot_dict, lots=lots,
                           user_id=user_id, email=email, logged_in=logged_in)


@app.route('/adc/')
def adc():
    """
    Define website's ADC page with both guest/ logged-in user
    access
    """
    (email, user_id, logged_in) = login_info(login_session)
    (adcs, lot_dict, lots) = set_category('adc')
    return render_template('adc.html', title='ADC', adcs=adcs,
                           lot_dict=lot_dict, lots=lots, user_id=user_id,
                           email=email, logged_in=logged_in)


@app.route('/<dbtype>/create', methods=['GET', 'POST'])
def create_type(dbtype):
    """
    Create new category (within 3 pre-defined type) in the database
    """
    # check login status
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. '
              'Please sign in first.')
        return redirect(url_for(dbtype))

    # get property names from table
    table = Table(dbtype, meta, autoload=True, autoload_with=engine)
    user_id = get_user_id(login_session['email'])

    if request.method == 'POST':
        # instantiate new object
        new = eval(dbtype.capitalize())()
        for field in request.form:
            # set attribute of new object with request form data
            if hasattr(new, field):
                setattr(new, field, request.form[field])
        setattr(new, 'user_id', user_id)
        session.add(new)
        session.commit()
        flash('%s Created' % dbtype.capitalize())

        # upload image
        image = request.files['picture']
        if image and allowed_file(image.filename):
            with store_context(fs_store):
                new.picture.from_file(image)
        # prevent user uploading unsupported file type
        elif image and not allowed_file(image.filename):
            flash('Unsupported file detected. No image has been uploaded.')
        return redirect(url_for(dbtype))
    else:
        return render_template('create-type.html',
                               columns=table.columns, dbtype=dbtype)


@app.route('/<dbtype>/<int:item_id>/create/', methods=['GET', 'POST'])
def create_type_lot(dbtype, item_id):
    """Create new item within the category in the database"""
    # check login status
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. '
              'Please sign in first.')
        return redirect(url_for(dbtype))

    # get property names from table, check maximum lot# from ab and cytotoxin
    table = Table('%s_lot' % dbtype, meta, autoload=True, autoload_with=engine)
    max_ab_lot = (session.query(AntibodyLot)
                  .order_by(desc(AntibodyLot.id)).first().id)
    max_cytotoxin_lot = (session.query(CytotoxinLot)
                         .order_by(desc(CytotoxinLot.id)).first().id)
    origin_id = (session.query(eval(dbtype.capitalize()))
                 .filter_by(id=item_id).one().user_id)
    user_id = get_user_id(login_session['email'])

    if request.method == 'POST':
        # instantiate new object
        new = eval(dbtype.capitalize()+'Lot')()
        for field in request.form:
            # set date attribute of new object with request form data
            if field == 'date':
                try:
                    setattr(new,
                            field,
                            (datetime
                             .strptime(request
                                       .form[field]
                                       .replace('-', ' '), '%Y %m %d')))
                # in some cases users can input 6 digit year, catch this error
                except ValueError as detail:
                    print 'Handling run-time error: ', detail
                    flash('Invalid date detected. Please type the date in '
                          'format: MM/DD/YYYY')
                    return redirect(url_for(dbtype))
            # set attribute of new object with request form data
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
                               max_ab_lot=max_ab_lot,
                               max_cytotoxin_lot=max_cytotoxin_lot,
                               origin_id=origin_id,
                               user_id=get_user_id(login_session['email']))


@app.route('/<dbtype>/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_type(dbtype, item_id):
    """Edit the category (within 3 pre-defined type) in the database"""
    # check login status
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. '
              'Please sign in first.')
        abort(401)

    # query the item user wants to edit
    edit_item = (session.query(eval(dbtype.capitalize()))
                 .filter_by(id=item_id).one())
    # make sure user is authorized to edit this item
    if login_session['user_id'] != edit_item.user_id:
        flash('You are not authorized to modify items you did not create. '
              'Please create your own item in order to modify it.')
        return redirect(url_for(dbtype))

    # get property names from table
    table = Table(dbtype, meta, autoload=True, autoload_with=engine)

    if request.method == 'POST':
        for column in table.columns:
            if column.name in ('id', 'user_id'):
                pass  # don't modify item id# and user_id#
            else:
                # set attribute of query object with request form data
                setattr(edit_item, column.name, request.form[column.name])
        session.add(edit_item)
        session.commit()
        flash('%s Edited' % dbtype.capitalize())

        # upload image
        image = request.files['picture']
        if image and allowed_file(image.filename):
            with store_context(fs_store):
                edit_item.picture.from_file(image)
        # prevent user uploading unsupported file type
        elif image and not allowed_file(image.filename):
            flash('Unsupported file detected. No image has been uploaded.')
        return redirect(url_for(dbtype))
    else:
        return render_template('edit-type.html', dbtype=dbtype,
                               columns=table.columns, item_id=item_id,
                               edit_item=edit_item)


@app.route('/<dbtype>/lot/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_type_lot(dbtype, item_id):
    """Edit item within the category in the database"""
    # check login status
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. '
              'Please sign in first.')
        abort(401)

    # query the item user wants to edit
    edit_item = (session.query(eval(dbtype.capitalize()+'Lot'))
                 .filter_by(id=item_id).one())
    # make sure user is authorized to edit this item
    if login_session['user_id'] != edit_item.user_id:
        flash('You are not authorized to modify items you did not create. '
              'Please create your own item in order to modify it.')
        return redirect(url_for(dbtype))

    # get property names from table, check maximum lot# from ab and cytotoxin
    table = Table('%s_lot' % dbtype, meta, autoload=True, autoload_with=engine)
    max_ab_lot = (session.query(AntibodyLot)
                  .order_by(desc(AntibodyLot.id)).first().id)
    max_cytotoxin_lot = (session.query(CytotoxinLot)
                         .order_by(desc(CytotoxinLot.id)).first().id)

    if request.method == 'POST':
        # set date attribute of query object with request form data
        try:
            edit_item.date = (datetime
                              .strptime(request
                                        .form['date']
                                        .replace('-', ' '), '%Y %m %d'))
        # in some cases users can input 6 digit year, catch this error
        except ValueError as detail:
            print 'Handling run-time error: ', detail
            flash('Invalid date detected. Please type the date in '
                  'format: MM/DD/YYYY')
            return redirect(url_for(dbtype))
        for column in table.columns:
            if column.name in ('id', 'date', 'antibody_id',
                               'cytotoxin_id', 'adc_id', 'user_id'):
                pass  # don't modify item identifier
            # set attribute of query object with request form data
            else:
                setattr(edit_item, column.name, request.form[column.name])
        session.add(edit_item)
        session.commit()
        flash('%s Lot Edited' % dbtype.capitalize())
        return redirect(url_for(dbtype))
    else:
        return render_template('edit-type-lot.html', dbtype=dbtype,
                               columns=table.columns, item_id=item_id,
                               edit_item=edit_item, max_ab_lot=max_ab_lot,
                               max_cytotoxin_lot=max_cytotoxin_lot)


@app.route('/<dbtype>/<int:item_id>/delete/', methods=['GET', 'POST'])
def delete(dbtype, item_id):
    """Delete either the item or category in the database"""
    # check login status
    if 'email' not in login_session:
        flash('Sorry, the page you tried to access is for members only. '
              'Please sign in first.')
        abort(401)

    # query the item user wants to delete
    delete_item = (session.query(eval(dbtype[0].upper()+dbtype[1:]))
                   .filter_by(id=item_id).one())

    # make sure user is authorized to delete this item
    if login_session['user_id'] != delete_item.user_id:
        flash('You are not authorized to modify items you did not create. '
              'Please create your own item in order to modify it.')
        return redirect(url_for(dbtype))

    if request.method == 'POST':
        try:
            session.delete(delete_item)
            session.commit()
        # handling legacy error when delete invovled cascade-delete
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
def collection_lots(dbtype):
    """
    Create an XML endpoint with all items within the categories
    available
    """
    collections = session.query(eval(dbtype.capitalize()+'Lot')).all()
    return render_template('collections-lot.xml', dbtype=dbtype,
                           collections=collections)


@app.route('/antibody/json')
def antibody_json():
    """Create an JSON endpoint with all antibody categories"""
    antibodies = session.query(Antibody).all()
    return jsonify(antibodies=[i.serialize for i in antibodies])


@app.route('/cytotoxin/json')
def cytotoxin_json():
    """Create an JSON endpoint with all cytotoxin categories"""
    cytotoxins = session.query(Cytotoxin).all()
    return jsonify(cytotoxins=[i.serialize for i in cytotoxins])


@app.route('/adc/json')
def adc_json():
    """Create an JSON endpoint with all ADC categories"""
    adcs = session.query(Adc).all()
    return jsonify(adcs=[i.serialize for i in adcs])


@app.route('/antibody/lot/json')
def antibody_lot_json():
    """
    Create an JSON endpoint with all items within the antibody
    categories
    """
    lots = session.query(AntibodyLot).all()
    return jsonify(antibody_lots=[i.serialize for i in lots])


@app.route('/cytotoxin/lot/json')
def cytotoxin_lot_json():
    """
    Create an JSON endpoint with all items within the cytotoxin
    categories
    """
    lots = session.query(CytotoxinLot).all()
    return jsonify(cytotoxin_lots=[i.serialize for i in lots])


@app.route('/adc/lot/json')
def adc_lot_json():
    """
    Create an JSON endpoint with all items within the ADC categories
    """
    lots = session.query(AdcLot).all()
    return jsonify(adc_lots=[i.serialize for i in lots])


@app.errorhandler(401)
def access_denied(e):
    """
    Render a 401 error page when user tries to perform unauthorized
    access
    """
    return render_template('401.html'), 401


@app.errorhandler(404)
def page_not_found(e):
    """
    Render a 404 error page when user tries to access page that doesn't
    exist
    """
    return render_template('404.html'), 404


@app.before_request
def start_implicit_store_context():
    push_store_context(fs_store)


@app.teardown_request
def stop_implicit_store_context(exception=None):
    pop_store_context()


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
