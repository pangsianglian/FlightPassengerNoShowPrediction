#!/usr/bin/env python
# coding: utf-8

# In[1]:


# predict_noshow_update_db.py
import os
import pickle
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, select, update
from sqlalchemy.orm import sessionmaker


# In[2]:


# Purpose: ETL + ML + write-back

os.environ["DB_PASSWORD"] = "Nail1925$$"

# 1) Load your DB password from the environment
pwd = os.getenv("DB_PASSWORD")
if not pwd:
    raise RuntimeError("Please set DB_PASSWORD in your environment")

# 2) Create your engine & session
DATABASE_URL = f"mysql+pymysql://root:{pwd}@localhost:3306/skylance"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


# 3) Reflect the table for updates
meta = MetaData()
flightbookingdetails = Table("flightbookingdetails", meta, autoload_with=engine)

# 4) Pull exactly once with your big JOIN
join_sql = """
SELECT
  fbd.Id                AS BookingID,
  ac.Airline,
  o.IataCode    AS Origin,
  d.IataCode    AS Destination,
  fd.FlightStatus AS Flight_Status,
  YEAR(fd.DepartureTime) - YEAR(au.DateOfBirth) AS Age,
  au.Gender,
  fbd.TravelPurpose AS Travel_Purpose,
  au.MembershipTier,
  fd.Distance      AS Distance_km,
  fd.IsHoliday,
  HOUR(fd.DepartureTime)      AS Departure_Hour,
  DAYOFWEEK(fd.DepartureTime)-1 AS Departure_Weekday,
  MONTH(fd.DepartureTime)     AS Departure_Month,
  fbd.Fareamount    AS Price,
  fbd.BaggageAllowance
FROM flightbookingdetails fbd
JOIN flightdetails    fd ON fd.Id = fbd.FlightDetailId
JOIN aircraft         ac ON ac.Id = fd.AircraftId
JOIN airports         o  ON o.Id  = fd.OriginAirportId
JOIN airports         d  ON d.Id  = fd.DestinationAirportId
JOIN bookingdetails   bd ON bd.Id = fbd.BookingDetailId
JOIN appusers         au ON au.Id = bd.AppUserId
WHERE fbd.Prediction IS NULL
"""

conn = engine.raw_connection()
try:
    df_raw = pd.read_sql_query(join_sql, conn,
        parse_dates=["DepartureTime","DateOfBirth"])
finally:
    conn.close()

if df_raw.empty:
    print("No new rows to predict.")
    exit()

# 5) Derive the engineered ones with existing (if needed)
# 5a) Map gender codes back to full strings
df_raw['Gender'] = df_raw['Gender'].map({
    'M': 'Male',
    'F': 'Female'
})

# 5b) Map your numeric travel-purpose codes to the original labels
df_raw['Travel_Purpose'] = df_raw['Travel_Purpose'].map({
    0: 'Business',
    1: 'Family',
    2: 'Leisure',
    3: 'Emergency'
})

# 5c) Fix the “Normal” label back to “None”
df_raw['MembershipTier'] = df_raw['MembershipTier'].replace({
    'Normal': 'None'
})

# 6) Fill in the missing features with sensible defaults:
df_raw['Seat_Class']              = 'Economy'
df_raw['Check_in_Method']         = 'Online'
df_raw['Flight_Status']         = 'On-time'
df_raw['Delay_Minutes']           = 0.0
df_raw['Booking_Days_In_Advance'] = 0
df_raw['Weather_Impact']          = 0

# 7) Rename columns to match the pipeline (if needed)

# 8) Now slice out exactly what the pipeline expects
feature_cols = [
    'Airline','Origin','Destination','Flight_Status',
    'Age','Gender','Travel_Purpose','Seat_Class',
    'MembershipTier','Check_in_Method','Delay_Minutes',
    'Booking_Days_In_Advance','Weather_Impact','Distance_km',
    'IsHoliday','Departure_Hour','Departure_Weekday',
    'Departure_Month','Price','BaggageAllowance'
]
X = df_raw[feature_cols]
print(X)


# In[3]:


# import numpy as _np
# import sklearn.preprocessing._encoders as _enc

# _orig_check_unknown = _enc._check_unknown

# def _patched_check_unknown(values, known_values, *args, **kwargs):
#     # skip the nan‐check on string dtypes
#     try:
#         return _orig_check_unknown(values, known_values, *args, **kwargs)
#     except TypeError:
#         # if it was barfing on np.isnan(known_values), assume no NaNs
#         if kwargs.get("return_mask", False):
#             mask = _np.ones(len(values), dtype=bool)
#             return (_np.array([]), mask)
#         else:
#             return _np.ones(len(values), dtype=bool)

# _enc._check_unknown = _patched_check_unknown

# 8) Load and run the model

with open("rf_pipeline.pkl","rb") as f:
    pipeline = pickle.load(f)

preds = pipeline.predict(X)

# # 9) Map 0/1 → 'Show'/'No Show'
# label_map = {0:"Show", 1:"No Show"}

# 10) Write back in one pass
session = SessionLocal()
for booking_id, pred in zip(df_raw["BookingID"], preds):
    stmt = (
      update(flightbookingdetails)
      .where(flightbookingdetails.c.Id == booking_id)
      .values(Prediction=int(pred))
    )
    session.execute(stmt)

session.commit()
session.close()
print(f"Updated {len(preds)} rows with Show/No Show labels.")


# In[4]:


import os
print("CWD:", os.getcwd())
print("Looking for pickle at:", os.path.abspath("rf_pipeline.pkl"))


# In[ ]:




