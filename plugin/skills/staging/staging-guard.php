<?php
/**
 * Plugin Name: Staging Guard (wp-studio)
 * Description: On any copy of the site that is not production, stops outbound email and
 *              requests to named webhook hosts, so a staging site never mails real people
 *              or adds them to real lists. Does nothing on production.
 * Version:     1.0.0
 * License:     MIT
 *
 * Install as wp-content/mu-plugins/staging-guard.php on EVERY environment (production too:
 * a push that copies files will carry it across anyway, and on production it is inert).
 *
 * Configure in wp-config.php on EVERY environment, with the SAME value everywhere:
 *
 *   define( 'WPSTUDIO_PRODUCTION_URL', 'https://example.com' );
 *
 * Optional, also the same everywhere — hosts whose requests are blocked off production
 * (a host also matches its subdomains):
 *
 *   define( 'WPSTUDIO_STAGING_BLOCKED_HOSTS', 'hooks.zapier.com,api.example-crm.com' );
 *
 * or add hosts in code with the 'wpstudio_staging_blocked_hosts' filter.
 *
 * Why home_url() and not wp_get_environment_type(): on some managed hosts a staging copy
 * reports 'production' (the default when nothing is set), and an environment constant stored
 * in the database or copied by a push reports the wrong answer on the environment that matters.
 * home_url() is what the copy is actually serving, and the production URL is identical on
 * every environment, so copying it anywhere is harmless.
 *
 * Fails closed: if WPSTUDIO_PRODUCTION_URL is missing or unparseable, the site is treated as
 * NOT production (mail and listed hosts blocked) and administrators see a notice. Set the
 * constant on production before or together with installing this file.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Lower-case host without a leading "www.", or '' when the URL has no host.
 *
 * @param string $url Any URL.
 * @return string
 */
function wpstudio_sg_normalize_host( $url ) {
	$host = wp_parse_url( (string) $url, PHP_URL_HOST );
	if ( ! is_string( $host ) || '' === $host ) {
		return '';
	}
	$host = strtolower( $host );
	if ( 0 === strpos( $host, 'www.' ) ) {
		$host = substr( $host, 4 );
	}
	return $host;
}

/**
 * The production host from WPSTUDIO_PRODUCTION_URL, or '' when it is not configured.
 *
 * @return string
 */
function wpstudio_sg_production_host() {
	if ( ! defined( 'WPSTUDIO_PRODUCTION_URL' ) ) {
		return '';
	}
	return wpstudio_sg_normalize_host( WPSTUDIO_PRODUCTION_URL );
}

/**
 * True only when the guard is configured and this copy serves the production host.
 *
 * @return bool
 */
function wpstudio_sg_is_production() {
	$production = wpstudio_sg_production_host();
	if ( '' === $production ) {
		return false; // Not configured: fail closed.
	}
	return wpstudio_sg_normalize_host( home_url() ) === $production;
}

/**
 * Hosts whose outbound HTTP requests are refused off production.
 *
 * @return string[]
 */
function wpstudio_sg_blocked_hosts() {
	$hosts = array();
	if ( defined( 'WPSTUDIO_STAGING_BLOCKED_HOSTS' ) ) {
		$hosts = explode( ',', (string) WPSTUDIO_STAGING_BLOCKED_HOSTS );
	}
	/**
	 * Filters the hosts blocked off production. A host also matches its subdomains.
	 *
	 * @param string[] $hosts Host names, e.g. 'hooks.zapier.com'.
	 */
	$hosts = (array) apply_filters( 'wpstudio_staging_blocked_hosts', $hosts );

	$clean = array();
	foreach ( $hosts as $host ) {
		$host = strtolower( trim( (string) $host ) );
		if ( '' !== $host ) {
			$clean[] = $host;
		}
	}
	return array_values( array_unique( $clean ) );
}

/**
 * Whether $host is one of $blocked or a subdomain of one.
 *
 * @param string   $host    Request host, lower case.
 * @param string[] $blocked Blocked hosts, lower case.
 * @return bool
 */
function wpstudio_sg_host_matches( $host, array $blocked ) {
	foreach ( $blocked as $entry ) {
		if ( $host === $entry ) {
			return true;
		}
		$suffix = '.' . $entry;
		if ( strlen( $host ) > strlen( $suffix ) && substr( $host, -strlen( $suffix ) ) === $suffix ) {
			return true;
		}
	}
	return false;
}

if ( ! wpstudio_sg_is_production() ) {

	/*
	 * Email: pre_wp_mail (WordPress 5.7+) short-circuits wp_mail() when it returns non-null.
	 * Returning true reports the message as sent, so forms and flows can be tested end to end
	 * on staging; the suppressed message is logged instead of delivered.
	 */
	add_filter(
		'pre_wp_mail',
		static function ( $return, $atts ) {
			if ( null !== $return ) {
				return $return; // Another plugin already decided.
			}
			$to      = isset( $atts['to'] ) ? $atts['to'] : array();
			$to      = is_array( $to ) ? $to : array_filter( array_map( 'trim', explode( ',', (string) $to ) ) );
			$subject = isset( $atts['subject'] ) ? (string) $atts['subject'] : '';
			error_log(
				sprintf(
					'[staging-guard] suppressed email to %d recipient(s), subject: %s',
					count( $to ),
					$subject
				)
			);
			return true;
		},
		PHP_INT_MAX,
		2
	);

	/*
	 * Webhooks and APIs: pre_http_request (WordPress 2.9+) short-circuits any request made
	 * through the WordPress HTTP API when it returns a WP_Error. Only listed hosts are
	 * blocked, so updates, licence checks and everything else keep working.
	 */
	add_filter(
		'pre_http_request',
		static function ( $response, $parsed_args, $url ) {
			if ( false !== $response ) {
				return $response; // Another plugin already short-circuited.
			}
			$blocked = wpstudio_sg_blocked_hosts();
			if ( empty( $blocked ) ) {
				return $response;
			}
			$host = wpstudio_sg_normalize_host( $url );
			$raw  = strtolower( (string) wp_parse_url( (string) $url, PHP_URL_HOST ) );
			if ( '' === $raw ) {
				return $response;
			}
			if ( wpstudio_sg_host_matches( $raw, $blocked ) || wpstudio_sg_host_matches( $host, $blocked ) ) {
				error_log( '[staging-guard] blocked outbound request to ' . $raw );
				return new WP_Error(
					'wpstudio_staging_guard',
					'Blocked by staging guard: outbound requests to ' . $raw . ' are disabled off production.'
				);
			}
			return $response;
		},
		PHP_INT_MAX,
		3
	);

	/* Tell administrators the guard is active, or that it is unconfigured. */
	add_action(
		'admin_notices',
		static function () {
			if ( ! current_user_can( 'manage_options' ) ) {
				return;
			}
			if ( '' === wpstudio_sg_production_host() ) {
				$message = 'Staging guard: WPSTUDIO_PRODUCTION_URL is not set in wp-config.php, so outbound email and listed webhooks are blocked on this site. Set it to the production URL on every environment.';
				$class   = 'notice notice-error';
			} else {
				$message = 'Staging guard is active: this is not the production site, so outbound email and listed webhooks are blocked.';
				$class   = 'notice notice-warning';
			}
			printf( '<div class="%1$s"><p>%2$s</p></div>', esc_attr( $class ), esc_html( $message ) );
		}
	);
}
