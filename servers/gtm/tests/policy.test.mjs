import test from 'node:test';
import assert from 'node:assert/strict';
import { policyFromEnv, READ_ACTIONS } from '../dist/policy.js';
for (const action of READ_ACTIONS) {
  test(`default permits ${action}`, () => assert.equal(policyFromEnv({}).check('gtm_tag', action), null));
}
for (const action of ['create', 'update', 'remove', 'publish', 'unknown']) {
  test(`default refuses ${action}`, () => assert.ok(policyFromEnv({}).check('gtm_tag', action)));
}
test('write permissions and OAuth scopes match explicit flags', () => {
  const limited = policyFromEnv({ GTM_ACCESS_MODE: 'write' });
  assert.equal(limited.check('gtm_tag', 'create'), null);
  assert.ok(limited.check('gtm_tag', 'remove'));
  assert.ok(limited.check('gtm_tag', 'publish'));
  const full = policyFromEnv({ GTM_ACCESS_MODE: 'write', GTM_ALLOW_DELETE: 'true', GTM_ALLOW_PUBLISH: '1' });
  assert.equal(full.check('gtm_tag', 'remove'), null);
  assert.equal(full.check('gtm_tag', 'publish'), null);
  assert.ok(full.scopes.some(s => s.endsWith('.publish')));
  for (const name of ['gtm_account', 'gtm_user_permission', 'gtm_environment', 'gtm_container']) {
    assert.ok(full.check(name, 'update'));
  }
});
test('flags cannot elevate read access; invalid modes fail closed', () => {
  assert.ok(policyFromEnv({ GTM_ALLOW_PUBLISH: 'true' }).check('gtm_tag', 'publish'));
  assert.throws(() => policyFromEnv({ GTM_ACCESS_MODE: 'admin' }));
});
