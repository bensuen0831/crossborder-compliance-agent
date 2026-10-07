"""Stable canonical inventory identity, immutable exact-version state/provenance.

Unknown legacy provenance remains NULL and is excluded from all formal readers;
only stored accepted resolutions prove a historical inventory version.
"""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0013_m2b_context_temporal_contract"
down_revision = "0012_m2b_document_inputs"
branch_labels = None
depends_on = None

VERSIONED = (
    "data_item_resolution_details", "data_item_candidate_links",
    "data_item_source_trace_links", "data_item_product_link_details",
    "data_item_flow_link_details",
)


def _columns(table):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _versioned_identity(table, owner_column, version_column, unique_name):
    if "detail_version_id" not in _columns(table):
        op.add_column(table, sa.Column("detail_version_id", sa.String(36), nullable=True))
        for row in op.get_bind().execute(sa.text(f"SELECT {owner_column} FROM {table}")):
            op.get_bind().execute(sa.text(f"UPDATE {table} SET detail_version_id=:id WHERE {owner_column}=:owner"), {"id": str(uuid4()), "owner": row[0]})
        op.alter_column(table, "detail_version_id", nullable=False)
        pk = sa.inspect(op.get_bind()).get_pk_constraint(table)["name"]
        op.drop_constraint(pk, table, type_="primary")
        op.create_primary_key(f"{table}_pkey", table, ["detail_version_id"])
    if unique_name not in {x["name"] for x in sa.inspect(op.get_bind()).get_unique_constraints(table)}:
        op.create_unique_constraint(unique_name, table, ["tenant_id", owner_column, version_column])


def _backfill_links(table, key_column, source_column, predicate):
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"SELECT * FROM {table} WHERE data_inventory_version IS NULL")).mappings().all()
    for row in rows:
        versions = bind.execute(sa.text(f"""
            SELECT DISTINCT r.version FROM candidate_resolutions r
            JOIN data_items i ON i.data_item_id=r.formal_object_id AND i.tenant_id=r.tenant_id
            JOIN context_resolution_runs cr ON cr.project_id=i.project_id AND cr.tenant_id=i.tenant_id AND cr.data_inventory_version=r.version
            WHERE r.tenant_id=:tenant AND r.formal_object_type='DATA_ITEM'
              AND r.formal_object_id=:item AND r.action IN ('ACCEPTED','MERGED')
              AND {predicate}
            ORDER BY r.version
        """), {"tenant": row["tenant_id"], "item": row["data_item_id"], "source": row[source_column]}).scalars().all()
        for index, version in enumerate(versions):
            if index == 0:
                bind.execute(sa.text(f"UPDATE {table} SET data_inventory_version=:version WHERE {key_column}=:key"), {"version": version, "key": row[key_column]})
            else:
                copy = dict(row)
                copy[key_column] = str(uuid4())
                copy["data_inventory_version"] = version
                columns = ",".join(copy)
                parameters = ",".join(":" + key for key in copy)
                bind.execute(sa.text(f"INSERT INTO {table} ({columns}) VALUES ({parameters})"), copy)


def upgrade():
    # The approved revision identifier exceeds Alembic's historical varchar32.
    op.alter_column("alembic_version", "version_num", type_=sa.String(64))
    for table in VERSIONED[1:]:
        if "data_inventory_version" not in _columns(table):
            op.add_column(table, sa.Column("data_inventory_version", sa.Integer(), nullable=True))
    _versioned_identity("data_item_resolution_details", "data_item_id", "version", "uq_data_item_detail_version")
    _versioned_identity("data_item_product_link_details", "data_item_product_link_id", "data_inventory_version", "uq_data_item_product_detail_version")
    for table, source, name in (
        ("data_item_candidate_links", "candidate_data_item_id", "uq_data_item_candidate_link"),
        ("data_item_source_trace_links", "source_trace_ref_id", "uq_data_item_source_trace_link"),
    ):
        constraints = {x["name"]: x["column_names"] for x in sa.inspect(op.get_bind()).get_unique_constraints(table)}
        wanted = ["tenant_id", "data_item_id", "data_inventory_version", source]
        if constraints.get(name) != wanted:
            op.drop_constraint(name, table, type_="unique")
            op.create_unique_constraint(name, table, wanted)
    _backfill_links("data_item_candidate_links", "data_item_candidate_link_id", "candidate_data_item_id", "r.candidate_type='DATA_ITEM' AND r.candidate_id=:source")
    _backfill_links("data_item_source_trace_links", "data_item_source_trace_link_id", "source_trace_ref_id", "r.candidate_type='DATA_ITEM' AND r.source_trace_ids_json::jsonb @> jsonb_build_array(CAST(:source AS text))")
    # Flow IDs are freshly created per context run, not reused. Their stored
    # exact edge version and item membership can prove a historical link.
    op.execute("""UPDATE data_item_flow_link_details ld SET data_inventory_version=ed.version
        FROM data_item_flow_links l JOIN data_flow_edge_details ed ON ed.flow_edge_id=l.flow_edge_id
        JOIN data_item_resolution_details id ON id.data_item_id=l.data_item_id AND id.tenant_id=l.tenant_id AND id.version=ed.version
        WHERE ld.link_id=l.link_id AND ld.tenant_id=l.tenant_id AND ed.tenant_id=l.tenant_id AND ld.data_inventory_version IS NULL""")
    # Product links without a stored version cannot be inferred from live
    # product scope. Keep their NULL version rather than invent provenance.
    op.execute("""CREATE OR REPLACE FUNCTION guard_m2b_temporal() RETURNS trigger AS $$
      DECLARE v integer; item text; t text; owner_project text;
      BEGIN
        IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'immutable formal context version'; END IF;
        IF TG_TABLE_NAME='data_item_resolution_details' THEN
          v=NEW.version; item=NEW.data_item_id;
        ELSIF TG_TABLE_NAME='data_item_product_link_details' THEN
          v=NEW.data_inventory_version;
          SELECT data_item_id INTO item FROM data_item_product_links WHERE data_item_product_link_id=NEW.data_item_product_link_id AND tenant_id=NEW.tenant_id;
        ELSIF TG_TABLE_NAME='data_item_flow_link_details' THEN
          v=NEW.data_inventory_version;
          SELECT data_item_id INTO item FROM data_item_flow_links WHERE link_id=NEW.link_id AND tenant_id=NEW.tenant_id;
        ELSE v=NEW.data_inventory_version; item=NEW.data_item_id;
        END IF;
        SELECT tenant_id, project_id INTO t,owner_project FROM data_items WHERE data_item_id=item;
        IF v IS NULL OR v < 1 OR t IS DISTINCT FROM NEW.tenant_id THEN
          RAISE EXCEPTION 'exact tenant/inventory membership required';
        END IF;
        IF TG_TABLE_NAME<>'data_item_resolution_details' AND NOT EXISTS(
          SELECT 1 FROM data_item_resolution_details WHERE tenant_id=NEW.tenant_id AND data_item_id=item AND version=v
        ) THEN RAISE EXCEPTION 'exact inventory detail membership required'; END IF;
        RETURN NEW;
      END; $$ LANGUAGE plpgsql""")
    for table in VERSIONED:
        op.execute(f"CREATE TRIGGER guard_m2b_temporal BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION guard_m2b_temporal()")


def downgrade():
    bind = op.get_bind()
    if any(bind.execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")).scalar() for table in VERSIONED):
        raise RuntimeError("M2-B formal temporal context retained; archive/export required before downgrade")
    for table in VERSIONED:
        op.execute(f"DROP TRIGGER guard_m2b_temporal ON {table}")
    op.execute("DROP FUNCTION guard_m2b_temporal()")
    for table, owner, constraint in (
        ("data_item_resolution_details", "data_item_id", "uq_data_item_detail_version"),
        ("data_item_product_link_details", "data_item_product_link_id", "uq_data_item_product_detail_version"),
    ):
        op.drop_constraint(constraint, table, type_="unique")
        op.drop_constraint(f"{table}_pkey", table, type_="primary")
        op.drop_column(table, "detail_version_id")
        op.create_primary_key(f"{table}_pkey", table, [owner])
    for table, source, name in (
        ("data_item_candidate_links", "candidate_data_item_id", "uq_data_item_candidate_link"),
        ("data_item_source_trace_links", "source_trace_ref_id", "uq_data_item_source_trace_link"),
    ):
        op.drop_constraint(name, table, type_="unique")
        op.create_unique_constraint(name, table, ["tenant_id", "data_item_id", source])
    for table in VERSIONED[1:]:
        op.drop_column(table, "data_inventory_version")
    # Keep Alembic's wider technical revision column: its value is updated by
    # Alembic after downgrade(), and narrowing here would truncate this head.
