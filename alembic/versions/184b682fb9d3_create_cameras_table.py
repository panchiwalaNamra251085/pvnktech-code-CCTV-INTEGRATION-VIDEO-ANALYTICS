"""create cameras table

Revision ID: 184b682fb9d3
Revises: 05c72439e66d
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "184b682fb9d3"
down_revision: Union[str, Sequence[str], None] = "05c72439e66d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create cameras table."""

    op.create_table(
        "cameras",

        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),

        sa.Column(
            "site_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "code",
            sa.String(length=100),
            nullable=False,
        ),

        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "rtsp_url",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint("code"),
    )

    op.create_index(
        "ix_cameras_site_id",
        "cameras",
        ["site_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop cameras table."""

    op.drop_index(
        "ix_cameras_site_id",
        table_name="cameras",
    )

    op.drop_table("cameras")