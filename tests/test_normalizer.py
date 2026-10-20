from app.printers import normalize_print, update_state

def test_print_normalization():
    assert normalize_print({'print': {'mc_percent': 44, 'subtask_name': 'part.3mf', 'x': 3}}) == {'mc_percent': 44, 'subtask_name': 'part.3mf'}
    assert normalize_print({}) == {}

def test_status_partial_updates():
    update_state('test', {'print': {'mc_percent': 22}})
    update_state('test', {'print': {'bed_temper': 55}})
