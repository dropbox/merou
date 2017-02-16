from datetime import datetime, timedelta
from functools import wraps

from expvar.stats import stats
from plop.collector import FlamegraphFormatter, PlopFormatter
from pyflamegraph import generate
import stopwatch

from grouper.models.perf_profile import PerfProfile


ONE_WEEK = timedelta(days=7)


class InvalidUUID(Exception):
    pass


def prune_old_traces(session, delta=ONE_WEEK):
    """Deletes old plop traces from the DB. By default, those older than one week.

    Args:
        session: database session
        delta (timedelta): time in past beyond which to delete
    """
    cutoff = datetime.utcnow() - delta
    session.query(PerfProfile).filter(PerfProfile.created_on < cutoff).delete()
    session.commit()


def record_trace(session, collector, trace_uuid):
    """Format and record a plop trace.

    Args:
        session: database session
        collector: plop.collector.Collector holding trace information
    """
    flamegraph_input = FlamegraphFormatter().format(collector)
    plop_input = PlopFormatter().format(collector)
    perf_trace = PerfProfile(uuid=trace_uuid, flamegraph_input=flamegraph_input,
            plop_input=plop_input)
    perf_trace.add(session)
    session.commit()


def get_trace(session, trace_uuid):
    """Retrieves traces given a uuid.

    Args:
        sesssion: db session
        trace_uuid: uuid of trace in question

    Returns 2-tuple of plop, flamegraph input or None if trace doesn't exist
    (or was garbage collected.
    """
    trace = session.query(PerfProfile).filter(PerfProfile.uuid == trace_uuid).first()
    if not trace:
        raise InvalidUUID()

    return trace.plop_input, trace.flamegraph_input


def get_flamegraph_svg(session, trace_uuid):
    plop_input, flamegraph_input = get_trace(session, trace_uuid)

    return generate(flamegraph_input)


_sw_obj = None
def get_stopwatch():
    # type: () -> stopwatch.StopWatch
    assert _sw_obj, 'stopwatch not initialized'
    return _sw_obj


def init_stopwatch():
    global _sw_obj
    _sw_obj = stopwatch.StopWatch()


def stopwatch_emit_stats():
    # type: () -> None
    report = get_stopwatch().get_last_aggregated_report()
    for name, (time_sec, _, _) in report.aggregated_values.items():
        stats.incr(name, time_sec)


def sw_func(scope_name):
    def decorator(func):
        @wraps(func)
        def f(*args, **kwargs):
            with get_stopwatch().timer(scope_name):
                return func(*args, **kwargs)
        return f
    return decorator
