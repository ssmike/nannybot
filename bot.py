import asyncio
import time
import os
import logging
import datetime
from base import make_session, Message, Chat, Meal, start_engine
from telegram.ext import Application, MessageHandler, CommandHandler
from threading import Thread


app = Application.builder().token(os.environ['TELEGRAM_TOKEN']).build()


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
start_engine()

log = logging.getLogger(__name__)


async def stop(update, context):
    _id = update.message.chat.id
    with make_session() as session:
        session.query(Chat).filter(Chat.id == _id).delete(synchronize_session='fetch')


app.add_handler(CommandHandler('stop', stop))


async def stats(update, context):
    _id = update.message.chat.id
    now = datetime.datetime.utcnow()
    maxtime = None
    sm = 0
    cnt = 0

    period_sm = 0
    with make_session() as session:
        chat = session.query(Chat).filter(Chat.id == _id).one()
        for meal in chat.meals:
            if meal.time + chat.period_time() > now:
                period_sm += meal.amount
            if maxtime is None or meal.time > maxtime:
                maxtime = meal.time
                if meal.time + datetime.timedelta(days=1) > now:
                    sm += meal.amount
                    cnt += 1

    delta = now - maxtime

    hour = datetime.timedelta(hours=1)
    hours = int(delta / hour)

    minute = datetime.timedelta(minutes=1)
    minutes = int((delta - hour * hours) / minute)

    await update.message.reply_text('За день кушали %d раз, суммарно выпили %dмл. За установленный период съели %dмл. Последний раз кушали %d часов %d минут назад' % (cnt, sm, period_sm, hours, minutes))


app.add_handler(CommandHandler('stats', stats))


def validate_period(period):
    h,m,s = period.split(':')
    return int(h) * 60**2 + int(m)*60 + int(s)


async def start(update, context):
    try:
        _, period = update.message.text.split(' ')
        period = validate_period(period)

        with make_session() as session:
            _id = update.message.chat.id
            existing_users = session.query(Chat).filter(Chat.id == _id).all()
            if len(existing_users) > 0:
                existing_users[0].period = period
            else:
                session.add(Chat(id=_id, period=period))

        await update.message.reply_text('записала период кормления в %s секунд' % (period,))
    except Exception as e:
        print(e)
        await update.message.reply_text('error: command should be /start h:m:s')


app.add_handler(CommandHandler('start', start))


def validate_meal(content):
    try:
        return int(content)
    except Exception as e:
        return None


def validate_time_and_meal(now, content):
    try:
        tp, amount = content.split(' ')
        amount = int(amount)
    
        if tp.endswith('h'):
            tp = now + datetime.timedelta(hours=int(tp[:-1]))
        elif tp.endswith('m'):
            tp = now + datetime.timedelta(minutes=int(tp[:-1]))
        else:
            return None, None

        return tp, amount
    except Exception as e:
        print(e)
        return None, None


async def callback(update, context):
    _id = update.message.chat.id
    _text = update.message.text
    _date = update.message.date
    
    meal_date = _date
    meal_amount = validate_meal(_text)

    if meal_amount is None:
        meal_date, meal_amount = validate_time_and_meal(meal_date, _text)

    with make_session() as session:
        session.add(Message(chat_id=_id, content=_text, time=_date))
        if meal_amount is not None:
            session.add(Meal(chat_id=_id, amount=meal_amount, time=meal_date))

    if meal_amount is not None:
        await update.message.reply_text('записала кормление %d мл %s' % (meal_amount, meal_date))

app.add_handler(MessageHandler(None, callback))

_muted_chats = {}

log.debug('starting polling')


async def checker(_):
    print('checking chats')
    notifies = {}
    now = datetime.datetime.utcnow()
    toclean = datetime.timedelta(days=3)
    with make_session() as session:
        chats = session.query(Chat)
        for chat in chats:
            try:
                print(chat)
                maxtime = None
                for meal in chat.meals:
                    if maxtime is None or meal.time > maxtime:
                        maxtime = meal.time
                    if meal.time + toclean < now:
                        meal.delete()

                if maxtime is not None and maxtime + chat.period_time() < now:
                    if chat.id in _muted_chats and _muted_chats[chat.id] > now:
                        continue
                    delta = now - meal.time
                    ratio = int(delta / datetime.timedelta(seconds=chat.period))
                    notifies[chat.id] = 'Пора кормить ребенка! Прошло больше %d периодов кормления!' % (ratio,)
                    _muted_chats[chat.id] = now + datetime.timedelta(minutes=10)
            except Exception as e:
                print(e)

    for key, value in notifies.items():
        print(key, value)
        await app.bot.send_message(key, value)

app.job_queue.run_repeating(checker, 60)

app.run_polling()
