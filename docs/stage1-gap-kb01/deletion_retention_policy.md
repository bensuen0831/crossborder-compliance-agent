# Deletion and retention

Package A implements reference impact, reason/CAS/idempotency, operation grants and policy-authorized eligible draft deletion. Missing/ambiguous/unreviewed management policy fails closed. Knowledge metadata labels are owned by unpublished versions; every other FK reference and snapshot pin protects deletion. Approved/published/ingested versions remain protected. Deletion leaves an immutable receipt/tombstone under canonical AdminChangeSet.

Active holds protect archival in both the original knowledge channel and the new management channel. Release is a server-actor-owned, one-time CAS transition. Released hold history remains; its FK still protects physical deletion, preserving audit evidence. Use lifecycle archive/expiry instead of discarding retained history. No binary object is purged merely because an administrative draft is removed.

Publication, expiry, supersession and archive reuse the original knowledge lifecycle. Archived versions remain available to authorized exact historical pins. No project trace is cascade-deleted. Durable batch cancellation/leases, object retention cleanup and per-item bulk mutation reports remain B/E work, and are not claimed complete by the A focused tests.
