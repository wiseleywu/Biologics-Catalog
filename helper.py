import string
from urllib2 import urlopen

from sqlalchemy_imageattach.entity import Image, image_attachment
from sqlalchemy_imageattach.context import store_context

from database_setup import Base, User, Antibody, Cytotoxin, Adc
from database_setup import AntibodyLot, CytotoxinLot, AdcLot
from database_setup import UserImg, AntibodyImg, CytotoxinImg, AdcImg

from settings import fs_store, ALLOWED_EXTENSIONS

from init_db import session


# User Helper Functions
def create_user(login_session):
    """
    Create a new user in the db using user info in the login_session
    """
    new_user = User(name=login_session['username'], email=login_session[
                   'email'])
    session.add(new_user)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    attach_picture_url(User, user.id, login_session['picture'])
    return user.id


def get_user_info(user_id):
    """Get user object in the db using its user_id"""
    user = session.query(User).filter_by(id=user_id).one()
    return user


def get_user_id(email):
    """Get user's id in the db using its e-mail address"""
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


def login_info(login_session):
    """Provide login status to pass onto html templates"""
    email, user_id, logged_in = None, None, False
    if 'email' in login_session:
        email = login_session['email']
        user_id = get_user_id(login_session['email'])
        logged_in = True
    return (email, user_id, logged_in)


def set_category(dbtype):
    """Provide category/item data to pass onto html templates"""
    # define object and object lots
    obj = eval(dbtype.capitalize())
    items = eval(dbtype.capitalize()+'Lot')

    # query the object items and object lots items
    cat = session.query(obj).order_by(obj.name).all()
    lots = session.query(items).all()

    # create a dict to associate object id with its respective object lot items
    lot_dict = {}
    for x in range(1, session.query(obj).count()+1):
        lot_dict[x] = (session.query(items)
                       .filter(getattr(items, dbtype+'_id') == x)
                       .order_by(items.date).all())
    return (cat, lot_dict, lots)


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
    A helper function used in populator.py to upload picture to the db
    from web
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
