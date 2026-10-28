<?php
/**
 * Plugin Name: WP Studio Hardening
 * Description: Application-level hardening for a site maintained over SSH and WP-CLI:
 *              XML-RPC off, username enumeration blocked, version hidden, Application
 *              Passwords off, security headers, generic login errors, the dashboard code
 *              editors off, and an optional login throttle. Asserts its own result and the
 *              companion update policy through a Site Health test and an admin notice.
 *              A must-use plugin cannot be deactivated from the dashboard and survives
 *              theme and plugin changes.
 * Version:     2.0.0
 * License:     MIT
 *
 * Install as wp-content/mu-plugins/wpstudio-hardening.php.
 *
 * What this file deliberately does NOT do: define DISALLOW_FILE_MODS. That constant stops
 * every automatic update, security releases included, and on an unattended site that is
 * negative security. The posture check below fails if it is set.
 *
 * Hook names verified against WordPress 6.9.1 source and developer.wordpress.org (2026-10-28);
 * template_redirect, redirect_canonical() and wp_login_errors re-checked against 6.9.4 source.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/* ---------------------------------------------------------------------------------------
 * Configuration. Define any of these in wp-config.php to override the defaults here.
 * ------------------------------------------------------------------------------------- */

/* Turn off XML-RPC. Set false only if something real uses it (Jetpack, a remote publishing app). */
if ( ! defined( 'WPSTUDIO_DISABLE_XMLRPC' ) ) {
	define( 'WPSTUDIO_DISABLE_XMLRPC', true );
}

/* Block ?author=N probing and the unauthenticated REST users list. */
if ( ! defined( 'WPSTUDIO_BLOCK_USER_ENUMERATION' ) ) {
	define( 'WPSTUDIO_BLOCK_USER_ENUMERATION', true );
}

/* Remove the WordPress version from the page head and feeds. */
if ( ! defined( 'WPSTUDIO_HIDE_VERSION' ) ) {
	define( 'WPSTUDIO_HIDE_VERSION', true );
}

/*
 * Turn off Application Passwords. The studio reaches sites over SSH and WP-CLI, so nothing
 * needs them, and each one is a standing credential that bypasses two-factor login. Set
 * false if an outside service (a mobile app, an automation tool) authenticates to the REST
 * API with one.
 */
if ( ! defined( 'WPSTUDIO_DISABLE_APP_PASSWORDS' ) ) {
	define( 'WPSTUDIO_DISABLE_APP_PASSWORDS', true );
}

/*
 * Response headers sent on front-end pages. Remove any the host already sends (check with
 * curl -sI) to avoid duplicates. Strict-Transport-Security is not here on purpose: it is a
 * browser-side commitment that outlives a certificate problem, so it is the owner's call.
 */
if ( ! defined( 'WPSTUDIO_SECURITY_HEADERS' ) ) {
	define(
		'WPSTUDIO_SECURITY_HEADERS',
		array(
			'X-Content-Type-Options' => 'nosniff',
			'X-Frame-Options'        => 'SAMEORIGIN',
			'Referrer-Policy'        => 'strict-origin-when-cross-origin',
			'Permissions-Policy'     => 'geolocation=(), camera=(), microphone=()',
			'X-XSS-Protection'       => '0',
		)
	);
}

/*
 * Login throttle: lock an address out for 15 minutes after this many failed logins.
 * 0 = off. Leave it off when a security plugin already throttles logins (two throttles
 * double the lockout). Before turning it on, confirm REMOTE_ADDR is the visitor's address
 * and not a proxy or CDN address; otherwise one attacker locks everyone out.
 */
if ( ! defined( 'WPSTUDIO_LOGIN_THROTTLE' ) ) {
	define( 'WPSTUDIO_LOGIN_THROTTLE', 0 );
}

/*
 * Optional $_SERVER key holding the real visitor address when the site sits behind a proxy
 * that sets it and strips any client-supplied copy (for example 'HTTP_CF_CONNECTING_IP' behind
 * Cloudflare). Never use HTTP_X_FORWARDED_FOR here: a client can send it.
 */
if ( ! defined( 'WPSTUDIO_CLIENT_IP_KEY' ) ) {
	define( 'WPSTUDIO_CLIENT_IP_KEY', '' );
}

/*
 * Turn off the dashboard theme and plugin code editors. Costs nothing and does not block
 * updates. Checked at capability time (wp-includes/capabilities.php), so defining it here
 * works when wp-config.php has not already set it.
 */
if ( ! defined( 'DISALLOW_FILE_EDIT' ) ) {
	define( 'DISALLOW_FILE_EDIT', true );
}

/* ---------------------------------------------------------------------------------------
 * Enforcement.
 * ------------------------------------------------------------------------------------- */

if ( WPSTUDIO_DISABLE_XMLRPC ) {
	add_filter( 'xmlrpc_enabled', '__return_false' );
	add_filter( 'xmlrpc_methods', '__return_empty_array' );
	add_filter(
		'wp_headers',
		function ( $headers ) {
			unset( $headers['X-Pingback'] );
			return $headers;
		}
	);
	add_filter( 'pings_open', '__return_false' );
	remove_action( 'wp_head', 'rsd_link' );
}

if ( WPSTUDIO_BLOCK_USER_ENUMERATION ) {
	/*
	 * ?author=N on the front end is an author archive request, and core's redirect_canonical()
	 * (template_redirect, priority 10) answers it with a redirect to /author/<username>/, which
	 * reveals the login name. Act at priority 1, before that, and only when the main query really
	 * is an author archive built from a numeric ?author= (the same test redirect_canonical() uses
	 * in wp-includes/canonical.php, WordPress 6.9), so REST requests (handled at
	 * parse_request, before template_redirect) and every other URL that carries an author
	 * parameter (/wp-json/wp/v2/posts?author=1, wp-admin/edit.php?author=1) keep working.
	 * A 302, not a 301: a permanent redirect is cached by browsers and outlives the setting.
	 */
	add_action(
		'template_redirect',
		function () {
			// Any ?author= value that produced an author archive (1, 1,2, an array) would show the
			// author's name in the page, so every form is sent home; /author/<name>/ links are untouched.
			if ( is_author() && isset( $_GET['author'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification
				wp_safe_redirect( home_url( '/' ), 302 );
				exit;
			}
		},
		1
	);
	add_filter(
		'rest_endpoints',
		function ( $endpoints ) {
			if ( ! is_user_logged_in() ) {
				unset( $endpoints['/wp/v2/users'], $endpoints['/wp/v2/users/(?P<id>[\d]+)'] );
			}
			return $endpoints;
		}
	);
}

if ( WPSTUDIO_HIDE_VERSION ) {
	remove_action( 'wp_head', 'wp_generator' );
	add_filter( 'the_generator', '__return_empty_string' );
}

if ( WPSTUDIO_DISABLE_APP_PASSWORDS ) {
	add_filter( 'wp_is_application_passwords_available', '__return_false' );
}

add_action(
	'send_headers',
	function () {
		if ( headers_sent() ) {
			return;
		}
		foreach ( (array) WPSTUDIO_SECURITY_HEADERS as $name => $value ) {
			header( $name . ': ' . $value );
		}
	}
);

/*
 * Never say whether a username exists. wp_login_errors (wp-login.php, WordPress 3.6+) filters the
 * WP_Error shown on the login screen, so the generic message replaces only the three errors that
 * tell a username apart from a password: invalid_username, invalid_email and incorrect_password
 * (wp_authenticate_username_password() and wp_authenticate_email_password(), priority 20 on
 * authenticate). Every other error, such as the login throttle's lockout or a security plugin's
 * message, passes through so the visitor learns why the login was refused. Registration errors
 * never pass through this filter.
 */
add_filter(
	'wp_login_errors',
	function ( $errors ) {
		if ( ! is_wp_error( $errors ) ) {
			return $errors;
		}
		$revealing = array_intersect( $errors->get_error_codes(), array( 'invalid_username', 'invalid_email', 'incorrect_password' ) );
		if ( ! $revealing ) {
			return $errors;
		}
		foreach ( $revealing as $code ) {
			$errors->remove( $code );
		}
		$errors->add( 'wpstudio_invalid_login', __( '<strong>Error:</strong> Invalid username or password.' ) );
		return $errors;
	}
);

/*
 * The lost-password form has its own tell: core shows "There is no account with that username or
 * email address" (error codes invalidcombo and invalid_email from retrieve_password()), while a real
 * account is sent to wp-login.php?checkemail=confirm. wp_login_errors doesn't run on that screen,
 * and lostpassword_errors runs before invalidcombo is added, so act on the lost_password action
 * (fired in wp-login.php with the errors, before the form is drawn, WordPress 6.9) and send an
 * unknown account to the same "check your email" page a real one gets.
 */
add_action(
	'lost_password',
	function ( $errors ) {
		if ( 'POST' !== ( isset( $_SERVER['REQUEST_METHOD'] ) ? $_SERVER['REQUEST_METHOD'] : '' ) || ! is_wp_error( $errors ) ) {
			return;
		}
		if ( array_intersect( $errors->get_error_codes(), array( 'invalidcombo', 'invalid_email' ) ) ) {
			wp_safe_redirect( site_url( 'wp-login.php?checkemail=confirm', 'login' ) );
			exit;
		}
	}
);

/**
 * The visitor's address, from the configured trusted key or REMOTE_ADDR.
 *
 * @return string
 */
function wpstudio_client_ip() {
	$key = WPSTUDIO_CLIENT_IP_KEY ? (string) WPSTUDIO_CLIENT_IP_KEY : 'REMOTE_ADDR';
	$ip  = isset( $_SERVER[ $key ] ) ? trim( (string) $_SERVER[ $key ] ) : ''; // phpcs:ignore WordPress.Security.ValidatedSanitizedInput
	return filter_var( $ip, FILTER_VALIDATE_IP ) ? $ip : 'unknown';
}

/**
 * Transient key that counts failures for the current address.
 *
 * @return string
 */
function wpstudio_lockout_key() {
	return 'wpstudio_lockout_' . md5( wpstudio_client_ip() );
}

if ( (int) WPSTUDIO_LOGIN_THROTTLE > 0 ) {
	// Priority 30: after core's username/password checks at 20.
	add_filter(
		'authenticate',
		function ( $user, $username, $password ) {
			if ( '' === (string) $username && '' === (string) $password ) {
				return $user; // Just viewing the login form.
			}
			$fails = (int) get_transient( wpstudio_lockout_key() );
			if ( $fails >= (int) WPSTUDIO_LOGIN_THROTTLE ) {
				return new WP_Error( 'wpstudio_locked', __( 'Too many failed attempts. Try again in 15 minutes.' ) );
			}
			return $user;
		},
		30,
		3
	);
	add_action(
		'wp_login_failed',
		function () {
			$key = wpstudio_lockout_key();
			set_transient( $key, (int) get_transient( $key ) + 1, 15 * MINUTE_IN_SECONDS );
		}
	);
	add_action(
		'wp_login',
		function () {
			delete_transient( wpstudio_lockout_key() );
		}
	);
}

/* ---------------------------------------------------------------------------------------
 * Assertion: checks the RESULT of each rule, not whether a line of code still exists.
 * ------------------------------------------------------------------------------------- */

/**
 * Every way the hardening is not holding right now.
 *
 * @return string[] Plain-language failures; empty when the posture holds.
 */
function wpstudio_hardening_failures() {
	$failures = array();

	if ( WPSTUDIO_DISABLE_XMLRPC && false !== apply_filters( 'xmlrpc_enabled', true ) ) {
		$failures[] = 'XML-RPC is enabled.';
	}

	if ( WPSTUDIO_DISABLE_APP_PASSWORDS && function_exists( 'wp_is_application_passwords_available' ) && wp_is_application_passwords_available() ) {
		$failures[] = 'Application Passwords are available.';
	}

	if ( ! defined( 'DISALLOW_FILE_EDIT' ) || true !== DISALLOW_FILE_EDIT ) {
		$failures[] = 'DISALLOW_FILE_EDIT is not true, so the dashboard code editors are reachable.';
	}

	if ( defined( 'DISALLOW_FILE_MODS' ) && DISALLOW_FILE_MODS ) {
		$failures[] = 'DISALLOW_FILE_MODS is set. It blocks every automatic update, security releases included. Remove it from wp-config.php.';
	}

	if ( function_exists( 'force_ssl_admin' ) && ! force_ssl_admin() && 'https' === wp_parse_url( site_url(), PHP_URL_SCHEME ) ) {
		$failures[] = 'The site is served over HTTPS but logins are not forced onto HTTPS (FORCE_SSL_ADMIN is false).';
	}

	if ( ! function_exists( 'wpstudio_update_policy_failures' ) ) {
		$failures[] = 'The update-policy must-use plugin (wpstudio-update-policy.php) is not loaded.';
	}

	return $failures;
}

add_filter(
	'site_status_tests',
	function ( $tests ) {
		$tests['direct']['wpstudio_hardening'] = array(
			'label' => 'Security hardening',
			'test'  => 'wpstudio_hardening_site_health',
		);
		return $tests;
	}
);

/**
 * Site Health result for the hardening.
 *
 * @return array
 */
function wpstudio_hardening_site_health() {
	$failures = wpstudio_hardening_failures();

	$result = array(
		'label'       => 'Security hardening is in effect',
		'status'      => 'good',
		'badge'       => array(
			'label' => 'Security',
			'color' => 'blue',
		),
		'description' => '<p>The hardening must-use plugin is loaded and each of its rules was checked by behaviour.</p>',
		'actions'     => '',
		'test'        => 'wpstudio_hardening',
	);

	if ( $failures ) {
		$result['status']         = 'critical';
		$result['label']          = 'Security hardening has regressed';
		$result['badge']['color'] = 'red';
		$result['description']    = '<p>These rules are no longer holding:</p><ul><li>'
			. implode( '</li><li>', array_map( 'esc_html', $failures ) )
			. '</li></ul><p>Restore the must-use plugins wpstudio-hardening.php and wpstudio-update-policy.php from the project folder.</p>';
	}

	return $result;
}

add_action(
	'admin_notices',
	function () {
		if ( ! current_user_can( 'update_core' ) ) {
			return;
		}
		$failures = wpstudio_hardening_failures();
		if ( ! $failures ) {
			return;
		}
		echo '<div class="notice notice-error"><p><strong>Security hardening has regressed on this site.</strong></p><ul style="list-style:disc;margin-left:2em">';
		foreach ( $failures as $failure ) {
			echo '<li>' . esc_html( $failure ) . '</li>';
		}
		echo '</ul></div>';
	}
);
