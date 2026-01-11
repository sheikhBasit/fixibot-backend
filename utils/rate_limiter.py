from slowapi import Limiter
from slowapi.util import get_remote_address

# Initialize the limiter here so it can be imported anywhere
limiter = Limiter(key_func=get_remote_address)