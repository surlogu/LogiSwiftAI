from engine import SCENARIOS, connect, mistake_log, recover, strategy_order


def test_scenarios():
    c = connect(':memory:')
    results = {s: recover('TEST', s, c) for s in SCENARIOS}
    assert results['Traffic delay']['status'] == 'RECOVERED'
    assert results['Traffic delay']['attempts'] == 2
    assert results['Vehicle breakdown']['status'] == 'RECOVERED'
    assert results['AI API outage']['status'] == 'RECOVERED'
    assert results['Capacity overload']['status'] == 'RECOVERED'
    assert results['Unrecoverable incident']['status'] == 'ESCALATED'
    assert all(r['attempts'] <= 3 for r in results.values())


def test_retry_limit():
    c = connect(':memory:')
    result = recover('TEST', 'Traffic delay', c, max_attempts=1)
    assert result['status'] == 'ESCALATED'
    assert result['attempts'] == 1


def test_feedback_recorded():
    c = connect(':memory:')
    recover('TEST', 'Traffic delay', c)
    assert strategy_order('TRAFFIC', c)[0][0] == 'alternate_route_B'
    assert c.execute('SELECT COUNT(*) FROM incidents').fetchone()[0] == 1

    # Verify second run self-heals on 1st attempt using learned memory
    second = recover('TEST2', 'Traffic delay', c)
    assert second['status'] == 'RECOVERED'
    assert second['attempts'] == 1
    assert len(mistake_log(c)) >= 1


def test_human_can_revoke_wrong_memory():
    from engine import audit_mistake_memory
    c = connect(':memory:')
    # 1. Agent runs Traffic delay: alternate_route_A fails and is penalized; alternate_route_B becomes #1
    recover('TEST', 'Traffic delay', c)
    assert strategy_order('TRAFFIC', c)[0][0] == 'alternate_route_B'

    # 2. Clear incident reward history to isolate mistake_memory effect, then revoke the mistake
    c.execute("DELETE FROM incidents")
    mistakes = mistake_log(c)
    assert len(mistakes) == 1
    audit_mistake_memory(mistakes[0]['id'], 'REVOKED_FALSE_POSITIVE', 'Sensor glitch on Route A', c)

    # 3. After human revokes the wrong memory, alternate_route_A is restored to its original #1 spot
    assert strategy_order('TRAFFIC', c)[0][0] == 'alternate_route_A'