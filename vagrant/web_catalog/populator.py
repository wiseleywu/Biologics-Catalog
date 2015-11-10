from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, User, UserImg, Antibody, Cytotoxin, AntibodyImg, AntibodyLot, CytotoxinImg, CytotoxinLot, Adc, AdcLot, AdcImg
from sqlalchemy_imageattach.entity import Image, image_attachment
from sqlalchemy_imageattach.context import store_context
from random import randint
from project import app, fs_store, session, get_picture_url, delete_picture, attach_picture, attach_picture_url
import datetime
import random

def createRandomDate():
	today = datetime.date.today()
	difference = randint(0,720)
	lotdate = today - datetime.timedelta(days = difference)
	return lotdate

#Add dummy user
def createUser():
	user=User(name='Wiseley', email='wiseleywu@gmail.com')
	session.add(user)
	session.commit()
	attach_picture_url(User, 1, 'https://lh6.googleusercontent.com/-45KCJFuShPk/AAAAAAAAAAI/AAAAAAAArRw/E7__AYvGSOQ/photo.jpg')

#Add Antibody
def createAntibody():
    antibody1=Antibody(name='Amatuximab', weight=144330, target='Mesothelin', user_id=1)
    session.add(antibody1)
    session.commit()
    antibody2=Antibody(name='Brentuximab', weight=153000, target='CD30', user_id=1)
    session.add(antibody2)
    session.commit()
    antibody3=Antibody(name='Gemtuzumab', weight=152000, target='CD33', user_id=1)
    session.add(antibody3)
    session.commit()
    antibody4=Antibody(name='Trastuzumab', weight=148000, target='HER2/neu', user_id=1)
    session.add(antibody4)
    session.commit()
    antibody5=Antibody(name='Vorsetuzumab', weight=150000, target='CD70', user_id=1)
    session.add(antibody5)
    session.commit()

#Add Antibody Lot
def createAntibodyLot():
    for x in range(20):
        antibodylot=AntibodyLot(date=createRandomDate(), aggregate=randint(0,5)+round(random.random(),2), endotoxin=randint(0,10)+round(random.random(),2),concentration=randint(0,10)+round(random.random(),2), vialVolume=random.choice([1,0.2,0.5]), vialNumber=randint(1,100), antibody_id=randint(1,5), user_id=1)
        session.add(antibodylot)
        session.commit()

def createCytotoxin():
	cytotoxin1=Cytotoxin(name='Maytansine', weight=692.19614, drugClass='tubulin inhibitor', user_id=1)
	cytotoxin2=Cytotoxin(name='Monomethyl auristatin E', weight=717.97858, drugClass='antineoplastic agent', user_id=1)
	cytotoxin3=Cytotoxin(name='Calicheamicin', weight=1368.34, drugClass='enediyne antitumor antibotics', user_id=1)
	cytotoxin4=Cytotoxin(name='Mertansine', weight=477.47, drugClass='tubulin inhibitor', user_id=1)
	cytotoxin5=Cytotoxin(name='Pyrrolobenzodiazepine', weight=25827, drugClass='DNA crosslinking agent', user_id=1)
	session.add_all([cytotoxin1, cytotoxin2, cytotoxin3, cytotoxin4, cytotoxin5])
	session.commit()

def createCytotoxinLot():
    for x in range(20):
        cytotoxinlot=CytotoxinLot(date=createRandomDate(), purity=randint(80,99)+round(random.random(),2), concentration=randint(0,10)+round(random.random(),2), vialVolume=random.choice([1,0.2,0.5]), vialNumber=randint(1,100), cytotoxin_id=randint(1,5), user_id=1)
        session.add(cytotoxinlot)
        session.commit()

def antibodylot():
    total=[]
    for x in range(1,6):
        lotlist=[]
        antibodies=session.query(AntibodyLot).filter(AntibodyLot.antibody_id==x).all()
        for antibody in antibodies:
            lotlist.append(antibody.id)
        total.append(lotlist)
    return total

def cytotoxinlot():
    total=[]
    for x in range(1,6):
        lotlist=[]
        cytotoxins=session.query(CytotoxinLot).filter(CytotoxinLot.cytotoxin_id==x).all()
        for cytotoxin in cytotoxins:
            lotlist.append(cytotoxin.id)
        total.append(lotlist)
    return total

def createADC():
	adc1=Adc(name='Amatuximab maytansine', chemistry='lysine conjugation', user_id=1)
	adc2=Adc(name='Brentuximab vedotin', chemistry='cysteine conjugation', user_id=1)
	adc3=Adc(name='Gemtuzumab ozogamicin', chemistry='site-specific conjugation', user_id=1)
	adc4=Adc(name='Trastuzumab emtansine', chemistry='engineered cysteine conjugation', user_id=1)
	adc5=Adc(name='Vorsetuzumab pyrrolobenzodiazepine', chemistry='enzyme-assisted conjugation', user_id=1)
	session.add_all([adc1, adc2, adc3, adc4, adc5])
	session.commit()

def createADCLot():
	lot=[1,2,3,4,5]
	for x in range(20):
		error=True
		while error==True:
			randomlot=random.choice(lot)
			try:
				id1=random.choice(antibodylot()[randomlot-1])
				id2=random.choice(cytotoxinlot()[randomlot-1])
			except IndexError:
				lot.remove(randomlot)
			else:
				error=False
		adclot=AdcLot(date=createRandomDate(),
					  aggregate=randint(0,5)+round(random.random(),2),
					  endotoxin=randint(0,10)+round(random.random(),2),
					  concentration=randint(0,10)+round(random.random(),2),
					  vialVolume=random.choice([1,0.2,0.5]),
					  vialNumber=randint(1,100),
					  adc_id=randomlot,
					  antibodylot_id=id1,
					  cytotoxinlot_id=id2,
					  user_id=1)
		session.add(adclot)
		session.commit()

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

if __name__ == '__main__':
	createUser()
	createAntibody()
	createAntibodyLot()
	createCytotoxin()
	createCytotoxinLot()
	createADC()
	createADCLot()
	for x in range(1,6):
		attach_picture_url(Antibody, x, 'http://www.prosci-inc.com/media/wysiwyg/antibody.png')
		attach_picture_url(Cytotoxin, x, 'http://www.prosci-inc.com/media/wysiwyg/antibody.png')
		attach_picture_url(Adc, x, 'http://www.prosci-inc.com/media/wysiwyg/antibody.png')
	print 'Database Populated'