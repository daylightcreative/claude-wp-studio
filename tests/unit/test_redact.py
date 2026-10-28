from wpstudio import redact


def test_wp_config_define_is_masked():
    line = "define( 'DB_PASSWORD', 'p4ss\\'word' );"
    assert redact.redact_line(line) == "define( 'DB_PASSWORD', '[redacted]' );"


def test_salts_are_masked_but_other_constants_are_not():
    text = "define('AUTH_KEY', 'abc');\ndefine('DB_NAME', 'wordpress');"
    assert redact.redact_text(text) == "define('AUTH_KEY', '[redacted]');\ndefine('DB_NAME', 'wordpress');"


def test_wp_config_list_rows_are_masked():
    assert redact.redact_line("DB_PASSWORD\tdbpw-e2e-secret\tconstant") == "DB_PASSWORD\t[redacted]"
    assert redact.redact_line("| NONCE_SALT | x9y8z7 | constant |") .startswith("| NONCE_SALT | [redacted]")
    assert redact.redact_line("DB_USER\twp\tconstant") == "DB_USER\twp\tconstant"


def test_json_output_is_masked():
    line = '[{"name":"DB_PASSWORD","value":"s3cret","type":"constant"}]'
    assert redact.redact_line(line) == '[{"name":"DB_PASSWORD","value":"[redacted]","type":"constant"}]'


def test_known_literal_values_are_masked_anywhere():
    assert redact.redact_line("login with Hunter2-secret! now", ["Hunter2-secret!"]) == "login with [redacted] now"


def test_config_get_of_a_secret_is_detected():
    assert redact.wp_secret_get(["config", "get", "DB_PASSWORD"]) is True
    assert redact.wp_secret_get(["config", "get", "db_password", "--format=json"]) is True
    assert redact.wp_secret_get(["config", "get", "DB_NAME"]) is False
