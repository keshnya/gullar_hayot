FROM postgres:16-alpine

# Кладём init-скрипт внутрь образа, чтобы в Coolify не зависеть от относительных путей/volume-mount.
# Скрипт выполнится автоматически при первом старте пустого volume.
COPY database/migrations/all_init.sql /docker-entrypoint-initdb.d/all_init.sql


