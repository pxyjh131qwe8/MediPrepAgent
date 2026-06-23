"""
SQLAlchemy database models for MediPrepAgent.
"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 2.定义orm模型
# (1)继承基类DeclarativeBase
# (2)定义数据库表对应的模型类
class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    create_time : Mapped[datetime] = mapped_column(DateTime, insert_default=func.now(), default=func.now(), comment="创建时间")
    update_time : Mapped[datetime] = mapped_column(DateTime, insert_default=func.now(), default=func.now(), onupdate=func.now(), comment="更新时间")


class HealthRecord(Base):
    """健康咨询记录表"""
    __tablename__ = "health_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symptoms: Mapped[str] = mapped_column(Text)
    duration: Mapped[str] = mapped_column(String(255), nullable=True)
    request_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    

class ReportRecord(Base):
    """检查报告记录表"""
    __tablename__ = "report_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    report_text: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)

# 存储病人信息
class HealthSessionContext(Base):
    __tablename__ = "health_session_contexts"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    thread_id: Mapped[str] = mapped_column(String(255), index=True, unique=True)
    
    age: Mapped[int | None] = mapped_column(nullable=True)
    gender: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    latest_symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    medical_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    medication_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergy_history: Mapped[str | None] = mapped_column(Text, nullable=True)

