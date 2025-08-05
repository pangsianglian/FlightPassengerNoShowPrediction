#!/usr/bin/env python
# coding: utf-8

# ## FastAPI talk directly to MySQL

# In[ ]:


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import os

# get DB_PASSWORD from my env
pwd = os.getenv("DB_PASSWORD")  
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:{pwd}@localhost:3306/skylance"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

