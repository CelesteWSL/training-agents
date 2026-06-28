# Load .env at package import so DEFAULT_CONFIG and all downstream
# consumers see the user's keys regardless of which entry point
# started the process. find_dotenv(usecwd=True) walks from the CWD,
# so it finds the project's .env instead of stepping up from
# site-packages. load_dotenv defaults to override=False, so it never
# clobbers values the caller has already exported.
try:
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv(usecwd=True))
except ImportError:
    pass

from .default_config import DEFAULT_CONFIG
