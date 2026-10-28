# A disposable WordPress host for the end-to-end tests: Apache + mod_php (opcache on, like most
# hosts), WP-CLI, the MariaDB client tools `wp db export` needs, and an SSH server that accepts a
# password login, like a managed host's SFTP/SSH account.
FROM wordpress:6-php8.3-apache
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-server mariadb-client less \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL -o /usr/local/bin/wp https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar \
 && chmod +x /usr/local/bin/wp \
 && useradd -m -s /bin/bash -g www-data deploy \
 && echo 'deploy:s3cret-Pass!word' | chpasswd \
 && mkdir -p /run/sshd \
 && sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
COPY start.sh /usr/local/bin/start-e2e
RUN chmod +x /usr/local/bin/start-e2e
CMD ["start-e2e"]
# Never re-check files on disk: only an explicit opcache reset makes new PHP visible, which is
# exactly what the deploy test needs to prove.
RUN printf 'opcache.enable=1\nopcache.validate_timestamps=0\n' > /usr/local/etc/php/conf.d/zz-e2e-opcache.ini
