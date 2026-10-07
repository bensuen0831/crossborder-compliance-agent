# M2B binary storage result

ObjectStoragePort remains the provider-neutral boundary. Existing S3 adapter is retained; immutable configured filesystem adapter supports local/restricted deployments. PostgreSQL stores canonical identity/hash/size/media/reference/audit only. Actual content is validated against a versioned server technical file policy. Required scan without a configured scanner fails closed. Test policy explicitly records NOT_REQUESTED, never fabricated scan PASS. Deployment/provider onboarding is outside this task.
