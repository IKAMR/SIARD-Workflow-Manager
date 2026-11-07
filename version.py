"""Applikasjonsversjon og utviklingsmerking for innholdskontroll.

VERSION benyttes av oppdatering og PREMIS. Utviklingssuffikset er kun
for visning i programtittelen.
"""

VERSION = "1.4.23"
DEVELOPMENT_SUFFIX = "ikamr-04-a4"
DISPLAY_VERSION = f"{VERSION}-{DEVELOPMENT_SUFFIX}" if DEVELOPMENT_SUFFIX else VERSION
