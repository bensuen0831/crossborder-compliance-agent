"""Authorized iterator-consumption recovery; never fabricate legal support."""
from uuid import UUID

import pytest

from crossborder_compliance.domain.decision_contracts import LegalSupport
from crossborder_compliance.domain.decision_engine import merge_support


FIELDS=tuple(LegalSupport.model_fields)

def support(index, *, sparse=False):
    return LegalSupport(**{
        name: () if sparse and position%2 else
        (f'synthetic-reviewed-source/article/{index}',) if name=='citation_locators' else
        (UUID(int=index*len(FIELDS)+position+1),)
        for position,name in enumerate(FIELDS)
    })

@pytest.mark.parametrize('kind',['tuple','list','iterator','generator'])
@pytest.mark.parametrize('case',['empty','two','three','overlap','sparse'])
def test_every_authorized_field_has_exact_deterministic_union(kind,case):
    inputs={'empty':(), 'two':(support(1),support(2)),
        'three':(support(1),support(2),support(3)),
        'overlap':(support(1),support(2),support(1)),
        'sparse':(support(1,sparse=True),support(2,sparse=True))}[case]
    before=tuple(value.model_dump(mode='json') for value in inputs)
    iterable={'tuple':lambda:inputs,'list':lambda:list(inputs),
        'iterator':lambda:iter(inputs),'generator':lambda:(value for value in inputs)}[kind]()
    actual=merge_support(iterable)
    for field in FIELDS:
        expected=tuple(sorted({ref for value in inputs for ref in getattr(value,field)},key=str))
        assert getattr(actual,field)==expected,field
    assert tuple(value.model_dump(mode='json') for value in inputs)==before
    assert merge_support(reversed(inputs))==actual
    assert merge_support((actual,actual))==actual

@pytest.mark.parametrize('field',['legal_basis_ids','evidence_ids'])
def test_missing_authority_is_never_fabricated(field):
    values=[support(1).model_copy(update={field:()}),support(2).model_copy(update={field:()})]
    actual=merge_support(value for value in values)
    assert getattr(actual,field)==()
    assert actual.rule_hit_ids
