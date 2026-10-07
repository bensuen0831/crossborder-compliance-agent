import pytest
from crossborder_compliance.application.document_upload import DocumentFilePolicy
from crossborder_compliance.infrastructure.document_storage import FileObjectStorageAdapter

def test_content_policy_and_immutable_storage(tmp_path):
    p=DocumentFilePolicy(version='v1',max_size_bytes=100,scan_required=True,allowed_types=[dict(extension='.txt',media_type='text/plain',signature='text')])
    assert p.validate_content('../facts.txt','text/plain',b'Fact: value')==('facts.txt','text/plain')
    for content in (b'',b'\x00',b'x'*101):
        with pytest.raises(ValueError): p.validate_content('facts.txt','text/plain',content)
    with pytest.raises(ValueError): p.validate_content('facts.txt','application/pdf',b'Fact: value')
    s=FileObjectStorageAdapter(str(tmp_path/'store')); ref=s.put(object_key='tenant/project/hash/facts.txt',content=b'value',content_type='text/plain')
    assert s.get(ref)==b'value' and s.put(object_key='tenant/project/hash/facts.txt',content=b'value',content_type='text/plain')==ref
    with pytest.raises(ValueError): s.put(object_key='tenant/project/hash/facts.txt',content=b'other',content_type='text/plain')
    with pytest.raises(ValueError): s.get('object://other/tenant/project/hash/facts.txt')
    with pytest.raises(ValueError): s.put(object_key='../escape',content=b'x',content_type='text/plain')
