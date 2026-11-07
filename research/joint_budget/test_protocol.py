import pytest

from research.joint_budget.protocol import Hardware, Domain, ResourceBudget, registered_domain, registered_budgets


def test_registered_budgets_preserve_one_global_chip_and_exact_byte_boundary():
    domain = registered_domain()
    assert len(domain.points) == 12
    assert {p.px * p.py for p in domain.points} == {6144}
    budgets = registered_budgets()
    assert [len(domain.under(b).points) for b in budgets] == [3, 9, 12]
    assert Hardware(32, 192, 135167) in domain.under(budgets[1]).points
    assert Hardware(32, 192, 135168) in domain.under(budgets[1]).points
    assert not ResourceBudget(6143, 262144).admits(domain.points[0])


def test_invalid_or_empty_budget_cannot_silently_grow_the_domain():
    with pytest.raises(ValueError):
        registered_domain().under(ResourceBudget(1, 1))
    with pytest.raises(ValueError):
        Domain((Hardware(1, 1, 1),) * 2)
    with pytest.raises(ValueError):
        Hardware(True, 2, 3)
