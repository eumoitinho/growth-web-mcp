import copy
import re
from pathlib import Path

import pytest
import yaml
from scripts.render_bq import taxonomy_rows, site_scope_case, sql_str

ROOT = Path(__file__).resolve().parents[2]


def test_taxonomy_rejects_collisions_and_unknown_alias_targets():
    config = yaml.safe_load((ROOT / 'config/event-taxonomy.yaml').read_text())
    assert "'generate_lead'" in taxonomy_rows(config)
    duplicate = copy.deepcopy(config)
    duplicate['noise'].append('generate_lead')
    with pytest.raises(SystemExit, match='more than once'):
        taxonomy_rows(duplicate)
    config['aliases']['missing'] = ['legacy']
    with pytest.raises(SystemExit, match='not a canonical'):
        taxonomy_rows(config)


@pytest.mark.parametrize('host,scope', [('www.example.com','website'), ('blog.example.com','blog'), ('lp.example.com','landing_pages'), ('app.example.com','product'), ('preview.example.com','staging'), ('evil-example.com','unknown')])
def test_hostname_contract(host, scope):
    config = yaml.safe_load((ROOT / 'config/site-scope.yaml').read_text())
    actual = next((r['scope'] for r in config['hostnames'] if re.search(r['pattern'], host)), config['default_scope'])
    assert actual == scope
    assert 'REGEXP_CONTAINS' in site_scope_case('hostname', config)


def test_sql_escaping_and_invalid_patterns():
    assert sql_str(None) == 'NULL'
    assert sql_str("a'b") == "'a\\'b'"
    with pytest.raises(re.error):
        site_scope_case('host', {'hostnames': [{'pattern': '[', 'scope': 'website'}]})
