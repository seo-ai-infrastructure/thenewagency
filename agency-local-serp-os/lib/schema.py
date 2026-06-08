"""JSON-Schema validation for the core artifacts (shared_schemas/). Cheap insurance against
fixture/schema drift — the tracker validates every snapshot record at write time, the scorer
validates every lane score, and the e2e test asserts both."""
import json, functools, pathlib
import jsonschema

_SCHEMAS = pathlib.Path(__file__).resolve().parents[1] / "shared_schemas"
SNAPSHOT = "serp_feature_snapshot.schema.json"
ESTATE = "estate_score.schema.json"
SATURATION = "serp_saturation.schema.json"
ENDPOINTS = "endpoints.schema.json"
AEO_AUDIT = "aeo_audit.schema.json"


@functools.lru_cache(maxsize=None)
def _schema(name):
    return json.loads((_SCHEMAS / name).read_text())


def validate(record, schema_name):
    """Raise jsonschema.ValidationError if `record` doesn't match shared_schemas/<schema_name>."""
    jsonschema.validate(record, _schema(schema_name))
