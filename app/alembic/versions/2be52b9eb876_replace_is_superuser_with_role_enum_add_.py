"""replace_is_superuser_with_role_enum_add_username_remove_items

Revision ID: 2be52b9eb876
Revises: fe56fa70289e
Create Date: 2026-03-07 20:55:00.937266

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "2be52b9eb876"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Drop the item table
    op.drop_table("item")

    # 2. Create the UserRole enum type
    userrole_enum = sa.Enum("facilitator", "admin", "superuser", name="userrole")
    userrole_enum.create(op.get_bind(), checkfirst=True)

    # 3. Add new columns as nullable first (so existing rows don't break)
    op.add_column(
        "user",
        sa.Column(
            "username",
            sqlmodel.sql.sqltypes.AutoString(length=150),
            nullable=True,
        ),
    )
    op.add_column(
        "user",
        sa.Column(
            "role",
            sa.Enum(
                "facilitator", "admin", "superuser", name="userrole", create_type=False
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "user",
        sa.Column(
            "last_login",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # 4. Populate existing rows:
    #    - username = email (guaranteed unique since email is unique)
    #    - role = 'superuser' if is_superuser else 'facilitator'
    op.execute(
        sa.text("""
        UPDATE "user"
        SET username = email,
            role = CASE
                WHEN is_superuser = true THEN 'superuser'::userrole
                ELSE 'facilitator'::userrole
            END
    """)
    )

    # 5. Make columns non-nullable now that all rows have values
    op.alter_column("user", "username", nullable=False)
    op.alter_column("user", "role", nullable=False)

    # 6. Create unique index on username
    op.create_index(op.f("ix_user_username"), "user", ["username"], unique=True)

    # 7. Drop the old is_superuser column
    op.drop_column("user", "is_superuser")


def downgrade():
    # 1. Re-add is_superuser column (nullable first for data migration)
    op.add_column(
        "user",
        sa.Column(
            "is_superuser",
            sa.BOOLEAN(),
            autoincrement=False,
            nullable=True,
        ),
    )

    # 2. Populate is_superuser from role
    op.execute(
        sa.text("""
        UPDATE "user"
        SET is_superuser = CASE
            WHEN role = 'superuser' THEN true
            ELSE false
        END
    """)
    )

    # 3. Make is_superuser non-nullable
    op.alter_column("user", "is_superuser", nullable=False)

    # 4. Drop new columns and index
    op.drop_index(op.f("ix_user_username"), table_name="user")
    op.drop_column("user", "last_login")
    op.drop_column("user", "role")
    op.drop_column("user", "username")

    # 5. Drop the UserRole enum type
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)

    # 6. Re-create the item table
    op.create_table(
        "item",
        sa.Column(
            "description", sa.VARCHAR(length=255), autoincrement=False, nullable=True
        ),
        sa.Column("title", sa.VARCHAR(length=255), autoincrement=False, nullable=False),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("owner_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["user.id"],
            name=op.f("item_owner_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("item_pkey")),
    )
