import pytest
from usaddress.assembly import normalize_address, AddressUnparsable, Address


def assert_address(add, number, street, city, state, zipc):
    """assertion for address object"""
    assert(add.number == number)
    assert(add.street == street)
    assert(add.city == city)
    assert(add.state == state)
    assert(add.zipc == zipc)


a = normalize_address("10422 Old Highway 25 Aberdeen MS 39730 9483")
assert_address(a, "10422", "OLD HWY 25", "ABERDEEN", "MS", "39730-9483")

a = normalize_address("6600 N County Road 925 W Yorktown IN 47396 9465")
assert_address(a, "6600", "N COUNTY RD 925 W", "YORKTOWN", "IN", "47396-9465")

a = normalize_address("7263 N 670 E Needham IN 46162 9734")
assert_address(a, "7263", "N 670 E", "NEEDHAM", "IN", "46162-9734")

a = normalize_address("2336 S County Road 900 E Bldg TRLR Dugger IN 47848 8114")
assert_address(a, "2336", "S COUNTY RD 900 E BLDG TRLR", "DUGGER", "IN", "47848-8114")

a = normalize_address("19161 1/2 State Highway 120 Bldg TRLR Groveland CA 95321 9701")
assert isinstance(a, Address)
assert_address(a, "19161 1/2", "STATE HWY 120 BLDG TRLR", "GROVELAND", "CA", "95321-9701")
a_usps = a.tousps()
assert(a_usps == "19161 1/2 STATE HWY 120 BLDG TRLR, GROVELAND CA 95321-9701")
assert(str(a) == "Address(number = 19161 1/2, street = STATE HWY 120 BLDG TRLR, city = GROVELAND, state = CA, zip = 95321-9701)")
assert(a.__str__() == "Address(number = 19161 1/2, street = STATE HWY 120 BLDG TRLR, city = GROVELAND, state = CA, zip = 95321-9701)")

a = normalize_address("111 fake avenue faketown nj 66006")
assert_address(a, "111", "FAKE AVE", "FAKETOWN", "NJ", "66006")

a = normalize_address("7710 N Madsen Ave Clovis CA 93619 8833")
assert_address(a, "7710", "N MADSEN AVE", "CLOVIS", "CA", "93619-8833")

a = normalize_address("1180 Westhaven Dr N Unit A Trinidad CA 95570 9696")
assert_address(a, "1180", "WESTHAVEN DR N UNIT A", "TRINIDAD", "CA", "95570-9696")

a = normalize_address("111 FAKE EXTENSION FakeTOwN NJ 66006")
assert_address(a, "111", "FAKE EXT", "FAKETOWN", "NJ", "66006")

a = normalize_address("111 FAKE AVENU EXTENSION FakeTOwN NJ 66006")
assert_address(a, "111", "FAKE AVE EXT", "FAKETOWN", "NJ", "66006")

a = normalize_address("111 FAKE STREET FakeTOwN NJ 66006")
assert_address(a, "111", "FAKE ST", "FAKETOWN", "NJ", "66006")

# Non-intentional raises: These shouldn't raise, but at the time of writing, these were unparsable by the ML lib I'm using. not sure which "might be fixed" by that ML lib later.

with pytest.raises(AddressUnparsable):
    a = normalize_address("7105 Mitchell Warrenton Rd Unit DATA Fl 1 Mitchell GA 30820")

with pytest.raises(AddressUnparsable):
    a = normalize_address("300 Avenue N Anson TX 79501 2414")

with pytest.raises(AddressUnparsable):
    a = normalize_address("69 Eagle Ln Unit OLD Oil Trough AR 72564 9790")

with pytest.raises(AddressUnparsable):
    a = normalize_address("1795 S Main Street Ext Surrency GA 31563")

with pytest.raises(AddressUnparsable):
    a = normalize_address("2446 Highway 42 Calera AL 35040 5240")

with pytest.raises(AddressUnparsable):
    a = normalize_address("5066 4th Eagle River MI 49950")

# Purposeful raises

with pytest.raises(AddressUnparsable):  # no number
    a = normalize_address("5th Street Aberdeen MS 39730 9483")
