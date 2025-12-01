#!bin/bash

if [ -d "/home/frappe/frappe-bench/apps/frappe" ]; then
    echo "Bench already exists, skipping init"
    cd frappe-bench
    bench start
else
    echo "Creating new bench..."
fi

bench init --skip-redis-config-generation frappe-bench --version version-15

cd frappe-bench

# Use containers instead of localhost
bench set-mariadb-host mariadb
bench set-redis-cache-host redis://redis-cache:6379
bench set-redis-queue-host redis://redis-queue:6379
bench set-redis-socketio-host redis://redis-queue:6379

# Remove redis, watch from Procfile
sed -i '/redis/d' ./Procfile
sed -i '/watch/d' ./Procfile

bench get-app telephony
bench get-app https://github.com/tortoiseclub/helpdesk --branch main

bench new-site helpdesk.tortoise.pro \
--force \
--mariadb-root-password 123 \
--admin-password admin \
--no-mariadb-socket

bench --site helpdesk.tortoise.pro install-app telephony
bench --site helpdesk.tortoise.pro install-app helpdesk
bench --site helpdesk.tortoise.pro set-config developer_mode 1
bench --site helpdesk.tortoise.pro set-config mute_emails 1
bench --site helpdesk.tortoise.pro set-config server_script_enabled 1
bench --site helpdesk.tortoise.pro clear-cache
bench use helpdesk.tortoise.pro

bench start
