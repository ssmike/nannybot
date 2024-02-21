from sqlalchemy import Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine
from contextlib import contextmanager
import datetime

Base = declarative_base()

class Notify(Base):
    __tablename__ = 'notify'
    id = Column(Integer, primary_key=True, unique=True)
    chat_id = Column(Integer, ForeignKey('chats_v1.id'))
    message = Column(String)
    period = Column(Integer)
    last_time = Column(DateTime)

    chat = relationship('Chat', back_populates='notifies')

    def period_time(self):
        return datetime.timedelta(seconds=1) * self.period


class Chat(Base):
    __tablename__ = 'chats_v1'
    id = Column(Integer, primary_key=True, unique=True)
    period = Column(Integer)
    state = Column(String)
    meals = relationship('Meal', back_populates='chat')
    topics = relationship('Topic', back_populates='chat')
    messages = relationship('Message', back_populates='chat')
    notifies = relationship('Notify', back_populates='chat')

    def period_time(self):
        return datetime.timedelta(seconds=1) * self.period


class Topic(Base):
    __tablename__ = 'topics'
    id = Column(String, primary_key=True, unique=True)
    chat_id = Column(Integer, ForeignKey('chats_v1.id'))
    name = Column(String)
    chat = relationship(Chat, back_populates='topics')
    messages = relationship('Message', back_populates='topic')


class Meal(Base):
    __tablename__ = 'meals'
    id = Column(Integer, primary_key=True, unique=True)
    amount = Column(Integer)
    time = Column(DateTime)
    chat_id = Column(Integer, ForeignKey('chats_v1.id'))
    chat = relationship(Chat, back_populates='meals')


class Message(Base):
    __tablename__ = 'messages_v1'
    id = Column(Integer, primary_key=True, unique=True)
    telegram_id = Column(Integer)
    chat_id = Column(Integer, ForeignKey('chats_v1.id'))
    topic_id = Column(String, ForeignKey('topics.id'))

    content = Column(String)
    time = Column(DateTime)

    topic = relationship(Topic, back_populates='messages')
    chat = relationship(Chat, back_populates='messages')


Session = None
Engine = None


def start_engine():
    global Session
    global Engine
    Engine = create_engine('sqlite:///chats.db', connect_args={'check_same_thread': False})
    Base.metadata.create_all(Engine)
    Base.metadata.bind = Engine

    Session = sessionmaker(bind=Engine)


def drop_all():
    Base.metadata.drop_all(bind=Engine)
    Base.metadata.create_all(bind=Engine)


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
