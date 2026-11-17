"""Initial database schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-17 18:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("purchase_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("retail_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("stock_qty", sa.Integer(), nullable=False),
        sa.Column("min_stock_qty", sa.Integer(), nullable=False),
        sa.CheckConstraint("min_stock_qty >= 0", name="ck_parts_min_stock_qty_non_negative"),
        sa.CheckConstraint("purchase_price >= 0", name="ck_parts_purchase_price_non_negative"),
        sa.CheckConstraint("retail_price >= 0", name="ck_parts_retail_price_non_negative"),
        sa.CheckConstraint("stock_qty >= 0", name="ck_parts_stock_qty_non_negative"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parts")),
    )
    op.create_index("ix_parts_category", "parts", ["category"], unique=False)
    op.create_index(op.f("ix_parts_sku"), "parts", ["sku"], unique=True)

    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("warranty_days", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("base_price >= 0", name="ck_services_base_price_non_negative"),
        sa.CheckConstraint("warranty_days >= 0", name="ck_services_warranty_days_non_negative"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
        sa.UniqueConstraint("title", name=op.f("uq_services_title")),
    )
    op.create_index("ix_services_category", "services", ["category"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(full_name)) >= 2", name="ck_users_full_name_len"),
        sa.CheckConstraint("role IN ('client', 'master', 'admin')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("phone", name=op.f("uq_users_phone")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    op.create_table(
        "requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("master_id", sa.Integer(), nullable=True),
        sa.Column("service_id", sa.Integer(), nullable=True),
        sa.Column("device_type", sa.String(length=80), nullable=False),
        sa.Column("device_brand", sa.String(length=80), nullable=False),
        sa.Column("device_model", sa.String(length=120), nullable=False),
        sa.Column("serial_number", sa.String(length=100), nullable=True),
        sa.Column("appearance", sa.Text(), nullable=True),
        sa.Column("problem_description", sa.Text(), nullable=False),
        sa.Column("diagnostic_result", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("labor_cost", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("parts_cost", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("total_cost", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("labor_cost >= 0", name="ck_requests_labor_cost_non_negative"),
        sa.CheckConstraint("parts_cost >= 0", name="ck_requests_parts_cost_non_negative"),
        sa.CheckConstraint(
            "length(trim(problem_description)) >= 5",
            name="ck_requests_problem_description_len",
        ),
        sa.CheckConstraint(
            "status IN ('accepted', 'diagnostics', 'in_repair', 'ready', 'issued')",
            name="ck_requests_status",
        ),
        sa.CheckConstraint("total_cost >= 0", name="ck_requests_total_cost_non_negative"),
        sa.ForeignKeyConstraint(
            ["client_id"], ["users.id"], name=op.f("fk_requests_client_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["master_id"], ["users.id"], name=op.f("fk_requests_master_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_requests_service_id_services"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requests")),
    )
    op.create_index(op.f("ix_requests_client_id"), "requests", ["client_id"], unique=False)
    op.create_index(op.f("ix_requests_master_id"), "requests", ["master_id"], unique=False)
    op.create_index(op.f("ix_requests_status"), "requests", ["status"], unique=False)
    op.create_index("ix_requests_status_created_at", "requests", ["status", "created_at"], unique=False)

    op.create_table(
        "master_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("comment_text", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(comment_text)) >= 1", name="ck_master_comments_text_not_empty"
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_master_comments_author_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["requests.id"],
            name=op.f("fk_master_comments_request_id_requests"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_master_comments")),
    )
    op.create_index(
        op.f("ix_master_comments_request_id"), "master_comments", ["request_id"], unique=False
    )

    op.create_table(
        "request_parts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("part_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="ck_request_parts_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_request_parts_unit_price_non_negative"),
        sa.ForeignKeyConstraint(
            ["part_id"],
            ["parts.id"],
            name=op.f("fk_request_parts_part_id_parts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["requests.id"],
            name=op.f("fk_request_parts_request_id_requests"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request_parts")),
        sa.UniqueConstraint("request_id", "part_id", name="uq_request_parts_request_part"),
    )
    op.create_index(op.f("ix_request_parts_part_id"), "request_parts", ["part_id"], unique=False)
    op.create_index(
        op.f("ix_request_parts_request_id"), "request_parts", ["request_id"], unique=False
    )

    op.create_table(
        "request_photos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=False),
        sa.Column("file_url", sa.String(length=500), nullable=False),
        sa.Column("caption", sa.String(length=200), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["requests.id"],
            name=op.f("fk_request_photos_request_id_requests"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["users.id"],
            name=op.f("fk_request_photos_uploaded_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request_photos")),
    )
    op.create_index(
        op.f("ix_request_photos_request_id"), "request_photos", ["request_id"], unique=False
    )

    op.create_table(
        "status_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=False),
        sa.Column("old_status", sa.String(length=30), nullable=True),
        sa.Column("new_status", sa.String(length=30), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "new_status IN ('accepted', 'diagnostics', 'in_repair', 'ready', 'issued')",
            name="ck_status_history_new_status",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"],
            ["users.id"],
            name=op.f("fk_status_history_changed_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["requests.id"],
            name=op.f("fk_status_history_request_id_requests"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_status_history")),
    )
    op.create_index(
        op.f("ix_status_history_request_id"), "status_history", ["request_id"], unique=False
    )

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("part_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=True),
        sa.Column("performed_by_id", sa.Integer(), nullable=False),
        sa.Column("movement_type", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "movement_type IN ('in', 'out', 'return', 'write_off')",
            name="ck_stock_movements_type",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_stock_movements_quantity_positive"),
        sa.ForeignKeyConstraint(
            ["part_id"],
            ["parts.id"],
            name=op.f("fk_stock_movements_part_id_parts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["performed_by_id"],
            ["users.id"],
            name=op.f("fk_stock_movements_performed_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["requests.id"],
            name=op.f("fk_stock_movements_request_id_requests"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_movements")),
    )
    op.create_index(op.f("ix_stock_movements_part_id"), "stock_movements", ["part_id"], unique=False)
    op.create_index(
        op.f("ix_stock_movements_request_id"), "stock_movements", ["request_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stock_movements_request_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_part_id"), table_name="stock_movements")
    op.drop_table("stock_movements")

    op.drop_index(op.f("ix_status_history_request_id"), table_name="status_history")
    op.drop_table("status_history")

    op.drop_index(op.f("ix_request_photos_request_id"), table_name="request_photos")
    op.drop_table("request_photos")

    op.drop_index(op.f("ix_request_parts_request_id"), table_name="request_parts")
    op.drop_index(op.f("ix_request_parts_part_id"), table_name="request_parts")
    op.drop_table("request_parts")

    op.drop_index(op.f("ix_master_comments_request_id"), table_name="master_comments")
    op.drop_table("master_comments")

    op.drop_index("ix_requests_status_created_at", table_name="requests")
    op.drop_index(op.f("ix_requests_status"), table_name="requests")
    op.drop_index(op.f("ix_requests_master_id"), table_name="requests")
    op.drop_index(op.f("ix_requests_client_id"), table_name="requests")
    op.drop_table("requests")

    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    op.drop_index("ix_services_category", table_name="services")
    op.drop_table("services")

    op.drop_index(op.f("ix_parts_sku"), table_name="parts")
    op.drop_index("ix_parts_category", table_name="parts")
    op.drop_table("parts")
