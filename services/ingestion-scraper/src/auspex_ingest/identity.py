from uuid import NAMESPACE_URL, UUID, uuid5


def compute_event_id(
    canonical_id: str | None, source_type: str, external_id: str
) -> UUID:
    if canonical_id is not None:
        return uuid5(NAMESPACE_URL, canonical_id)
    return uuid5(NAMESPACE_URL, f"{source_type}:{external_id}")


def compute_extraction_id(
    event_id: UUID,
    schema_version: str,
    prompt_version: str,
    prefilter_version: str,
    extraction_model: str,
) -> UUID:
    key = f"{event_id}:{schema_version}:{prompt_version}:{prefilter_version}:{extraction_model}"
    return uuid5(NAMESPACE_URL, key)
