<?php
/**
 * Plugin Name: <CLIENT> Custom Styles
 * Description: Durable custom CSS for <client>. Lives in wp-content/mu-plugins/, so it
 *              survives theme and plugin updates and loads on every request automatically.
 *
 * WHY AN MU-PLUGIN AND NOT THE CUSTOMIZER:
 *   The Customizer's "Additional CSS" and Divi's own custom-CSS box are unreliable — on
 *   some sites (especially Divi 5) they are silently suppressed on the front end. An
 *   mu-plugin is the one channel that always works and can't be wiped by an update.
 *   See library/lessons/custom_css_belongs_in_mu_plugin.md.
 *
 * DEPLOY:
 *   1. Edit this file locally.
 *   2. ALWAYS lint first:   php -l <CLIENT>-custom-styles.php
 *      (a syntax error in any mu-plugin fatals the ENTIRE site.)
 *   3. Upload to the server's wp-content/mu-plugins/ via SFTP/scp. It's live immediately —
 *      no build step, no activation. Then purge the cache.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit; // never run outside WordPress
}

add_action( 'wp_head', function () {
    ?>
<style id="<client>-custom-css">
/* Scope every rule to specific selectors so nothing leaks.
   This block is printed late on wp_head (priority 99) so it wins specificity battles. */

</style>
    <?php
}, 99 );
