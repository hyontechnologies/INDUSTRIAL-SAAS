from app.tag_router import TagRouter


def test_tag_router_temperature():
    router = TagRouter()
    hypertable = router.route_tag("TT-201", "temperature")
    assert hypertable == "telemetry_temperature"


def test_tag_router_pressure():
    router = TagRouter()
    hypertable = router.route_tag("PT-201", "pressure")
    assert hypertable == "telemetry_pressure"


def test_tag_router_raw_fallback():
    router = TagRouter()
    hypertable = router.route_tag("UNKNOWN-100", None)
    assert hypertable == "telemetry_raw"


def test_tag_router_level():
    router = TagRouter()
    hypertable = router.route_tag("LT-201", "level")
    assert hypertable == "telemetry_level"
