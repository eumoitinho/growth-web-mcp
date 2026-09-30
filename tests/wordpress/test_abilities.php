<?php
// Minimal WordPress boundary stubs; execute the real parser and permission function.
define('ABSPATH', __DIR__);
function add_action($event, $callback) {}
function wp_parse_url($url, $component) { return parse_url($url, $component); }
$GLOBALS['qa_permission'] = false;
function current_user_can($cap) { return $cap === 'growth_read' && $GLOBALS['qa_permission']; }
require __DIR__ . '/../../wordpress/growth-abilities.php';
function check($condition, $label) { if (!$condition) throw new Exception($label); }
check(growth_can_read() === false, 'deny without capability');
$GLOBALS['qa_permission'] = true;
check(growth_can_read() === true, 'allow explicit capability');
$markup = '<script src="https://www.googletagmanager.com/gtm.js?id=GTM-TEST123"></script>' .
  '<script>gtag("config", "G-TEST123456");fbq("init","1234567890");hbspt.forms.create({portalId:"123456",formId:"12345678-abcd-abcd-abcd-123456789012"});</script>' .
  '<a href="https://wa.me/123456">Contact</a><span>private@example.invalid</span>';
$data = growth_scan_markup($markup);
check($data['gtm_containers'] === ['GTM-TEST123'], 'GTM detection');
check($data['ga4_measurement'] === ['G-TEST123456'], 'GA4 detection');
check($data['meta_pixel'] === ['1234567890'], 'Meta detection');
check($data['hubspot_forms_embed'], 'HubSpot detection');
check($data['whatsapp_links'] === 1, 'WhatsApp detection');
check(!str_contains(json_encode($data), 'private@example.invalid'), 'No copied contact data');
check(growth_scan_markup('')['gtm_containers'] === [], 'Empty markup');
echo "WordPress parser and permissions: PASS\n";
