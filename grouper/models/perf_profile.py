from datetime import datetime
from sqlalchemy import Column, String, DateTime, Index, LargeBinary
from grouper.models.base.model_base import Model


class PerfProfile(Model):
    __tablename__ = "perf_profiles"
    __table_args__ = (
            Index(
                "perf_trace_created_on_idx",
                "created_on",
            ),
    )

    uuid = Column(String(length=36), primary_key=True)
    plop_input = Column(LargeBinary(length=1000000), nullable=False)
    flamegraph_input = Column(LargeBinary(length=1000000), nullable=False)
    created_on = Column(DateTime, default=datetime.utcnow, nullable=False)
