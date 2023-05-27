import datetime
import time
#def validate_period2(content):
#    try:
#        segments = []
#        cur = ''
#        for c in content:
#            if not c.isalnum():
#                continue
#            if c.isdigit():
#                cur += c
#            else:
#                segments.append((cur, c))
#                cur = ''
#        if cur != '': return None
#        result = 0
#        for (num, modifier) in segments:
#            if modifier == 'h':
#                result += int(num) * 60 * 60
#            elif modifier == 'm':
#                result += int(num) * 60
#            elif modifier == 's':
#                result += int(num)
#        return result
#    except:
#        return None

#assert validate_period('1h') == 60**2
#assert validate_period('2h3m25s') == 2 * 60**2 + 3*60 + 25

def silent_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            pass
    return wrapper

@silent_errors
def validate_period(period):
    h,m,s = period.split(':')
    return int(h) * 60**2 + int(m)*60 + int(s)


def format_period(seconds):
    minutes = seconds // 60
    seconds = seconds % 60
    hours = minutes // 60
    minutes = minutes % 60
    result = ''
    if hours > 0:
        result += ' %d часов' % (hours,)
    if minutes > 0:
        result += ' %d минут' % (minutes,)
    if seconds > 0:
        result += ' %d секунд' % (seconds,)
    return result.strip()

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


@silent_errors
def validate_meal(content):
    return int(content)


def format_time(dt):
    return str(dt)


@silent_errors
def validate_time_with_year(content):
    conv=time.strptime(content,"%b %d %Y")
    return datetime.datetime.fromtimestamp(time.mktime(conv), tz=datetime.timezone.utc)


def validate_time(content):
    result = validate_time_with_year(content)
    if result is not None:
        return result
    else:
        return validate_time_with_year(content + ' ' + str(datetime.datetime.utcnow().year))

assert validate_time('Feb 8') is not None
assert validate_time('Apr 8') is not None
