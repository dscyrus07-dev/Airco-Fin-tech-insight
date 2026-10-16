#!/bin/sh
# Expire queued/dead-lettered payloads after 7 days (604800000 ms) via a policy.
# Policies apply to existing durable queues without redeclaring them.
# Usage (inside the rabbitmq container): sh apply_retention_policy.sh
set -eu
rabbitmqctl set_policy --apply-to queues airco-retention \
  "^(file_upload_queue|dead_letter_queue)$" '{"message-ttl":604800000}'
rabbitmqctl list_policies
