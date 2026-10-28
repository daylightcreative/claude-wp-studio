<?php
/**
 * Attribute <head> output to the wp_head callback that prints it.
 *
 * Simulates a request for one page, then runs every wp_head callback on its own and prints each
 * callback whose output contains the search text, with its priority and its source.
 *
 * Usage (WP-CLI eval-file; positional args arrive in $args):
 *   wpsite wp <site> --input head-attribution.php eval-file - '<search text>' [<page path or post ID>]
 *
 * Examples of search text: 'og:image', 'googletagmanager', 'name="robots"'.
 * With no page given it simulates the front page.
 *
 * Calling a callback runs its code. Most wp_head callbacks only print markup, but run this on
 * staging when you can, and take a database backup first if the site has unknown plugins.
 *
 * @package wp-studio
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit( "Run this through WP-CLI eval-file.\n" );
}

$wps_needle = isset( $args[0] ) ? (string) $args[0] : '';
$wps_target = isset( $args[1] ) ? (string) $args[1] : '';

if ( '' === $wps_needle ) {
	WP_CLI::error( 'Give the text to look for as the first argument, e.g. og:image' );
}

// Work out which post to simulate.
$wps_post_id = 0;
if ( '' === $wps_target ) {
	$wps_post_id = (int) get_option( 'page_on_front' );
} elseif ( ctype_digit( $wps_target ) ) {
	$wps_post_id = (int) $wps_target;
} else {
	$wps_page = get_page_by_path( trim( $wps_target, '/' ) );
	if ( $wps_page instanceof WP_Post ) {
		$wps_post_id = (int) $wps_page->ID;
	}
}

// Build the main query the way a front-end request would.
global $wp_query, $wp_the_query, $wp_filter;
if ( $wps_post_id > 0 ) {
	$wps_type = get_post_type( $wps_post_id );
	$wps_args = ( 'page' === $wps_type )
		? array( 'page_id' => $wps_post_id )
		: array(
			'p'         => $wps_post_id,
			'post_type' => $wps_type,
		);
} elseif ( '' === $wps_target ) {
	$wps_args = array(); // Front page shows latest posts.
} else {
	WP_CLI::error( "No page found for '$wps_target'. Pass a page path such as about/team, or a post ID." );
}

$wp_query     = new WP_Query( $wps_args ); // phpcs:ignore WordPress.WP.GlobalVariablesOverride.Prohibited
$wp_the_query = $wp_query; // phpcs:ignore WordPress.WP.GlobalVariablesOverride.Prohibited
if ( $wp_query->have_posts() ) {
	$wp_query->the_post();
}

// Let plugins register the late filters they add on the 'wp' action.
do_action( 'wp', isset( $GLOBALS['wp'] ) ? $GLOBALS['wp'] : null );

if ( empty( $wp_filter['wp_head'] ) || ! ( $wp_filter['wp_head'] instanceof WP_Hook ) ) {
	WP_CLI::error( 'Nothing is hooked to wp_head.' );
}

/**
 * Describe a callback as Class::method, function name, or closure with its file and line.
 *
 * @param mixed $callback The registered callback.
 * @return string
 */
function wps_describe_callback( $callback ) {
	if ( is_string( $callback ) ) {
		return $callback;
	}
	if ( is_array( $callback ) && 2 === count( $callback ) ) {
		$owner = is_object( $callback[0] ) ? get_class( $callback[0] ) : (string) $callback[0];
		return $owner . '::' . $callback[1];
	}
	if ( $callback instanceof Closure ) {
		$ref = new ReflectionFunction( $callback );
		return 'Closure in ' . $ref->getFileName() . ':' . $ref->getStartLine();
	}
	if ( is_object( $callback ) ) {
		return get_class( $callback ) . '::__invoke';
	}
	return 'unknown callback';
}

/**
 * Find the file that defines a callback, when PHP can tell us.
 *
 * @param mixed $callback The registered callback.
 * @return string
 */
function wps_callback_file( $callback ) {
	try {
		if ( is_array( $callback ) && 2 === count( $callback ) ) {
			$ref = new ReflectionMethod( $callback[0], $callback[1] );
		} elseif ( is_string( $callback ) && false !== strpos( $callback, '::' ) ) {
			$ref = new ReflectionMethod( $callback );
		} elseif ( is_string( $callback ) || $callback instanceof Closure ) {
			$ref = new ReflectionFunction( $callback );
		} else {
			return '';
		}
		return $ref->getFileName() . ':' . $ref->getStartLine();
	} catch ( ReflectionException $e ) {
		return '';
	}
}

$wps_hits = 0;
foreach ( $wp_filter['wp_head']->callbacks as $wps_priority => $wps_callbacks ) {
	foreach ( $wps_callbacks as $wps_cb ) {
		$wps_fn = $wps_cb['function'];
		ob_start();
		try {
			call_user_func( $wps_fn );
		} catch ( Throwable $e ) {
			echo '[callback threw: ' . esc_html( $e->getMessage() ) . ']';
		}
		$wps_out = (string) ob_get_clean();
		if ( false === stripos( $wps_out, $wps_needle ) ) {
			continue;
		}
		++$wps_hits;
		WP_CLI::log( '### priority ' . $wps_priority . '  ' . wps_describe_callback( $wps_fn ) );
		$wps_file = wps_callback_file( $wps_fn );
		if ( '' !== $wps_file ) {
			WP_CLI::log( '    defined in ' . $wps_file );
		}
		foreach ( preg_split( '/\R/', trim( $wps_out ) ) as $wps_line ) {
			if ( false !== stripos( $wps_line, $wps_needle ) ) {
				WP_CLI::log( '    ' . trim( $wps_line ) );
			}
		}
	}
}

if ( 0 === $wps_hits ) {
	WP_CLI::warning( "No wp_head callback printed '$wps_needle'. It may come from the theme's header template, a later hook, or JavaScript." );
} else {
	WP_CLI::success( "$wps_hits callback(s) printed '$wps_needle'." );
}
