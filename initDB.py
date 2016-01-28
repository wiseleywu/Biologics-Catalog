from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from database_setup import Base

from settings import db_path


# Setting up postgres Database and SQL Alchemy's ORM
engine = create_engine(db_path)
Base.metadata.bind = engine
meta = MetaData(bind=engine)
DBSession = sessionmaker(bind=engine)
session = DBSession()
