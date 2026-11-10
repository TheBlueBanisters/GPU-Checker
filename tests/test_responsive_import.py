import json
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_multihost import window,snapshot


def test_card_and_process_labels_keep_native_index_gaps(window):
    window.show();window.connect_all()
    data=snapshot(1)
    data['gpus']=[dict(data['gpus'][0],uuid=f'GPU-{i}',index=i) for i in (0,3,7)]
    data['processes']=[dict(data['processes'][0],uuid=f'GPU-{i}',gpu=i,pid=str(100+i)) for i in (0,3,7)]
    window.selected.worker.data.emit(data)
    assert [card.title.text() for card in window.cards.values()]==['GPU 0','GPU 3','GPU 7']
    assert [window.table.item(i,0).text() for i in range(3)]==['0','3','7']
    assert window.tiles[window.selected_id].gpu_count.text()=='显卡 3 张'


def test_new_config_import_starts_once_but_does_not_resume_existing_paused_hosts(window,tmp_path,monkeypatch):
    monkeypatch.setattr(window,'notify',lambda *args:None)
    config=tmp_path/'config'
    config.write_text('Host lab-new\n HostName gpu.example.test\n User demo\n',encoding='utf-8')
    existing=window.selected
    existing.pause();window.persist_session_preferences()
    window.import_path(str(config))
    added=next(s for s in window.sessions.values() if s.profile['name']=='lab-new')
    worker=added.worker
    assert added.desired and worker.isRunning() and added.profile['autoconnect']
    assert not existing.desired and not existing.profile['autoconnect']
    added.pause();window.persist_session_preferences()
    window.import_path(str(config))
    assert len(window.sessions)==3 and not added.desired and worker.stops==1
    assert not existing.desired


def test_migration_first_import_enables_monitoring_even_if_export_was_paused(window,tmp_path,monkeypatch):
    monkeypatch.setattr(window,'notify',lambda *args:None)
    path=tmp_path/'migration.json'
    path.write_text(json.dumps({'profiles':[{'name':'new-export','host':'gpu.example.test','autoconnect':False}]}))
    window.import_path(str(path))
    assert window.selected.profile['name']=='new-export'
    assert window.selected.desired and window.selected.worker.isRunning()


def test_compact_layout_wraps_and_keeps_content_reachable(window):
    window.show();window.connect_all()
    data=snapshot(1)
    data['gpus']=[dict(data['gpus'][0],uuid=f'GPU-{i}',index=i) for i in range(5)]
    window.selected.worker.data.emit(data)
    for width,height in ((800,500),(960,540),(1280,720),(1920,1080)):
        window.resize(width,height);QApplication.processEvents();QTest.qWait(30)
        assert window.size().toTuple()==(width,height)
        assert window.dashboard.width()<=window.dashboard_scroll.viewport().width()
        assert window.side_scroll.widget().width()<=window.side_scroll.viewport().width()
        boxes=[card.geometry() for card in window.cards.values()]
        assert all(box.width()>=round(240*window.property('uiDensity')) for box in boxes)
        assert all(not a.intersects(b) for i,a in enumerate(boxes) for b in boxes[i+1:])
        window.card_scroll.verticalScrollBar().setValue(window.card_scroll.verticalScrollBar().maximum())
        QApplication.processEvents()
        assert window.card_widget.height()-max(box.bottom()+1 for box in boxes)>=18
        buttons=(window.connect_button,window.edit_button,window.remove_button)
        assert len({b.size().toTuple() for b in buttons})==1
        assert all(b.geometry().right()<b.parentWidget().width() for b in buttons)
    window.selected.pause();QApplication.processEvents()
    assert window.connect_button.resume_emphasis
    assert window.connect_button.monitor_action=='resume'
    effect=window.connect_button.action_glow
    assert effect.isEnabled() and effect.blurRadius()>=32
    assert effect.color().green()>effect.color().red()
    first=window.connect_button.grab().toImage()
    QTest.qWait(250)
    assert first==window.connect_button.grab().toImage()
    window.connect_button.click();QApplication.processEvents()
    assert window.connect_button.monitor_action=='pause'
    assert effect.color().red()>effect.color().green()
    first=window.connect_button.grab().toImage()
    QTest.qWait(250)
    assert first==window.connect_button.grab().toImage()
    window.hide();QApplication.processEvents()


def test_gpu_card_spacing_stays_compact_after_count_and_width_changes(window):
    window.show();window.connect_all()
    for count in (2,8,1,5,2):
        data=snapshot(1)
        data['gpus']=[dict(data['gpus'][0],uuid=f'GPU-{i}',index=i) for i in range(count)]
        window.selected.worker.data.emit(data)
        for width in (1920,800,1280,1920):
            window.resize(width,900);QApplication.processEvents();QTest.qWait(30)
            rows={}
            for card in window.cards.values():
                rows.setdefault(card.y(),[]).append(card.geometry())
            assert min(row[0].left() for row in rows.values())==10
            for row in rows.values():
                row.sort(key=lambda rect:rect.left())
                assert all(b.left()-a.right()-1==12 for a,b in zip(row,row[1:]))


def test_small_window_scales_components_and_fleet_count_remains_inside(window):
    window.show();window.connect_all();window.selected.worker.data.emit(snapshot(1))
    sizes=[]
    for width,height in ((1920,1080),(1280,720),(960,600),(1920,1080)):
        window.resize(width,height);QApplication.processEvents();QTest.qWait(50)
        card=next(iter(window.cards.values()))
        sizes.append((card.height(),window.title_bar.height(),window.side_scroll.width()))
        for _ in range(3):
            window.render_status();QApplication.processEvents()
            assert card.height()==round(270*window.property('uiDensity'))
        header=window.host_header;counter=window.host_count
        assert counter.geometry().right()<header.width()
        assert abs(counter.geometry().center().y()-header.rect().center().y())<=2
        assert counter.fontMetrics().horizontalAdvance(counter.text())<=counter.width()
        right=counter.mapTo(window.side_scroll.viewport(),counter.rect().topRight())
        assert right.x()<window.side_scroll.viewport().width()
    assert all(small<large for small,large in zip(sizes[1],sizes[0]))
    assert sizes[0]==sizes[-1]  # Repeated screen/window moves cannot compound scaling.
