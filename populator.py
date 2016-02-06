import datetime
import os
from random import randint, random, choice

from sqlalchemy_imageattach.entity import Image, image_attachment
from sqlalchemy_imageattach.context import store_context

from database_setup import Base, User, Antibody, Cytotoxin, Adc
from database_setup import AntibodyLot, CytotoxinLot, AdcLot
from database_setup import UserImg, AntibodyImg, CytotoxinImg, AdcImg

from helper import attach_picture, attach_picture_url

from init_db import session

from settings import app_path, fs_store


def create_random_date():
    today = datetime.date.today()
    difference = randint(0, 720)
    lotdate = today - datetime.timedelta(days=difference)
    return lotdate


# Add dummy user
def create_user(name, email, picture):
    user = User(name=name, email=email)
    session.add(user)
    session.commit()
    new_user_id = session.query(User).filter_by(email=email).one().id
    if picture.startswith("https"):
        attach_picture_url(User, new_user_id, picture)
    else:
        attach_picture(User, new_user_id, picture)


# Add Antibody
def create_antibody():
    antibody1 = Antibody(name='Amatuximab', weight=144330,
                         target='Mesothelin', user_id=1)
    session.add(antibody1)
    session.commit()
    antibody2 = Antibody(name='Brentuximab', weight=153000,
                         target='CD30', user_id=2)
    session.add(antibody2)
    session.commit()
    antibody3 = Antibody(name='Gemtuzumab', weight=152000,
                         target='CD33', user_id=3)
    session.add(antibody3)
    session.commit()
    antibody4 = Antibody(name='Trastuzumab', weight=148000,
                         target='HER2/neu', user_id=1)
    session.add(antibody4)
    session.commit()
    antibody5 = Antibody(name='Vorsetuzumab', weight=150000,
                         target='CD70', user_id=2)
    session.add(antibody5)
    session.commit()


# Add Antibody Lot
def create_antibody_lot():
    for x in range(20):
        antibody_lot = AntibodyLot(
                      date=create_random_date(),
                      aggregate=randint(0, 5)+round(random(), 2),
                      endotoxin=randint(0, 10)+round(random(), 2),
                      concentration=randint(0, 10)+round(random(), 2),
                      vial_volume=choice([1, 0.2, 0.5]),
                      vial_number=randint(1, 100),
                      antibody_id=randint(1, 5),
                      user_id=randint(1, 3))
        session.add(antibody_lot)
        session.commit()


def create_cytotoxin():
    cytotoxin1 = Cytotoxin(name='Maytansine',
                           weight=692.19614,
                           drug_class='tubulin inhibitor',
                           user_id=1)
    cytotoxin2 = Cytotoxin(name='Monomethyl auristatin E',
                           weight=717.97858,
                           drug_class='antineoplastic agent',
                           user_id=2)
    cytotoxin3 = Cytotoxin(name='Calicheamicin',
                           weight=1368.34,
                           drug_class='enediyne antitumor antibotics',
                           user_id=3)
    cytotoxin4 = Cytotoxin(name='Mertansine',
                           weight=477.47,
                           drug_class='tubulin inhibitor',
                           user_id=1)
    cytotoxin5 = Cytotoxin(name='Pyrrolobenzodiazepine',
                           weight=25827,
                           drug_class='DNA crosslinking agent',
                           user_id=2)
    session.add_all([cytotoxin1, cytotoxin2, cytotoxin3,
                     cytotoxin4, cytotoxin5])
    session.commit()


def create_cytotoxin_lot():
    for x in range(20):
        cytotoxin_lot = CytotoxinLot(date=create_random_date(),
                                    purity=randint(80, 99)+round(random(), 2),
                                    concentration=randint(0, 10)+round(random(), 2),
                                    vial_volume=choice([1, 0.2, 0.5]),
                                    vial_number=randint(1, 100),
                                    cytotoxin_id=randint(1, 5),
                                    user_id=randint(1, 3))
        session.add(cytotoxin_lot)
        session.commit()


def antibody_lot():
    total = []
    for x in range(1, 6):
        lotlist = []
        antibodies = (session.query(AntibodyLot)
                             .filter(AntibodyLot.antibody_id == x).all())
        for antibody in antibodies:
            lotlist.append(antibody.id)
        total.append(lotlist)
    return total


def cytotoxin_lot():
    total = []
    for x in range(1, 6):
        lotlist = []
        cytotoxins = (session.query(CytotoxinLot)
                             .filter(CytotoxinLot.cytotoxin_id == x).all())
        for cytotoxin in cytotoxins:
            lotlist.append(cytotoxin.id)
        total.append(lotlist)
    return total


def create_adc():
    adc1 = Adc(name='Amatuximab maytansine',
               chemistry='lysine conjugation',
               user_id=1)
    adc2 = Adc(name='Brentuximab vedotin',
               chemistry='cysteine conjugation',
               user_id=2)
    adc3 = Adc(name='Gemtuzumab ozogamicin',
               chemistry='site-specific conjugation',
               user_id=3)
    adc4 = Adc(name='Trastuzumab emtansine',
               chemistry='engineered cysteine conjugation',
               user_id=1)
    adc5 = Adc(name='Vorsetuzumab pyrrolobenzodiazepine',
               chemistry='enzyme-assisted conjugation',
               user_id=2)
    session.add_all([adc1, adc2, adc3, adc4, adc5])
    session.commit()


def create_adc_lot():
    lot = [1, 2, 3, 4, 5]
    for x in range(20):
        error = True
        while error:
            randomlot = choice(lot)
            try:
                id1 = choice(antibody_lot()[randomlot-1])
                id2 = choice(cytotoxin_lot()[randomlot-1])
            except IndexError:
                lot.remove(randomlot)
            else:
                error = False
                adclot = AdcLot(date=create_random_date(),
                                aggregate=randint(0, 5)+round(random(), 2),
                                endotoxin=randint(0, 10)+round(random(), 2),
                                concentration=randint(0, 10)+round(random(), 2),
                                vial_volume=choice([1, 0.2, 0.5]),
                                vial_number=randint(1, 100),
                                adc_id=randomlot,
                                antibodylot_id=id1,
                                cytotoxinlot_id=id2,
                                user_id=randint(1, 3))
        session.add(adclot)
        session.commit()

if __name__ == '__main__':
    create_user('Wiseley Wu', 'wiseleywu@gmail.com', 'https://lh6.googleusercontent.com/-45KCJFuShPk/AAAAAAAAAAI/AAAAAAAArRw/E7__AYvGSOQ/photo.jpg')
    create_user('John Doe',
                'john.doe@gmail.com',
                os.path.join(app_path, 'static/images/user.png'))
    create_user('Jane Doe',
                'jane.doe@gmail.com',
                os.path.join(app_path, 'static/images/user.png'))
    create_antibody()
    create_antibody_lot()
    create_cytotoxin()
    create_cytotoxin_lot()
    create_adc()
    create_adc_lot()
    for x in range(1, 6):
        attach_picture(Antibody,
                       x,
                       os.path.join(app_path, 'static/images/antibody.png'))
        attach_picture(Cytotoxin,
                       x,
                       os.path.join(app_path, 'static/images/cytotoxin.png'))
        attach_picture(Adc,
                       x,
                       os.path.join(app_path, 'static/images/adc.png'))
    print 'Database Populated'
