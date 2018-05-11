"""
Represents a higher level function of assembling a tagged address into a USPS compliant address, either as a segmented object, or a string
"""

import usaddress
import re


zips = re.compile("\d{5}(?:[-\s]\d{4})?")  # from https://stackoverflow.com/questions/2577236/regex-for-zip-code


class Address(object):
    """reoresents an address"""
    def __init__(self, number, street, city, state, zipc):
        self.number = number
        self.street = street
        self.city = city
        self.state = state
        self.zipc = zipc

    def __str__(self):
        """override the string method to control how this gets prints"""
        return """Address(number = {n}, street = {s}, city = {c}, state = {st}, zip = {z})""".format(n=self.number, s=self.street, c=self.city, st=self.state, z=self.zipc)

    def tousps(self):
        """
        Converts the object into a USPS representation
        this attempts to adhere to https://smartystreets.com/articles/address-standardization
        """
        return """{n} {s}, {c} {st} {z}""".format(n=self.number, s=self.street, c=self.city, st=self.state, z=self.zipc)


class AddressUnparsable(BaseException):
    """represents an exception that for some various reason this address was not parsable"""
    def __init__(self, addr, reason, tagset):
        self.addr = addr
        self.reason = reason
        self.tagset = tagset


def normalize_address(addr):
    """Parse an address. Return it, or raise an exception"""
    try:
        tags = usaddress.tag(addr)
    except usaddress.RepeatedLabelError:
        raise AddressUnparsable(addr, "usaddress.RepeatedLabelError", ())
    tagset = tags[0]
    add_type = tags[1]
    if add_type != "Street Address":
        raise AddressUnparsable(addr, "Library has unknown address type of {0}".format(add_type), tagset)

    add_number = None
    add_number_suffix = None
    street_name_pretype = None
    street_name = None
    street_directional_pre = None
    street_directional_post = None
    street_type = None
    street_postfix = None
    occ_type = None
    city = None
    state_name = None
    zipc = None

    for tag in tagset:
        val = tagset[tag]
        if tag == 'AddressNumber':
            add_number = val
        elif tag == "AddressNumberSuffix":
            add_number_suffix = val
        elif tag in ["StreetNamePreDirectional", "StreetNamePostDirectional"]:
            # the tags Pre and Post are semantically significant in terms of addresses: https://pe.usps.com/text/pub28/28c2_014.htm
            # However in this library they seem to get mixed up often in cases where only one side exists.
            # If both exist we assume they are correct. However if only one exists, we ignore the tag, but use the ordering of the original address to do the directional

            # check to see if both exist
            if "StreetNamePreDirectional" in tagset and "StreetNamePostDirectional" in tagset:
                street_directional_pre = tagset["StreetNamePreDirectional"]
                street_directional_post = tagset["StreetNamePostDirectional"]
            elif street_name is None:  # this tag/val came BEFORE street name, regardless of position
                street_directional_pre = val
            else:
                street_directional_post = val  # came AFTER street
        elif tag == "StreetNamePreType":
            street_name_pretype = tagset["StreetNamePreModifier"] + " " + val if "StreetNamePreModifier" in tagset else val
        elif tag == "StreetNamePreModifier":
            if "StreetNamePreType" not in tagset:
                raise AddressUnparsable(addr, "Unexpected Tag Scenario: {0}".format("StreetNamePreType"), tagset)
        elif tag == 'StreetName':
            street_name = val
        elif tag == "StreetNamePostType":
            street_type = val
        elif tag == 'SubaddressType' and "SubaddressIdentifier" in tagset:
            street_postfix = val + " " + tagset["SubaddressIdentifier"]
        elif tag == "SubaddressIdentifier":
            pass  # already handled
        elif tag == "OccupancyType":
            occ_type = val + " " + tagset["OccupancyIdentifier"] if "OccupancyIdentifier" in tagset else val
        elif tag == "OccupancyIdentifier":
            pass  # already handled above
        elif tag == 'PlaceName':  # sometimes the zip code gets tacked on here
            m = zips.search(val)
            if m and zipc is None:
                zipc = m.group(0)
                val = val.replace(zipc, "").strip()
            city = val

        elif tag == 'StateName':
            state_name = val
        elif tag == "ZipCode":
            zipc = val + "-" + tagset["ZipPlus4"] if "ZipPlus4" in tagset else val
        elif tag == "ZipPlus4":
            pass  # already handled above
        else:
            raise AddressUnparsable(addr, "Unexpected Tag: {0}".format(tag), tagset)

    if add_number is None:  # a common case
        raise AddressUnparsable(addr, "Missing street number", tagset)
    else:
        if add_number_suffix:
            add_number += " " + add_number_suffix

    if street_name is None:
        raise AddressUnparsable(addr, "Missing street name", tagset)

    # handle the pretype:
    if street_name_pretype:
        street_name = street_name_pretype + " " + street_name

    # handle the street type
    if street_type:
        street_name = street_name + " " + street_type

    # do the USPS abbreviation
    street_name = street_to_abbreviated(street_name)

    # handle the street directional
    if street_directional_pre:
        street_name = street_directional_pre + " " + street_name
    if street_directional_post:
        street_name += " " + street_directional_post

    # handle the street postfix
    if street_postfix:
        street_name = street_name + " " + street_postfix

    # handle the occupancy type
    if occ_type:
        street_name = street_name + " " + occ_type

    if None in [city, state_name, zipc]:
        raise AddressUnparsable(addr, "Missing city, state, or zip", tagset)

    return Address(add_number.upper(), street_name.upper(), city.upper(), state_name.upper(), zipc)


def street_to_abbreviated(street):
    """
    Implements: https://pe.usps.com/text/pub28/28apc_002.htm
    CSV from https://github.com/SwoopSearch/pyaddress/blob/master/address/suffixes.CSV
    """
    mapping = {'WAY': 'WAY', 'BYPSS': 'BYP', 'WLS': 'WLS', 'CPE': 'CPE', 'ORCHRD': 'ORCH', 'CRESCENT': 'CRES', 'FALL': 'FALL', 'BEACH': 'BCH', 'MSSN': 'MSN', 'KYS': 'KY', 'SPG': 'SPG', 'JCTN': 'JCT', 'TUNEL': 'TUNL', 'BYU': 'BYU', 'PARKWAYS': 'PKY', 'COVE': 'CV', 'BYP': 'BYP', 'SPRINGS': 'SPGS', 'ISLANDS': 'ISS', 'RIVER': 'RIV', 'SPUR': 'SPUR', 'JCTS': 'JCT', 'VIADCT': 'VIA', 'PINES': 'PNES', 'EXPRESS': 'EXPY', 'MNRS': 'MNR', 'TUNLS': 'TUNL', 'GROVES': 'GRV', 'SUMITT': 'SMT', 'OVL': 'OVAL', 'VIEW': 'VW', 'CRSNT': 'CRES', 'PKWYS': 'PKY', 'TRK': 'TRAK', 'SQUARE': 'SQ', 'CSWY': 'CSWY', 'CMP': 'CP', 'BPSS': 'BYP', 'CENTR': 'CTR', 'VLG': 'VLG', 'VLY': 'VLY', 'FRD': 'FRD', 'GRV': 'GRV', 'FLAT': 'FLT', 'LOAF': 'LF', 'JCTNS': 'JCT', 'INLET': 'INLT', 'UNION': 'UN', 'BAYOO': 'BYU', 'DRIVES': 'DR', 'BAYOU': 'BYU', 'GRN': 'GRN', 'FERRY': 'FRY', 'TRCE': 'TRCE', 'BLF': 'BLF', 'BYPAS': 'BYP', 'ML': 'ML', 'RADL': 'RADL', 'HLS': 'HLS', 'VWS': 'VW', 'MT': 'MT', 'GRDN': 'GDNS', 'FT': 'FT', 'GLN': 'GLN', 'CTS': 'CTS', 'SMT': 'SMT', 'KNOL': 'KNLS', 'STATION': 'STA', 'BEND': 'BND', 'CORNER': 'COR', 'POINT': 'PT', 'MDW': 'MDWS', 'BURGS': 'BG', 'ESTATE': 'EST', 'CRSENT': 'CRES', 'CORNERS': 'CORS', 'MOUNT': 'MT', 'MNTAIN': 'MTN', 'MEDOWS': 'MDWS', 'SPRNGS': 'SPGS', 'TURNPIKE': 'TPKE', 'CREEK': 'CRK', 'SQ': 'SQ', 'ST': 'ST', 'ALY': 'ALY', 'ROADS': 'RD', 'RADIEL': 'RADL', 'TRLS': 'TRL', 'RIDGE': 'RDG', 'FORESTS': 'FRST', 'GREEN': 'GRN', 'CAN': 'CYN', 'LF': 'LF', 'GARDN': 'GDNS', 'VDCT': 'VIA', 'LN': 'LN', 'AVN': 'AVE', 'BLUFF': 'BLF', 'CLIFFS': 'CLFS', 'STRAVN': 'STRA', 'FORK': 'FRK', 'STA': 'STA', 'STRAVE': 'STRA', 'KEYS': 'KY', 'STN': 'STA', 'RANCH': 'RNCH', 'HGTS': 'HTS', 'REST': 'RST', 'FORD': 'FRD', 'FRWAY': 'FWY', 'CRSSNG': 'XING', 'CNTR': 'CTR', 'STR': 'ST', 'KNOLL': 'KNLS', 'FORT': 'FT', 'BOUL': 'BLVD', 'HAVEN': 'HVN', 'NCK': 'NCK', 'RST': 'RST', 'PIKES': 'PIKE', 'GLENS': 'GLN', 'SQRE': 'SQ', 'RAPID': 'RPDS', 'PKWAY': 'PKY', 'LK': 'LK', 'GARDENS': 'GDNS', 'PIKE': 'PIKE', 'RAD': 'RADL', 'EXTS': 'EXT', 'BOTTOM': 'BTM', 'STRAV': 'STRA', 'FRRY': 'FRY', 'LCKS': 'LCKS', 'CNYN': 'CYN', 'RD': 'RD', 'PRT': 'PRT', 'PRR': 'PR', 'EXTN': 'EXT', 'ROAD': 'RD', 'CRSE': 'CRSE', 'TPK': 'TPKE', 'SHOARS': 'SHRS', 'VIA': 'VIA', 'XING': 'XING', 'STREME': 'STRM', 'LAKE': 'LK', 'TRAIL': 'TRL', 'RADIAL': 'RADL', 'EXPRESSWAY': 'EXPY', 'JUNCTIONS': 'JCT', 'CLIFF': 'CLFS', 'CNTER': 'CTR', 'TRAFFICWAY': 'TRFY', 'MEADOWS': 'MDWS', 'HARBORS': 'HBR', 'MOUNTAIN': 'MTN', 'GREENS': 'GRN', 'ANNX': 'ANX', 'CEN': 'CTR', 'PKY': 'PKY', 'FALLS': 'FLS', 'STRVN': 'STRA', 'BRNCH': 'BR', 'HILL': 'HL', 'VILLAGE': 'VLG', 'PLNS': 'PLNS', 'SHR': 'SHR', 'MISSN': 'MSN', 'FORG': 'FRG', 'PLAZA': 'PLZ', 'EXPY': 'EXPY', 'SHRS': 'SHRS', 'HWAY': 'HWY', 'SHL': 'SHL', 'HIGHWAY': 'HWY', 'GLEN': 'GLN', 'SHORES': 'SHRS', 'MOUNTIN': 'MTN', 'CRES': 'CRES', 'CANYON': 'CYN', 'LOOP': 'LOOP', 'FRKS': 'FRKS', 'BTM': 'BTM', 'CENTERS': 'CTR', 'COURT': 'CT', 'ISS': 'ISS', 'SPRING': 'SPG', 'TUNL': 'TUNL', 'HARBR': 'HBR', 'LAKES': 'LKS', 'COURTS': 'CTS', 'LANE': 'LN', 'BOTTM': 'BTM', 'JCTION': 'JCT', 'EXPR': 'EXPY', 'STREETS': 'ST', 'EXPW': 'EXPY', 'MISSION': 'MSN', 'CAUSEWAY': 'CSWY', 'VILLIAGE': 'VLG', 'GATEWY': 'GTWY', 'AVNU': 'AVE', 'FRG': 'FRG', 'MOUNTAINS': 'MTN', 'FRK': 'FRK', 'CLF': 'CLFS', 'CLB': 'CLB', 'TRKS': 'TRAK', 'FRT': 'FT', 'FRY': 'FRY', 'BOULV': 'BLVD', 'ISLNDS': 'ISS', 'HVN': 'HVN', 'KEY': 'KY', 'KY': 'KY', 'FLTS': 'FLT', 'BRIDGE': 'BRG', 'DL': 'DL', 'DM': 'DM', 'EXTENSION': 'EXT', 'LODG': 'LDG', 'VISTA': 'VIS', 'BPS': 'BYP', 'ESTATES': 'EST', 'ISLND': 'IS', 'DV': 'DV', 'PATH': 'PATH', 'DR': 'DR', 'HIGHWY': 'HWY', 'VALLEYS': 'VLY', 'CAMP': 'CP', 'RPD': 'RPDS', 'LOOPS': 'LOOP', 'CYN': 'CYN', 'RAPIDS': 'RPDS', 'HOLW': 'HOLW', 'RNCHS': 'RNCH', 'HOLLOW': 'HOLW', 'MLS': 'MLS', 'VALLY': 'VLY', 'MILL': 'ML', 'STRVNUE': 'STRA', 'ANNEX': 'ANX', 'PNES': 'PNES', 'TUNNL': 'TUNL', 'ISLES': 'ISLE', 'LGT': 'LGT', 'CIR': 'CIR', 'MEADOW': 'MDWS', 'TRAILS': 'TRL', 'EXT': 'EXT', 'STREET': 'ST', 'WELLS': 'WLS', 'EXP': 'EXPY', 'BLVD': 'BLVD', 'WY': 'WAY', 'CIRCLES': 'CIR', 'RIV': 'RIV', 'GRDEN': 'GDNS', 'TUNNELS': 'TUNL', 'PATHS': 'PATH', 'KNL': 'KNLS', 'PARK': 'PARK', 'VILLAGES': 'VLG', 'PARKS': 'PARK', 'TRACKS': 'TRAK', 'BLUF': 'BLF', 'PASS': 'PASS', 'BND': 'BND', 'GRDNS': 'GDNS', 'RDGS': 'RDG', 'LNDG': 'LNDG', 'LANDING': 'LNDG', 'RDGE': 'RDG', 'CIRCLE': 'CIR', 'CRT': 'CT', 'LIGHT': 'LGT', 'VLYS': 'VLY', 'FREEWAY': 'FWY', 'SHORE': 'SHR', 'CRK': 'CRK', 'PORT': 'PRT', 'SPNGS': 'SPGS', 'PR': 'PR', 'LDG': 'LDG', 'PT': 'PT', 'FIELDS': 'FLDS', 'DRIV': 'DR', 'HAVN': 'HVN', 'MALL': 'MALL', 'BYPASS': 'BYP', 'PK': 'PARK', 'PL': 'PL', 'BLV': 'BLVD', 'DIVIDE': 'DV', 'CLUB': 'CLB', 'VILL': 'VLG', 'LODGE': 'LDG', 'ANEX': 'ANX', 'NECK': 'NCK', 'TRACE': 'TRCE', 'TRACK': 'TRAK', 'FRST': 'FRST', 'STRT': 'ST', 'RPDS': 'RPDS', 'STRM': 'STRM', 'STRA': 'STRA', 'ANX': 'ANX', 'LCK': 'LCKS', 'COR': 'COR', 'JUNCTION': 'JCT', 'STREAM': 'STRM', 'DVD': 'DV', 'HARB': 'HBR', 'PRK': 'PARK', 'RIVR': 'RIV', 'OVAL': 'OVAL', 'CRECENT': 'CRES', 'VIST': 'VIS', 'MANOR': 'MNR', 'TUNNEL': 'TUNL', 'GTWAY': 'GTWY', 'PKWY': 'PKY', 'AVENU': 'AVE', 'JUNCTON': 'JCT', 'SUMMIT': 'SMT', 'HWY': 'HWY', 'MTIN': 'MTN', 'TRACES': 'TRCE', 'TERRACE': 'TER', 'CK': 'CRK', 'ORCHARD': 'ORCH', 'CENTRE': 'CTR', 'LOCK': 'LCKS', 'COVES': 'CV', 'FIELD': 'FLD', 'STATN': 'STA', 'CR': 'CRK', 'CP': 'CP', 'GROV': 'GRV', 'CV': 'CV', 'CT': 'CT', 'LNDNG': 'LNDG', 'RUN': 'RUN', 'CRESENT': 'CRES', 'PLZ': 'PLZ', 'TRAK': 'TRAK', 'LOCKS': 'LCKS', 'PLN': 'PLN', 'MNTN': 'MTN', 'TPKE': 'TPKE', 'RANCHES': 'RNCH', 'FRWY': 'FWY', 'DIV': 'DV', 'KNOLLS': 'KNLS', 'LIGHTS': 'LGT', 'CRCLE': 'CIR', 'HIWY': 'HWY', 'TERR': 'TER', 'JCT': 'JCT', 'INLT': 'INLT', 'IS': 'IS', 'BROOK': 'BRK', 'BROOKS': 'BRK', 'MTN': 'MTN', 'CIRCL': 'CIR', 'VW': 'VW', 'FLATS': 'FLT', 'ARCADE': 'ARC', 'PINE': 'PNES', 'ARC': 'ARC', 'LDGE': 'LDG', 'BG': 'BG', 'FREEWY': 'FWY', 'HILLS': 'HLS', 'BL': 'BLVD', 'WELL': 'WLS', 'SHLS': 'SHLS', 'BOT': 'BTM', 'BRDGE': 'BRG', 'DRV': 'DR', 'BV': 'BLVD', 'FWY': 'FWY', 'BR': 'BR', 'BCH': 'BCH', 'FORKS': 'FRKS', 'HIWAY': 'HWY', 'BY': 'PASS', 'VL': 'VL', 'HBR': 'HBR', 'TURNPK': 'TPKE', 'CTR': 'CTR', 'CENT': 'CTR', 'SPRNG': 'SPG', 'RVR': 'RIV', 'HOLWS': 'HOLW', 'PRAIRIE': 'PR', 'BRANCH': 'BR', 'VALLEY': 'VLY', 'ALLY': 'ALY', 'GROVE': 'GRV', 'CLFS': 'CLFS', 'RIDGES': 'RDG', 'PORTS': 'PRT', 'VILLAG': 'VLG', 'BYPA': 'BYP', 'VIEWS': 'VW', 'HARBOR': 'HBR', 'SQR': 'SQ', 'SQU': 'SQ', 'BYPS': 'BYP', 'BVD': 'BLVD', 'MANORS': 'MNR', 'ISLE': 'ISLE', 'CRCL': 'CIR', 'BURG': 'BG', 'HLLW': 'HOLW', 'GARDEN': 'GDNS', 'FLS': 'FLS', 'FLT': 'FLT', 'HT': 'HTS', 'HL': 'HL', 'BULEVARD': 'BLVD', 'AVENUE': 'AVE', 'FLD': 'FLD', 'GTWY': 'GTWY', 'LANES': 'LN', 'CENTER': 'CTR', 'VIS': 'VIS', 'MNR': 'MNR', 'PLAINES': 'PLNS', 'MNT': 'MT', 'PLAINS': 'PLNS', 'JUNCTN': 'JCT', 'PTS': 'PT', 'ROW': 'ROW', 'FORGES': 'FRG', 'BOULEVARD': 'BLVD', 'TRL': 'TRL', 'FORDS': 'FRD', 'COURSE': 'CRSE', 'PLACE': 'PL', 'CAPE': 'CPE', 'HEIGHTS': 'HTS', 'SHOAR': 'SHR', 'VIADUCT': 'VIA', 'PARKWY': 'PKY', 'UN': 'UN', 'HTS': 'HTS', 'SHOAL': 'SHL', 'CROSSING': 'XING', 'AVE': 'AVE', 'FLDS': 'FLDS', 'VLGS': 'VLG', 'AVNUE': 'AVE', 'ESTS': 'EST', 'FORGE': 'FRG', 'STRAVENUE': 'STRA', 'MNTNS': 'MTN', 'AVEN': 'AVE', 'VLLY': 'VLY', 'VSTA': 'VIS', 'WALKS': 'WALK', 'TRFY': 'TRFY', 'TER': 'TER', 'PRTS': 'PRT', 'RDS': 'RD', 'MILLS': 'MLS', 'RDG': 'RDG', 'KNLS': 'KNLS', 'CORS': 'CORS', 'CANYN': 'CYN', 'SPURS': 'SPUR', 'VILLE': 'VL', 'VILLG': 'VLG', 'WAYS': 'WAY', 'ISLAND': 'IS', 'SUMIT': 'SMT', 'MDWS': 'MDWS', 'CIRC': 'CIR', 'BRK': 'BRK', 'PRARIE': 'PR', 'BRG': 'BRG', 'GDN': 'GDNS', 'DALE': 'DL', 'TRNPK': 'TPKE', 'WALK': 'WALK', 'HRBOR': 'HBR', 'BLUFFS': 'BLF', 'DRIVE': 'DR', 'PLZA': 'PLZ', 'MSN': 'MSN', 'CRSSING': 'XING', 'PARKWAY': 'PKY', 'SPNG': 'SPG', 'EXTNSN': 'EXT', 'HEIGHT': 'HTS', 'DAM': 'DM', 'TR': 'TRL', 'ALLEY': 'ALY', 'LKS': 'LKS', 'ALLEE': 'ALY', 'POINTS': 'PT', 'FOREST': 'FRST', 'ORCH': 'ORCH', 'PLAIN': 'PLN', 'EST': 'EST', 'STRAVEN': 'STRA', 'SHOALS': 'SHLS', 'RNCH': 'RNCH', 'HOLLOWS': 'HOLW', 'AV': 'AVE', 'SQUARES': 'SQ', 'GDNS': 'GDNS', 'SPGS': 'SPGS', 'VST': 'VIS', 'CRSCNT': 'CRES', 'GATEWAY': 'GTWY', 'UNIONS': 'UN', 'GATWAY': 'GTWY', 'CAUSWAY': 'CSWY'}
    # NOTE! Google seems to be MORE aggressive than the US standard.
    # For example, https://pe.usps.com/text/pub28/28apc_002.htm does not list COUNTY as going to CO

    # Plug in 6600 N County Road 925 W Yorktown IN 47396 9465
    # Into google maps, and you get 6600 N Co Rd 925 W

    # So google is doing even more abbreviations. I'm sticking with USPS.

    def mapover(street):
        street_upper = street.upper()
        longest = ""  # replace the longest first, so e.g., AVENUE doesnt go to AVEE because AVENU gets replaced first
        for m in mapping:
            # we dont want to replace the Aven in Westhaven. Look for _m_ or _m
            if " {0}".format(m) in street_upper or " {0} ".format(m) in street_upper:
                if len(m) > len(longest):
                    longest = m
        if longest != "":
            return street_upper.replace(longest, mapping[longest])
        else:
            return street

    # we might have to map over mutliple times like AVENUE EXTENSION
    keep_going = True
    old_street = street
    while keep_going:
        street = mapover(old_street)
        if street == old_street:
            keep_going = False
        else:
            old_street = street
    return street
