from __future__ import annotations

import os, uuid, math
import requests as _requests
from typing import Optional, Tuple
from datetime import datetime, timedelta, timezone
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, sessionmaker
from flask import Flask, render_template, redirect, url_for, request, flash, abort, jsonify
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user, UserMixin
)
import json
from urllib.parse import urlparse
import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from ..config import settings
from necls_backend.db import (
    engine as db1_engine,
    generations,
    summary_localized,
    db2_links,
    sources,
    slides,
    slide_localized, articles, story_clusters
)
from necls_backend.save_to_app_db import export_cluster_to_db2, _ensure_seo_tag
from necls_backend.app_db import (
    engine as db2_engine,
    event, localized_event_data, source, event_analysis, localized_event_analysis,
    event_so_far, localized_event_so_far, category, seo_tag, event_seo_tag, event_faq,
    app_config, collection, collection_seo_tag, users, user_devices,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert

Base = declarative_base()
SessionLocal = sessionmaker(bind=db1_engine)

_s3_client = boto3.client("s3", aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                          aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))


def _presign_s3_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme != "s3":
        return url
    try:
        return _s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": parsed.netloc, "Key": parsed.path.lstrip("/")},
            ExpiresIn=3600,
        )
    except (BotoCoreError, NoCredentialsError):
        return url



class ReviewUser(Base, UserMixin):
    __tablename__ = "review_users"
    id = sa.Column(sa.Integer, primary_key=True)
    username = sa.Column(sa.String(50), unique=True, nullable=False)
    password_hash = sa.Column(sa.String(255), nullable=False)
    role = sa.Column(sa.String(20), nullable=False, default="reviewer")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def is_admin(self) -> bool:
        return self.role == "admin"

    def can_save(self) -> bool:
        return self.role in ("admin", "editor")

    def can_sync(self) -> bool:
        return self.role == "admin"


class ReviewStatus(Base):
    __tablename__ = "review_status"
    cluster_id = sa.Column(sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True)
    reviewed_at = sa.Column(sa.DateTime(timezone=True))
    reviewer_id = sa.Column(sa.Integer, sa.ForeignKey("review_users.id"))
    # Make these columns nullable to handle missing database columns gracefully
    approval_status = sa.Column(sa.String(20), default="pending", nullable=True)  # pending, approved, rejected
    approved_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    rejection_reason = sa.Column(sa.Text, nullable=True)
    processing_status = sa.Column(sa.String(20), default="pending", nullable=True)  # pending, processing, completed, failed
    processed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)


# Pending article changes: table created by migration 001_pending_article_changes.sql (DB1). Not in Base so app never creates it.
_pending_meta = sa.MetaData()
pending_article_changes_table = sa.Table(
    "pending_article_changes",
    _pending_meta,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("created_by_id", sa.Integer, sa.ForeignKey("review_users.id"), nullable=False),
    sa.Column("created_by_username", sa.String(255), nullable=False),
    sa.Column("change_type", sa.String(50), nullable=False),
    sa.Column("target_event_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("target_title", sa.Text, nullable=True),
    sa.Column("summary", sa.Text, nullable=True),
    sa.Column("payload", sa.dialects.postgresql.JSONB, nullable=False),
    sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
    sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("reviewed_by_id", sa.Integer, sa.ForeignKey("review_users.id"), nullable=True),
)


def ensure_webadmin_schema() -> None:
    """Ensure webadmin tables and columns exist with correct schema.
    This function is idempotent and safe to call multiple times.
    Handles both new tables and adding missing columns to existing tables.
    """
    try:
        with db1_engine.begin() as conn:
            # Ensure review_users table exists
            table_exists = conn.execute(sa.text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'review_users'
                );
            """)).scalar()
            
            if not table_exists:
                # Create table with all required columns
                conn.execute(sa.text("""
                    CREATE TABLE review_users (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(50) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        role VARCHAR(20) NOT NULL DEFAULT 'reviewer'
                    );
                """))
                print("[OK] Created review_users table")
            else:
                # Table exists - check and add missing columns
                result = conn.execute(sa.text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'review_users';
                """))
                existing_columns = {row[0] for row in result}
                
                # Add password_hash if missing
                if 'password_hash' not in existing_columns:
                    conn.execute(sa.text("""
                        ALTER TABLE review_users 
                        ADD COLUMN password_hash VARCHAR(255);
                    """))
                    print("[OK] Added password_hash column to review_users")
                    
                    # Make it NOT NULL if table is empty
                    null_count = conn.execute(sa.text("""
                        SELECT COUNT(*) FROM review_users WHERE password_hash IS NULL;
                    """)).scalar()
                    if null_count == 0:
                        try:
                            conn.execute(sa.text("""
                                ALTER TABLE review_users 
                                ALTER COLUMN password_hash SET NOT NULL;
                            """))
                        except Exception:
                            pass  # May fail if there are NULL values
                
                # Add role if missing
                if 'role' not in existing_columns:
                    conn.execute(sa.text("""
                        ALTER TABLE review_users 
                        ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'reviewer';
                    """))
                    print("[OK] Added role column to review_users")
                
            # Ensure review_status table exists
            status_table_exists = conn.execute(sa.text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'review_status'
                );
            """)).scalar()
            
            if not status_table_exists:
                # Create table with all required columns
                conn.execute(sa.text("""
                    CREATE TABLE review_status (
                        cluster_id UUID PRIMARY KEY,
                        reviewed_at TIMESTAMP WITH TIME ZONE,
                        reviewer_id INTEGER REFERENCES review_users(id),
                        approval_status VARCHAR(20) DEFAULT 'pending',
                        approved_at TIMESTAMP WITH TIME ZONE,
                        rejection_reason TEXT,
                        processing_status VARCHAR(20) DEFAULT 'pending',
                        processed_at TIMESTAMP WITH TIME ZONE
                    );
                """))
                print("[OK] Created review_status table")
            else:
                # Table exists - check and add missing columns
                result = conn.execute(sa.text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'review_status';
                """))
                existing_columns = {row[0] for row in result}
                
                # Add missing columns if they don't exist
                columns_to_add = {
                    'approval_status': "VARCHAR(20) DEFAULT 'pending'",
                    'approved_at': 'TIMESTAMP WITH TIME ZONE',
                    'rejection_reason': 'TEXT',
                    'processing_status': "VARCHAR(20) DEFAULT 'pending'",
                    'processed_at': 'TIMESTAMP WITH TIME ZONE'
                }
                
                for col_name, col_def in columns_to_add.items():
                    if col_name not in existing_columns:
                        conn.execute(sa.text(f"""
                            ALTER TABLE review_status 
                            ADD COLUMN {col_name} {col_def};
                        """))
                        print(f"[OK] Added {col_name} column to review_status")
            
            conn.commit()
            print("[OK] Webadmin schema verified and up-to-date")
            
    except Exception as e:
        print(f"[ERROR] Failed to ensure webadmin schema: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - allow app to start even if schema setup fails
        # (user can fix manually if needed)


def ensure_initial_admin() -> None:
    """Create the first admin user using env vars if no users exist."""
    username = settings.username # os.getenv("INITIAL_ADMIN_USERNAME")
    password = settings.password # os.getenv("INITIAL_ADMIN_PASSWORD")
    if not username or not password:
        return
    with SessionLocal() as session:
        count = session.execute(sa.select(sa.func.count()).select_from(ReviewUser)).scalar()
        if count == 0:
            user = ReviewUser(username=username, role="admin")
            user.set_password(password)
            session.add(user)
            session.commit()


# Ensure schema is correct before creating tables
try:
    ensure_webadmin_schema()
    # Create tables (SQLAlchemy will handle existing tables gracefully)
    Base.metadata.create_all(db1_engine)
    # Create initial admin user
    ensure_initial_admin()
except Exception as e:
    print(f"[WARNING] Database initialization failed: {e}")
    print("[WARNING] The app will run but database features may not work")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("ADMIN_SECRET", "dev-secret")
# Avoid escaping non-ASCII characters when using the ``tojson`` filter so
# languages like Hindi render correctly in the admin templates.
app.jinja_env.policies["json.dumps_kwargs"] = {"ensure_ascii": False}

login_manager = LoginManager(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id: str):
    with SessionLocal() as session:
        return session.get(ReviewUser, int(user_id))


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return fn(*args, **kwargs)

    return wrapper


def approver_required(fn):
    """Require admin or reviewer (for pending-changes list / approve / reject)."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ("admin", "reviewer"):
            abort(403)
        return fn(*args, **kwargs)

    return wrapper


def _get_clusters(
    conn,
    *,
    page: int,
    per_page: int,
    filters: dict,
    search: Optional[str] = None,
    order: Optional[Tuple[str, str]] = None,
) -> Tuple[list, int, int]:
    # Special handling for rejected clusters that may not have summary generations
    approval_status = filters.get("approval_status")
    if approval_status in ('editorial_rejected', 'manual_rejected', 'all_rejected', 'manual_approved'):
        return _get_rejected_clusters(conn, page=page, per_page=per_page, filters=filters, search=search, order=order)
    g = generations.alias("g")
    sg = (
        sa.select(
            g.c.id.label("gen_id"),
            g.c.cluster_id,
            g.c.created_at,
            sa.func.coalesce(
                g.c.extra["classification"]["categories"][0]["name"].astext,
                sa.literal("Uncategorized")
            ).label("category"),
            sa.func.row_number()
            .over(partition_by=g.c.cluster_id, order_by=g.c.created_at.desc())
            .label("rn"),
        )
        .where(g.c.artifact == "summary")
        .subquery()
    )
    latest = (
        sa.select(
            sg.c.gen_id,
            sg.c.cluster_id,
            sg.c.created_at.label("last_gen"),
            sg.c.category,
        )
        .where(sg.c.rn == 1)
        .subquery()
    )
    l = db2_links.alias("l")
    rs = ReviewStatus.__table__.alias("rs")
    sl = summary_localized.alias("sl")
    sc = story_clusters.alias("sc")
    base = (
        sa.select(
            latest.c.cluster_id,
            latest.c.last_gen,
            latest.c.category,
            sl.c.mini_headline.label("mini_heading"),
            sl.c.headline.label("title"),
            (l.c.last_synced_at != None)
            & (l.c.last_synced_at >= latest.c.last_gen)
            .label("synced"),
            (rs.c.reviewed_at != None).label("reviewed"),
            sc.c.filter_status.label("approval_status"),
            sa.func.coalesce(sc.c.rejection_reason, sa.literal("No reason provided")).label("rejection_reason"),
            sc.c.auto_approved,
        )
        .select_from(latest)
        .outerjoin(l, l.c.cluster_id == latest.c.cluster_id)
        .outerjoin(rs, rs.c.cluster_id == latest.c.cluster_id)
        .outerjoin(sc, sc.c.cluster_id == latest.c.cluster_id)
        .outerjoin(
            sl,
            sa.and_(
                sl.c.generation_id == latest.c.gen_id,
                sl.c.language_id == "en",
            ),
        )
    )
    if filters.get("start_date"):
        base = base.where(latest.c.last_gen >= filters["start_date"])
    if filters.get("end_date"):
        base = base.where(latest.c.last_gen <= filters["end_date"])
    if filters.get("reviewed") == "reviewed":
        base = base.where(rs.c.reviewed_at != None)
    elif filters.get("reviewed") == "not_reviewed":
        base = base.where(rs.c.reviewed_at == None)
    if filters.get("category"):
        base = base.where(latest.c.category == filters["category"])
    if filters.get("approval_status"):
        base = base.where(sc.c.filter_status == filters["approval_status"])
    total_stmt = sa.select(sa.func.count()).select_from(base.subquery())
    if search:
        pattern = f"%{search}%"
        base = base.where(
            sa.or_(
                sl.c.headline.ilike(pattern),
                sl.c.mini_headline.ilike(pattern),
                latest.c.category.ilike(pattern),
                sa.cast(latest.c.cluster_id, sa.String).ilike(pattern),
            )
        )
    filtered_stmt = sa.select(sa.func.count()).select_from(base.subquery())
    if order:
        col_name, direction = order
        col_map = {
            "cluster_id": latest.c.cluster_id,
            "category": latest.c.category,
            "title": sl.c.headline,
            "last_gen": latest.c.last_gen,
        }
        col = col_map.get(col_name, latest.c.last_gen)
        if direction == "desc":
            base = base.order_by(sa.desc(col))
        else:
            base = base.order_by(sa.asc(col))
    else:
        base = base.order_by(latest.c.last_gen.desc())
    rows = [
        dict(r._mapping)
        for r in conn.execute(base.limit(per_page).offset((page - 1) * per_page))
    ]
    filtered = conn.execute(filtered_stmt).scalar() or 0
    total = conn.execute(total_stmt).scalar() or 0
    return rows, int(filtered), int(total)


def _get_rejected_clusters(
    conn,
    *,
    page: int,
    per_page: int,
    filters: dict,
    search: Optional[str] = None,
    order: Optional[Tuple[str, str]] = None,
) -> Tuple[list, int, int]:
    """Get rejected or manually-approved clusters, including those without summary generations.
    Supports approval_status='all_rejected' (both rejected types), 'editorial_rejected',
    'manual_rejected', and 'manual_approved' (approval history tab).
    Date filters apply to rejected_at for rejected clusters, updated_at for manual_approved.
    """
    sc = story_clusters.alias("sc")
    g = generations.alias("g")
    sl = summary_localized.alias("sl")
    l = db2_links.alias("l")

    status = filters.get("approval_status")
    if status == "all_rejected":
        status_clause = sc.c.filter_status.in_(('editorial_rejected', 'manual_rejected'))
    else:
        status_clause = sc.c.filter_status == status

    rn_sq = (
        sa.select(
            g.c.id.label("gen_id"),
            g.c.cluster_id,
            sa.func.row_number()
            .over(partition_by=g.c.cluster_id, order_by=g.c.created_at.desc())
            .label("rn"),
        )
        .where(g.c.artifact == "summary")
        .subquery()
    )
    latest_gen_sq = (
        sa.select(rn_sq.c.gen_id, rn_sq.c.cluster_id)
        .where(rn_sq.c.rn == 1)
        .subquery()
    )

    base = (
        sa.select(
            sc.c.cluster_id,
            sa.func.coalesce(sc.c.rejected_at, sc.c.created_at).label("last_gen"),
            sc.c.rejected_at,
            sc.c.created_at,
            sc.c.updated_at,
            sa.literal("Rejected").label("category"),
            sa.func.coalesce(sl.c.headline, sc.c.headline, sa.literal("No title")).label("title"),
            sa.func.coalesce(sl.c.mini_headline, sc.c.headline, sa.literal("No headline")).label("mini_heading"),
            (l.c.cluster_id != None).label("synced"),
            sa.literal(False).label("reviewed"),
            sc.c.filter_status.label("approval_status"),
            sa.func.coalesce(sc.c.rejection_reason, sa.literal("No reason provided")).label("rejection_reason"),
            sc.c.auto_approved,
        )
        .select_from(sc)
        .outerjoin(latest_gen_sq, latest_gen_sq.c.cluster_id == sc.c.cluster_id)
        .outerjoin(
            sl,
            sa.and_(
                sl.c.generation_id == latest_gen_sq.c.gen_id,
                sl.c.language_id == "en",
            ),
        )
        .outerjoin(l, l.c.cluster_id == sc.c.cluster_id)
        .where(status_clause)
    )

    # Date range filters: use updated_at for manual_approved, rejected_at otherwise
    if status == "manual_approved":
        if filters.get("start_date"):
            base = base.where(sc.c.updated_at >= filters["start_date"])
        if filters.get("end_date"):
            base = base.where(sc.c.updated_at <= filters["end_date"])
    else:
        if filters.get("start_date"):
            base = base.where(
                sa.or_(
                    sc.c.rejected_at >= filters["start_date"],
                    sa.and_(sc.c.rejected_at == None, sc.c.created_at >= filters["start_date"]),
                )
            )
        if filters.get("end_date"):
            base = base.where(
                sa.or_(
                    sc.c.rejected_at <= filters["end_date"],
                    sa.and_(sc.c.rejected_at == None, sc.c.created_at <= filters["end_date"]),
                )
            )

    total_stmt = sa.select(sa.func.count()).select_from(base.subquery())
    total = conn.execute(total_stmt).scalar() or 0

    if search:
        pattern = f"%{search}%"
        base = base.where(
            sa.or_(
                sl.c.mini_headline.ilike(pattern),
                sl.c.headline.ilike(pattern),
                sc.c.headline.ilike(pattern),
                sc.c.rejection_reason.ilike(pattern),
                sa.cast(sc.c.cluster_id, sa.String).ilike(pattern),
            )
        )

    filtered_stmt = sa.select(sa.func.count()).select_from(base.subquery())
    filtered = conn.execute(filtered_stmt).scalar() or 0

    # Ordering: use updated_at for manual_approved, coalesce(rejected_at, created_at) otherwise
    default_order_col = sc.c.updated_at if status == "manual_approved" else sa.func.coalesce(sc.c.rejected_at, sc.c.created_at)
    if order:
        _, direction = order
        base = base.order_by(default_order_col.asc() if direction == "asc" else default_order_col.desc())
    else:
        base = base.order_by(default_order_col.desc())

    rows = [
        dict(r._mapping)
        for r in conn.execute(base.limit(per_page).offset((page - 1) * per_page))
    ]

    return rows, int(filtered), int(total)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with SessionLocal() as session:
            user = session.execute(
                sa.select(ReviewUser).where(ReviewUser.username == username)
            ).scalar_one_or_none()
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for("index"))
        flash("Invalid username or password", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
@login_required
@admin_required
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form.get("role", "reviewer")
        with SessionLocal() as session:
            exists = session.execute(
                sa.select(ReviewUser).where(ReviewUser.username == username)
            ).first()
            if exists:
                flash("Username already exists", "warning")
            else:
                user = ReviewUser(username=username, role=role)
                user.set_password(password)
                session.add(user)
                session.commit()
                flash("User created", "success")
                return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def manage_users():
    if request.method == "POST":
        uid = int(request.form["user_id"])
        new_role = request.form.get("role")
        new_password = request.form.get("new_password")
        with SessionLocal() as session:
            user = session.get(ReviewUser, uid)
            if user:
                if new_role:
                    user.role = new_role
                if new_password:
                    user.set_password(new_password)
                session.commit()
                flash("User updated", "success")
        return redirect(url_for("manage_users"))
    with SessionLocal() as session:
        users = session.execute(sa.select(ReviewUser)).scalars().all()
    return render_template("users.html", users=users)


@app.route("/users/delete", methods=["POST"])
@login_required
@admin_required
def delete_user():
    uid = request.form.get("user_id", type=int)
    if uid is None:
        flash("Invalid request", "danger")
        return redirect(url_for("manage_users"))
    if uid == current_user.id:
        flash("You cannot delete your own account", "danger")
        return redirect(url_for("manage_users"))
    with SessionLocal() as session:
        user = session.get(ReviewUser, uid)
        if not user:
            flash("User not found", "danger")
            return redirect(url_for("manage_users"))
        admin_count = session.execute(
            sa.select(sa.func.count()).select_from(ReviewUser).where(ReviewUser.role == "admin")
        ).scalar()
        if user.role == "admin" and admin_count <= 1:
            flash("Cannot delete the last admin", "danger")
            return redirect(url_for("manage_users"))
        session.delete(user)
        session.commit()
        flash("User deleted", "success")
    return redirect(url_for("manage_users"))


@app.route("/approval", methods=["GET"])
@login_required
@admin_required
def approval_dashboard():
    abort(404)


@app.route("/rejected", methods=["GET"])
@login_required
@admin_required
def rejected_clusters():
    return render_template("rejected.html")


@app.route("/manual-approved", methods=["GET"])
@login_required
@admin_required
def manual_approved_history():
    return render_template("manual_approved.html")


@app.route("/api/clusters/<cluster_id>/manual-approve", methods=["POST"])
@login_required
@admin_required
def manual_approve_cluster(cluster_id: str):
    try:
        cid = uuid.UUID(cluster_id)
    except ValueError:
        return jsonify({"error": "Invalid cluster ID"}), 400
    with db1_engine.begin() as conn:
        row = conn.execute(
            sa.select(story_clusters.c.filter_status)
            .where(story_clusters.c.cluster_id == cid)
        ).first()
        if not row:
            return jsonify({"error": "Cluster not found"}), 404
        if row.filter_status != "editorial_rejected":
            return jsonify({"error": f"Cannot approve cluster with status '{row.filter_status}'"}), 400
        conn.execute(
            sa.update(story_clusters)
            .where(story_clusters.c.cluster_id == cid)
            .values(filter_status="manual_approved")
        )
    return jsonify({"status": "ok", "cluster_id": cluster_id})


@app.route("/articles", methods=["GET"])
@login_required
def get_articles():
    """Articles Management dashboard – available to editors and admins."""
    return render_template("articles.html")


@app.route("/user-insights", methods=["GET"])
@login_required
@admin_required
def user_insights():
    """User insights dashboard."""
    return render_template("user_insights.html")


@app.route("/api/user-insights/new-users", methods=["GET"])
@login_required
@admin_required
def api_user_insights_new_users():
    """Return new device installs per day, based on first user_devices.createdAt per device_id."""
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    platform = request.args.get("platform")

    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) + timedelta(days=1) if end_date else None

    # First seen devices (for daily new users)
    first_seen_base = (
        sa.select(
            user_devices.c.device_id,
            user_devices.c.platform,
            sa.func.min(user_devices.c["createdAt"]).label("first_created_at"),
        )
        .where(
            user_devices.c.device_id.isnot(None),
            user_devices.c.device_id != "",
        )
    )

    if platform:
        first_seen_base = first_seen_base.where(user_devices.c.platform == platform)

    first_seen_base = first_seen_base.group_by(user_devices.c.device_id, user_devices.c.platform).subquery()

    filtered_first_seen = sa.select(first_seen_base)
    if start_dt:
        filtered_first_seen = filtered_first_seen.where(first_seen_base.c.first_created_at >= start_dt)
    if end_dt:
        filtered_first_seen = filtered_first_seen.where(first_seen_base.c.first_created_at < end_dt)
    filtered_first_seen = filtered_first_seen.subquery()

    # Cast to date in IST timezone (UTC+5:30)
    day_col = sa.cast(
        filtered_first_seen.c.first_created_at + timedelta(hours=5, minutes=30),
        sa.Date
    ).label("day")
    daily_stmt = (
        sa.select(
            day_col,
            sa.func.count().label("new_users"),
        )
        .select_from(filtered_first_seen)
        .group_by(day_col)
        .order_by(day_col)
    )
    total_stmt = sa.select(sa.func.count()).select_from(filtered_first_seen)
    all_time_stmt = sa.select(sa.func.count()).select_from(first_seen_base)

    # Platform breakdown (all-time, respecting current platform filter)
    platform_counts_stmt = (
        sa.select(
            first_seen_base.c.platform,
            sa.func.count().label("count"),
        )
        .group_by(first_seen_base.c.platform)
    )

    with db2_engine.connect() as conn:
        daily_rows = conn.execute(daily_stmt).all()
        total_new_users = conn.execute(total_stmt).scalar() or 0
        all_time_users = conn.execute(all_time_stmt).scalar() or 0
        platform_rows = conn.execute(platform_counts_stmt).all()

    daily = [
        {
            "date": row.day.isoformat() if hasattr(row.day, "isoformat") else str(row.day),
            "new_users": int(row.new_users or 0),
        }
        for row in daily_rows
    ]

    platform_counts = {
        row.platform: int(row.count or 0)
        for row in platform_rows
    }

    return jsonify(
        {
            "daily": daily,
            "total_new_users": int(total_new_users),
            "all_time_users": int(all_time_users),
            "platform_counts": platform_counts,
        }
    )


@app.route("/api/user-insights/dau", methods=["GET"])
@login_required
@admin_required
def api_user_insights_dau():
    """Return daily active users based on last_active_at with platform breakdown."""
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    platform = request.args.get("platform")

    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) + timedelta(days=1) if end_date else None
    # Get today's date in IST timezone
    ist = timezone(timedelta(hours=5, minutes=30))
    today = datetime.now(ist).date()

    # Base query for filtered activity (with platform for breakdown)
    base_stmt = sa.select(
        user_devices.c.user_id,
        user_devices.c.platform,
        sa.cast(
            user_devices.c.last_active_at + timedelta(hours=5, minutes=30),
            sa.Date
        ).label("day"),
    ).where(user_devices.c.last_active_at.isnot(None))

    if platform:
        base_stmt = base_stmt.where(user_devices.c.platform == platform)

    # Add date range filters
    if start_dt:
        base_stmt = base_stmt.where(user_devices.c.last_active_at >= start_dt)
    if end_dt:
        base_stmt = base_stmt.where(user_devices.c.last_active_at < end_dt)

    # Convert to subquery for grouping
    daily_stmt_with_filter = base_stmt.subquery()

    # Get daily DAU with platform breakdown
    daily_dau_stmt = (
        sa.select(
            daily_stmt_with_filter.c.day,
            daily_stmt_with_filter.c.platform,
            sa.func.count(sa.distinct(daily_stmt_with_filter.c.user_id)).label("dau"),
        )
        .group_by(daily_stmt_with_filter.c.day, daily_stmt_with_filter.c.platform)
        .order_by(daily_stmt_with_filter.c.day, daily_stmt_with_filter.c.platform)
    )

    # Summary metrics (no date range filter, but respects platform)
    summary_base = sa.select(
        user_devices.c.user_id,
        user_devices.c.platform,
        sa.cast(
            user_devices.c.last_active_at + timedelta(hours=5, minutes=30),
            sa.Date
        ).label("day"),
    ).where(user_devices.c.last_active_at.isnot(None))

    if platform:
        summary_base = summary_base.where(user_devices.c.platform == platform)

    summary_base = summary_base.subquery()

    today_dau_stmt = sa.select(
        sa.func.count(sa.distinct(summary_base.c.user_id))
    ).where(summary_base.c.day == today)

    wau_stmt = sa.select(
        sa.func.count(sa.distinct(summary_base.c.user_id))
    ).where(summary_base.c.day >= today - timedelta(days=6))

    mau_stmt = sa.select(
        sa.func.count(sa.distinct(summary_base.c.user_id))
    ).where(summary_base.c.day >= today - timedelta(days=29))

    with db2_engine.connect() as conn:
        daily_rows = conn.execute(daily_dau_stmt).all()
        today_dau = conn.execute(today_dau_stmt).scalar() or 0
        wau = conn.execute(wau_stmt).scalar() or 0
        mau = conn.execute(mau_stmt).scalar() or 0

    # Process daily data with platform breakdown
    daily_dict = {}
    for row in daily_rows:
        date_str = row.day.isoformat() if hasattr(row.day, "isoformat") else str(row.day)
        if date_str not in daily_dict:
            daily_dict[date_str] = {
                "date": date_str,
                "dau": 0,
                "ios": 0,
                "android": 0,
                "web": 0,
            }

        # Sum the total DAU
        daily_dict[date_str]["dau"] += int(row.dau or 0)

        # Add platform-specific counts
        if row.platform == "ios":
            daily_dict[date_str]["ios"] = int(row.dau or 0)
        elif row.platform == "android":
            daily_dict[date_str]["android"] = int(row.dau or 0)
        elif row.platform == "web":
            daily_dict[date_str]["web"] = int(row.dau or 0)

    daily = list(daily_dict.values())

    # Sort by date
    daily.sort(key=lambda x: x["date"])

    return jsonify(
        {
            "daily": daily,
            "today_dau": int(today_dau),
            "wau": int(wau),
            "mau": int(mau),
        }
    )


@app.route("/articles/<event_id>", methods=["GET"])
@login_required
def edit_article(event_id):
    view_only = getattr(current_user, "role", None) == "reviewer"
    return render_template("article_edit.html", event_id=event_id, view_only=view_only)


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        old = request.form.get("old_password")
        new = request.form.get("new_password")
        with SessionLocal() as session:
            user = session.get(ReviewUser, current_user.id)
            if user and user.check_password(old or ""):
                user.set_password(new or "")
                session.commit()
                flash("Password updated", "success")
                return redirect(url_for("index"))
            flash("Invalid current password", "danger")
    return render_template("change_password.html")



@app.route("/")
@login_required
def index():
    # Homepage: Articles Management.
    return redirect(url_for("get_articles"))


@app.route("/api/clusters")
@login_required
def clusters_data():
    page = int(request.args.get("page", 1))
    length = int(request.args.get("per_page", 10))
    search_value = request.args.get("search")
    sort_by = request.args.get("sort_by", "last_gen")
    order_dir = request.args.get("order", "desc")
    allowed_cols = {"cluster_id", "category", "title", "last_gen"}
    if sort_by not in allowed_cols:
        sort_by = "last_gen"
    if order_dir not in {"asc", "desc"}:
        order_dir = "desc"
    order = (sort_by, order_dir)

    raw_filters = {
        "start_date": request.args.get("start_date"),
        "end_date": request.args.get("end_date"),
        "reviewed": request.args.get("reviewed"),
        "category": request.args.get("category"),
        "approval_status": request.args.get("approval_status"),
    }
    parsed_filters = raw_filters.copy()
    for key in ("start_date", "end_date"):
        if parsed_filters[key]:
            parsed_filters[key] = datetime.fromisoformat(parsed_filters[key])
    with db1_engine.connect() as conn:
        rows, filtered, total = _get_clusters(
            conn,
            page=page,
            per_page=length,
            filters=parsed_filters,
            search=search_value or None,
            order=order,
        )
    data = []
    for r in rows:
        item = r.copy()
        item["cluster_url"] = url_for("cluster", cluster_id=r["cluster_id"])
        if current_user.is_admin():
            item["sync_url"] = url_for("sync_cluster", cluster_id=r["cluster_id"])
        data.append(item)
    return jsonify(
        {
            "page": page,
            "per_page": length,
            "total": total,
            "filtered": filtered,
            "data": data,
        }
    )


@app.route("/cluster/<cluster_id>", methods=["GET", "POST"])
@login_required
def cluster(cluster_id: str):
    cid = uuid.UUID(cluster_id)
    with db1_engine.begin() as conn:
        # Check if cluster exists
        cluster_info = conn.execute(
            sa.select(
                story_clusters.c.filter_status,
                story_clusters.c.rejection_reason,
                story_clusters.c.headline,
                story_clusters.c.created_at
            ).where(story_clusters.c.cluster_id == cid)
        ).first()
        
        if not cluster_info:
            abort(404)
        
        gen_id = conn.execute(
            sa.select(generations.c.id)
            .where(generations.c.cluster_id == cid, generations.c.artifact == "summary")
            .order_by(generations.c.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        
        # If no summary generation exists, show a simplified view for rejected clusters
        if not gen_id:
            filter_status = cluster_info.filter_status
            if filter_status in ('editorial_rejected', 'manual_rejected'):
                # Get any sources from the cluster (might exist from other artifacts)
                norm = lambda c: sa.func.rtrim(c, '/')
                source_rows_output = conn.execute(
                    sa.select(
                        sources.c.id,
                        sources.c.url,
                        articles.c.title,
                        articles.c.date_publish,
                    )
                    .outerjoin(articles, norm(sources.c.url) == norm(articles.c.url))
                    .join(generations, sources.c.generation_id == generations.c.id)
                    .where(generations.c.cluster_id == cid)
                    .distinct()
                ).mappings().all()
                source_rows = [dict(r) for r in source_rows_output]
                
                # If no sources from generations, try to get articles from cluster members
                if not source_rows:
                    from necls_backend.db import story_members
                    article_rows = conn.execute(
                        sa.select(
                            articles.c.url,
                            articles.c.title,
                            articles.c.date_publish,
                        )
                        .join(story_members, articles.c.id == story_members.c.article_id)
                        .where(story_members.c.cluster_id == cid)
                        .distinct()
                    ).mappings().all()
                    source_rows = [
                        {
                            "id": None,
                            "url": r["url"],
                            "title": r["title"],
                            "date_publish": r["date_publish"]
                        }
                        for r in article_rows
                    ]
                
                return render_template(
                    "cluster.html",
                    cluster_id=cluster_id,
                    summaries=[],
                    sources=source_rows,
                    extra={"rejection_reason": cluster_info.rejection_reason, "filter_status": filter_status},
                    artifacts={},
                    is_rejected_no_summary=True,
                    cluster_headline=cluster_info.headline,
                    cluster_created_at=cluster_info.created_at
                )
            else:
                abort(404)
        if request.method == "POST":
            if not current_user.can_save():
                abort(403)
            form_type = request.form.get("form_type")
            if form_type == "summary":
                lang = request.form.get("language_id", "en")
                headline = request.form.get("headline")
                mini_headline = request.form.get("mini_headline")
                mini_summary = request.form.get("mini_summary")
                bullets = request.form.get("bullets") or ""
                bullets_list = [b.strip() for b in bullets.splitlines() if b.strip()]
                audio_text = request.form.get("audio_text")
                quotes_raw = request.form.get("quotes") or "[]"
                facts_raw = request.form.get("facts") or "[]"
                try:
                    quotes = json.loads(quotes_raw)
                except Exception:
                    quotes = []
                try:
                    facts = json.loads(facts_raw)
                except Exception:
                    facts = []
                conn.execute(
                    sa.update(summary_localized)
                    .where(
                        summary_localized.c.generation_id == gen_id,
                        summary_localized.c.language_id == lang,
                    )
                    .values(
                        headline=headline,
                        mini_headline=mini_headline,
                        mini_summary=mini_summary,
                        bullets=bullets_list,
                        audio_text=audio_text,
                        quotes=quotes,
                        facts=facts,
                    )
                )
                if lang == "en":
                    conn.execute(
                        pg_insert(ReviewStatus.__table__)
                        .values(cluster_id=cid, reviewed_at=sa.func.now(), reviewer_id=current_user.id)
                        .on_conflict_do_update(
                            index_elements=[ReviewStatus.__table__.c.cluster_id],
                            set_={"reviewed_at": sa.func.now(), "reviewer_id": current_user.id},
                        )
                    )
                flash("Summary updated", "success")
            elif form_type == "slide":
                lang = request.form.get("language_id")
                slide_id = uuid.UUID(request.form.get("slide_id"))
                heading = request.form.get("heading")
                content_type = request.form.get("content_type") or "raw"
                content_raw = request.form.get("content") or ""
                try:
                    content = json.loads(content_raw) if content_raw else None
                except Exception:
                    flash("Invalid JSON; content not updated", "danger")
                    content = None
                values = {"heading": heading, "content_type": content_type}
                if content is not None:
                    values["content"] = content
                conn.execute(
                    sa.update(slide_localized)
                    .where(
                        slide_localized.c.slide_id == slide_id,
                        slide_localized.c.language_id == lang,
                    )
                    .values(**values)
                )
                flash("Slide updated", "success")
            elif form_type == "source":
                src_id = uuid.UUID(request.form.get("source_id"))
                title = request.form.get("title")
                url_val = request.form.get("url")
                ad_str = request.form.get("article_date")
                article_date = datetime.fromisoformat(ad_str) if ad_str else None
                conn.execute(
                    sa.update(sources)
                    .where(sources.c.id == src_id)
                    .values(title=title, url=url_val, article_date=article_date)
                )
                flash("Source updated", "success")

        summaries = conn.execute(
            sa.select(
                summary_localized.c.language_id,
                summary_localized.c.mini_headline,
                summary_localized.c.mini_summary,
                summary_localized.c.headline,
                summary_localized.c.bullets,
                summary_localized.c.audio_text,
                summary_localized.c.audio_s3_url,
                summary_localized.c.quotes,
                summary_localized.c.facts,
            ).where(summary_localized.c.generation_id == gen_id)
        ).mappings().all()
        summaries = [dict(s) for s in summaries]
        for s in summaries:
            # Extract description from bullets if mini_summary is None
            if not s.get("mini_summary") and s.get("bullets"):
                bullets = s.get("bullets") or []
                if bullets and len(bullets) > 0:
                    s["mini_summary"] = bullets[0]  # For display purposes
            if s.get("audio_s3_url"):
                s["audio_url"] = _presign_s3_url('s3://' + s.get("audio_s3_url"))
        gen_extra = conn.execute(
            sa.select(generations.c.extra).where(generations.c.id == gen_id)
        ).scalar_one_or_none()
        norm = lambda c: sa.func.rtrim(c, '/')
        source_rows_output = conn.execute(
            sa.select(
                sources.c.id,
                sources.c.url,
                articles.c.title,
                articles.c.date_publish,
            ).join(articles, norm(sources.c.url) == norm(articles.c.url)).where(sources.c.generation_id == gen_id)
        ).mappings().all()
        source_rows = [dict(r) for r in source_rows_output]

        artifacts: dict[str, dict] = {}
        for art in ["looking_ahead", "story_so_far"]:
            aid = conn.execute(
                sa.select(generations.c.id)
                .where(generations.c.cluster_id == cid, generations.c.artifact == art)
                .order_by(generations.c.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if aid:
                source_rows_aid_output = conn.execute(
                    sa.select(
                        sources.c.id,
                        sources.c.url,
                        articles.c.title,
                        articles.c.date_publish,
                    ).join(articles, norm(sources.c.url) == norm(articles.c.url)).where(sources.c.generation_id == aid)
                ).mappings().all()
                source_rows_aid = [dict(r) for r in source_rows_aid_output]

                slide_rows = conn.execute(
                    sa.select(
                        slides.c.id,
                        slides.c.type,
                        slides.c.sequence,
                    )
                    .where(slides.c.generation_id == aid)
                    .order_by(slides.c.sequence)
                ).mappings().all()
                slide_rows = [dict(r) for r in slide_rows]
                slide_ids = [r["id"] for r in slide_rows]
                loc_rows = []
                if slide_ids:
                    loc_rows = conn.execute(
                        sa.select(
                            slide_localized.c.slide_id,
                            slide_localized.c.language_id,
                            slide_localized.c.heading,
                            slide_localized.c.content_type,
                            slide_localized.c.content,
                        ).where(slide_localized.c.slide_id.in_(slide_ids))
                    ).mappings().all()
                    loc_rows = [dict(r) for r in loc_rows]
                artifacts[art] = {"slides": slide_rows, "localized": loc_rows, "sources":source_rows_aid}

    return render_template(
        "cluster.html",
        cluster_id=cluster_id,
        summaries=summaries,
        sources=source_rows,
        extra=gen_extra or {},
        artifacts=artifacts,
        is_rejected_no_summary=False,
        cluster_headline=None,
        cluster_created_at=None
    )


@app.post("/sync/<cluster_id>")
@login_required
@admin_required
def sync_cluster(cluster_id: str):
    try:
        export_cluster_to_db2(cluster_id, db1_engine, db2_engine)
        flash("Synced to app DB", "success")
    except Exception as exc:  # pragma: no cover - runtime failure
        flash(f"Sync failed: {exc}", "danger")
    return redirect(url_for("index"))


@app.route("/api/temporal-news", methods=["POST"])
@login_required
def get_temporal_news():
    """Get news articles based on temporal queries."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON body required'}), 400

        user_query = data.get('query', '').strip()
        if not user_query:
            return jsonify({'error': 'Query parameter is required'}), 400

        # Initialize retriever with existing engines
        retriever = TemporalNewsRetriever(db1_engine, db2_engine)

        # Process the temporal query
        result = retriever.process_temporal_query(user_query)

        if not result['success']:
            return jsonify({'error': result['error']}), 400

        return jsonify(result)

    except Exception as e:
        print(f"Temporal query error: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@app.route("/api/test-temporal-query", methods=["POST"])
@login_required
def test_temporal_query():
    """Test temporal query parsing without hitting database."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON body required'}), 400

        user_query = data.get('query', '').strip()
        if not user_query:
            return jsonify({'error': 'Query parameter is required'}), 400

        # Parse temporal expression
        date_range = TemporalQueryParser.parse_temporal_query(user_query)
        article_count = TemporalQueryParser.extract_article_count(user_query)
        is_temporal = TemporalQueryParser.is_temporal_query(user_query)

        result = {
            'query': user_query,
            'is_temporal_query': is_temporal,
            'parsed_date_range': {
                'start_date': date_range[0].isoformat() if date_range else None,
                'end_date': date_range[1].isoformat() if date_range else None,
            } if date_range else None,
            'article_count': article_count
        }

        return jsonify(result)

    except Exception as e:
        print(f"Temporal test error: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@app.route("/api/approve/<cluster_id>", methods=["POST"])
@login_required
@admin_required
def approve_cluster(cluster_id):
    # Approval dashboard removed
    abort(404)


@app.route("/api/reject/<cluster_id>", methods=["POST"])
@login_required
@admin_required
def reject_cluster(cluster_id):
    # Approval dashboard removed
    abort(404)


@app.route("/api/auto-approve", methods=["POST"])
@login_required
@admin_required
def auto_approve_clusters():
    # Approval dashboard removed
    abort(404)


@app.route("/api/rerun-pipeline/<cluster_id>", methods=["POST"])
@login_required
@admin_required
def rerun_pipeline(cluster_id):
    # Re-run pipeline feature removed
    abort(404)


@app.route("/api/articles", methods=["GET"])
@login_required
def api_get_articles():
    """Get synced articles with filtering"""
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 25))
        search = request.args.get("search", "").strip()
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        category_filter = request.args.get("category")
        tag_name_filter = request.args.get("tag_name", "").strip()
        tag_type_filter = request.args.get("tag_type", "").strip()

        with db2_engine.begin() as conn:
            # Build query for events with localized data and tags
            led = localized_event_data.alias("led")
            evt = event.alias("evt")
            est = event_seo_tag.alias("est")
            st = seo_tag.alias("st")

            # Get events with categories (tags of type 'Category')
            category_subquery = (
                sa.select(
                    est.c.event_id,
                    sa.func.array_agg(st.c.name).label("categories")
                )
                .select_from(est)
                .join(st, est.c.seo_tag_id == st.c.id)
                # seo_tag.type is an enum in DB2; values are Title Case (see necls_backend/app_db.py)
                .where(st.c.type == "Category")
                .group_by(est.c.event_id)
                .subquery()
            )

            # Get events with all tags (cast type to text so values like 'topic' don't raise enum error)
            tags_subquery = (
                sa.select(
                    est.c.event_id,
                    sa.func.json_agg(
                        sa.func.json_build_object(
                            "name", st.c.name,
                            "type", sa.cast(st.c.type, sa.Text),
                            "weight", est.c.weight
                        )
                    ).label("tags")
                )
                .select_from(est)
                .join(st, est.c.seo_tag_id == st.c.id)
                .group_by(est.c.event_id)
                .subquery()
            )

            # Get FAQ counts for each event
            faq_subquery = (
                sa.select(
                    event_faq.c.event_id,
                    sa.func.count(event_faq.c.id).label("faq_count")
                )
                .group_by(event_faq.c.event_id)
                .subquery()
            )

            base = (
                sa.select(
                    evt.c.id.label("event_id"),
                    evt.c.time_stamp,
                    evt.c.created_date,
                    evt.c.article_type,
                    evt.c.image,
                    led.c.language_id,
                    led.c.title,
                    led.c.description,
                    led.c.content,
                    led.c.audio,
                    led.c.audio_full_story,
                    category_subquery.c.categories.label("categories"),
                    tags_subquery.c.tags.label("tags"),
                    faq_subquery.c.faq_count.label("faq_count"),
                )
                .select_from(evt)
                .outerjoin(led, led.c.event_id == evt.c.id)
                .outerjoin(category_subquery, category_subquery.c.event_id == evt.c.id)
                .outerjoin(tags_subquery, tags_subquery.c.event_id == evt.c.id)
                .outerjoin(faq_subquery, faq_subquery.c.event_id == evt.c.id)
                .where(led.c.language_id == "en")  # Default to English
            )

            # Apply filters
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date)
                    base = base.where(evt.c.time_stamp >= start_dt)
                except ValueError:
                    pass  # Invalid date format, skip filter
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date)
                    base = base.where(evt.c.time_stamp <= end_dt)
                except ValueError:
                    pass  # Invalid date format, skip filter
            if category_filter:
                # Filter by category names in the array
                base = base.where(
                    sa.func.array_to_string(category_subquery.c.categories, ',')
                    .ilike(f"%{category_filter}%")
                )
            if search:
                base = base.where(
                    sa.or_(
                        led.c.title.ilike(f"%{search}%"),
                        led.c.description.ilike(f"%{search}%")
                    )
                )
            if tag_name_filter or tag_type_filter:
                tag_sq = (
                    sa.select(event_seo_tag.c.event_id)
                    .select_from(event_seo_tag)
                    .join(seo_tag, event_seo_tag.c.seo_tag_id == seo_tag.c.id)
                )
                if tag_name_filter:
                    tag_sq = tag_sq.where(seo_tag.c.name.ilike(f"%{tag_name_filter}%"))
                if tag_type_filter:
                    tag_sq = tag_sq.where(sa.cast(seo_tag.c.type, sa.Text) == tag_type_filter)
                base = base.where(evt.c.id.in_(tag_sq))

            # Get total count
            total_stmt = sa.select(sa.func.count()).select_from(base.subquery())
            total = conn.execute(total_stmt).scalar() or 0

            # Get paginated results
            rows = conn.execute(
                base.order_by(evt.c.time_stamp.desc())
                .limit(per_page)
                .offset((page - 1) * per_page)
            ).mappings().all()

            # Get all event IDs from the results
            event_ids = [row['event_id'] for row in rows if row.get('event_id')]
            
            # Fetch all localized audio data for these events in one query
            audio_data_map = {}
            if event_ids:
                all_audio_data = conn.execute(
                    sa.select(
                        localized_event_data.c.event_id,
                        localized_event_data.c.language_id,
                        localized_event_data.c.audio,
                        localized_event_data.c.audio_full_story
                    )
                    .where(localized_event_data.c.event_id.in_(event_ids))
                ).mappings().all()
                
                # Group by event_id
                for audio_row in all_audio_data:
                    eid = audio_row['event_id']
                    if eid not in audio_data_map:
                        audio_data_map[eid] = []
                    audio_data_map[eid].append(dict(audio_row))

            # Format the results
            formatted_data = []
            for row in rows:
                row_dict = dict(row)
                # Format created_date in IST (only date, no time)
                if row_dict.get('created_date'):
                    from datetime import datetime
                    from pytz import timezone
                    ist = timezone('Asia/Kolkata')
                    created_date_ist = row_dict['created_date'].astimezone(ist)
                    row_dict['formatted_date'] = created_date_ist.strftime('%Y-%m-%d')
                else:
                    row_dict['formatted_date'] = 'N/A'

                # Format categories
                categories = row_dict.get('categories', [])
                if categories and len(categories) > 0:
                    row_dict['category_name'] = ', '.join(categories)
                else:
                    row_dict['category_name'] = 'Uncategorized'

                # Format tags for display
                tags = row_dict.get('tags', [])
                if tags:
                    row_dict['formatted_tags'] = tags
                else:
                    row_dict['formatted_tags'] = []

                # Format description (extract from content list if description is empty)
                description = row_dict.get('description', '')

                # If no description, try to get it from content[0] (it's stored as a list)
                if not description:
                    content = row_dict.get('content')
                    if content and isinstance(content, list) and len(content) > 0:
                        description = str(content[0])

                if description and len(description) > 200:
                    row_dict['short_description'] = description[:200] + '...'
                else:
                    row_dict['short_description'] = description or 'No description available'

                # Format content availability
                content = row_dict.get('content')
                row_dict['has_content'] = bool(content and str(content).strip())

                # Format FAQ availability
                faq_count = row_dict.get('faq_count', 0) or 0
                row_dict['has_faqs'] = faq_count > 0
                row_dict['faq_count'] = faq_count

                # Format audio links - get all languages from pre-fetched data
                audio_links = []
                event_id = row_dict.get('event_id')
                
                # Get audio data for this event from the map
                event_audio_data = audio_data_map.get(event_id, [])
                
                # Add audio links for all languages
                for loc_data in event_audio_data:
                    lang_id = loc_data.get('language_id')
                    if not lang_id:
                        continue
                    lang_name = lang_id.upper()
                    
                    if loc_data.get('audio') and loc_data['audio'].strip():
                        audio_path = loc_data['audio']
                        audio_links.append({
                            'label': f'{lang_name} Gist Audio',
                            'url': _presign_s3_url('s3://' + audio_path) if audio_path.startswith('necls-backend') else audio_path,
                            'language': lang_id,
                            'type': 'gist'
                        })
                    
                    if loc_data.get('audio_full_story') and loc_data['audio_full_story'].strip():
                        audio_path = loc_data['audio_full_story']
                        audio_links.append({
                            'label': f'{lang_name} Full Story Audio',
                            'url': _presign_s3_url('s3://' + audio_path) if audio_path.startswith('necls-backend') else audio_path,
                            'language': lang_id,
                            'type': 'full'
                        })
                
                row_dict['audio_links'] = audio_links

                formatted_data.append(row_dict)

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total": total,
            "data": formatted_data
        })

    except Exception as e:
        import traceback
        print(f"Get articles error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/articles/<event_id>", methods=["GET"])
@login_required
def api_get_article(event_id):
    """Get detailed article data"""
    try:
        eid = uuid.UUID(event_id)

        with db2_engine.begin() as conn:
            # Get event data
            event_data = conn.execute(
                sa.select(event).where(event.c.id == eid)
            ).mappings().first()

            if not event_data:
                return jsonify({"success": False, "error": "Article not found"}), 404

            # Get localized data for all languages
            localized_data_raw = conn.execute(
                sa.select(localized_event_data)
                .where(localized_event_data.c.event_id == eid)
            ).mappings().all()

            # Process localized data and add audio links
            localized_data = []
            for row in localized_data_raw:
                row_dict = dict(row)
                audio_links = []

                # Add audio links based on language
                if row_dict.get('audio') and row_dict['audio'].strip():
                    audio_links.append({
                        'label': f"{row_dict['language_id'].upper()} Gist Audio",
                        'url': _presign_s3_url('s3://' + row_dict['audio']) if row_dict['audio'].startswith('necls-backend') else row_dict['audio'],
                        'language': row_dict['language_id'],
                        'type': 'gist'
                    })

                if row_dict.get('audio_full_story') and row_dict['audio_full_story'].strip():
                    audio_links.append({
                        'label': f"{row_dict['language_id'].upper()} Full Story Audio",
                        'url': _presign_s3_url('s3://' + row_dict['audio_full_story']) if row_dict['audio_full_story'].startswith('necls-backend') else row_dict['audio_full_story'],
                        'language': row_dict['language_id'],
                        'type': 'full'
                    })

                row_dict['audio_links'] = audio_links
                localized_data.append(row_dict)

            # Get sources
            sources_data = conn.execute(
                sa.select(source)
                .where(source.c.event_id == eid)
            ).mappings().all()

            # Get analysis data
            analysis_data = conn.execute(
                sa.select(
                    event_analysis.c.id,
                    event_analysis.c.sequence,
                    localized_event_analysis.c.language_id,
                    localized_event_analysis.c.content,
                    localized_event_analysis.c.content_type
                )
                .select_from(event_analysis)
                .outerjoin(
                    localized_event_analysis,
                    localized_event_analysis.c.event_analysis_id == event_analysis.c.id
                )
                .where(event_analysis.c.event_id == eid)
                .order_by(event_analysis.c.sequence)
            ).mappings().all()

            # Get story so far / concepts decoded (event_so_far + localized_event_so_far)
            so_far_data = conn.execute(
                sa.select(
                    event_so_far.c.id,
                    event_so_far.c.sequence,
                    localized_event_so_far.c.language_id,
                    localized_event_so_far.c.content,
                    localized_event_so_far.c.content_type,
                )
                .select_from(event_so_far)
                .outerjoin(
                    localized_event_so_far,
                    localized_event_so_far.c.event_so_far_id == event_so_far.c.id
                )
                .where(event_so_far.c.event_id == eid)
                .order_by(event_so_far.c.sequence)
            ).mappings().all()
            so_far_payload = [
                {
                    "id": str(r["id"]),
                    "sequence": int(r["sequence"]) if r.get("sequence") is not None else 0,
                    "language_id": r.get("language_id") or "",
                    "content": r.get("content"),
                    "content_type": r.get("content_type") or "",
                }
                for r in so_far_data
                if (r.get("language_id") or "").strip()
            ]

            # Get tags: one row per tag from event_seo_tag only (event-level link = single source of truth)
            # Cast type to text so DB values like 'topic' (not in enum_seo_tag_type) don't raise
            linked_st = seo_tag.alias("linked_tag")
            tags_data = conn.execute(
                sa.select(
                    seo_tag.c.id.label("tag_id"),
                    seo_tag.c.name,
                    sa.cast(seo_tag.c.type, sa.Text).label("type"),
                    event_seo_tag.c.weight,
                    event_seo_tag.c.role,
                    event_seo_tag.c.linked_to_tag_id,
                    linked_st.c.name.label("linked_to_tag_name"),
                )
                .select_from(event_seo_tag)
                .join(seo_tag, event_seo_tag.c.seo_tag_id == seo_tag.c.id)
                .outerjoin(linked_st, event_seo_tag.c.linked_to_tag_id == linked_st.c.id)
                .where(event_seo_tag.c.event_id == eid)
                .order_by(sa.cast(seo_tag.c.type, sa.Text), seo_tag.c.name)
            ).mappings().all()

            tags_payload = []
            for r in tags_data:
                raw_role = r.get("role")
                role = "core" if (raw_role and str(raw_role).lower() == "core") else "contextual"
                linked_to_tag = (r.get("linked_to_tag_name") or "").strip() if r.get("linked_to_tag_id") else ""
                relations = [{"linked_to_tag_name": linked_to_tag}] if linked_to_tag else []
                tags_payload.append({
                    "tag_id": str(r["tag_id"]),
                    "name": r["name"],
                    "type": r["type"],
                    "weight": r["weight"],
                    "role": role,
                    "linked_to_tag": linked_to_tag,
                    "relations": relations,
                })

            # Get FAQs
            faqs_data = conn.execute(
                sa.select(event_faq)
                .where(event_faq.c.event_id == eid)
                .order_by(event_faq.c.sequence, event_faq.c.id)
            ).mappings().all()
            faqs_payload = [
                {
                    "id": str(r["id"]),
                    "language_id": r.get("language_id") or "",
                    "question": r.get("question") or "",
                    "answer": r.get("answer") or "",
                    "sequence": int(r["sequence"]) if r.get("sequence") is not None else 0,
                }
                for r in faqs_data
            ]

            img_path = (dict(event_data).get("image") or "").strip()
            if img_path.startswith("necls-backend"):
                image_preview_url = _presign_s3_url("s3://" + img_path)
            elif img_path.startswith(("http://", "https://")):
                image_preview_url = img_path
            else:
                image_preview_url = None

            return jsonify({
                "event": dict(event_data),
                "image_preview_url": image_preview_url,
                "localized_data": [dict(row) for row in localized_data],
                "sources": [dict(row) for row in sources_data],
                "analysis": [dict(row) for row in analysis_data],
                "so_far": so_far_payload,
                "faqs": faqs_payload,
                "tags": tags_payload,
            })

    except Exception as e:
        print(f"Get article error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def _get_article_title_from_db2(event_id: uuid.UUID) -> str:
    """Return article title from db2 (English or first localized row) for display in pending list."""
    with db2_engine.connect() as conn:
        row = conn.execute(
            sa.select(localized_event_data.c.title)
            .where(localized_event_data.c.event_id == event_id)
            .order_by(sa.case((localized_event_data.c.language_id == "en", 0), else_=1))
            .limit(1)
        ).first()
        return (row[0] or "") if row else ""


def _get_current_article_data_from_db2(event_id: uuid.UUID) -> dict:
    """Return current article data from db2 in same shape as payload for diffing: localized_data, sources, analysis."""
    with db2_engine.connect() as conn:
        eid = event_id
        loc_rows = conn.execute(
            sa.select(localized_event_data).where(localized_event_data.c.event_id == eid)
        ).mappings().all()
        localized_data = [
            {
                "language_id": r["language_id"],
                "title": r.get("title") or "",
                "content": r.get("content") or "",
                "audio": r.get("audio") or "",
                "audio_full_story": r.get("audio_full_story") or "",
            }
            for r in loc_rows
        ]
        src_rows = conn.execute(sa.select(source).where(source.c.event_id == eid)).mappings().all()
        sources = [{"source_url": r.get("source_url") or "", "title": r.get("title") or ""} for r in src_rows]
        ana_rows = conn.execute(
            sa.select(
                event_analysis.c.id,
                localized_event_analysis.c.language_id,
                localized_event_analysis.c.content,
                localized_event_analysis.c.content_type,
            )
            .select_from(event_analysis)
            .outerjoin(
                localized_event_analysis,
                localized_event_analysis.c.event_analysis_id == event_analysis.c.id,
            )
            .where(event_analysis.c.event_id == eid)
        ).mappings().all()
        analysis = [
            {
                "id": str(r["id"]),
                "language_id": r.get("language_id") or "",
                "content": r.get("content") or "",
                "content_type": r.get("content_type") or "",
            }
            for r in ana_rows
        ]
        so_far_rows = conn.execute(
            sa.select(
                event_so_far.c.id,
                event_so_far.c.sequence,
                localized_event_so_far.c.language_id,
                localized_event_so_far.c.content,
                localized_event_so_far.c.content_type,
            )
            .select_from(event_so_far)
            .outerjoin(
                localized_event_so_far,
                localized_event_so_far.c.event_so_far_id == event_so_far.c.id,
            )
            .where(event_so_far.c.event_id == eid)
        ).mappings().all()
        so_far = [
            {
                "id": str(r["id"]),
                "sequence": int(r["sequence"]) if r.get("sequence") is not None else 0,
                "language_id": r.get("language_id") or "",
                "content": r.get("content") or "",
                "content_type": r.get("content_type") or "",
            }
            for r in so_far_rows
        ]
        faq_rows = conn.execute(
            sa.select(event_faq).where(event_faq.c.event_id == eid).order_by(event_faq.c.sequence, event_faq.c.id)
        ).mappings().all()
        faqs = [
            {
                "id": str(r["id"]),
                "language_id": r.get("language_id") or "",
                "question": r.get("question") or "",
                "answer": r.get("answer") or "",
                "sequence": int(r["sequence"]) if r.get("sequence") is not None else 0,
            }
            for r in faq_rows
        ]
        evt_row = conn.execute(
            sa.select(event.c.image, event.c.image_source_url).where(event.c.id == eid)
        ).first()
        return {
            "localized_data": localized_data,
            "sources": sources,
            "analysis": analysis,
            "so_far": so_far,
            "faqs": faqs,
            "image": (evt_row.image or "") if evt_row else "",
            "image_source_url": (evt_row.image_source_url or "") if evt_row else "",
        }


def _diff_article(current: dict, payload: dict) -> dict:
    """Compare current article data with payload. Return only what changed for display."""
    out = {
        "localized_changes": [],
        "sources_added": [],
        "sources_removed": [],
        "analysis_changes": [],
        "so_far_changes": [],
        "faqs_added": [],
        "faqs_removed": [],
        "faqs_changes": [],
        "image_changes": {},
    }
    # Compare image fields
    for field in ("image", "image_source_url"):
        pv = payload.get(field)
        if pv is None:
            pv = ""
        cv = current.get(field) or ""
        if pv != cv:
            out["image_changes"][field] = {"old": cv, "new": pv}
    cur_loc = {r["language_id"]: r for r in (current.get("localized_data") or [])}
    pay_loc = payload.get("localized_data") or []
    for pl in pay_loc:
        lang = pl.get("language_id") or ""
        cl = cur_loc.get(lang)
        changes = {}
        for field in ("title", "content", "audio", "audio_full_story"):
            pv = pl.get(field)
            cv = (cl.get(field) if cl else None) if cl else None
            if cv is None:
                cv = ""
            if pv != cv:
                changes[field] = {"old": cv, "new": pv}
        if changes:
            out["localized_changes"].append({"language_id": lang, "changes": changes})

    cur_src = {(s.get("source_url") or "").strip(): (s.get("title") or "") for s in (current.get("sources") or [])}
    pay_src = payload.get("sources") or []
    pay_src_set = set()
    for s in pay_src:
        url = (s.get("source_url") or "").strip()
        pay_src_set.add(url)
        if url not in cur_src:
            out["sources_added"].append({"source_url": url, "title": (s.get("title") or "").strip()})
    for url, title in cur_src.items():
        if url and url not in pay_src_set:
            out["sources_removed"].append({"source_url": url, "title": title})

    cur_ana = {(r.get("id"), r.get("language_id")): r for r in (current.get("analysis") or [])}
    pay_ana = payload.get("analysis") or []
    for pa in pay_ana:
        key = (str(pa.get("id") or ""), pa.get("language_id") or "")
        ca = cur_ana.get(key)
        changes = {}
        for field in ("content", "content_type"):
            pv = pa.get(field)
            cv = (ca.get(field) if ca else None) if ca else ""
            if cv is None:
                cv = ""
            if pv != cv:
                changes[field] = {"old": cv, "new": pv}
        if changes:
            out["analysis_changes"].append({"id": key[0], "language_id": key[1], "changes": changes})

    cur_sf = {(r.get("id"), r.get("language_id")): r for r in (current.get("so_far") or [])}
    pay_sf = payload.get("so_far") or []
    for ps in pay_sf:
        key = (str(ps.get("id") or ""), ps.get("language_id") or "")
        cs = cur_sf.get(key)
        changes = {}
        for field in ("content", "content_type"):
            pv = ps.get(field)
            cv = (cs.get(field) if cs else None) if cs else ""
            if cv is None:
                cv = ""
            if pv != cv:
                changes[field] = {"old": cv, "new": pv}
        if changes:
            out["so_far_changes"].append({"id": key[0], "language_id": key[1], "changes": changes})

    cur_faqs = {(r.get("language_id") or "", (r.get("question") or "").strip()): r for r in (current.get("faqs") or [])}
    pay_faqs = payload.get("faqs") or []
    pay_faq_keys = set()
    for pf in pay_faqs:
        key = (pf.get("language_id") or "", (pf.get("question") or "").strip())
        if not key[1]:
            continue
        pay_faq_keys.add(key)
        cf = cur_faqs.get(key)
        if not cf:
            out["faqs_added"].append({"language_id": key[0], "question": key[1], "answer": pf.get("answer") or ""})
        else:
            old_ans = cf.get("answer") or ""
            new_ans = pf.get("answer") or ""
            if old_ans != new_ans:
                out["faqs_changes"].append({"language_id": key[0], "question": key[1], "old_answer": old_ans, "new_answer": new_ans})
    for k, cf in cur_faqs.items():
        if k[1] and k not in pay_faq_keys:
            out["faqs_removed"].append({"language_id": k[0], "question": k[1], "answer": cf.get("answer") or ""})

    return out


def _format_article_diff_summary(diff: dict) -> str:
    """Build short summary of article diff for pending list."""
    parts = []
    if diff.get("localized_changes"):
        for loc in diff["localized_changes"]:
            lang = loc.get("language_id") or "?"
            fields = list((loc.get("changes") or {}).keys())
            parts.append(f"{lang}: {', '.join(fields)}")
    if diff.get("sources_added"):
        parts.append(f"{len(diff['sources_added'])} source(s) added")
    if diff.get("sources_removed"):
        parts.append(f"{len(diff['sources_removed'])} source(s) removed")
    if diff.get("analysis_changes"):
        parts.append(f"{len(diff['analysis_changes'])} analysis block(s) changed")
    if diff.get("so_far_changes"):
        parts.append(f"{len(diff['so_far_changes'])} story so far block(s) changed")
    if diff.get("faqs_added"):
        parts.append(f"{len(diff['faqs_added'])} FAQ(s) added")
    if diff.get("faqs_removed"):
        parts.append(f"{len(diff['faqs_removed'])} FAQ(s) removed")
    if diff.get("faqs_changes"):
        parts.append(f"{len(diff['faqs_changes'])} FAQ(s) changed")
    return "; ".join(parts) if parts else "Article update"


def _build_article_update_summary(data: dict, current: dict | None = None) -> str:
    """Build summary: if current is provided, summarize only the diff; otherwise fallback to generic."""
    if current is not None:
        try:
            diff = _diff_article(current, data)
            return _format_article_diff_summary(diff)
        except Exception:
            pass
    parts = []
    localized = data.get("localized_data") or []
    if localized:
        langs = [str(ld.get("language_id", "")) for ld in localized]
        lang_str = ", ".join(langs) if langs else "?"
        parts.append(f"Article content: {len(localized)} language(s) ({lang_str})")
    if data.get("sources"):
        n = len(data["sources"])
        parts.append(f"{n} source(s)")
    if data.get("analysis"):
        n = len(data["analysis"])
        parts.append(f"{n} analysis block(s)")
    if data.get("so_far"):
        n = len(data["so_far"])
        parts.append(f"{n} story so far block(s)")
    if data.get("faqs"):
        n = len(data["faqs"])
        parts.append(f"{n} FAQ(s)")
    return "; ".join(parts) if parts else "Article update"


def _apply_article_update(conn, event_id: uuid.UUID, payload: dict) -> None:
    """Apply article update to db2 (localized_data, sources, analysis). Caller holds db2 connection."""
    eid = event_id
    data = payload

    # Update image fields on the event table
    evt_updates = {}
    if "image" in data:
        evt_updates["image"] = data["image"] or None
    if "image_source_url" in data:
        evt_updates["image_source_url"] = data["image_source_url"] or None
    if evt_updates:
        conn.execute(sa.update(event).where(event.c.id == eid).values(**evt_updates))

    if "localized_data" in data:
        for lang_data in data["localized_data"]:
            conn.execute(
                sa.update(localized_event_data)
                .where(
                    sa.and_(
                        localized_event_data.c.event_id == eid,
                        localized_event_data.c.language_id == lang_data["language_id"]
                    )
                )
                .values(
                    title=lang_data.get("title"),
                    content=lang_data.get("content"),
                    audio=lang_data.get("audio"),
                    audio_full_story=lang_data.get("audio_full_story"),
                    quotes=lang_data.get("quotes")
                )
            )

    if "sources" in data:
        conn.execute(sa.delete(source).where(source.c.event_id == eid))
        for src_data in data["sources"]:
            conn.execute(
                sa.insert(source).values(
                    id=uuid.uuid4(),
                    event_id=eid,
                    source_url=src_data["source_url"],
                    title=src_data.get("title")
                )
            )

    if "analysis" in data:
        for analysis_item in data["analysis"]:
            analysis_id = uuid.UUID(analysis_item["id"])
            language_id = analysis_item["language_id"]
            content = analysis_item.get("content")
            content_type = analysis_item.get("content_type")
            ins = pg_insert(localized_event_analysis).values(
                id=uuid.uuid4(),
                event_analysis_id=analysis_id,
                language_id=language_id,
                content=content,
                content_type=content_type
            )
            conn.execute(
                ins.on_conflict_do_update(
                    index_elements=[localized_event_analysis.c.event_analysis_id, localized_event_analysis.c.language_id],
                    set_={
                        "content": ins.excluded.content,
                        "content_type": ins.excluded.content_type
                    }
                )
            )

    if "so_far" in data:
        for so_far_item in data["so_far"]:
            so_far_id = uuid.UUID(so_far_item["id"])
            language_id = so_far_item.get("language_id") or ""
            if not language_id:
                continue
            content = so_far_item.get("content")
            content_type = so_far_item.get("content_type")
            ins = pg_insert(localized_event_so_far).values(
                id=uuid.uuid4(),
                event_so_far_id=so_far_id,
                language_id=language_id,
                content=content,
                content_type=content_type
            )
            conn.execute(
                ins.on_conflict_do_update(
                    index_elements=[localized_event_so_far.c.event_so_far_id, localized_event_so_far.c.language_id],
                    set_={
                        "content": ins.excluded.content,
                        "content_type": ins.excluded.content_type
                    }
                )
            )

    if "faqs" in data:
        conn.execute(sa.delete(event_faq).where(event_faq.c.event_id == eid))
        for seq, faq_item in enumerate(data["faqs"] or []):
            language_id = (faq_item.get("language_id") or "").strip()
            question = (faq_item.get("question") or "").strip()
            answer = faq_item.get("answer") or ""
            if not language_id or not question:
                continue
            conn.execute(
                pg_insert(event_faq).values(
                    id=uuid.uuid4(),
                    event_id=eid,
                    language_id=language_id,
                    question=question,
                    answer=answer,
                    sequence=seq,
                )
            )



@app.route("/api/articles/<event_id>/preview", methods=["GET"])
@login_required
def api_article_preview(event_id):
    """Return title and image URL for a single article (used by the notification link picker)."""
    try:
        eid = uuid.UUID(event_id)
        with db2_engine.connect() as conn:
            row = conn.execute(
                sa.select(event.c.image, localized_event_data.c.title)
                .join(localized_event_data, localized_event_data.c.event_id == event.c.id)
                .where(event.c.id == eid)
                .where(localized_event_data.c.language_id == "en")
                .limit(1)
            ).mappings().first()
        if not row:
            return jsonify({"error": "Article not found"}), 404
        img = row["image"] or ""
        image_url = _presign_s3_url(img if img.startswith("s3://") else "s3://" + img) if img and not img.startswith("http") else img or None
        return jsonify({"title": row["title"], "image_url": image_url})
    except ValueError:
        return jsonify({"error": "Invalid article ID"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/collections/<collection_id>/preview", methods=["GET"])
@login_required
def api_collection_preview(collection_id):
    """Return title and image URL (from first linked article) for a collection."""
    try:
        cid = uuid.UUID(collection_id)
        with db2_engine.connect() as conn:
            # Fetch collection title
            col_row = conn.execute(
                sa.select(collection.c.title).where(collection.c.id == cid).limit(1)
            ).mappings().first()
            if not col_row:
                return jsonify({"error": "Collection not found"}), 404

            # Get image from the most recent article linked via seo_tags
            img_row = conn.execute(
                sa.select(event.c.image)
                .join(event_seo_tag, event_seo_tag.c.event_id == event.c.id)
                .join(collection_seo_tag, collection_seo_tag.c.seo_tag_id == event_seo_tag.c.seo_tag_id)
                .where(collection_seo_tag.c.collection_id == cid)
                .where(event.c.image.isnot(None))
                .order_by(event.c.time_stamp.desc())
                .limit(1)
            ).mappings().first()

        img = (img_row["image"] or "") if img_row else ""
        image_url = _presign_s3_url(img if img.startswith("s3://") else "s3://" + img) if img and not img.startswith("http") else img or None
        return jsonify({"title": col_row["title"], "image_url": image_url})
    except ValueError:
        return jsonify({"error": "Invalid collection ID"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Notification Groups (stored in app_config key 'notification_groups')
# ---------------------------------------------------------------------------

def _load_notification_groups(conn) -> list:
    row = conn.execute(
        sa.select(app_config.c.config_value).where(app_config.c.config_key == "notification_groups")
    ).scalar_one_or_none()
    return row if isinstance(row, list) else []


def _save_notification_groups(conn, groups: list):
    conn.execute(
        pg_insert(app_config).values(
            config_key="notification_groups",
            config_value=groups,
        ).on_conflict_do_update(
            index_elements=["config_key"],
            set_={"config_value": groups, "updated_at": sa.func.now()},
        )
    )


@app.route("/notification-groups", methods=["GET"])
@login_required
@admin_required
def notification_groups_page():
    return render_template("notification_groups.html")


@app.route("/api/notification-groups", methods=["GET"])
@login_required
def api_list_notification_groups():
    try:
        with db2_engine.connect() as conn:
            groups = _load_notification_groups(conn)
        return jsonify(groups)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/notification-groups", methods=["POST"])
@login_required
@admin_required
def api_create_notification_group():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    new_group = {
        "id": str(uuid.uuid4()),
        "name": name,
        "description": (data.get("description") or "").strip(),
        "type": "custom",
        "uids": [u.strip() for u in data.get("uids", []) if u.strip()],
    }
    try:
        with db2_engine.begin() as conn:
            groups = _load_notification_groups(conn)
            if any(g["name"] == name for g in groups):
                return jsonify({"error": "A group with that name already exists"}), 409
            groups.append(new_group)
            _save_notification_groups(conn, groups)
        return jsonify(new_group), 201
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/notification-groups/<group_id>", methods=["PUT"])
@login_required
@admin_required
def api_update_notification_group(group_id):
    data = request.get_json(silent=True) or {}
    try:
        with db2_engine.begin() as conn:
            groups = _load_notification_groups(conn)
            idx = next((i for i, g in enumerate(groups) if g["id"] == group_id), None)
            if idx is None:
                return jsonify({"error": "Group not found"}), 404
            g = groups[idx]
            if "name" in data:
                g["name"] = data["name"].strip()
            if "description" in data:
                g["description"] = data["description"].strip()
            if "uids" in data:
                g["uids"] = [u.strip() for u in data["uids"] if u.strip()]
            groups[idx] = g
            _save_notification_groups(conn, groups)
        return jsonify(g)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/notification-groups/<group_id>", methods=["DELETE"])
@login_required
@admin_required
def api_delete_notification_group(group_id):
    try:
        with db2_engine.begin() as conn:
            groups = _load_notification_groups(conn)
            new_groups = [g for g in groups if g["id"] != group_id]
            if len(new_groups) == len(groups):
                return jsonify({"error": "Group not found"}), 404
            _save_notification_groups(conn, new_groups)
        return jsonify({"success": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/articles/<event_id>", methods=["PUT"])
@login_required
def api_update_article(event_id):
    """Update article data. Reviewers cannot edit; editors get pending approval; admin apply immediately."""
    if getattr(current_user, "role", None) == "reviewer":
        return jsonify({"success": False, "error": "Reviewers do not have edit access"}), 403
    try:
        eid = uuid.UUID(event_id)
        data = request.get_json()
        is_editor = getattr(current_user, "role", None) == "editor"

        if is_editor:
            target_title = _get_article_title_from_db2(eid)
            try:
                current_article = _get_current_article_data_from_db2(eid)
                summary = _build_article_update_summary(data, current_article)
                payload_with_before = {**data, "_before": current_article}
            except Exception:
                summary = _build_article_update_summary(data)
                payload_with_before = data
            with SessionLocal() as session:
                session.execute(
                    sa.insert(pending_article_changes_table).values(
                        created_by_id=current_user.id,
                        created_by_username=current_user.username or "",
                        change_type="article_update",
                        target_event_id=eid,
                        target_title=target_title or None,
                        summary=summary,
                        payload=payload_with_before,
                        status="pending",
                    )
                )
                session.commit()
            return jsonify({"success": True, "pending_approval": True})

        with db2_engine.begin() as conn:
            _apply_article_update(conn, eid, data)
        flash("Article updated", "success")
        return jsonify({"success": True})

    except Exception as e:
        print(f"Update article error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def _resolve_seo_tag_id_by_name(conn, name: str):
    """Return seo_tag id for the first tag with this name (any type), or None."""
    if not name or not name.strip():
        return None
    row = conn.execute(
        sa.select(seo_tag.c.id).where(sa.func.lower(seo_tag.c.name) == name.strip().lower()).limit(1)
    ).first()
    return row[0] if row else None


def _get_current_article_tags_from_db2(event_id: uuid.UUID) -> list[dict]:
    """Return current article tags from db2 as list of {name, type, weight, relations: [{linked_to_tag, relation_type}]}."""
    with db2_engine.connect() as conn:
        eid = event_id
        linked_st = seo_tag.alias("linked_tag")
        tags_data = conn.execute(
            sa.select(
                seo_tag.c.id.label("tag_id"),
                seo_tag.c.name,
                sa.cast(seo_tag.c.type, sa.Text).label("type"),
                event_seo_tag.c.weight,
                event_seo_tag.c.role,
                linked_st.c.name.label("linked_to_tag_name"),
            )
            .select_from(event_seo_tag)
            .join(seo_tag, event_seo_tag.c.seo_tag_id == seo_tag.c.id)
            .outerjoin(linked_st, event_seo_tag.c.linked_to_tag_id == linked_st.c.id)
            .where(event_seo_tag.c.event_id == eid)
            .order_by(sa.cast(seo_tag.c.type, sa.Text), seo_tag.c.name)
        ).mappings().all()
        out = []
        for r in tags_data:
            raw_role = r.get("role")
            role = "core" if (raw_role and str(raw_role).lower() == "core") else "contextual"
            linked_name = (r.get("linked_to_tag_name") or "").strip()
            relations = [{"linked_to_tag": linked_name}] if linked_name else []
            out.append({
                "name": (r["name"] or "").strip(),
                "type": str(r.get("type") or "tag"),
                "weight": int(r["weight"]) if r.get("weight") is not None else 50,
                "role": role,
                "relations": relations,
            })
        return out


def _diff_tags(current_list: list[dict], payload_list: list[dict]) -> dict:
    """Compare current db2 tags with payload tags. Returns dict with added_tags, removed_tags, weight_changes, relation_added, relation_removed."""
    def norm(tag: dict) -> tuple:
        name = (tag.get("name") or "").strip().lower()
        tag_type = (tag.get("type") or "tag").strip().lower()
        weight = int(tag.get("weight", 50))
        rels = tag.get("relations") or []
        if not rels and tag.get("linked_to_tag"):
            rels = [{"linked_to_tag": (tag.get("linked_to_tag") or "").strip()}]
        rel_set = frozenset(
            (r.get("linked_to_tag") or "").strip().lower()
            for r in rels
            if (r.get("linked_to_tag") or "").strip()
        )
        return (name, tag_type, weight, rel_set)

    current_by_key = {}
    for t in current_list:
        n, tt, w, rs = norm(t)
        if n:
            current_by_key[(n, tt)] = (w, rs, t)

    payload_by_key = {}
    for t in payload_list:
        n, tt, w, rs = norm(t)
        if n:
            payload_by_key[(n, tt)] = (w, rs, t)

    added_tags = []
    removed_tags = []
    weight_changes = []
    relation_added = []
    relation_removed = []

    all_keys = set(current_by_key) | set(payload_by_key)
    for key in all_keys:
        name, tag_type = key
        display_name = name  # keep original case from payload if present
        cur = current_by_key.get(key)
        pay = payload_by_key.get(key)
        if pay and not cur:
            added_tags.append({
                "name": pay[2].get("name", name),
                "type": tag_type,
                "weight": pay[0],
                "relations": [{"linked_to_tag": r} for r in pay[1]],
            })
        elif cur and not pay:
            removed_tags.append({"name": cur[2].get("name", name), "type": tag_type})
        elif cur and pay:
            cw, crs = cur[0], cur[1]
            pw, prs = pay[0], pay[1]
            if cw != pw:
                weight_changes.append({"name": pay[2].get("name", name), "old_weight": cw, "new_weight": pw})
            for r in prs - crs:
                relation_added.append({"tag_name": pay[2].get("name", name), "linked_to_tag": r})
            for r in crs - prs:
                relation_removed.append({"tag_name": cur[2].get("name", name), "linked_to_tag": r})

    return {
        "added_tags": added_tags,
        "removed_tags": removed_tags,
        "weight_changes": weight_changes,
        "relation_added": relation_added,
        "relation_removed": relation_removed,
    }


def _format_tags_diff_summary(diff: dict) -> str:
    """Build short summary of tag diff for pending list."""
    parts = []
    if diff.get("added_tags"):
        n = len(diff["added_tags"])
        parts.append(f"{n} tag(s) added")
    if diff.get("removed_tags"):
        n = len(diff["removed_tags"])
        parts.append(f"{n} tag(s) removed")
    if diff.get("weight_changes"):
        n = len(diff["weight_changes"])
        parts.append(f"{n} weight change(s)")
    if diff.get("relation_added"):
        n = len(diff["relation_added"])
        parts.append(f"{n} relation(s) added")
    if diff.get("relation_removed"):
        n = len(diff["relation_removed"])
        parts.append(f"{n} relation(s) removed")
    return "; ".join(parts) if parts else "Tags update"


def _apply_article_tags_update(conn, event_id: uuid.UUID, payload: dict) -> None:
    """Apply article tags update to db2. Caller holds db2 connection."""
    eid = event_id
    tags = payload.get("tags", [])

    conn.execute(sa.delete(event_seo_tag).where(event_seo_tag.c.event_id == eid))

    # Key by (name, type) so same name with different type = different tags
    def _tag_key(name: str, t: str) -> tuple:
        return ((name or "").strip().lower(), (t or "tag").strip().lower())

    name_type_to_id = {}
    for tag_data in tags:
        tag_name = (tag_data.get("name") or "").strip()
        tag_type = tag_data.get("type", "tag")
        if not tag_name:
            continue
        tag_id = _ensure_seo_tag(conn, tag_name, tag_type)
        name_type_to_id[_tag_key(tag_name, tag_type)] = tag_id

    # Resolve "linked to" core tag names to id (built as we process; core tags come first)
    name_to_id_for_relation = {}

    for tag_data in tags:
        tag_name = (tag_data.get("name") or "").strip()
        tag_type = tag_data.get("type", "tag")
        tag_weight = int(tag_data.get("weight", 50))

        if not tag_name:
            continue

        tag_id = name_type_to_id.get(_tag_key(tag_name, tag_type))
        if not tag_id:
            continue

        relations = tag_data.get("relations") or []
        if not relations and tag_data.get("linked_to_tag"):
            relations = [{"linked_to_tag": (tag_data.get("linked_to_tag") or "").strip()}]

        raw_role = (tag_data.get("role") or "contextual").strip().lower()
        role = "core" if raw_role == "core" else "contextual"
        if role == "core":
            name_to_id_for_relation[tag_name.lower()] = tag_id

        linked_to_tag_id = None
        if relations:
            first_linked = (relations[0].get("linked_to_tag") or "").strip()
            if first_linked:
                linked_to_tag_id = name_to_id_for_relation.get(first_linked.lower())
                if linked_to_tag_id is None:
                    linked_to_tag_id = _resolve_seo_tag_id_by_name(conn, first_linked)

        conn.execute(
            pg_insert(event_seo_tag).values(
                id=uuid.uuid4(),
                event_id=eid,
                seo_tag_id=tag_id,
                weight=tag_weight,
                role=role,
                linked_to_tag_id=linked_to_tag_id,
            ).on_conflict_do_update(
                index_elements=[event_seo_tag.c.event_id, event_seo_tag.c.seo_tag_id],
                set_={
                    "weight": tag_weight,
                    "role": role,
                    "linked_to_tag_id": linked_to_tag_id,
                    "created_date": sa.func.now(),
                },
            )
        )



@app.route("/api/articles/<event_id>/tags", methods=["PUT"])
@login_required
def api_update_article_tags(event_id):
    """Update article tags. Reviewers cannot edit; editors get pending approval; admin apply immediately."""
    if getattr(current_user, "role", None) == "reviewer":
        return jsonify({"success": False, "error": "Reviewers do not have edit access"}), 403
    try:
        eid = uuid.UUID(event_id)
        data = request.get_json()
        tags = data.get("tags", []) if isinstance(data, dict) else []
        is_editor = getattr(current_user, "role", None) == "editor"

        if is_editor:
            target_title = _get_article_title_from_db2(eid)
            try:
                current_tags = _get_current_article_tags_from_db2(eid)
                diff = _diff_tags(current_tags, tags)
                summary = _format_tags_diff_summary(diff)
                payload_with_before = {**data, "_before": current_tags}
            except Exception:
                summary = f"{len(tags)} tag(s) changed" if tags else "Tags update"
                payload_with_before = data
            with SessionLocal() as session:
                session.execute(
                    sa.insert(pending_article_changes_table).values(
                        created_by_id=current_user.id,
                        created_by_username=current_user.username or "",
                        change_type="article_tags_update",
                        target_event_id=eid,
                        target_title=target_title or None,
                        summary=summary,
                        payload=payload_with_before,
                        status="pending",
                    )
                )
                session.commit()
            return jsonify({"success": True, "pending_approval": True})

        with db2_engine.begin() as conn:
            _apply_article_tags_update(conn, eid, data)
        return jsonify({"success": True})

    except Exception as e:
        print(f"Update article tags error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def _changes_only_from_payload(payload: dict, change_type: str) -> dict | None:
    """Compute changes_only from payload when it contains _before (stored at submit time). No schema change."""
    if not payload or "_before" not in payload:
        return None
    before = payload["_before"]
    if change_type == "article_update":
        payload_without_before = {k: v for k, v in payload.items() if k != "_before"}
        return _diff_article(before, payload_without_before)
    if change_type == "article_tags_update":
        return _diff_tags(before, payload.get("tags") or [])
    return None


def _get_pending_row(session, pk: int):
    """Return pending row as dict or None. Only returns rows with status='pending' for approve/reject."""
    row = session.execute(
        sa.select(pending_article_changes_table).where(
            sa.and_(
                pending_article_changes_table.c.id == pk,
                pending_article_changes_table.c.status == "pending",
            )
        )
    ).first()
    if not row:
        return None
    return row._mapping


@app.route("/pending-changes", methods=["GET"])
@login_required
@approver_required
def pending_changes_list():
    """List pending article/tag changes for approval (admin/reviewer only)."""
    with SessionLocal() as session:
        rows = session.execute(
            sa.select(pending_article_changes_table)
            .where(pending_article_changes_table.c.status == "pending")
            .order_by(pending_article_changes_table.c.created_at.desc())
        ).all()
        pending = [dict(r._mapping) for r in rows]
    return render_template("pending_changes.html", pending=pending)


def _serialize_pending_row(row) -> dict:
    """Convert pending row to JSON-serializable dict."""
    d = dict(row)
    for key in ("created_at", "reviewed_at"):
        if key in d and d[key] is not None:
            d[key] = d[key].isoformat()
    for key in ("target_event_id",):
        if key in d and d[key] is not None:
            d[key] = str(d[key])
    return d


@app.route("/pending-changes/<int:pk>", methods=["GET"])
@login_required
@approver_required
def pending_changes_detail(pk):
    """Return one pending change as JSON for the View modal (admin/reviewer only). Includes changes_only from stored _before when present."""
    with SessionLocal() as session:
        row = session.execute(
            sa.select(pending_article_changes_table).where(
                pending_article_changes_table.c.id == pk,
                pending_article_changes_table.c.status == "pending",
            )
        ).first()
        if not row:
            return jsonify({"error": "Not found or already processed"}), 404
        out = _serialize_pending_row(row._mapping)
    payload = out.get("payload") or {}
    changes = _changes_only_from_payload(payload, out.get("change_type") or "")
    if changes is not None:
        out["changes_only"] = changes
    else:
        event_id_val = out.get("target_event_id")
        if event_id_val:
            try:
                eid = uuid.UUID(event_id_val) if isinstance(event_id_val, str) else event_id_val
                if out.get("change_type") == "article_update":
                    current_article = _get_current_article_data_from_db2(eid)
                    out["changes_only"] = _diff_article(current_article, payload)
                elif out.get("change_type") == "article_tags_update":
                    current_tags = _get_current_article_tags_from_db2(eid)
                    out["changes_only"] = _diff_tags(current_tags, payload.get("tags") or [])
            except Exception:
                pass
    return jsonify(out)


@app.route("/pending-changes/<int:pk>/approve", methods=["POST"])
@login_required
@approver_required
def pending_changes_approve(pk):
    """Apply pending change to db2 and mark approved."""
    with SessionLocal() as session:
        row = _get_pending_row(session, pk)
        if not row:
            return jsonify({"success": False, "error": "Not found or already processed"}), 404
        change_type = row["change_type"]
        target_event_id = row["target_event_id"]
        payload = row["payload"] or {}

        try:
            with db2_engine.begin() as conn:
                if change_type == "article_update":
                    _apply_article_update(conn, target_event_id, payload)
                elif change_type == "article_tags_update":
                    _apply_article_tags_update(conn, target_event_id, payload)
                else:
                    return jsonify({"success": False, "error": f"Unknown change_type: {change_type}"}), 400
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

        session.execute(
            sa.update(pending_article_changes_table)
            .where(pending_article_changes_table.c.id == pk)
            .values(
                status="approved",
                reviewed_at=datetime.now(timezone.utc),
                reviewed_by_id=current_user.id,
            )
        )
        session.commit()
    return jsonify({"success": True})


@app.route("/pending-changes/<int:pk>/reject", methods=["POST"])
@login_required
@approver_required
def pending_changes_reject(pk):
    """Mark pending change as rejected."""
    with SessionLocal() as session:
        row = _get_pending_row(session, pk)
        if not row:
            return jsonify({"success": False, "error": "Not found or already processed"}), 404
        session.execute(
            sa.update(pending_article_changes_table)
            .where(pending_article_changes_table.c.id == pk)
            .values(
                status="rejected",
                reviewed_at=datetime.now(timezone.utc),
                reviewed_by_id=current_user.id,
            )
        )
        session.commit()
    return jsonify({"success": True})


def _get_history_records(role: str, user_id: int) -> list[dict]:
    """Fetch history of pending_article_changes for the given role. Enrich with reviewed_by_username."""
    with SessionLocal() as session:
        q = (
            sa.select(pending_article_changes_table)
            .order_by(pending_article_changes_table.c.created_at.desc())
        )
        if role == "admin":
            pass  # all records
        elif role == "editor":
            q = q.where(pending_article_changes_table.c.created_by_id == user_id)
        elif role == "reviewer":
            q = q.where(
                pending_article_changes_table.c.reviewed_by_id == user_id,
                pending_article_changes_table.c.status.in_(["approved", "rejected"]),
            )
        else:
            return []
        rows = session.execute(q).all()
        records = [dict(r._mapping) for r in rows]
        reviewer_ids = {r["reviewed_by_id"] for r in records if r.get("reviewed_by_id")}
        id_to_username = {}
        if reviewer_ids:
            users = session.execute(
                sa.select(ReviewUser.id, ReviewUser.username).where(ReviewUser.id.in_(reviewer_ids))
            ).all()
            for row in users:
                m = row._mapping
                id_to_username[m["id"]] = m["username"]
        for r in records:
            r["reviewed_by_username"] = id_to_username.get(r["reviewed_by_id"]) if r.get("reviewed_by_id") else None
            if r.get("target_event_id"):
                r["target_event_id"] = str(r["target_event_id"])
            if r.get("created_at"):
                r["created_at"] = r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"])
            if r.get("reviewed_at"):
                r["reviewed_at"] = r["reviewed_at"].isoformat() if hasattr(r["reviewed_at"], "isoformat") else str(r["reviewed_at"])
        return records


@app.route("/history", methods=["GET"])
@login_required
def history():
    """History of edits/approvals: admin sees all; editor sees own submissions; reviewer sees own approvals."""
    role = getattr(current_user, "role", None) or ""
    if role not in ("admin", "editor", "reviewer"):
        return redirect(url_for("get_articles"))
    records = _get_history_records(role, current_user.id)
    view_type = role  # admin | editor | reviewer
    return render_template("history.html", records=records, view_type=view_type)


def _can_view_history_record(role: str, user_id: int, row: dict) -> bool:
    """True if current user is allowed to view this history record."""
    if role == "admin":
        return True
    if role == "editor":
        return row.get("created_by_id") == user_id
    if role == "reviewer":
        return row.get("reviewed_by_id") == user_id
    return False


@app.route("/history/<int:pk>", methods=["GET"])
@login_required
def history_detail(pk):
    """Return one history record as JSON for the View modal. Permission: admin any; editor own; reviewer own approvals."""
    role = getattr(current_user, "role", None) or ""
    if role not in ("admin", "editor", "reviewer"):
        return jsonify({"error": "Forbidden"}), 403
    with SessionLocal() as session:
        row = session.execute(
            sa.select(pending_article_changes_table).where(pending_article_changes_table.c.id == pk)
        ).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        out = _serialize_pending_row(row._mapping)
    if not _can_view_history_record(role, current_user.id, out):
        return jsonify({"error": "Forbidden"}), 403
    payload = out.get("payload") or {}
    changes = _changes_only_from_payload(payload, out.get("change_type") or "")
    if changes is not None:
        out["changes_only"] = changes
    else:
        event_id_val = out.get("target_event_id")
        if event_id_val and out.get("status") == "pending":
            try:
                eid = uuid.UUID(event_id_val) if isinstance(event_id_val, str) else event_id_val
                if out.get("change_type") == "article_update":
                    current_article = _get_current_article_data_from_db2(eid)
                    out["changes_only"] = _diff_article(current_article, payload)
                elif out.get("change_type") == "article_tags_update":
                    current_tags = _get_current_article_tags_from_db2(eid)
                    out["changes_only"] = _diff_tags(current_tags, payload.get("tags") or [])
            except Exception:
                pass
    return jsonify(out)


@app.route("/api/articles/<event_id>", methods=["DELETE"])
@login_required
@admin_required
def api_delete_article(event_id):
    """Soft delete article (mark as deleted)"""
    try:
        eid = uuid.UUID(event_id)

        with db2_engine.begin() as conn:
            # Instead of hard delete, we could add a deleted flag
            # For now, we'll do a cascade delete
            conn.execute(sa.delete(event).where(event.c.id == eid))

        flash("Article deleted", "warning")
        return jsonify({"success": True})

    except Exception as e:
        print(f"Delete article error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500




@app.route("/notifications", methods=["GET"])
@login_required
@admin_required
def notifications_page():
    """Dedicated notifications hub — send breaking news + link to settings."""
    return render_template("notifications.html")


@app.route("/notifications/send-breaking", methods=["POST"])
@login_required
@admin_required
def send_breaking_news_direct():
    """Send a breaking news notification not tied to any specific article."""
    title = request.form.get("breaking_title", "").strip()
    body = request.form.get("breaking_body", "").strip()
    link = request.form.get("deep_link", "").strip() or None
    group_id = request.form.get("group_id", "").strip() or None

    if not title or not body:
        flash("Title and body are required.", "danger")
        return redirect(url_for("notifications_page"))

    # Resolve target_user_ids from group (if selected)
    target_user_ids = None
    if group_id:
        try:
            with db2_engine.connect() as conn:
                groups = _load_notification_groups(conn)
                group = next((g for g in groups if g["id"] == group_id), None)
                if group:
                    uids = group.get("uids", [])
                    if uids:
                        rows = conn.execute(
                            sa.select(users.c.id).where(users.c.uid.in_(uids))
                        ).all()
                        target_user_ids = [str(r.id) for r in rows]
        except Exception:
            target_user_ids = None

    core_url = os.environ.get("CORE_SERVICE_URL", "").rstrip("/")
    internal_secret = os.environ.get("INTERNAL_API_SECRET", "")
    if not core_url or not internal_secret:
        flash("CORE_SERVICE_URL or INTERNAL_API_SECRET is not configured.", "danger")
        return redirect(url_for("notifications_page"))

    # Resolve image from the deeplink (article or collection)
    image = None
    if link:
        import re as _re
        article_match = _re.search(r'[?&]articleId=([^&]+)', link)
        collection_match = _re.search(r'[?&]collectionId=([^&]+)', link)
        try:
            if article_match:
                eid = uuid.UUID(article_match.group(1))
                with db2_engine.connect() as conn:
                    img_val = conn.execute(
                        sa.select(event.c.image).where(event.c.id == eid)
                    ).scalar_one_or_none()
                if img_val:
                    image = _presign_s3_url(img_val if img_val.startswith("s3://") else "s3://" + img_val) if not img_val.startswith("http") else img_val
            elif collection_match:
                cid = uuid.UUID(collection_match.group(1))
                with db2_engine.connect() as conn:
                    img_val = conn.execute(
                        sa.select(event.c.image)
                        .join(event_seo_tag, event_seo_tag.c.event_id == event.c.id)
                        .join(collection_seo_tag, collection_seo_tag.c.seo_tag_id == event_seo_tag.c.seo_tag_id)
                        .where(collection_seo_tag.c.collection_id == cid)
                        .where(event.c.image.isnot(None))
                        .order_by(event.c.time_stamp.desc())
                        .limit(1)
                    ).scalar_one_or_none()
                if img_val:
                    image = _presign_s3_url(img_val if img_val.startswith("s3://") else "s3://" + img_val) if not img_val.startswith("http") else img_val
        except Exception:
            image = None

    payload = {"title": title, "body": body}
    if link:
        payload["link"] = link
    if image:
        payload["image"] = image
    if target_user_ids is not None:
        payload["target_user_ids"] = target_user_ids

    try:
        resp = _requests.post(
            f"{core_url}/api/internal/notifications/breaking-news",
            json=payload,
            headers={"x-internal-secret": internal_secret},
            timeout=15,
        )
        data = resp.json()
        if resp.ok and data.get("success"):
            flash(
                f"Notification sent to {data.get('sent_count', 0)} device(s) "
                f"({data.get('failed_count', 0)} failed).",
                "success",
            )
        else:
            flash(f"Failed to send: {data.get('error', resp.text)}", "danger")
    except Exception as exc:
        flash(f"Error contacting core service: {exc}", "danger")

    return redirect(url_for("notifications_page"))




def create_app():
    return app


def main() -> None:  # pragma: no cover - CLI helper
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":  # pragma: no cover
    main()
