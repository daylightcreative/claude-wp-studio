#!/bin/sh
set -e
/usr/sbin/sshd
# Let the official entrypoint lay down WordPress and wp-config.php, then install it.
docker-entrypoint.sh apache2-foreground &
until [ -f /var/www/html/wp-config.php ]; do sleep 1; done
cd /var/www/html
# The image reads DB settings from container variables, which an SSH session doesn't have. Bake the
# real values in, the way a hosted wp-config.php looks.
for k in DB_NAME DB_USER DB_PASSWORD DB_HOST; do
  [ "$k" = DB_NAME ] && v=$WORDPRESS_DB_NAME
  [ "$k" = DB_USER ] && v=$WORDPRESS_DB_USER
  [ "$k" = DB_PASSWORD ] && v=$WORDPRESS_DB_PASSWORD
  [ "$k" = DB_HOST ] && v=$WORDPRESS_DB_HOST
  wp config set "$k" "$v" --allow-root --quiet
done
chown -R deploy:www-data /var/www/html
chmod -R g+w /var/www/html
cd /var/www/html
until su deploy -s /bin/sh -c "wp db check" >/dev/null 2>&1; do sleep 2; done
su deploy -s /bin/sh -c "wp core is-installed || wp core install --url=http://localhost:8089 --title=E2E --admin_user=admin --admin_password=admin-pass-123 --admin_email=admin@example.com --skip-email"
touch /tmp/e2e-ready
wait
