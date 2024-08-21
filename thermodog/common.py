import datetime
import pytz
import pprint
import string

from dateutil import parser
from datetime import timedelta, datetime

PDT    = pytz.timezone("America/Los_Angeles")
UTC    = pytz.utc
ISOFMT = "YYYY-MM-DDTHH:MM:SS"

## lifted from stack overflow: 6760685/creating-a-singleton-in-python
class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(
                *args, **kwargs)
        return cls._instances[cls]


def sanitizeName(nm):
    """Create valid AWS names"""
    validChars = "-_ %s%s" % (string.ascii_letters, string.digits)
    mname = "".join((c for c in nm if c in validChars))
    return mname.replace(" ", "_")

def utcNow():
    return UTC.localize(datetime.utcnow()).replace(microsecond=0)

def pstNow():
    return utcNow().astimezone(PDT)

def utcIso(n=None):
    if not n:
        n = utcNow()
    return n.isoformat()

def pstIso(n=None):
    if not n:
        n = pstNow()
    else:
        n = n.astimezone(PDT)
    return n.isoformat()

def isoToUtc(s):
    return parser.parse(s).astimezone(UTC)

def isoToPst(s):
    return isoToUtc(s).astimezone(PDT)

# [pstIso(ct - timedelta(hours=i)) for i in range(0, 10)]
# sfr = utcNow()
# sts = [utcIso(sfr - timedelta(hours=i)) for i in range(0, 10)]
