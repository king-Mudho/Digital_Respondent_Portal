from apps.qa.required_fields import required_field_names

SURVEY = [
    {"type": "start", "name": "start"},
    {"type": "hidden", "name": "sample_id"},
    {"type": "begin_group", "name": "admin_consent", "relevant": ""},
    {"type": "select_one yes_no", "name": "E1", "required": True},
    {"type": "select_one yes_no", "name": "E2", "required": True, "relevant": "${E1}='yes'"},
    {"type": "note", "name": "e1_end", "relevant": "${E1}='no'"},
    {"type": "end_group"},
    {"type": "calculate", "name": "SAMPLE_ID_FINAL"},
    {"type": "begin_group", "name": "profile", "relevant": "${C1}='yes'"},
    {"type": "select_one org_type", "name": "P1", "required": True},
    {"type": "text", "name": "P1_OTHER", "required": True, "relevant": "${P1}='other'"},
    {"type": "text", "name": "D3", "required": False},
    {"type": "end_group"},
]


def test_required_fields_follow_the_form_with_group_paths():
    assert required_field_names(SURVEY) == ["SAMPLE_ID_FINAL", "admin_consent/E1", "profile/P1"]
