---
name: images
description: Image work on WordPress sites — the standard optimize recipe, getting responsive srcset on hand-written or migrated <img> tags, full-size originals filling the disk, social-share (Open Graph) images, and featured images in RSS-to-email newsletters. Use when a page is slow or heavy, images serve at full size, migrating images, a host warns about disk use, a shared link shows the wrong picture, or a newsletter built from the feed has no images.
---

# Images

## The optimize recipe (before upload)

Photos straight off a phone or an old site are often 12–25 megapixels. Optimize the batch before
it goes into the Media Library:

```bash
magick INPUT -auto-orient -resize '1600x1600>' -strip -quality 82 OUTPUT.webp
```

- `-auto-orient` first, so removing EXIF does not leave the picture sideways.
- `-resize '1600x1600>'` caps the longest edge and never enlarges a smaller image.
- `-strip` removes metadata, including camera location.
- `-quality 82` WebP was visually lossless on photos and cut files by roughly 95% on the sites
  this came from.
- **Animated GIF:** the recipe makes a huge multi-frame WebP. Take the first frame
  (`magick 'INPUT[0]' -strip -quality 82 OUTPUT.webp`) or make it a real video.
- **Logos and line art:** use the SVG if one exists.
- **Names:** descriptive kebab-case (`front-entrance-evening.webp`), not `IMG_4821.JPG`. In a
  migration, `<page-slug>-NN.webp` keeps them findable.

Upload the file to a holding folder, import it, then remove the holding folder:

```bash
wpsite deploy acme projects/acme/work/images/front-entrance.webp wp-content/wpstudio-import/front-entrance.webp
wpsite wp acme media import wp-content/wpstudio-import/front-entrance.webp --porcelain   # prints the attachment ID
wpsite sh acme 'rm -r wp-content/wpstudio-import'
```

WordPress copies the file into the uploads folder and generates the sub-sizes.

## Responsive images need the attachment class

**Rule: every content `<img>` that should get `srcset` carries `class="wp-image-<ID>"` for its
attachment, a root-relative `src`, and a real `sizes`.**

Why: core's `wp_filter_content_tags()` (WordPress 5.5+, on `the_content` at priority 12) finds
the attachment by matching `wp-image-([0-9]+)` in the tag. With an ID it adds `srcset`, `sizes`,
`width` and `height` (when missing) and loading optimization attributes. Without the class it adds
no `srcset` or `sizes`. Hand-written Custom HTML, migrated markup and cover-block backgrounds
usually lack it, so they serve the full file. On one site a 376px slot loaded a 5184px, 8.2 MB
original; fixing the markup took the home page from about 16 MB to 676 KB with no visible change.

How:

1. Map each `src` to its attachment. `attachment_url_to_postid()` matches `_wp_attached_file`,
   which for a large upload is the `-scaled` file; it returns **0** for the un-scaled original
   URL, so map those to the attachment explicitly.
2. Rewrite each tag: `src` = `/wp-content/uploads/` + the `_wp_attached_file` value (root-relative,
   so it survives a staging → live push; core builds the absolute `srcset` at render), add
   `class="wp-image-<ID>"`, and a real `sizes` such as `(min-width: 782px) 480px, 92vw`. The
   default `sizes` assumes the image's full width and makes browsers pick a big file.
3. Above-the-fold hero: `fetchpriority="high"` and no lazy loading.
4. Do the rewrite in a `wp eval-file` script that calls `wp_set_current_user()` with an
   administrator first, so `unfiltered_html` keeps the markup on `wp_update_post()`. Back up each
   post first (`wpsite backup acme --post <ID>`).
5. `wpsite wp acme media regenerate <IDs> --yes` if sub-sizes are missing, then `wpsite purge acme`
   and check the rendered page has `srcset`.

## Full-size originals fill the disk

Since WordPress 5.3, an upload larger than the `big_image_size_threshold` (default 2560px) is
scaled down, and the scaled copy becomes the attachment's file. The original upload is kept on
disk and recorded as `original_image` in the attachment metadata
(`wp_get_original_image_path()` returns it). WordPress never serves it in pages.

On one site a host's "80% disk" warning traced to this: 7.1 GB of 7.5 GB was uploads, and 484
retained originals (mostly ~20 MB event photos) made up 4.5 GB. The 80% was a plan threshold,
not a capacity emergency. Measure before acting:

```bash
wpsite sh acme 'du -sh wp-content/uploads'
wpsite wp acme eval '$n=0;$b=0;foreach(get_posts(["post_type"=>"attachment","post_mime_type"=>"image","posts_per_page"=>-1,"fields"=>"ids"]) as $id){$o=wp_get_original_image_path($id);if($o&&$o!==get_attached_file($id)&&file_exists($o)){$n++;$b+=filesize($o);}}echo "$n originals, ".size_format($b)."\n";'
```

Deleting originals is irreversible and needs the operator's sign-off (they may be the only
full-resolution copy of a client's photos — offer to download them first with `wpsite pull`).
To delete one: unlink the file returned by `wp_get_original_image_path()` only when it differs
from `get_attached_file()`, then remove `original_image` from the metadata with
`wp_update_attachment_metadata()`. Removing the key matters: `wp media regenerate` re-derives the
`-scaled` file from the original while it is recorded, which also overwrites any compression you
applied to the scaled file.

To stop keeping huge originals in future, resize before upload (the recipe above). Turning the
threshold off (`add_filter( 'big_image_size_threshold', '__return_false' )`) does the opposite:
the full-size file becomes the attachment and nothing is scaled.

## Social-share (Open Graph) images

**Symptom:** a shared link shows the wrong picture (a partner logo, a random image) or none.

**Cause:** the page has no featured image and the SEO plugin has no default share image, so the
platform guesses from the page content. WordPress core prints no `og:image`; the SEO plugin does.

**Fix**, in order: give the page a featured image; set the SEO plugin's site-wide default share
image (and the front page's, which some plugins keep separately); then verify:

```bash
curl -s "https://example.com/?cb=$RANDOM" | grep -i 'og:image'
```

On Yoast SEO the observed option keys are `wpseo_social` → `og_default_image` /
`og_default_image_id` (site-wide) and `wpseo_titles` → `open_graph_frontpage_image` /
`open_graph_frontpage_image_id` (front page), settable with `wp option patch update`. Other SEO
plugins differ — use their settings screen or read their option before writing.

- Size: **1200×630** (1.91:1), JPEG or PNG.
- A logo composited onto a photo stays legible only on a light area, or on a white badge over a
  dark one. Composite the real logo file; never let an image generator redraw a logo.
- Platforms cache previews of links already shared. New shares update at once; old ones refresh
  later, or force a re-scrape in the platform's sharing debugger. Tell the operator this so a
  stale preview is not reported as a failed fix.

## Featured images in RSS-to-email newsletters

**Symptom:** an email platform's RSS-to-newsletter block shows each post as text only.

**Cause:** the platform reads the item's `<description>`, which WordPress fills from the excerpt,
with no image. Check what the feed carries: `curl -s "https://example.com/feed/?cb=$RANDOM"`
and `wpsite wp acme option get rss_use_excerpt` (`1` = summary only, `0` = also full text).

**Fix:** deploy `rss-featured-image.php` from this skill's folder as an mu-plugin. It prepends the
featured image to `<description>` and `<content:encoded>` at priority 9 (above SEO-plugin
footers) and serves a **JPEG** copy when the featured image is WebP: classic Outlook for Windows
does not render WebP, and support elsewhere is partial (caniemail.com, checked June 2026). The
JPEG is made once and cached in attachment meta.

Verify it converted: the first `<img src>` in the feed ends in `-rss.jpg` and
`curl -sI <that url>` returns `200` with `content-type: image/jpeg`. If it is still `.webp`, the
server's image editor cannot read WebP:
`wpsite wp acme eval 'var_dump(wp_image_editor_supports(["mime_type"=>"image/webp"]));'`.

Tell the operator: the newsletter text is the post's **Excerpt**. Fill it for a hand-written
summary or leave it blank for an automatic one. If the SEO plugin appends "The post … appeared
first on …" to every item and they don't want it, Yoast keeps that text in `wpseo_titles` →
`rssafter` (Settings → Advanced → RSS); record the old value before clearing it.
