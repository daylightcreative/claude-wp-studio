<?php
/**
 * Plugin Name: Studio Custom Styles
 * Description: Durable custom CSS for this site. Lives in wp-content/mu-plugins/, so theme and
 *              plugin updates never touch it and it loads on every request without activation.
 * Version:     1.0.0
 *
 * HOW TO USE THIS TEMPLATE
 *   1. Copy it into the project's work folder and rename it with the project's prefix, for
 *      example `acme-custom-styles.php`. Rename the handle below to match (`acme-custom-styles`).
 *   2. Put the CSS in ONE of two places:
 *        a) a stylesheet next to this file with the same base name
 *           (`acme-custom-styles.css`). Preferred once the CSS is more than a few rules: it is
 *           versioned by its modification time, so browsers and CDNs fetch the new copy on
 *           every deploy; or
 *        b) the INLINE_CSS string below, for a handful of rules.
 *      If the stylesheet exists, it wins and the inline string is ignored.
 *   3. Deploy with `wpsite deploy <site> <local> wp-content/mu-plugins/<file>` for the PHP file
 *      (and the .css file, if used), then `wpsite purge <site>`.
 *
 * WHY wp_enqueue_scripts AND NOT AN ECHO ON wp_head
 *   Enqueued styles go through WordPress's style queue, so they can be inspected, deduplicated
 *   and ordered. A handle registered with src `false` carries inline CSS only; WordPress core
 *   uses the same register-false + wp_add_inline_style pattern for its own global-styles
 *   stylesheet. Priority 20 enqueues after styles enqueued at the default priority 10
 *   (including core's global styles), so this CSS prints after them. Print order only breaks
 *   ties between rules of equal specificity; it never beats a more specific selector.
 *
 * A PHP syntax error in any mu-plugin takes the whole site down. `wpsite deploy` lints PHP on the
 * server before it goes live; lint locally too: `php -l <file>`.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

add_action(
	'wp_enqueue_scripts',
	function () {
		$handle   = 'studio-custom-styles';
		$css_file = __DIR__ . '/' . basename( __FILE__, '.php' ) . '.css';

		if ( is_readable( $css_file ) ) {
			wp_enqueue_style(
				$handle,
				plugins_url( basename( $css_file ), __FILE__ ),
				array(),
				(string) filemtime( $css_file )
			);
			return;
		}

		// Scope every rule to a page, template or component class so nothing leaks site-wide.
		$inline_css = <<<'CSS'
/* Keep iOS Safari from enlarging text in narrow columns (see the block-themes skill). */
html {
	-webkit-text-size-adjust: 100%;
	text-size-adjust: 100%;
}
CSS;

		if ( '' === trim( $inline_css ) ) {
			return;
		}

		wp_register_style( $handle, false, array(), '1.0.0' );
		wp_enqueue_style( $handle );
		wp_add_inline_style( $handle, $inline_css );
	},
	20
);
