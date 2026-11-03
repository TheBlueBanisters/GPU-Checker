import pytest
from availability import Rules,Tracker,candidate


def gpu(**updates):
    g=dict(uuid='GPU-test',util=0.,used=100.,free=23976.,total=24576.,temp=45.,slowdown_temp=90.,
           compute_mode='Default',device_access=True,process_query_ok=True,mig_mode='Disabled',
           recovery_action='None',ecc_uncorrectable=None,remap_failure='No')
    return dict(g,**updates)


def test_idle_requires_elapsed_time_and_multiple_samples():
    t=Tracker()
    sample={'gpus':[gpu()],'processes':[]}
    assert t.observe(sample,0,5)['GPU-test']['status']=='observing'
    assert not t.observe(sample,5,5)['GPU-test']['available']
    final=t.observe(sample,10,5)['GPU-test']
    assert final['idle'] and final['available']


@pytest.mark.parametrize('kind',['C','C+G','M','N/A',''])
def test_zero_utilization_with_compute_or_opaque_process_is_occupied(kind):
    state=candidate(gpu(),[{'kind':kind}],Rules())
    assert state['status']=='busy' and not state['available']


def test_small_graphics_context_is_available_but_not_idle():
    state=candidate(gpu(),[{'kind':'G'}],Rules())
    assert state['status']=='available' and state['available'] and not state['idle']


@pytest.mark.parametrize('changes,status',[
    ({'compute_mode':'Prohibited'},'blocked'),
    ({'compute_mode':'N/A'},'unknown'),
    ({'recovery_action':'Reset'},'blocked'),
    ({'ecc_uncorrectable':1},'blocked'),
    ({'remap_failure':'Yes'},'blocked'),
    ({'mig_mode':'Enabled'},'unknown'),
    ({'device_access':False},'blocked'),
    ({'device_access':None},'unknown'),
    ({'process_query_ok':False},'unknown'),
    ({'util':None},'unknown'),
    ({'util':float('nan')},'unknown'),
    ({'util':-1},'unknown'),
    ({'free':None},'unknown'),
    ({'free':25000},'unknown'),
    ({'temp':None},'unknown'),
    ({'temp':90},'blocked'),
    ({'util':11},'busy'),
    ({'used':2048.,'free':22000.},'unknown'),
    ({'free':4500.},'busy'),
])
def test_unproven_or_busy_device_never_becomes_available(changes,status):
    state=candidate(gpu(**changes),[],Rules())
    assert state['status']==status and not state['available']


def test_exact_free_threshold_and_reported_reserved_memory():
    rules=Rules(free_fraction=0)
    # Driver reports much less free than total-used because of reserved memory.
    assert candidate(gpu(total=8192.,free=4095.),[],rules)['status']=='busy'
    assert candidate(gpu(total=8192.,free=4096.),[],rules)['available']


def test_exclusive_mode_does_not_share_with_graphics():
    assert candidate(gpu(compute_mode='Exclusive_Process'),[{'kind':'G'}],Rules())['status']=='busy'


def test_bad_sample_interrupts_confirmation_and_long_gap_resets():
    t=Tracker()
    sample={'gpus':[gpu()],'processes':[]}
    for now in (0,5,10): t.observe(sample,now,5)
    assert t.observe(sample,11,5)['GPU-test']['idle']
    occupied={'gpus':[gpu()],'processes':[{'uuid':'GPU-test','kind':'C'}]}
    assert t.observe(occupied,12,5)['GPU-test']['status']=='busy'
    assert t.observe(sample,14,5)['GPU-test']['status']=='observing'
    assert t.observe(sample,16,5)['GPU-test']['status']=='observing'
    assert t.observe(sample,50,5)['GPU-test']['status']=='observing'


def test_gpu_removal_and_reappearance_does_not_reuse_old_confirmation():
    t=Tracker()
    sample={'gpus':[gpu()],'processes':[]}
    for now in (0,5,10): t.observe(sample,now,5)
    t.observe({'gpus':[],'processes':[]},11,5)
    assert t.observe(sample,12,5)['GPU-test']['status']=='observing'


def test_process_query_na_instance_fields_do_not_hide_real_processes():
    import remote_probe
    xml='''<nvidia_smi_log><gpu><uuid>GPU-test</uuid><compute_mode>Default</compute_mode>
    <processes><process_info><pid>123</pid><type>C</type><gpu_instance_id>N/A</gpu_instance_id>
    <compute_instance_id>N/A</compute_instance_id><process_name>/home/error/python</process_name>
    </process_info></processes></gpu></nvidia_smi_log>'''
    data=remote_probe.parse_xml(xml,lambda pid:{})
    assert data['gpus'][0]['process_query_ok'] is True
    assert data['processes'][0]['kind']=='C'
