"""Single-table DynamoDB access. Partition key U#cbg#<entity>, sort key an
ISO timestamp — every access pattern in this app is "this entity, this date
range" for one user. Built out starting phase 1."""
