"""Official, fixed-endpoint, read-only DeepSeek account balance adapter."""
from dataclasses import dataclass
from decimal import Decimal,InvalidOperation
import json
import socket
import urllib.request
import urllib.error

BALANCE_URL="https://api.deepseek.com/user/balance"


class AdapterError(Exception):
    def __init__(self,code,retryable=False,retry_after=None):
        super().__init__(code)
        self.code,self.retryable,self.retry_after=code,retryable,retry_after


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None


@dataclass(frozen=True)
class Balance:
    currency:str
    total_balance:Decimal
    granted_balance:Decimal
    topped_up_balance:Decimal
    is_available:bool


def parse_balances(payload):
    try:
        available=payload['is_available'];rows=payload['balance_infos']
        if type(available) is not bool or not isinstance(rows,list) or not 1<=len(rows)<=2:raise ValueError()
        result=[];seen=set()
        for row in rows:
            currency=row['currency']
            if currency not in {'CNY','USD'} or currency in seen:raise ValueError()
            seen.add(currency);values=[]
            for field in ('total_balance','granted_balance','topped_up_balance'):
                if not isinstance(row[field],str):raise ValueError()
                value=Decimal(row[field])
                if not value.is_finite() or abs(value)>=Decimal('1000000000000000') or value.as_tuple().exponent < -8:raise ValueError()
                values.append(value)
            result.append(Balance(currency,*values,available))
        return result
    except (KeyError,TypeError,ValueError,InvalidOperation):
        raise AdapterError('PROVIDER_SCHEMA_INVALID') from None


def fetch_balances(secret):
    if not secret or '\r' in secret or '\n' in secret or len(secret)>200:raise AdapterError('CREDENTIAL_INVALID')
    request=urllib.request.Request(BALANCE_URL,headers={'Authorization':'Bearer '+secret,'Accept':'application/json','User-Agent':'digital-asset-platform/1'},method='GET')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    try:
        with opener.open(request,timeout=15) as response:
            raw=response.read(65537)
            if len(raw)>65536:raise AdapterError('PROVIDER_RESPONSE_TOO_LARGE')
            return parse_balances(json.loads(raw))
    except urllib.error.HTTPError as error:
        code=error.code
        if code in {401,403}:raise AdapterError('CREDENTIAL_REJECTED') from None
        if code==402:raise AdapterError('PROVIDER_BALANCE_UNAVAILABLE') from None
        if code==429:
            try:delay=min(3600,max(30,int(error.headers.get('Retry-After','30'))))
            except ValueError:delay=30
            raise AdapterError('PROVIDER_RATE_LIMITED',True,delay) from None
        if code>=500:raise AdapterError('PROVIDER_UNAVAILABLE',True) from None
        raise AdapterError('PROVIDER_REQUEST_REJECTED') from None
    except (urllib.error.URLError,TimeoutError,socket.timeout):raise AdapterError('PROVIDER_TIMEOUT',True) from None
    except (json.JSONDecodeError,UnicodeDecodeError):raise AdapterError('PROVIDER_SCHEMA_INVALID') from None
