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


def compute(**updates):
    return dict(dict(uuid='GPU-test',kind='C',pid='123',name='python',memory=410.),**updates)


def test_light_compute_requires_sustained_low_resources_and_is_counted_available():
    tracker=Tracker()
    data={'gpus':[gpu(used=410.,free=24166.)],'processes':[compute()]}
    assert tracker.observe(data,0,5)['GPU-test']['status']=='observing'
    assert tracker.observe(data,5,5)['GPU-test']['status']=='observing'
    state=tracker.observe(data,10,5)['GPU-test']
    assert state['status']=='light' and state['available'] and not state['idle']
    data['gpus'][0]['util']=90
    assert tracker.observe(data,11,5)['GPU-test']['status']=='busy'
    data['gpus'][0]['util']=0
    assert tracker.observe(data,12,5)['GPU-test']['status']=='busy'


@pytest.mark.parametrize('changes,process',[
    ({'compute_mode':'Exclusive_Process'},compute()),
    ({'used':4096.,'free':20480.},compute()),
    ({'util':11.},compute()),
    ({},compute(name='nvidia-cuda-mps-server')),
    ({},compute(kind='M')),
    ({},compute(memory=None)),
    ({},compute(pid='')),
])
def test_active_context_is_not_light_when_sharing_cannot_be_confirmed(changes,process):
    state=candidate(gpu(**changes),[process],Rules())
    assert state['status']=='busy' and not state['available']


def test_light_memory_limits_apply_to_absolute_and_fractional_usage():
    rules=Rules(light_used_mib=1024,light_used_fraction=.05)
    assert candidate(gpu(used=1024.,free=23552.),[compute()],rules)['status']=='light'
    assert candidate(gpu(used=1025.,free=23551.),[compute()],rules)['status']=='busy'
    assert candidate(gpu(total=8192.,used=410.,free=7782.),[compute()],rules)['status']=='busy'


def test_busy_light_boundary_does_not_bounce_through_observing():
    tracker=Tracker()
    data={'gpus':[gpu(util=95,used=410.,free=24166.)],'processes':[compute()]}
    assert tracker.observe(data,0,2)['GPU-test']['status']=='busy'
    for now in range(2,24,2):
        data['gpus'][0]['util']=9 if now%4 else 11
        state=tracker.observe(data,now,2)['GPU-test']
        assert state['status']=='busy' and not state['available']
    data['gpus'][0]['util']=90
    assert tracker.observe(data,24,2)['GPU-test']['status']=='busy'
    data['gpus'][0]['util']=0
    for now in range(26,36,2):
        assert tracker.observe(data,now,2)['GPU-test']['status']=='busy'
    state=tracker.observe(data,36,2)['GPU-test']
    assert state['status']=='light' and state['available']
    data['gpus'][0]['util']=80
    assert tracker.observe(data,38,2)['GPU-test']['status']=='busy'


def test_eligible_category_changes_keep_confirmation_but_idle_needs_continuous_absence():
    tracker=Tracker();data={'gpus':[gpu()],'processes':[]}
    for now in range(0,12,2):
        data['processes']=[] if now%6==0 else [{'uuid':'GPU-test','kind':'G'}] if now%6==2 else [compute(memory=80)]
        state=tracker.observe(data,now,2)['GPU-test']
    assert state['status']=='light' and state['available']
    data['processes']=[]
    for now in range(12,22,2):
        state=tracker.observe(data,now,2)['GPU-test']
        assert state['status']=='available' and not state['idle']
    assert tracker.observe(data,22,2)['GPU-test']['idle']


def test_reset_starts_a_fresh_observation_instead_of_reusing_busy_history():
    tracker=Tracker();data={'gpus':[gpu(util=90)],'processes':[]}
    assert tracker.observe(data,0,2)['GPU-test']['status']=='busy'
    tracker.reset();data['gpus'][0]['util']=0
    assert tracker.observe(data,2,2)['GPU-test']['status']=='observing'


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
    assert t.observe(sample,14,5)['GPU-test']['status']=='busy'
    assert t.observe(sample,16,5)['GPU-test']['status']=='busy'
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
