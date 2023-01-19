from sqlalchemy import Column, ForeignKey, Integer, String, Table, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine
from contextlib import contextmanager

Base = declarative_base()

class Chat(Base):
    __tablename__ = 'chats'
    id = Column(Integer, primary_key=True, unique=True)
    period = Column(Integer)
    messages = relationship('Message', back_populates='chat')
    meals = relationship('Meal', back_populates='chat')

class Meal(Base):
    __tablename__ = 'meals'
    id = Column(Integer, primary_key=True, unique=True)
    amount = Column(Integer)
    time = Column(DateTime)
    chat_id = Column(Integer, ForeignKey('chats.id'))
    chat = relationship(Chat, back_populates='meals')

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, unique=True)
    chat_id = Column(Integer, ForeignKey('chats.id'))
    content = Column(String)
    time = Column(DateTime)
    chat = relationship(Chat, back_populates='messages')

Session = None

def start_engine():
    global Session
    engine = create_engine('sqlite:///chats.db', connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    Base.metadata.bind = engine

    Session = sessionmaker(bind=engine)


def drop_all():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def drop(tables):
    for name in tables:
        Base.metadata.tables[name].drop()


@contextmanager
def make_session():
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


def with_session(func):
    def result(*args, **kwargs):
        with make_session() as session:
            return func(session, *args, **kwargs)
    return result
