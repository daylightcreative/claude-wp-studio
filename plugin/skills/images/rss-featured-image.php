<?php
/**
 * Plugin Name: Studio RSS Featured Image
 * Description: Puts each post's featured image at the top of its RSS item, as a JPEG, so email
 *              newsletters built from the feed (RSS-to-email) show a picture.
 * Version:     1.0.0
 *
 * WHY
 *   Email platforms that build a newsletter from the feed usually read the item's
 *   <description>, which WordPress fills from the excerpt: no image. This prepends the featured
 *   image to <description> (the_excerpt_rss) and <content:encoded> (the_content_feed).
 *   Priority 9 puts it above anything an SEO plugin appends at the default priority 10.
 *
 *   WebP is not safe in email (classic Outlook for Windows does not render it; see
 *   caniemail.com), so a WebP or AVIF featured image is converted once to a JPEG copy that is
 *   cached in attachment meta and regenerated only when the source changes. If the server's
 *   image editor cannot read the source format, the original URL is used; the feed never breaks.
 *
 * HOW TO USE
 *   Rename with the project prefix, `php -l`, then
 *   `wpsite deploy <site> <file> wp-content/mu-plugins/<file>`. Verify with
 *   `curl -s "https://example.com/feed/?cb=$RANDOM"`: the first <img src> should end in -rss.jpg,
 *   and `curl -sI <that url>` should return 200 with content-type image/jpeg.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

const STUDIO_RSS_IMAGE_SIZE = 'large';
const STUDIO_RSS_META_KEY   = '_studio_rss_jpeg';

add_filter( 'the_excerpt_rss', 'studio_rss_prepend_featured_image', 9 );
add_filter( 'the_content_feed', 'studio_rss_prepend_featured_image', 9 );

/**
 * Prepend the featured image to a feed item's text.
 *
 * @param string $content Feed item text.
 * @return string
 */
function studio_rss_prepend_featured_image( $content ) {
	$post_id = get_the_ID();
	if ( ! $post_id || ! has_post_thumbnail( $post_id ) ) {
		return $content;
	}

	$url = studio_rss_email_image_url( (int) get_post_thumbnail_id( $post_id ) );
	if ( ! $url ) {
		return $content;
	}

	// Skip if the item already leads with this image.
	if ( false !== strpos( substr( (string) $content, 0, 800 ), wp_basename( $url ) ) ) {
		return $content;
	}

	return '<img src="' . esc_url( $url ) . '" width="600" alt="' . esc_attr( get_the_title( $post_id ) ) . '"'
		. ' style="display:block;width:100%;max-width:100%;height:auto;margin:0 0 16px;" />'
		. $content;
}

/**
 * Return an email-safe (JPEG, PNG or GIF) URL for an attachment, converting once if needed.
 *
 * @param int $attachment_id Attachment ID.
 * @return string Image URL, or '' if none.
 */
function studio_rss_email_image_url( $attachment_id ) {
	$src = wp_get_attachment_image_url( $attachment_id, STUDIO_RSS_IMAGE_SIZE );
	if ( ! $src ) {
		return '';
	}

	$mime = get_post_mime_type( $attachment_id );
	if ( in_array( $mime, array( 'image/jpeg', 'image/png', 'image/gif' ), true ) ) {
		return $src;
	}

	$cached = get_post_meta( $attachment_id, STUDIO_RSS_META_KEY, true );
	if ( is_array( $cached ) && isset( $cached['src'], $cached['url'], $cached['path'] )
		&& $cached['src'] === $src && file_exists( $cached['path'] ) ) {
		return $cached['url'];
	}

	$path         = get_attached_file( $attachment_id );
	$intermediate = image_get_intermediate_size( $attachment_id, STUDIO_RSS_IMAGE_SIZE );
	$uploads      = wp_get_upload_dir();
	if ( $intermediate && ! empty( $intermediate['path'] ) ) {
		$path = trailingslashit( $uploads['basedir'] ) . $intermediate['path'];
	}
	if ( ! $path || ! file_exists( $path ) ) {
		return $src;
	}

	$editor = wp_get_image_editor( $path );
	if ( is_wp_error( $editor ) ) {
		return $src;
	}
	$editor->set_quality( 82 );

	$target = preg_replace( '/\.[^.\/]+$/', '', $path ) . '-rss.jpg';
	$saved  = $editor->save( $target, 'image/jpeg' );
	if ( is_wp_error( $saved ) || empty( $saved['path'] ) ) {
		return $src;
	}

	$url = str_replace(
		trailingslashit( $uploads['basedir'] ),
		trailingslashit( $uploads['baseurl'] ),
		$saved['path']
	);

	update_post_meta(
		$attachment_id,
		STUDIO_RSS_META_KEY,
		array(
			'src'  => $src,
			'url'  => $url,
			'path' => $saved['path'],
		)
	);

	return $url;
}
