# Image Optimization (The Standard Recipe)

**Date**: 2026-06-15
**Status**: Active
**Scope**: How to optimize images for the web during builds and migrations. One recipe, ~95% size reduction, no visible quality loss.

Client sites — especially ones migrated from Wix or older builds — are often loaded with
huge, unoptimized images (12–25 megapixel originals straight off a phone). Optimizing them
is usually the single biggest performance win. The standard recipe:

```bash
magick INPUT -auto-orient -resize '1600x1600>' -strip -quality 82 OUTPUT.webp
```

What each part does:

- **WebP** output — modern, well-supported, much smaller than JPEG/PNG at equal quality.
- **`-resize '1600x1600>'`** — cap the longest edge at 1600px. The `>` means *shrink only,
  never upscale* a smaller image.
- **`-strip`** — remove EXIF/metadata (smaller file, no leaking camera/location data).
- **`-auto-orient`** — bake in the rotation first, so stripped EXIF doesn't leave it sideways.
- **`-quality 82`** — the sweet spot; visually lossless for photos, big savings.

Typical result: **~95% smaller** files.

## Filenames

Rename to **descriptive, kebab-case, SEO-friendly** names — e.g. `red-rock-crawler-front.webp`,
not a Wix hash like `abc123~mv2.jpg` or `IMG_4821.JPG`. During a migration, a good convention
is `<page-slug>-NN.webp`.

## Edge cases

- **Animated GIFs:** the recipe turns a long animated GIF into a giant multi-frame WebP.
  Instead, flatten to the first frame: `magick INPUT[0] -strip -quality 82 OUTPUT.webp` (or
  keep it as a real video if motion matters).
- **Logos / line art / transparency:** WebP handles transparency; for crisp logos, SVG is
  better than any raster format if you have the vector.
- **Responsive sizes:** once images are in the WordPress Media Library with a known
  attachment ID, WordPress generates responsive `srcset` sizes automatically — but only when
  the `<img>` carries its `wp-image-<id>` class. If you inject image markup by hand (e.g. in
  migrated content), make sure each image is wired to its Media Library attachment ID so
  `srcset`/`sizes` render.

## When to use it

- Building or redesigning any page with photography.
- Migrating a site (optimize the whole image set as a batch before import).
- Any time a client's site is slow and the images are the obvious culprit (check with the
  browser dev tools network tab or a Lighthouse run).
