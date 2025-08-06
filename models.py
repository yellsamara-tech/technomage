from sqlalchemy import Column, Integer, String
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    full_name = Column(String, nullable=True)
    status = Column(String, nullable=True)
