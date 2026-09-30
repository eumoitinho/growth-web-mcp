<?php
/**
 * Plugin Name: Growth Abilities (read-only)
 * Description: Read-only abilities for the growth agent, exposed over MCP by the official WordPress MCP Adapter. Lists active plugins, tracking snippets, forms and pages so the agent can see WHERE tags and form integrations come from.
 * Version: 0.1.0
 * Requires at least: 6.9
 * Requires PHP: 8.0
 * License: Apache-2.0
 *
 * Install as a must-use plugin: wp-content/mu-plugins/growth-abilities.php
 * Requires the WordPress MCP Adapter plugin (github.com/WordPress/mcp-adapter).
 *
 * Every ability is read-only and only runs for users with the
 * `growth_read` capability (role "Growth Agent", created below). No
 * option values, credentials or personal data are returned: only plugin
 * metadata, IDs found in markup (GTM-, G-, AW-, pixel, HubSpot portal/form),
 * file paths and page URLs.
 */

defined( 'ABSPATH' ) || exit;

const GROWTH_CAP      = 'growth_read';
const GROWTH_CATEGORY = 'growth';

/**
 * Dedicated low-privilege role for the agent user: can read, cannot edit.
 */
add_action(
	'init',
	static function () {
		if ( ! get_role( 'growth_agent' ) ) {
			add_role( 'growth_agent', 'Growth Agent (read-only)', array( 'read' => true, GROWTH_CAP => true ) );
		}
		$admin = get_role( 'administrator' );
		if ( $admin && ! $admin->has_cap( GROWTH_CAP ) ) {
			$admin->add_cap( GROWTH_CAP );
		}
	}
);

function growth_can_read(): bool {
	return current_user_can( GROWTH_CAP );
}

/**
 * Tracking IDs and third-party script hosts found in a chunk of HTML/JS.
 */
function growth_scan_markup( string $markup ): array {
	$patterns = array(
		'gtm_containers'   => '/\bGTM-[A-Z0-9]{4,10}\b/',
		'ga4_measurement'  => '/\bG-[A-Z0-9]{6,12}\b/',
		'google_ads'       => '/\bAW-\d{6,12}\b/',
		'meta_pixel'       => '/fbq\(\s*[\'"]init[\'"]\s*,\s*[\'"](\d{8,20})[\'"]/',
		'hubspot_portal'   => '/js(?:-[a-z0-9]+)?\.hs-scripts\.com\/(\d+)\.js|portalId[\'"]?\s*[:=]\s*[\'"]?(\d{4,12})/',
		'hubspot_form_ids' => '/formId[\'"]?\s*[:=]\s*[\'"]([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i',
	);
	$found = array();
	foreach ( $patterns as $key => $regex ) {
		preg_match_all( $regex, $markup, $m );
		$values = array();
		foreach ( array_slice( $m, count( $m ) > 1 ? 1 : 0 ) as $group ) {
			$values = array_merge( $values, $group );
		}
		$found[ $key ] = array_values( array_unique( array_filter( $values ) ) );
	}

	preg_match_all( '/<script[^>]+src=[\'"]([^\'"]+)[\'"]/i', $markup, $scripts );
	$hosts = array();
	foreach ( $scripts[1] as $src ) {
		$host = wp_parse_url( $src, PHP_URL_HOST );
		if ( $host ) {
			$hosts[ $host ] = ( $hosts[ $host ] ?? 0 ) + 1;
		}
	}
	arsort( $hosts );
	$found['script_hosts']          = $hosts;
	$found['inline_gtag_config']    = (bool) preg_match( '/gtag\(\s*[\'"]config[\'"]/', $markup );
	$found['hubspot_forms_embed']   = (bool) preg_match( '/hbspt\.forms\.create/', $markup );
	$found['hubspot_forms_api']     = (bool) preg_match( '/api\.hsforms\.com|submissions\/v3\/integration/', $markup );
	$found['whatsapp_links']        = (int) preg_match_all( '/(?:wa\.me|api\.whatsapp\.com)\//', $markup );
	return $found;
}

add_action(
	'wp_abilities_api_categories_init',
	static function () {
		wp_register_ability_category(
			GROWTH_CATEGORY,
			array(
				'label'       => 'Growth',
				'description' => 'Read-only site inventory for tracking and inbound audits.',
			)
		);
	}
);

add_action(
	'wp_abilities_api_init',
	static function () {
		$common = array(
			'category'            => GROWTH_CATEGORY,
			'permission_callback' => 'growth_can_read',
			'meta'                => array(
				'annotations' => array(
					'readonly'    => true,
					'destructive' => false,
					'idempotent'  => true,
				),
				'mcp'         => array( 'public' => true ),
			),
		);

		wp_register_ability(
			'growth/list-active-plugins',
			$common + array(
				'label'            => 'List active plugins',
				'description'      => 'Active plugins (and must-use plugins) with name, version, author and plugin URI. Use to find plugins that inject GTM, gtag, Meta pixel, HubSpot or forms.',
				'input_schema'     => array( 'type' => 'object', 'properties' => new stdClass() ),
				'output_schema'    => array( 'type' => 'object' ),
				'execute_callback' => static function () {
					if ( ! function_exists( 'get_plugins' ) ) {
						require_once ABSPATH . 'wp-admin/includes/plugin.php';
					}
					$active  = (array) get_option( 'active_plugins', array() );
					$plugins = array();
					foreach ( get_plugins() as $file => $data ) {
						if ( in_array( $file, $active, true ) ) {
							$plugins[] = array(
								'file'    => $file,
								'name'    => $data['Name'],
								'version' => $data['Version'],
								'author'  => wp_strip_all_tags( $data['Author'] ),
								'uri'     => $data['PluginURI'],
							);
						}
					}
					$mu = array();
					foreach ( get_mu_plugins() as $file => $data ) {
						$mu[] = array( 'file' => $file, 'name' => $data['Name'], 'version' => $data['Version'] );
					}
					return array(
						'wordpress_version' => get_bloginfo( 'version' ),
						'theme'             => wp_get_theme()->get( 'Name' ) . ' ' . wp_get_theme()->get( 'Version' ),
						'active_plugins'    => $plugins,
						'mu_plugins'        => $mu,
					);
				},
			)
		);

		wp_register_ability(
			'growth/list-tracking-snippets',
			$common + array(
				'label'            => 'List tracking snippets on a page',
				'description'      => 'Fetches a page of this site server-side and returns the tracking IDs found (GTM-, G-, AW-, Meta pixel, HubSpot portal/form IDs), third-party script hosts, and whether HubSpot forms are embedded or posted via the Forms API. Also reports tracking IDs configured in common header/footer and GTM plugins (IDs only).',
				'input_schema'     => array(
					'type'       => 'object',
					'properties' => array(
						'path' => array(
							'type'        => 'string',
							'description' => 'Path on this site, e.g. "/" or "/demonstracao". Only this site\'s host is fetched.',
							'default'     => '/',
						),
					),
				),
				'output_schema'    => array( 'type' => 'object' ),
				'execute_callback' => static function ( $input = array() ) {
					$path = '/' . ltrim( (string) ( $input['path'] ?? '/' ), '/' );
					$url  = home_url( $path );
					if ( wp_parse_url( $url, PHP_URL_HOST ) !== wp_parse_url( home_url(), PHP_URL_HOST ) ) {
						return new WP_Error( 'growth_bad_path', 'Only paths on this site can be fetched.' );
					}
					$response = wp_remote_get( $url, array( 'timeout' => 20, 'redirection' => 3 ) );
					if ( is_wp_error( $response ) ) {
						return $response;
					}
					$page = growth_scan_markup( (string) wp_remote_retrieve_body( $response ) );

					// IDs configured in plugins that inject code (values are scanned, never returned).
					$option_sources = array(
						'insert_headers_footers_header' => 'ihaf_insert_header',
						'insert_headers_footers_footer' => 'ihaf_insert_footer',
						'gtm4wp'                        => 'gtm4wp-options',
						'hubspot_leadin_portal'         => 'leadin_portalId',
					);
					$configured = array();
					foreach ( $option_sources as $label => $option ) {
						$value = get_option( $option, null );
						if ( null !== $value ) {
							// Keep only what was actually found (non-empty lists, true flags, counts > 0).
							$configured[ $label ] = array_filter(
								growth_scan_markup( is_scalar( $value ) ? (string) $value : (string) wp_json_encode( $value ) )
							);
						}
					}
					return array(
						'url'           => $url,
						'http_status'   => wp_remote_retrieve_response_code( $response ),
						'page'          => $page,
						'configured_in' => $configured,
					);
				},
			)
		);

		wp_register_ability(
			'growth/list-forms',
			$common + array(
				'label'            => 'List forms and their HubSpot wiring',
				'description'      => 'Forms known to this site: Contact Form 7, WPForms and Gravity Forms entries (id, title), HubSpot form embeds found in published content (page URL + form GUID), and theme/plugin files that post to the HubSpot Forms API (file + line numbers).',
				'input_schema'     => array( 'type' => 'object', 'properties' => new stdClass() ),
				'output_schema'    => array( 'type' => 'object' ),
				'execute_callback' => static function () {
					$result = array( 'form_plugins' => array() );

					foreach ( array( 'wpcf7_contact_form' => 'contact-form-7', 'wpforms' => 'wpforms' ) as $post_type => $label ) {
						if ( post_type_exists( $post_type ) ) {
							$result['form_plugins'][ $label ] = array_map(
								static fn( $p ) => array( 'id' => $p->ID, 'title' => $p->post_title ),
								get_posts( array( 'post_type' => $post_type, 'numberposts' => 200, 'post_status' => 'publish' ) )
							);
						}
					}
					if ( class_exists( 'GFAPI' ) ) {
						$result['form_plugins']['gravity-forms'] = array_map(
							static fn( $f ) => array( 'id' => $f['id'], 'title' => $f['title'] ),
							GFAPI::get_forms()
						);
					}

					// HubSpot embeds in published content.
					$embeds = array();
					$posts  = get_posts(
						array(
							'post_type'   => 'any',
							'post_status' => 'publish',
							'numberposts' => 500,
							's'           => 'formId',
						)
					);
					foreach ( $posts as $post ) {
						$ids = growth_scan_markup( $post->post_content )['hubspot_form_ids'];
						if ( $ids ) {
							$embeds[] = array( 'url' => get_permalink( $post ), 'hubspot_form_ids' => $ids );
						}
					}
					$result['hubspot_embeds_in_content'] = $embeds;

					// Custom code posting to the HubSpot Forms API (theme + plugins).
					$needles = array( 'api.hsforms.com', 'submissions/v3/integration', 'hbspt.forms.create', 'hubspotutk' );
					$roots   = array_unique( array( get_stylesheet_directory(), get_template_directory(), WP_PLUGIN_DIR, WPMU_PLUGIN_DIR ) );
					$hits    = array();
					$scanned = 0;
					foreach ( $roots as $root ) {
						if ( ! is_dir( $root ) ) {
							continue;
						}
						$iterator = new RecursiveIteratorIterator( new RecursiveDirectoryIterator( $root, FilesystemIterator::SKIP_DOTS ) );
						foreach ( $iterator as $file ) {
							if ( count( $hits ) >= 200 || ++$scanned > 20000 ) {
								break 2;
							}
							$ext = strtolower( $file->getExtension() );
							if ( ! in_array( $ext, array( 'php', 'js' ), true ) || $file->getSize() > 1048576 || str_contains( $file->getPathname(), '/node_modules/' ) ) {
								continue;
							}
							$lines = @file( $file->getPathname(), FILE_IGNORE_NEW_LINES ); // phpcs:ignore
							if ( ! $lines ) {
								continue;
							}
							foreach ( $lines as $n => $line ) {
								foreach ( $needles as $needle ) {
									if ( str_contains( $line, $needle ) ) {
										$hits[] = array(
											'file'   => str_replace( ABSPATH, '', $file->getPathname() ),
											'line'   => $n + 1,
											'match'  => $needle,
										);
										break;
									}
								}
							}
						}
					}
					$result['code_referencing_hubspot_forms'] = $hits;
					$result['files_scanned']                  = min( $scanned, 20000 );
					return $result;
				},
			)
		);

		wp_register_ability(
			'growth/list-pages',
			$common + array(
				'label'            => 'List published pages',
				'description'      => 'Published pages (and optionally other public post types) with URL, template, last modified date and whether the content embeds a form or WhatsApp link. Use to build config/site-scope.yaml and the list of landing pages.',
				'input_schema'     => array(
					'type'       => 'object',
					'properties' => array(
						'post_type' => array( 'type' => 'string', 'default' => 'page', 'description' => 'page, post, or another public post type.' ),
						'limit'     => array( 'type' => 'integer', 'default' => 300, 'maximum' => 1000 ),
					),
				),
				'output_schema'    => array( 'type' => 'object' ),
				'execute_callback' => static function ( $input = array() ) {
					$post_type = sanitize_key( $input['post_type'] ?? 'page' );
					if ( ! post_type_exists( $post_type ) || ! get_post_type_object( $post_type )->public ) {
						return new WP_Error( 'growth_bad_post_type', 'Unknown or non-public post type.' );
					}
					$posts = get_posts(
						array(
							'post_type'   => $post_type,
							'post_status' => 'publish',
							'numberposts' => min( 1000, max( 1, (int) ( $input['limit'] ?? 300 ) ) ),
							'orderby'     => 'modified',
						)
					);
					return array(
						'post_type' => $post_type,
						'count'     => count( $posts ),
						'items'     => array_map(
							static function ( $p ) {
								$scan = growth_scan_markup( $p->post_content );
								return array(
									'url'            => get_permalink( $p ),
									'title'          => $p->post_title,
									'template'       => get_page_template_slug( $p ) ?: 'default',
									'modified'       => $p->post_modified_gmt,
									'hubspot_forms'  => $scan['hubspot_form_ids'],
									'whatsapp_links' => $scan['whatsapp_links'],
								);
							},
							$posts
						),
					);
				},
			)
		);
	}
);
