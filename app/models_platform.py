"""v0.6 Platform MVP models -- industry social network, intelligence, resources, collaboration."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


# ── Tag system ──
class IndustryTag(Base):
    __tablename__ = "v06_tags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    tag_group: Mapped[str] = mapped_column(String(50), index=True)
    label: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class PersonTag(Base):
    __tablename__ = "v06_person_tags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(Integer, index=True)  # FK: people.id
    tag_id: Mapped[int] = mapped_column(Integer, index=True)  # FK: v06_tags.id
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class OrganizationTag(Base):
    __tablename__ = "v06_organization_tags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(Integer, index=True)  # FK: organizations.id
    tag_id: Mapped[int] = mapped_column(Integer, index=True)  # FK: v06_tags.id
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


# ── Person profile extensions ──
class PersonProfile(Base):
    __tablename__ = "v06_person_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)  # FK: people.id
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cooperation_preferences: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_wechat: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_visibility: Mapped[str] = mapped_column(String(20), default="private")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


# ── Favorites ──
class Favorite(Base):
    __tablename__ = "v06_favorites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)  # FK: v05a_users.id
    target_type: Mapped[str] = mapped_column(String(30), index=True)
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


# ── Follows ──
class Follow(Base):
    __tablename__ = "v06_follows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)  # FK: v05a_users.id
    target_type: Mapped[str] = mapped_column(String(30), index=True)
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


# ── Contact intents ──
class ContactIntent(Base):
    __tablename__ = "v06_contact_intents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_user_id: Mapped[int] = mapped_column(Integer, index=True)  # FK: v05a_users.id
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[int] = mapped_column(Integer)
    intent_type: Mapped[str] = mapped_column(String(50), default="connection")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    response_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    responded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


# ── Intelligence items ──
class IntelligenceItem(Base):
    __tablename__ = "v06_intelligence_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(400), index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    intel_type: Mapped[str] = mapped_column(String(50), index=True)
    companies: Mapped[str | None] = mapped_column(Text, nullable=True)
    people_involved: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry_directions: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    credibility: Mapped[int] = mapped_column(Integer, default=3)
    importance: Mapped[int] = mapped_column(Integer, default=2)
    visibility: Mapped[str] = mapped_column(String(20), default="public")
    status: Mapped[str] = mapped_column(String(20), default="published", index=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)  # FK: v05a_users.id
    organization_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # FK: organizations.id
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


# ── Intelligence subscriptions ──
class IntelSubscription(Base):
    __tablename__ = "v06_intel_subscriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)  # FK: v05a_users.id
    intel_types: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry_directions: Mapped[str | None] = mapped_column(Text, nullable=True)
    companies: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    regions: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_importance: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


# ── Resources ──
class MarketResource(Base):
    __tablename__ = "v06_market_resources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    direction: Mapped[str] = mapped_column(String(10), index=True)
    resource_type: Mapped[str] = mapped_column(String(50), index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    publisher_id: Mapped[int] = mapped_column(Integer, index=True)  # FK: v05a_users.id
    organization_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # FK: organizations.id
    region: Mapped[str | None] = mapped_column(String(200), nullable=True)
    industry_direction: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    cooperation_mode: Mapped[str | None] = mapped_column(String(200), nullable=True)
    budget_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    contact_visibility: Mapped[str] = mapped_column(String(20), default="connected")
    status: Mapped[str] = mapped_column(String(20), default="published", index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


# ── Cooperation opportunities ──
class CooperationOpportunity(Base):
    __tablename__ = "v06_opportunities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    opp_type: Mapped[str] = mapped_column(String(50), index=True)
    source_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    initiator_id: Mapped[int] = mapped_column(Integer, index=True)  # FK: v05a_users.id
    organization_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # FK: organizations.id
    target_person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_organization_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    related_resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str] = mapped_column(String(30), default="lead", index=True)
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # FK: v05a_users.id
    participants: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    visibility: Mapped[str] = mapped_column(String(20), default="organization")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


# ── Follow-ups ──
class FollowUp(Base):
    __tablename__ = "v06_follow_ups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(Integer, index=True)  # FK: v06_opportunities.id
    follow_type: Mapped[str] = mapped_column(String(30), default="note")
    content: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(Integer)  # FK: v05a_users.id
    followed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    next_follow_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="organization")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


# ── Collaboration tasks ──
class CollabTask(Base):
    __tablename__ = "v06_collab_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300))
    opportunity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, index=True)
    participants: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    priority: Mapped[str] = mapped_column(String(10), default="P2")
    status: Mapped[str] = mapped_column(String(20), default="todo", index=True)
    created_by: Mapped[int] = mapped_column(Integer)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


# ── Timeline entries ──
class TimelineEntry(Base):
    __tablename__ = "v06_timeline_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(Integer, index=True)  # FK: v06_opportunities.id
    event_type: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
