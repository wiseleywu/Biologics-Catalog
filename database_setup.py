from sqlalchemy import Column, ForeignKey, Integer, String, Float, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_imageattach.entity import Image, image_attachment
from sqlalchemy_imageattach.context import store_context
from sqlalchemy.orm import relationship, backref
from sqlalchemy import create_engine

Base = declarative_base()


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    name = Column(String(250))
    email = Column(String(250), nullable=False)
    picture = image_attachment('UserImg')


class UserImg(Base, Image):
    __tablename__ = 'user_img'
    user_id = Column(Integer, ForeignKey('user.id'), primary_key=True)
    user = relationship('User')


class Antibody(Base):
    __tablename__ = 'antibody'
    name = Column(String(80), nullable=False)
    id = Column(Integer, primary_key=True)
    weight = Column(Float, nullable=False)
    target = Column(String(80), nullable=False)
    a_lot = relationship('AntibodyLot', cascade='all, delete-orphan')
    picture = image_attachment('AntibodyImg')
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        try:
            url = self.picture.locate()
        except IOError:
            url = ''
        return {
            "Antibody_Id": self.id,
            "Antibody_Name": self.name,
            "Molecular_Weight": self.weight,
            "Target": self.target,
            "Picture_Url": url,
            "User_Id": self.user_id
        }


class AntibodyImg(Base, Image):
    __tablename__ = 'antibody_img'
    antibody_id = Column(Integer, ForeignKey('antibody.id'), primary_key=True)
    antibody = relationship('Antibody')


class AntibodyLot(Base):
    __tablename__ = 'antibody_lot'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    aggregate = Column(Float, nullable=False)
    endotoxin = Column(Float, nullable=False)
    concentration = Column(Float, nullable=False)
    vialVolume = Column(Float, nullable=False)
    vialNumber = Column(Integer, nullable=False)
    antibody_id = Column(Integer, ForeignKey('antibody.id'))
    antibody = relationship('Antibody')
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User, single_parent=True)

    @property
    def serialize(self):
        return {
            "Lot_Number": self.id,
            "Manufactured_Date": str(self.date),
            "Aggregate_Percent": self.aggregate,
            "Endotoxin_EU_per_mg": self.endotoxin,
            "Concentration_mg_per_ml": self.concentration,
            "Vial_Volume_ml": self.vialVolume,
            "Available_Vials": self.vialNumber,
            "Antibody_Id": self.antibody_id,
            "User_Id": self.user_id
        }


class Cytotoxin(Base):
    __tablename__ = 'cytotoxin'
    name = Column(String(80), nullable=False)
    id = Column(Integer, primary_key=True)
    weight = Column(Float, nullable=False)
    drugClass = Column(String(80), nullable=False)
    lot = relationship('CytotoxinLot', cascade='all, delete-orphan')
    picture = image_attachment('CytotoxinImg')
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        return {
            'Cytotoxin_Id': self.id,
            'Molecular_Weight': self.weight,
            'Drug_Class': self.drugClass,
            'Picture_Url': self.picture.locate(),
            'User_Id': self.user_id
        }


class CytotoxinImg(Base, Image):
    __tablename__ = 'cytotoxin_img'
    cytotoxin_id = Column(Integer, ForeignKey('cytotoxin.id'), primary_key=True)
    cytotoxin = relationship('Cytotoxin')


class CytotoxinLot(Base):
    __tablename__ = 'cytotoxin_lot'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    purity = Column(Float, nullable=False)
    concentration = Column(Float, nullable=False)
    vialVolume = Column(Float, nullable=False)
    vialNumber = Column(Integer, nullable=False)
    cytotoxin_id = Column(Integer, ForeignKey('cytotoxin.id'))
    cytotoxin = relationship('Cytotoxin')
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        return {
            'Lot_Number': self.id,
            'Manufactured_Date': str(self.date),
            'Purity_Percent': self.purity,
            'Concentration_mg_per_ml': self.concentration,
            'Vial_Volume_ml': self.vialVolume,
            'Available_Vials': self.vialNumber,
            'Cytotoxin_Id': self.cytotoxin_id,
            'User_Id': self.user_id
        }


class Adc(Base):
    __tablename__ = 'adc'
    name = Column(String(80), nullable=False)
    chemistry = Column(String(80), nullable=False)
    id = Column(Integer, primary_key=True)
    lot = relationship('AdcLot', cascade='all, delete-orphan')
    picture = image_attachment('AdcImg')
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        return {
            'Adc_Id': self.id,
            'Conjugation_Chemistry': self.chemistry,
            'Picture_Url': self.picture.locate(),
            'User_Id': self.user_id
        }


class AdcLot(Base):
    __tablename__ = 'adc_lot'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    aggregate = Column(Float, nullable=False)
    endotoxin = Column(Float, nullable=False)
    concentration = Column(Float, nullable=False)
    vialVolume = Column(Float, nullable=False)
    vialNumber = Column(Integer, nullable=False)
    adc_id = Column(Integer, ForeignKey('adc.id'))
    adc = relationship('Adc')
    antibodylot_id = Column(Integer,
                            ForeignKey('antibody_lot.id', ondelete='cascade'))
    antibodylot = relationship(AntibodyLot)
    cytotoxinlot_id = Column(Integer,
                             ForeignKey('cytotoxin_lot.id', ondelete='cascade'))
    cytotoxinlot = relationship(CytotoxinLot)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        return {
            'Lot_Number': self.id,
            'Manufactured_Date': str(self.date),
            'Aggregate_Percent': self.aggregate,
            'Endotoxin_EU_per_mg': self.endotoxin,
            'Concentration_mg_per_ml': self.concentration,
            'Vial_Volume_ml': self.vialVolume,
            'Available_Vials': self.vialNumber,
            'Antibody_Lot_Id': self.antibodylot_id,
            'Cytotoxin_Lot_Id': self.cytotoxinlot_id,
            'Adc_Id': self.adc_id,
            'User_Id': self.user_id
        }


class AdcImg(Base, Image):
    __tablename__ = 'adc_img'
    adc_id = Column(Integer, ForeignKey('adc.id'), primary_key=True)
    adc = relationship('Adc')

# #########################insert at end of file ##############################
engine = create_engine(
    'postgresql://postgres:biologics@localhost/biologics-catalog')
# engine = create_engine('sqlite:///biologicscatalog.db')
Base.metadata.create_all(engine)
