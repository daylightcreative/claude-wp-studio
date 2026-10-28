<?php
/**
 * Plugin Name: WP Studio Update Policy
 * Description: Forces automatic updates on for WordPress core, every plugin, every theme and
 *              translations, and holds back only the cross-major upgrades you list below.
 *              Enforced in code, so it cannot be switched off from the dashboard: WordPress
 *              treats a non-null answer from the auto_update_{$type} filter as "forced" and
 *              removes the per-item toggle. Asserted by a Site Health test and an admin notice;
 *              hardening.php (its companion) reports it if this file goes missing.
 * Version:     2.0.0
 * License:     MIT
 *
 * Install as wp-content/mu-plugins/wpstudio-update-policy.php.
 *
 * Verified against WordPress 6.9.1 source and developer.wordpress.org (2026-10-28):
 *   - auto_update_{$type}( $update, $item ): wp-admin/includes/class-wp-automatic-updater.php.
 *     Core also calls it with $update === null only to ask "is this forced?" for the UI
 *     (wp_is_auto_update_forced_for_item(), wp-admin/includes/update.php), so always answer
 *     with a real boolean.
 *   - $item->plugin is the plugin file ("folder/file.php"); $item->theme is the theme
 *     stylesheet (folder name); $item->new_version is the version on offer.
 *   - allow_{dev,minor,major}_auto_core_updates and automatic_updater_disabled:
 *     wp-admin/includes/class-core-upgrader.php and class-wp-automatic-updater.php.
 *   - The updater refuses to run at all when DISALLOW_FILE_MODS is true
 *     (wp_is_file_mod_allowed( 'automatic_updater' )); no filter here can override that.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/* ---------------------------------------------------------------------------------------
 * Configuration. Define any of these in wp-config.php to override the defaults here.
 * ------------------------------------------------------------------------------------- */

/*
 * Themes whose MAJOR upgrades are held for a person to review (same-major updates still
 * install automatically). Use the theme folder name, for example array( 'Divi' ).
 * Hold only page builders, whose major releases rewrite the builder.
 */
if ( ! defined( 'WPSTUDIO_HOLD_MAJOR_THEMES' ) ) {
	define( 'WPSTUDIO_HOLD_MAJOR_THEMES', array() );
}

/*
 * Plugins whose MAJOR upgrades are held, by plugin file, for example
 * array( 'elementor/elementor.php' ). Hold a free plugin when its paid companion is
 * version-locked to it and the paid half has no update channel.
 */
if ( ! defined( 'WPSTUDIO_HOLD_MAJOR_PLUGINS' ) ) {
	define( 'WPSTUDIO_HOLD_MAJOR_PLUGINS', array() );
}

/* Allow automatic MAJOR WordPress core upgrades (minor and security releases are always on). */
if ( ! defined( 'WPSTUDIO_AUTO_UPDATE_CORE_MAJOR' ) ) {
	define( 'WPSTUDIO_AUTO_UPDATE_CORE_MAJOR', true );
}

/* ---------------------------------------------------------------------------------------
 * Enforcement.
 * ------------------------------------------------------------------------------------- */

/**
 * Leading major version number of a version string, or null when there is none.
 *
 * @param mixed $version A version string such as "4.27.7".
 * @return int|null
 */
function wpstudio_version_major( $version ) {
	if ( ! is_string( $version ) || ! preg_match( '/^\s*(\d+)/', $version, $m ) ) {
		return null;
	}
	return (int) $m[1];
}

/**
 * Installed version of a plugin file, or '' when it is not installed.
 *
 * @param string $plugin_file Plugin file relative to the plugins folder.
 * @return string
 */
function wpstudio_installed_plugin_version( $plugin_file ) {
	if ( ! function_exists( 'get_plugins' ) ) {
		require_once ABSPATH . 'wp-admin/includes/plugin.php';
	}
	$plugins = get_plugins();
	return isset( $plugins[ $plugin_file ]['Version'] ) ? (string) $plugins[ $plugin_file ]['Version'] : '';
}

/**
 * Installed version of a theme, or '' when it is not installed.
 *
 * @param string $stylesheet Theme folder name.
 * @return string
 */
function wpstudio_installed_theme_version( $stylesheet ) {
	$theme = wp_get_theme( $stylesheet );
	return $theme->exists() ? (string) $theme->get( 'Version' ) : '';
}

/**
 * True when $offered is a higher major version than $installed.
 *
 * @param string $installed Installed version.
 * @param string $offered   Offered version.
 * @return bool
 */
function wpstudio_is_cross_major( $installed, $offered ) {
	$from = wpstudio_version_major( $installed );
	$to   = wpstudio_version_major( $offered );
	return null !== $from && null !== $to && $to > $from;
}

/**
 * Plugin auto-update decision: always update, except a cross-major jump of a held plugin.
 *
 * @param bool|null $update Core's current intent (null when only asking whether it is forced).
 * @param object    $item   The update offer.
 * @return bool
 */
function wpstudio_auto_update_plugin( $update, $item ) {
	$file = isset( $item->plugin ) ? (string) $item->plugin : '';
	if ( in_array( $file, (array) WPSTUDIO_HOLD_MAJOR_PLUGINS, true ) && isset( $item->new_version ) ) {
		if ( wpstudio_is_cross_major( wpstudio_installed_plugin_version( $file ), (string) $item->new_version ) ) {
			return false;
		}
	}
	return true;
}
add_filter( 'auto_update_plugin', 'wpstudio_auto_update_plugin', 10, 2 );

/**
 * Theme auto-update decision: always update, except a cross-major jump of a held theme.
 *
 * @param bool|null $update Core's current intent (null when only asking whether it is forced).
 * @param object    $item   The update offer.
 * @return bool
 */
function wpstudio_auto_update_theme( $update, $item ) {
	$slug = isset( $item->theme ) ? (string) $item->theme : '';
	if ( in_array( $slug, (array) WPSTUDIO_HOLD_MAJOR_THEMES, true ) && isset( $item->new_version ) ) {
		if ( wpstudio_is_cross_major( wpstudio_installed_theme_version( $slug ), (string) $item->new_version ) ) {
			return false;
		}
	}
	return true;
}
add_filter( 'auto_update_theme', 'wpstudio_auto_update_theme', 10, 2 );

add_filter( 'auto_update_translation', '__return_true', 10, 0 );
add_filter( 'allow_dev_auto_core_updates', '__return_true', 10, 0 );
add_filter( 'allow_minor_auto_core_updates', '__return_true', 10, 0 );
add_filter(
	'allow_major_auto_core_updates',
	function () {
		return (bool) WPSTUDIO_AUTO_UPDATE_CORE_MAJOR;
	},
	10,
	0
);
add_filter( 'automatic_updater_disabled', '__return_false', 10, 0 );

/* ---------------------------------------------------------------------------------------
 * Assertion. Each check runs the live filter chain, so it fails however the behaviour
 * regressed: an edited file, a deleted file, or another plugin overriding the filter later.
 * ------------------------------------------------------------------------------------- */

/**
 * Every way the update policy is not holding right now.
 *
 * @return string[] Plain-language failures; empty when the policy holds.
 */
function wpstudio_update_policy_failures() {
	$failures = array();

	$plugin_probe = (object) array(
		'plugin'      => 'wpstudio-probe/wpstudio-probe.php',
		'new_version' => '1.0.0',
	);
	if ( true !== apply_filters( 'auto_update_plugin', null, $plugin_probe ) ) {
		$failures[] = 'Plugin automatic updates are not forced on.';
	}

	$theme_probe = (object) array(
		'theme'       => 'wpstudio-probe',
		'new_version' => '1.0.0',
	);
	if ( true !== apply_filters( 'auto_update_theme', null, $theme_probe ) ) {
		$failures[] = 'Theme automatic updates are not forced on.';
	}

	foreach ( array( 'allow_dev_auto_core_updates', 'allow_minor_auto_core_updates' ) as $core_filter ) {
		if ( true !== apply_filters( $core_filter, null ) ) {
			$failures[] = "WordPress core automatic updates are not forced on ({$core_filter}).";
		}
	}
	if ( WPSTUDIO_AUTO_UPDATE_CORE_MAJOR && true !== apply_filters( 'allow_major_auto_core_updates', null ) ) {
		$failures[] = 'Major WordPress core automatic updates are configured on but something has turned them off.';
	}

	if ( false !== apply_filters( 'automatic_updater_disabled', null ) ) {
		$failures[] = 'The WordPress automatic updater is disabled.';
	}

	if ( function_exists( 'wp_is_file_mod_allowed' ) && ! wp_is_file_mod_allowed( 'automatic_updater' ) ) {
		$failures[] = 'File changes are blocked (DISALLOW_FILE_MODS or the file_mod_allowed filter), so no automatic update, including security releases, can install.';
	}

	// The holds, proved by behaviour: same major must update, next major must be held.
	foreach ( (array) WPSTUDIO_HOLD_MAJOR_THEMES as $slug ) {
		$failures = array_merge( $failures, wpstudio_hold_failures( 'theme', (string) $slug, wpstudio_installed_theme_version( (string) $slug ) ) );
	}
	foreach ( (array) WPSTUDIO_HOLD_MAJOR_PLUGINS as $file ) {
		$failures = array_merge( $failures, wpstudio_hold_failures( 'plugin', (string) $file, wpstudio_installed_plugin_version( (string) $file ) ) );
	}

	if ( ! function_exists( 'wpstudio_hardening_failures' ) ) {
		$failures[] = 'The hardening must-use plugin (wpstudio-hardening.php) is not loaded.';
	}

	return $failures;
}

/**
 * Prove that one held item updates within its major and is held across it.
 *
 * @param string $type      'plugin' or 'theme'.
 * @param string $id        Plugin file or theme folder.
 * @param string $installed Installed version ('' when not installed).
 * @return string[]
 */
function wpstudio_hold_failures( $type, $id, $installed ) {
	$major = wpstudio_version_major( $installed );
	if ( null === $major ) {
		return array( sprintf( 'Cannot read the installed version of %s "%s", so its major-version hold cannot be verified. Remove it from the hold list if it is no longer installed.', $type, $id ) );
	}

	$failures   = array();
	$same_major = (object) array(
		$type         => $id,
		'new_version' => $installed,
	);
	if ( true !== apply_filters( "auto_update_{$type}", null, $same_major ) ) {
		$failures[] = sprintf( '%s "%s" is not auto-updating within its current major version.', ucfirst( $type ), $id );
	}

	$next_major = (object) array(
		$type         => $id,
		'new_version' => ( $major + 1 ) . '.0.0',
	);
	if ( false !== apply_filters( "auto_update_{$type}", null, $next_major ) ) {
		$failures[] = sprintf( '%s "%s" major-version upgrades are NOT being held for review.', ucfirst( $type ), $id );
	}

	return $failures;
}

/**
 * Held major upgrades currently on offer, so a hold is a decision rather than a silent skip.
 *
 * @return string[] Lines such as 'Theme "Divi" 5.0.1'.
 */
function wpstudio_held_upgrades() {
	$held = array();

	$themes = get_site_transient( 'update_themes' );
	foreach ( (array) WPSTUDIO_HOLD_MAJOR_THEMES as $slug ) {
		if ( ! empty( $themes->response[ $slug ]['new_version'] ) ) {
			$offer = (string) $themes->response[ $slug ]['new_version'];
			if ( wpstudio_is_cross_major( wpstudio_installed_theme_version( $slug ), $offer ) ) {
				$held[] = sprintf( 'Theme "%s" %s', $slug, $offer );
			}
		}
	}

	$plugins = get_site_transient( 'update_plugins' );
	foreach ( (array) WPSTUDIO_HOLD_MAJOR_PLUGINS as $file ) {
		if ( ! empty( $plugins->response[ $file ]->new_version ) ) {
			$offer = (string) $plugins->response[ $file ]->new_version;
			if ( wpstudio_is_cross_major( wpstudio_installed_plugin_version( $file ), $offer ) ) {
				$held[] = sprintf( 'Plugin "%s" %s', $file, $offer );
			}
		}
	}

	return $held;
}

add_filter(
	'site_status_tests',
	function ( $tests ) {
		$tests['direct']['wpstudio_update_policy'] = array(
			'label' => 'Automatic update policy',
			'test'  => 'wpstudio_update_policy_site_health',
		);
		return $tests;
	}
);

/**
 * Site Health result for the update policy.
 *
 * @return array
 */
function wpstudio_update_policy_site_health() {
	$failures = wpstudio_update_policy_failures();
	$held     = wpstudio_held_upgrades();

	$result = array(
		'label'       => 'Automatic updates are enforced',
		'status'      => 'good',
		'badge'       => array(
			'label' => 'Security',
			'color' => 'blue',
		),
		'description' => '<p>WordPress core, every plugin and every theme update automatically, and the setting cannot be switched off from the dashboard.</p>',
		'actions'     => '',
		'test'        => 'wpstudio_update_policy',
	);

	if ( $failures ) {
		$result['status']         = 'critical';
		$result['label']          = 'The automatic update policy is not holding';
		$result['badge']['color'] = 'red';
		$result['description']    = '<p>Each item below was found by running the live update filters, so each is a real change in behaviour:</p><ul><li>'
			. implode( '</li><li>', array_map( 'esc_html', $failures ) )
			. '</li></ul><p>Restore the must-use plugins wpstudio-update-policy.php and wpstudio-hardening.php from the project folder.</p>';
	} elseif ( $held ) {
		$result['status']         = 'critical';
		$result['label']          = 'A held major upgrade is waiting for review';
		$result['badge']['color'] = 'red';
		$result['description']    = '<p>These major upgrades are deliberately not installed automatically. Test each one on staging, then apply it by hand:</p><ul><li>'
			. implode( '</li><li>', array_map( 'esc_html', $held ) )
			. '</li></ul>';
	}

	return $result;
}

add_action(
	'admin_notices',
	function () {
		if ( ! current_user_can( 'update_core' ) ) {
			return;
		}
		$failures = wpstudio_update_policy_failures();
		$held     = wpstudio_held_upgrades();

		if ( $failures ) {
			echo '<div class="notice notice-error"><p><strong>Automatic updates are not fully enforced on this site.</strong></p><ul style="list-style:disc;margin-left:2em">';
			foreach ( $failures as $failure ) {
				echo '<li>' . esc_html( $failure ) . '</li>';
			}
			echo '</ul></div>';
		} elseif ( $held ) {
			echo '<div class="notice notice-warning"><p><strong>Major upgrades waiting for review</strong> (held on purpose; test on staging first):</p><ul style="list-style:disc;margin-left:2em">';
			foreach ( $held as $line ) {
				echo '<li>' . esc_html( $line ) . '</li>';
			}
			echo '</ul></div>';
		}
	}
);
